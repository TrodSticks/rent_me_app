import math
import os
from datetime import date
from urllib.parse import urlparse
from flask import render_template, url_for, flash, redirect, request, Blueprint, jsonify, current_app
from flask_login import current_user, login_required
from flask_wtf.csrf import CSRFError
from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload
from app import db
from locations import LOCATIONS, TOWN_COORDS
from models import (AMENITIES, REPORT_REASONS, STATUSES, Favorite, Message, Property,
                    PropertyAmenity, User)
from search_engine import MAX_PRICE, MAX_QUERY_LENGTH, PropertySearchEngine
from security import verification_notice
from llm_parser import LLMQueryParser

bp = Blueprint("main", __name__)

# Initialize the search engine (LLM search is paused; set USE_LLM_SEARCH=1 to enable it)
use_llm = os.environ.get('USE_LLM_SEARCH', '0') == '1'
search_engine = PropertySearchEngine(llm_parser=LLMQueryParser() if use_llm else None)

# Every sort ends on the id, so the order is the same on every request and pages never overlap
SORT_OPTIONS = {
    'newest': (Property.id.desc(),),
    'price_asc': (Property.price.asc(), Property.id.desc()),
    'price_desc': (Property.price.desc(), Property.id.desc()),
}

PER_PAGE = 12  # listings per page on the home page
MAX_PINS_PER_REQUEST = 300  # most pins the map loads for one view
SIMILAR_COUNT = 3


@bp.app_context_processor
def inject_shared_values():
    return {
        'locations': LOCATIONS,
        'town_coords': TOWN_COORDS,
        'AMENITIES': AMENITIES,
        'STATUSES': STATUSES,
        'REPORT_REASONS': REPORT_REASONS,
        'filter_url': filter_url,
        'today': date.today(),
        # The development mailbox only exists on a developer's machine
        'dev_mailbox': current_app.config['MAIL_BACKEND'] == 'file',
    }


@bp.app_errorhandler(413)
def upload_too_large(e):
    flash("Those photos are too large to upload together. Each photo can be up to 5 MB; "
          "try adding a few at a time.", "danger")
    return redirect(request.url)


@bp.app_errorhandler(403)
def forbidden(e):
    return render_template("error.html", title="Not allowed", heading="You can't open this page",
                           message="This page is only for Rent Me administrators."), 403


@bp.app_errorhandler(404)
def not_found(e):
    return render_template("error.html", title="Not found", heading="We couldn't find that page",
                           message="It may have been removed, or the link may be wrong."), 404


@bp.app_errorhandler(CSRFError)
def csrf_failed(e):
    if request.path.startswith('/favorite/'):
        return jsonify({"error": "Your session expired. Reload the page and try again."}), 400
    flash("That form expired or came from another site. Please try again.", "danger")
    return redirect(request.referrer if is_safe_redirect(request.referrer) else url_for("main.home"))


def is_safe_redirect(target):
    """Only allow redirects that stay on this site."""
    if not target:
        return False
    target = target.replace('\\', '/')
    url = urlparse(target)
    if url.scheme or url.netloc:
        # Absolute URLs are fine only when they point back at this host
        return url.scheme in ('http', 'https') and url.netloc == request.host
    return target.startswith('/') and not target.startswith('//')


# ---------- Browsing & search ----------

def _int_arg(name, low, high):
    """A whole-number filter from the URL, or None if it is missing, malformed or out of range."""
    value = request.args.get(name, type=int)
    return value if value is not None and low <= value <= high else None


def read_filters():
    """The search text and filters in the URL, validated.

    The plain-English search is parsed into the same kind of structured filters as the
    drop-downs, so everything can be applied by the database.
    """
    search_query = request.args.get('search', '').strip()[:MAX_QUERY_LENGTH]
    sort = request.args.get('sort', 'newest')
    filters = {
        'property_type': request.args.get('property_type', '') if request.args.get('property_type') in ('house', 'flat') else '',
        'location': request.args.get('location', '') if request.args.get('location') in LOCATIONS else '',
        'bedrooms': _int_arg('bedrooms', 1, 10),
        'bathrooms': _int_arg('bathrooms', 1, 10),
        'min_price': _int_arg('min_price', 1, MAX_PRICE),
        'max_price': _int_arg('max_price', 1, MAX_PRICE),
        'amenities': [key for key in AMENITIES if key in request.args.getlist('amenities')],
        'sort': sort if sort in SORT_OPTIONS else 'newest',
    }
    filters_active = bool(search_query) or any(
        filters[k] for k in ('property_type', 'location', 'bedrooms', 'bathrooms', 'min_price', 'max_price', 'amenities')
    )
    # Filters tucked away in the panel (type has its own chips, so it doesn't count)
    panel_filters = sum(1 for k in ('location', 'bedrooms', 'bathrooms', 'min_price', 'max_price') if filters[k]) \
        + len(filters['amenities']) + (filters['sort'] in ('price_asc', 'price_desc'))
    return {'search_query': search_query, 'filters': filters,
            'parsed': search_engine.parse_query(search_query) if search_query else None,
            'filters_active': filters_active, 'panel_filters': panel_filters}


def _like(word):
    """A pattern for "contains this word", with the wildcard characters taken literally."""
    escaped = word.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
    return f"%{escaped}%"


def search_conditions(search):
    """Everything the URL asks for, as database conditions on Property.

    Starts from what the public may see (published, not hidden, available) and adds the
    drop-down filters and the filters read from the plain-English search.
    """
    filters = search['filters']
    parsed = search['parsed'] or {}
    conditions = Property.public_conditions()

    if filters['property_type']:
        conditions.append(Property.property_type == filters['property_type'])
    if filters['location']:
        conditions.append(Property.location == filters['location'])
    if filters['bedrooms']:
        # The "5+" option means five or more bedrooms
        conditions.append(Property.bedrooms >= 5 if filters['bedrooms'] >= 5
                          else Property.bedrooms == filters['bedrooms'])
    if filters['bathrooms']:
        conditions.append(Property.bathrooms >= filters['bathrooms'])
    if filters['min_price']:
        conditions.append(Property.price >= filters['min_price'])
    if filters['max_price']:
        conditions.append(Property.price <= filters['max_price'])

    if parsed.get('property_type'):
        conditions.append(Property.property_type == parsed['property_type'])
    if parsed.get('location'):
        conditions.append(Property.location == parsed['location'])
    if parsed.get('bedrooms'):
        conditions.append(Property.bedrooms == parsed['bedrooms'])
    if parsed.get('bathrooms'):
        conditions.append(Property.bathrooms >= parsed['bathrooms'])
    if parsed.get('min_price'):
        conditions.append(Property.price >= parsed['min_price'])
    if parsed.get('max_price'):
        conditions.append(Property.price <= parsed['max_price'])

    # One EXISTS per amenity: a listing must have them all, and can never appear twice
    wanted = [key for key in AMENITIES if key in set(filters['amenities']) | set(parsed.get('amenities') or [])]
    for key in wanted:
        conditions.append(exists().where(PropertyAmenity.property_id == Property.id,
                                         PropertyAmenity.amenity == key))

    keywords = parsed.get('keywords') or []
    if keywords:
        conditions.append(or_(*[
            or_(Property.title.ilike(_like(word), escape='\\'),
                Property.description.ilike(_like(word), escape='\\'))
            for word in keywords
        ]))
    return conditions


def count_properties(conditions):
    return db.session.scalar(select(func.count(Property.id)).where(*conditions)) or 0


def filter_url(endpoint="main.home", **changes):
    """The current search on another view or with some filters changed; an empty value removes a filter."""
    args = request.args.to_dict(flat=False)
    for transient in ('page', 'focus'):
        args.pop(transient, None)
    for key, value in changes.items():
        if value in (None, '', []):
            args.pop(key, None)
        else:
            args[key] = value
    return url_for(endpoint, **args)


def favorite_ids_for(properties):
    """Which of these listings the signed-in renter has saved, found with a single query."""
    if not (current_user.is_authenticated and current_user.role == "Renter") or not properties:
        return set()
    ids = [p.id for p in properties]
    return set(db.session.scalars(
        select(Favorite.property_id).where(Favorite.user_id == current_user.id, Favorite.property_id.in_(ids))))


@bp.route("/")
@bp.route("/home")
def home():
    search = read_filters()
    conditions = search_conditions(search)

    # Count the matches, then fetch only the page being shown
    total = count_properties(conditions)
    pages = max(1, -(-total // PER_PAGE))
    page = min(max(request.args.get('page', 1, type=int) or 1, 1), pages)
    properties = Property.query.filter(*conditions) \
        .order_by(*SORT_OPTIONS[search['filters']['sort']]) \
        .limit(PER_PAGE).offset((page - 1) * PER_PAGE).all()

    return render_template("home.html", properties=properties, total=total, page=page, pages=pages,
                           favorite_ids=favorite_ids_for(properties),
                           page_url=lambda number: filter_url(page=number), **search)


# ---------- Map ----------

PIN_COLUMNS = (Property.id, Property.title, Property.price, Property.bedrooms, Property.property_type,
               Property.location, Property.map_lat, Property.map_lng, Property.latitude,
               Property.longitude, Property.image_file)


def make_pin(property):
    """What the map needs to draw one listing. Works on a Property or on a row of PIN_COLUMNS."""
    if property.map_lat is None or property.map_lng is None:
        return None
    return {
        'id': property.id,
        'title': property.title,
        'price': property.price,
        'bedrooms': property.bedrooms,
        'type': 'Flat' if property.property_type == 'flat' else 'House',
        'town': property.location,
        'lat': property.map_lat,
        'lng': property.map_lng,
        # Exact when the landlord placed the pin; otherwise a stable spot near the town centre
        'exact': property.latitude is not None and property.longitude is not None,
        'photo': url_for('static', filename='property_pics/' + property.image_file),
        'url': url_for('main.property_detail', property_id=property.id),
    }


def town_counts(conditions):
    """How many matching properties each town has, counted by the database."""
    counts = dict(db.session.execute(
        select(Property.location, func.count(Property.id))
        .where(*conditions, Property.map_lat.isnot(None))
        .group_by(Property.location)).all())
    return [{'name': name, 'lat': lat, 'lng': lng, 'count': counts[name]}
            for name, (lat, lng) in TOWN_COORDS.items() if counts.get(name)]


@bp.route("/map")
def map_view():
    search = read_filters()
    towns = town_counts(search_conditions(search))

    # Opening on one property: /map?focus=<id>, used by "View on map"
    focus = None
    focus_id = request.args.get('focus', type=int)
    focus_property = db.session.get(Property, focus_id) if focus_id else None
    if focus_property and focus_property.is_public:
        focus = make_pin(focus_property)

    return render_template("map.html", title="Map", towns=towns, focus=focus,
                           total=sum(town['count'] for town in towns),
                           town_centres=[{'name': name, 'lat': lat, 'lng': lng}
                                         for name, (lat, lng) in TOWN_COORDS.items()],
                           **search)


@bp.route("/api/map-pins")
def map_pins_api():
    """The matching properties inside the visible part of the map.

    bbox is south,west,north,east. The database picks out the area, counts the matches and
    returns at most MAX_PINS_PER_REQUEST of them; `total` lets the page ask the visitor to zoom in.
    """
    try:
        south, west, north, east = (float(part) for part in request.args.get('bbox', '').split(','))
    except ValueError:
        return jsonify({"error": "bbox must be south,west,north,east"}), 400
    if not all(math.isfinite(v) for v in (south, west, north, east)) or south > north or west > east:
        return jsonify({"error": "bbox must be south,west,north,east"}), 400

    conditions = search_conditions(read_filters()) + [
        Property.map_lat.between(south, north),
        Property.map_lng.between(west, east),
    ]
    total = count_properties(conditions)
    rows = db.session.execute(
        select(*PIN_COLUMNS).where(*conditions).order_by(Property.id.desc()).limit(MAX_PINS_PER_REQUEST)).all()
    return jsonify({
        'pins': [make_pin(row) for row in rows],
        'total': total,
        'truncated': total > len(rows),
    })

@bp.route("/api/search-suggestions")
def search_suggestions():
    query = request.args.get('q', '')
    suggestions = search_engine.get_search_suggestions(query)
    return jsonify(suggestions)


# ---------- Favorites ----------

@bp.route("/favorite/<int:property_id>", methods=["POST"])
@login_required
def toggle_favorite(property_id):
    if current_user.role != "Renter":
        return jsonify({"error": "Only renters can favorite properties"}), 403

    property = db.get_or_404(Property, property_id)
    if not property.is_public:
        return jsonify({"error": "This listing is no longer available"}), 404
    favorite = Favorite.query.filter_by(user_id=current_user.id, property_id=property_id).first()

    if favorite:
        db.session.delete(favorite)
        is_favorited = False
    else:
        db.session.add(Favorite(user_id=current_user.id, property_id=property_id))
        is_favorited = True

    try:
        db.session.commit()
    except IntegrityError:
        # Two taps at once: the favourite is already saved
        db.session.rollback()
        is_favorited = True
    return jsonify({"is_favorited": is_favorited})

@bp.route("/favorites")
@login_required
def favorites():
    if current_user.role != "Renter":
        flash("You do not have access to this page.", "danger")
        return redirect(url_for("main.home"))

    # Saved listings stay on this page when they are reserved or rented, but not once hidden
    properties = Property.query.join(Favorite, Favorite.property_id == Property.id) \
        .filter(Favorite.user_id == current_user.id, *Property.public_conditions(available_only=False)) \
        .order_by(Favorite.timestamp.desc(), Favorite.id.desc()).all()
    return render_template("favorites.html", title="Favorites", properties=properties)


# ---------- Messaging ----------

def thread_exists(user_a_id, user_b_id, property_id):
    """Have these two people already exchanged a message about this listing?"""
    return db.session.scalar(select(exists().where(
        Message.property_id == property_id if property_id else Message.property_id.is_(None),
        or_(and_(Message.sender_id == user_a_id, Message.recipient_id == user_b_id),
            and_(Message.sender_id == user_b_id, Message.recipient_id == user_a_id)),
    )))


def get_conversations(user):
    """Group a user's sent and received messages into threads, one per (other user, property)."""
    messages = Message.query.options(
        joinedload(Message.sender), joinedload(Message.recipient), joinedload(Message.property)
    ).filter(
        or_(Message.sender_id == user.id, Message.recipient_id == user.id)
    ).order_by(Message.timestamp.desc(), Message.id.desc()).all()

    threads = {}
    for message in messages:
        other_user = message.recipient if message.sender_id == user.id else message.sender
        key = (other_user.id, message.property_id)
        if key not in threads:
            # Messages are newest first, so the first one seen is the latest
            threads[key] = {'user': other_user, 'property': message.property,
                            'latest': message, 'unread': 0, 'count': 0}
        thread = threads[key]
        thread['count'] += 1
        if message.recipient_id == user.id and not message.read:
            thread['unread'] += 1
    return list(threads.values())


def _get_property_or_none(property_id):
    """The listing a conversation is about, if the signed-in user is allowed to see it."""
    property = db.session.get(Property, property_id) if property_id else None
    if property is not None and not property.visible_to(current_user):
        return None
    return property


@bp.route("/message/<int:recipient_id>", methods=["GET", "POST"])
@login_required
def send_message(recipient_id):
    recipient = db.get_or_404(User, recipient_id)
    if recipient == current_user:
        flash("You can't send a message to yourself.", "danger")
        return redirect(url_for("main.inbox"))
    property = _get_property_or_none(request.args.get('property_id', type=int))
    property_id = property.id if property else None

    # Starting a conversation needs a confirmed email; carrying one on does not
    if not thread_exists(current_user.id, recipient.id, property_id):
        if not current_user.email_verified:
            return verification_notice()
        if property and property.status == 'rented' and property.landlord_id != current_user.id:
            flash("This property has been rented, so it isn't taking new enquiries.", "warning")
            return redirect(url_for("main.property_detail", property_id=property.id))

    if request.method == "POST":
        content = request.form.get("content", "").strip()
        if not content:
            flash("Your message can't be empty.", "danger")
            return render_template("send_message.html", title="Send Message", recipient=recipient, property=property)
        db.session.add(Message(sender=current_user, recipient=recipient, content=content[:5000],
                               property_id=property_id))
        db.session.commit()
        flash("Your message has been sent!", "success")
        return redirect(url_for("main.conversation", user_id=recipient.id, property_id=property_id))

    return render_template("send_message.html", title="Send Message", recipient=recipient, property=property)

@bp.route("/inbox")
@login_required
def inbox():
    conversations = get_conversations(current_user)
    unread_count = current_user.messages_received.filter_by(read=False).count()

    # Landlords can narrow the inbox down to one of their listings
    my_properties = []
    selected_property = None
    if current_user.role == "Landlord":
        my_properties = Property.query.filter_by(landlord_id=current_user.id).order_by(Property.id.desc()).all()
        selected_id = request.args.get('property_id', type=int)
        selected_property = next((p for p in my_properties if p.id == selected_id), None)
        if selected_property:
            conversations = [c for c in conversations
                             if c['property'] and c['property'].id == selected_property.id]

    return render_template("inbox.html", title="Messages", conversations=conversations,
                           unread_count=unread_count, my_properties=my_properties,
                           selected_property=selected_property)

@bp.route("/conversation/<int:user_id>")
@login_required
def conversation(user_id):
    other_user = db.get_or_404(User, user_id)
    property = _get_property_or_none(request.args.get('property_id', type=int))
    property_id = property.id if property else None

    between_users = or_(
        (Message.sender_id == current_user.id) & (Message.recipient_id == user_id),
        (Message.sender_id == user_id) & (Message.recipient_id == current_user.id),
    )
    messages = Message.query.filter(between_users, Message.property_id == property_id) \
        .order_by(Message.timestamp.asc(), Message.id.asc()).all()

    # Mark messages in this thread as read
    Message.query.filter_by(sender_id=user_id, recipient_id=current_user.id,
                            property_id=property_id, read=False).update({'read': True})
    db.session.commit()

    return render_template("conversation.html", title=f"Chat with {other_user.username}", messages=messages,
                           other_user=other_user, property=property)

@bp.route("/send_reply/<int:recipient_id>", methods=["POST"])
@login_required
def send_reply(recipient_id):
    content = request.form.get("content", "").strip()
    recipient = db.get_or_404(User, recipient_id)
    property = _get_property_or_none(request.form.get("property_id", type=int))
    property_id = property.id if property else None

    # A reply continues a conversation. Anything else is a new one and goes through send_message.
    if recipient != current_user and not thread_exists(current_user.id, recipient.id, property_id):
        return redirect(url_for("main.send_message", recipient_id=recipient_id, property_id=property_id))

    if content and recipient != current_user:
        db.session.add(Message(sender=current_user, recipient=recipient, content=content[:5000],
                               property_id=property_id))
        db.session.commit()

    return redirect(url_for("main.conversation", user_id=recipient_id, property_id=property_id))


# The rest of the site's routes live in their own modules and attach to the same blueprint
import listings   # noqa: E402,F401  property pages, the landlord dashboard and reporting
import accounts   # noqa: E402,F401  sign-up, sign-in, email verification and password recovery
import admin      # noqa: E402,F401  moderation and landlord verification

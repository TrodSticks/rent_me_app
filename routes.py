import math
import os
import re
import secrets
from urllib.parse import urlparse
from flask import render_template, url_for, flash, redirect, request, Blueprint, jsonify, current_app
from flask_login import login_user, current_user, logout_user, login_required
from flask_wtf.csrf import CSRFError
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import and_, func, or_
from app import db
from models import User, Property, Message, Favorite
from search_engine import PropertySearchEngine, LOCATIONS, TOWN_COORDS
from llm_parser import LLMQueryParser

bp = Blueprint("main", __name__)

# Initialize the search engine (LLM search is paused; set USE_LLM_SEARCH=1 to enable it)
use_llm = os.environ.get('USE_LLM_SEARCH', '0') == '1'
search_engine = PropertySearchEngine(llm_parser=LLMQueryParser() if use_llm else None)

SORT_OPTIONS = {
    'newest': Property.id.desc(),
    'price_asc': Property.price.asc(),
    'price_desc': Property.price.desc(),
}

PER_PAGE = 12  # listings per page on the home page
PIN_SPREAD_DEGREES = 0.012  # about 1.3 km between approximate map pins in the same town
MAX_PIN_DISTANCE_KM = 40    # how far a landlord's pin may be from the town they chose
MAX_PINS_PER_REQUEST = 300  # most pins the map loads for one view
SIMILAR_COUNT = 3

MIN_PASSWORD_LENGTH = 6
MAX_USERNAME_LENGTH = 20
EMAIL_PATTERN = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
ROLES = ('Renter', 'Landlord')


@bp.app_context_processor
def inject_locations():
    return {'locations': LOCATIONS, 'town_coords': TOWN_COORDS}


@bp.app_errorhandler(413)
def upload_too_large(e):
    flash("That image is too large. The maximum size is 5 MB.", "danger")
    return redirect(request.url)


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


# ---------- Property photo helpers ----------

ALLOWED_IMAGE_FORMATS = ('JPEG', 'PNG', 'GIF', 'WEBP')
MAX_IMAGE_SIDE = 1200  # pixels; larger photos are shrunk to fit
JPEG_QUALITY = 82


def save_picture(file_storage):
    """Shrink an uploaded photo and save it as a JPEG under a random name.

    Returns the filename, or None if the upload isn't a readable image.
    """
    try:
        image = Image.open(file_storage.stream)
        if image.format not in ALLOWED_IMAGE_FORMATS:
            return None
        image = ImageOps.exif_transpose(image)  # respect phone camera rotation
        image.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
        if image.mode != 'RGB':
            # Flatten transparency onto white, since JPEG has none
            rgba = image.convert('RGBA')
            image = Image.new('RGB', rgba.size, (255, 255, 255))
            image.paste(rgba, mask=rgba.getchannel('A'))
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        return None

    filename = f"{secrets.token_hex(7)}.jpg"
    folder = current_app.config['UPLOAD_FOLDER']
    os.makedirs(folder, exist_ok=True)
    image.save(os.path.join(folder, filename), 'JPEG', quality=JPEG_QUALITY, optimize=True)
    return filename


def delete_picture(filename):
    if filename and filename != 'default.jpg':
        path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        if os.path.exists(path):
            os.remove(path)


def _apply_property_form(property):
    """Copy the submitted form onto a property. Returns an error message, or None if valid."""
    form = request.form
    title = form.get("title", "").strip()
    description = form.get("description", "").strip()
    price = form.get("price", type=int)
    bedrooms = form.get("bedrooms", type=int)
    location = form.get("location")
    property_type = form.get("property_type")

    if not title or not description:
        return "Please enter a title and description."
    if price is None or price <= 0:
        return "Please enter a valid monthly price."
    if bedrooms is None or not 1 <= bedrooms <= 10:
        return "Bedrooms must be between 1 and 10."
    if location not in LOCATIONS:
        return "Please choose a location from the list."
    if property_type not in ("house", "flat"):
        return "Please choose a property type."

    # Optional map pin: both numbers or neither, and it has to be in or near the chosen town
    raw_lat, raw_lng = form.get("latitude", "").strip(), form.get("longitude", "").strip()
    latitude = longitude = None
    if raw_lat or raw_lng:
        try:
            latitude, longitude = float(raw_lat), float(raw_lng)
        except ValueError:
            return "The map pin couldn't be read. Please place it again."
        if not (math.isfinite(latitude) and math.isfinite(longitude)):
            return "The map pin couldn't be read. Please place it again."
        if distance_km((latitude, longitude), TOWN_COORDS[location]) > MAX_PIN_DISTANCE_KM:
            return f"The map pin is too far from {location}. Move the pin, or choose the town it's in."

    image = request.files.get("image")
    if image and image.filename:
        filename = save_picture(image)
        if not filename:
            return "The photo must be a JPG, PNG, GIF or WebP image."
        delete_picture(property.image_file)
        property.image_file = filename

    property.title = title
    property.description = description
    property.price = price
    property.bedrooms = bedrooms
    property.location = location
    property.property_type = property_type
    property.latitude = round(latitude, 6) if latitude is not None else None
    property.longitude = round(longitude, 6) if longitude is not None else None
    return None


def distance_km(a, b):
    """Rough distance between two (latitude, longitude) points. Accurate enough within a town."""
    north = (a[0] - b[0]) * 111.0
    east = (a[1] - b[1]) * 111.0 * math.cos(math.radians((a[0] + b[0]) / 2))
    return math.hypot(north, east)


# ---------- Browsing & search ----------

def read_filters():
    """The search text and filters in the URL."""
    search_query = request.args.get('search', '').strip()
    filters = {
        'property_type': request.args.get('property_type', ''),
        'location': request.args.get('location', ''),
        'bedrooms': request.args.get('bedrooms', type=int),
        'min_price': request.args.get('min_price', type=int),
        'max_price': request.args.get('max_price', type=int),
        'sort': request.args.get('sort', 'newest'),
    }
    filters_active = bool(search_query) or any(
        filters[k] for k in ('property_type', 'location', 'bedrooms', 'min_price', 'max_price')
    )
    # Filters tucked away in the panel (type has its own chips, so it doesn't count)
    panel_filters = sum(1 for k in ('location', 'bedrooms', 'min_price', 'max_price') if filters[k]) \
        + (filters['sort'] in ('price_asc', 'price_desc'))
    return {'search_query': search_query, 'filters': filters,
            'filters_active': filters_active, 'panel_filters': panel_filters}


def filtered_query(filters):
    """A database query with the drop-down filters applied (not the text search or sorting)."""
    query = Property.query
    if filters['property_type'] in ('house', 'flat'):
        query = query.filter(Property.property_type == filters['property_type'])
    if filters['location'] in LOCATIONS:
        query = query.filter(Property.location == filters['location'])
    if filters['bedrooms']:
        # The "5+" option means five or more bedrooms
        if filters['bedrooms'] >= 5:
            query = query.filter(Property.bedrooms >= 5)
        else:
            query = query.filter(Property.bedrooms == filters['bedrooms'])
    if filters['min_price']:
        query = query.filter(Property.price >= filters['min_price'])
    if filters['max_price']:
        query = query.filter(Property.price <= filters['max_price'])
    return query


def text_search(properties, search_query):
    """Narrow a list of properties with the plain-English search."""
    if not search_query:
        return properties
    return search_engine.filter_properties(properties, search_engine.parse_query(search_query))


def search_from_request():
    """Run the search and filters in the URL and return every match, sorted."""
    search = read_filters()
    filters = search['filters']
    properties = filtered_query(filters) \
        .order_by(SORT_OPTIONS.get(filters['sort'], SORT_OPTIONS['newest'])).all()
    search['properties'] = text_search(properties, search['search_query'])
    return search


def filter_url(endpoint="main.home", **changes):
    """The current search on another view or with some filters changed; an empty value removes a filter."""
    args = request.args.to_dict()
    for transient in ('page', 'focus'):
        args.pop(transient, None)
    for key, value in changes.items():
        if value in (None, ''):
            args.pop(key, None)
        else:
            args[key] = value
    return url_for(endpoint, **args)


@bp.app_context_processor
def inject_filter_url():
    return {'filter_url': filter_url}


@bp.route("/")
@bp.route("/home")
def home():
    search = search_from_request()

    # Text search filters in Python, so page the final list rather than the SQL query
    properties = search.pop('properties')
    total = len(properties)
    pages = max(1, -(-total // PER_PAGE))
    page = min(max(request.args.get('page', 1, type=int), 1), pages)
    properties = properties[(page - 1) * PER_PAGE:page * PER_PAGE]

    return render_template("home.html", properties=properties, total=total, page=page, pages=pages,
                           page_url=lambda number: filter_url(page=number), **search)


# ---------- Map ----------

def pin_position(property):
    """Where a property goes on the map: (latitude, longitude, exact).

    A landlord's pin is used as it is. Without one, the property is placed near its town
    centre at a spot worked out from its id, so it stays put between visits and filters.
    """
    if property.latitude is not None and property.longitude is not None:
        return property.latitude, property.longitude, True
    centre = TOWN_COORDS.get(property.location)
    if not centre:
        return None
    angle = math.radians(property.id * 137.5)            # golden angle keeps neighbours apart
    radius = PIN_SPREAD_DEGREES * math.sqrt(property.id % 12 + 1)
    return (round(centre[0] + radius * math.sin(angle), 5),
            round(centre[1] + radius * math.cos(angle), 5), False)


def make_pin(property):
    position = pin_position(property)
    if not position:
        return None
    return {
        'id': property.id,
        'title': property.title,
        'price': property.price,
        'bedrooms': property.bedrooms,
        'type': 'Flat' if property.property_type == 'flat' else 'House',
        'town': property.location,
        'lat': position[0],
        'lng': position[1],
        'exact': position[2],
        'photo': url_for('static', filename='property_pics/' + property.image_file),
        'url': url_for('main.property_detail', property_id=property.id),
    }


def town_counts(search):
    """How many matching properties each town has, for the bubbles and the town chooser."""
    query = filtered_query(search['filters'])
    if search['search_query']:
        # The plain-English search runs in Python, so count after it
        counts = {}
        for property in text_search(query.all(), search['search_query']):
            counts[property.location] = counts.get(property.location, 0) + 1
    else:
        counts = dict(query.with_entities(Property.location, func.count(Property.id))
                      .group_by(Property.location).all())
    return [{'name': name, 'lat': lat, 'lng': lng, 'count': counts.get(name, 0)}
            for name, (lat, lng) in TOWN_COORDS.items() if counts.get(name)]


@bp.route("/map")
def map_view():
    search = read_filters()
    towns = town_counts(search)

    # Opening on one property: /map?focus=<id>, used by "View on map"
    focus = None
    focus_property = db.session.get(Property, request.args.get('focus', type=int) or 0)
    if focus_property:
        focus = make_pin(focus_property)

    return render_template("map.html", title="Map", towns=towns, focus=focus,
                           total=sum(town['count'] for town in towns),
                           town_centres=[{'name': name, 'lat': lat, 'lng': lng}
                                         for name, (lat, lng) in TOWN_COORDS.items()],
                           **search)


@bp.route("/api/map-pins")
def map_pins_api():
    """The matching properties inside the visible part of the map.

    bbox is south,west,north,east. At most MAX_PINS_PER_REQUEST pins come back; `total`
    says how many there are, so the page can ask the visitor to zoom in.
    """
    try:
        south, west, north, east = (float(part) for part in request.args.get('bbox', '').split(','))
    except ValueError:
        return jsonify({"error": "bbox must be south,west,north,east"}), 400
    if not all(math.isfinite(v) for v in (south, west, north, east)) or south > north or west > east:
        return jsonify({"error": "bbox must be south,west,north,east"}), 400

    search = read_filters()
    # Approximate pins sit within a few km of their town centre, so only towns near the view can matter
    margin = PIN_SPREAD_DEGREES * 4
    nearby_towns = [name for name, (lat, lng) in TOWN_COORDS.items()
                    if south - margin <= lat <= north + margin and west - margin <= lng <= east + margin]
    in_view = or_(
        and_(Property.latitude.between(south, north), Property.longitude.between(west, east)),
        and_(Property.latitude.is_(None), Property.location.in_(nearby_towns)),
    )
    properties = filtered_query(search['filters']).filter(in_view).order_by(Property.id.desc()).all()
    properties = text_search(properties, search['search_query'])

    pins = [pin for pin in (make_pin(p) for p in properties)
            if pin and south <= pin['lat'] <= north and west <= pin['lng'] <= east]
    return jsonify({
        'pins': pins[:MAX_PINS_PER_REQUEST],
        'total': len(pins),
        'truncated': len(pins) > MAX_PINS_PER_REQUEST,
    })

@bp.route("/api/search-suggestions")
def search_suggestions():
    query = request.args.get('q', '')
    suggestions = search_engine.get_search_suggestions(query)
    return jsonify(suggestions)


# ---------- Authentication ----------

@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role")

        error = None
        if not username or len(username) > MAX_USERNAME_LENGTH:
            error = f"Please choose a username of 1 to {MAX_USERNAME_LENGTH} characters."
        elif not EMAIL_PATTERN.match(email) or len(email) > 120:
            error = "Please enter a valid email address."
        elif len(password) < MIN_PASSWORD_LENGTH:
            error = f"Your password must be at least {MIN_PASSWORD_LENGTH} characters."
        elif role not in ROLES:
            error = "Please choose whether you are a renter or a landlord."
        elif User.query.filter(func.lower(User.email) == email).first():
            error = "Email already registered. Please choose a different one."
        elif User.query.filter_by(username=username).first():
            error = "Username already taken. Please choose a different one."
        if error:
            flash(error, "danger")
            return render_template("register.html", title="Register", form=request.form)

        user = User(username=username, email=email, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash("Your account has been created! You are now able to log in", "success")
        return redirect(url_for("main.login"))
    return render_template("register.html", title="Register", form={})

@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter(func.lower(User.email) == email).first()
        if user and user.check_password(password):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page if is_safe_redirect(next_page) else url_for("main.home"))
        else:
            flash("Login Unsuccessful. Please check email and password", "danger")
    return render_template("login.html", title="Login")

@bp.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("main.home"))


# ---------- Account ----------

@bp.route("/account", methods=["GET", "POST"])
@login_required
def account():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        if not username or not email:
            flash("Username and email can't be empty.", "danger")
        elif len(username) > MAX_USERNAME_LENGTH:
            flash("Username must be 20 characters or fewer.", "danger")
        elif not EMAIL_PATTERN.match(email) or len(email) > 120:
            flash("Please enter a valid email address.", "danger")
        elif User.query.filter(User.username == username, User.id != current_user.id).first():
            flash("That username is already taken.", "danger")
        elif User.query.filter(func.lower(User.email) == email, User.id != current_user.id).first():
            flash("That email is already registered to another account.", "danger")
        else:
            current_user.username = username
            current_user.email = email
            db.session.commit()
            flash("Your profile has been updated.", "success")
        return redirect(url_for("main.account"))

    conversations = get_conversations(current_user)
    if current_user.role == "Landlord":
        stats = {'properties': Property.query.filter_by(landlord_id=current_user.id).count()}
    else:
        stats = {'favorites': current_user.favorites.count()}
    stats['conversations'] = len(conversations)
    return render_template("account.html", title="My Account", stats=stats,
                           conversations=conversations[:5])

@bp.route("/account/password", methods=["POST"])
@login_required
def change_password():
    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")
    if not current_user.check_password(current_password):
        flash("Your current password is incorrect.", "danger")
    elif len(new_password) < MIN_PASSWORD_LENGTH:
        flash(f"Your new password must be at least {MIN_PASSWORD_LENGTH} characters.", "danger")
    elif new_password != confirm_password:
        flash("The new passwords don't match.", "danger")
    else:
        current_user.set_password(new_password)
        db.session.commit()
        flash("Your password has been changed.", "success")
    return redirect(url_for("main.account"))


# ---------- Landlord property management ----------

@bp.route("/dashboard")
@login_required
def dashboard():
    if current_user.role == "Landlord":
        properties = Property.query.filter_by(landlord_id=current_user.id).all()
        message_counts = {
            p.id: Message.query.filter_by(property_id=p.id, recipient_id=current_user.id).count()
            for p in properties
        }
        return render_template("landlord_dashboard.html", title="Dashboard", properties=properties,
                               message_counts=message_counts)
    else:
        flash("You do not have access to this page.", "danger")
        return redirect(url_for("main.home"))

@bp.route("/property/new", methods=["GET", "POST"])
@login_required
def new_property():
    if current_user.role != "Landlord":
        flash("You do not have permission to add properties.", "danger")
        return redirect(url_for("main.home"))
    if request.method == "POST":
        property = Property()
        error = _apply_property_form(property)
        if error:
            flash(error, "danger")
            return render_template("create_property.html", title="New Property", values=request.form)
        property.landlord = current_user
        db.session.add(property)
        db.session.commit()
        flash("Your property has been listed!", "success")
        return redirect(url_for("main.dashboard"))
    return render_template("create_property.html", title="New Property", values={})

@bp.route("/property/<int:property_id>")
def property_detail(property_id):
    property = db.get_or_404(Property, property_id)
    is_favorited = False
    if current_user.is_authenticated:
        is_favorited = Favorite.query.filter_by(user_id=current_user.id, property_id=property_id).first() is not None
    return render_template("property_detail.html", title=property.title, property=property,
                           is_favorited=is_favorited, similar=similar_properties(property))


def similar_properties(property):
    """The listings most like this one: same town counts most, then type, bedrooms and price."""
    def score(other):
        points = 0
        if other.location == property.location:
            points += 3
        if other.property_type == property.property_type:
            points += 2
        if other.bedrooms == property.bedrooms:
            points += 1
        if abs(other.price - property.price) <= property.price * 0.25:
            points += 1
        return points

    candidates = Property.query.filter(Property.id != property.id).all()
    scored = [(score(other), other) for other in candidates]
    scored = [item for item in scored if item[0] > 0]
    # Best score first; among equals, the closest price
    scored.sort(key=lambda item: (-item[0], abs(item[1].price - property.price)))
    return [other for _, other in scored[:SIMILAR_COUNT]]

@bp.route("/property/<int:property_id>/update", methods=["GET", "POST"])
@login_required
def update_property(property_id):
    property = db.get_or_404(Property, property_id)
    if property.landlord != current_user:
        flash("You do not have permission to edit this property.", "danger")
        return redirect(url_for("main.home"))
    if request.method == "POST":
        error = _apply_property_form(property)
        if error:
            db.session.rollback()
            flash(error, "danger")
            return render_template("create_property.html", title="Update Property",
                                   property=property, values=request.form)
        db.session.commit()
        flash("Your property has been updated!", "success")
        return redirect(url_for("main.dashboard"))
    return render_template("create_property.html", title="Update Property", property=property, values=property)

@bp.route("/property/<int:property_id>/delete", methods=["POST"])
@login_required
def delete_property(property_id):
    property = db.get_or_404(Property, property_id)
    if property.landlord != current_user:
        flash("You do not have permission to delete this property.", "danger")
        return redirect(url_for("main.home"))
    Favorite.query.filter_by(property_id=property.id).delete()
    # Keep the conversation history, just detach it from the deleted listing
    Message.query.filter_by(property_id=property.id).update({'property_id': None})
    delete_picture(property.image_file)
    db.session.delete(property)
    db.session.commit()
    flash("Your property has been deleted!", "success")
    return redirect(url_for("main.dashboard"))


# ---------- Favorites ----------

@bp.route("/favorite/<int:property_id>", methods=["POST"])
@login_required
def toggle_favorite(property_id):
    if current_user.role != "Renter":
        return jsonify({"error": "Only renters can favorite properties"}), 403

    property = db.get_or_404(Property, property_id)
    favorite = Favorite.query.filter_by(user_id=current_user.id, property_id=property_id).first()

    if favorite:
        db.session.delete(favorite)
        is_favorited = False
    else:
        favorite = Favorite(user_id=current_user.id, property_id=property_id)
        db.session.add(favorite)
        is_favorited = True

    db.session.commit()
    return jsonify({"is_favorited": is_favorited})

@bp.route("/favorites")
@login_required
def favorites():
    if current_user.role != "Renter":
        flash("You do not have access to this page.", "danger")
        return redirect(url_for("main.home"))

    favorites = Favorite.query.filter_by(user_id=current_user.id).all()
    properties = [fav.property for fav in favorites]
    return render_template("favorites.html", title="Favorites", properties=properties)


# ---------- Messaging ----------

def get_conversations(user):
    """Group a user's sent and received messages into threads, one per (other user, property)."""
    messages = Message.query.filter(
        or_(Message.sender_id == user.id, Message.recipient_id == user.id)
    ).order_by(Message.timestamp.desc()).all()

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
    return db.session.get(Property, property_id) if property_id else None


@bp.route("/message/<int:recipient_id>", methods=["GET", "POST"])
@login_required
def send_message(recipient_id):
    recipient = db.get_or_404(User, recipient_id)
    if recipient == current_user:
        flash("You can't send a message to yourself.", "danger")
        return redirect(url_for("main.inbox"))
    property = _get_property_or_none(request.args.get('property_id', type=int))

    if request.method == "POST":
        content = request.form.get("content", "").strip()
        if not content:
            flash("Your message can't be empty.", "danger")
            return render_template("send_message.html", title="Send Message", recipient=recipient, property=property)
        message = Message(
            sender=current_user,
            recipient=recipient,
            content=content,
            property_id=property.id if property else None
        )
        db.session.add(message)
        db.session.commit()
        flash("Your message has been sent!", "success")
        return redirect(url_for("main.conversation", user_id=recipient.id,
                                property_id=property.id if property else None))

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
        my_properties = Property.query.filter_by(landlord_id=current_user.id).all()
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
        .order_by(Message.timestamp.asc()).all()

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

    if content and recipient != current_user:
        message = Message(sender=current_user, recipient=recipient, content=content, property_id=property_id)
        db.session.add(message)
        db.session.commit()

    return redirect(url_for("main.conversation", user_id=recipient_id, property_id=property_id))

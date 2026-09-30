import os
import secrets
from flask import render_template, url_for, flash, redirect, request, Blueprint, jsonify, current_app
from flask_login import login_user, current_user, logout_user, login_required
from sqlalchemy import or_
from app import db
from models import User, Property, Message, Favorite
from search_engine import PropertySearchEngine, LOCATIONS
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

MIN_PASSWORD_LENGTH = 6


@bp.app_context_processor
def inject_locations():
    return {'locations': LOCATIONS}


@bp.app_errorhandler(413)
def upload_too_large(e):
    flash("That image is too large. The maximum size is 5 MB.", "danger")
    return redirect(request.url)


# ---------- Property photo helpers ----------

def _image_extension(header: bytes):
    """Identify an image from its first bytes, so renamed non-images are rejected."""
    if header.startswith(b'\xff\xd8\xff'):
        return 'jpg'
    if header.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'png'
    if header[:6] in (b'GIF87a', b'GIF89a'):
        return 'gif'
    if header[:4] == b'RIFF' and header[8:12] == b'WEBP':
        return 'webp'
    return None


def save_picture(file_storage):
    """Save an uploaded image under a random name. Returns the filename, or None if not an image."""
    header = file_storage.stream.read(12)
    file_storage.stream.seek(0)
    ext = _image_extension(header)
    if not ext:
        return None
    filename = f"{secrets.token_hex(7)}.{ext}"
    folder = current_app.config['UPLOAD_FOLDER']
    os.makedirs(folder, exist_ok=True)
    file_storage.save(os.path.join(folder, filename))
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
    return None


# ---------- Browsing & search ----------

@bp.route("/")
@bp.route("/home")
def home():
    search_query = request.args.get('search', '').strip()
    filters = {
        'property_type': request.args.get('property_type', ''),
        'location': request.args.get('location', ''),
        'bedrooms': request.args.get('bedrooms', type=int),
        'min_price': request.args.get('min_price', type=int),
        'max_price': request.args.get('max_price', type=int),
        'sort': request.args.get('sort', 'newest'),
    }

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
    properties = query.order_by(SORT_OPTIONS.get(filters['sort'], SORT_OPTIONS['newest'])).all()

    if search_query:
        search_params = search_engine.parse_query(search_query)
        properties = search_engine.filter_properties(properties, search_params)

    filters_active = bool(search_query) or any(
        filters[k] for k in ('property_type', 'location', 'bedrooms', 'min_price', 'max_price')
    )
    return render_template("home.html", properties=properties, search_query=search_query,
                           filters=filters, filters_active=filters_active)

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
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        role = request.form.get("role")

        # Check if user already exists
        if User.query.filter_by(email=email).first():
            flash("Email already registered. Please choose a different one.", "danger")
            return render_template("register.html", title="Register")

        if User.query.filter_by(username=username).first():
            flash("Username already taken. Please choose a different one.", "danger")
            return render_template("register.html", title="Register")

        user = User(username=username, email=email, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash("Your account has been created! You are now able to log in", "success")
        return redirect(url_for("main.login"))
    return render_template("register.html", title="Register")

@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for("main.home"))
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
        email = request.form.get("email", "").strip()
        if not username or not email:
            flash("Username and email can't be empty.", "danger")
        elif len(username) > 20:
            flash("Username must be 20 characters or fewer.", "danger")
        elif User.query.filter(User.username == username, User.id != current_user.id).first():
            flash("That username is already taken.", "danger")
        elif User.query.filter(User.email == email, User.id != current_user.id).first():
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
        return render_template("landlord_dashboard.html", properties=properties,
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
    property = Property.query.get_or_404(property_id)
    is_favorited = False
    if current_user.is_authenticated:
        is_favorited = Favorite.query.filter_by(user_id=current_user.id, property_id=property_id).first() is not None
    return render_template("property_detail.html", title=property.title, property=property, is_favorited=is_favorited)

@bp.route("/property/<int:property_id>/update", methods=["GET", "POST"])
@login_required
def update_property(property_id):
    property = Property.query.get_or_404(property_id)
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
    property = Property.query.get_or_404(property_id)
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

    property = Property.query.get_or_404(property_id)
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
    return render_template("favorites.html", properties=properties)


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
    recipient = User.query.get_or_404(recipient_id)
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

    return render_template("inbox.html", title="Inbox", conversations=conversations,
                           unread_count=unread_count, my_properties=my_properties,
                           selected_property=selected_property)

@bp.route("/conversation/<int:user_id>")
@login_required
def conversation(user_id):
    other_user = User.query.get_or_404(user_id)
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

    return render_template("conversation.html", messages=messages, other_user=other_user, property=property)

@bp.route("/send_reply/<int:recipient_id>", methods=["POST"])
@login_required
def send_reply(recipient_id):
    content = request.form.get("content", "").strip()
    recipient = User.query.get_or_404(recipient_id)
    property = _get_property_or_none(request.form.get("property_id", type=int))
    property_id = property.id if property else None

    if content and recipient != current_user:
        message = Message(sender=current_user, recipient=recipient, content=content, property_id=property_id)
        db.session.add(message)
        db.session.commit()

    return redirect(url_for("main.conversation", user_id=recipient_id, property_id=property_id))

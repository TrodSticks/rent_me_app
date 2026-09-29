from flask import render_template, url_for, flash, redirect, request, Blueprint, jsonify
from flask_login import login_user, current_user, logout_user, login_required
from app import db
from models import User, Property, Message, Favorite
from search_engine import PropertySearchEngine

bp = Blueprint("main", __name__)

# Initialize the search engine
search_engine = PropertySearchEngine()

@bp.route("/")
@bp.route("/home")
def home():
    search_query = request.args.get('search', '')
    properties = Property.query.all()
    
    if search_query:
        search_params = search_engine.parse_query(search_query)
        properties = search_engine.filter_properties(properties, search_params)
    
    return render_template("home.html", properties=properties, search_query=search_query)

@bp.route("/api/search-suggestions")
def search_suggestions():
    query = request.args.get('q', '')
    suggestions = search_engine.get_search_suggestions(query)
    return jsonify(suggestions)

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

@bp.route("/dashboard")
@login_required
def dashboard():
    if current_user.role == "Landlord":
        properties = Property.query.filter_by(landlord_id=current_user.id).all()
        return render_template("landlord_dashboard.html", properties=properties)
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
        title = request.form.get("title")
        description = request.form.get("description")
        price = int(request.form.get("price"))
        location = request.form.get("location")
        bedrooms = int(request.form.get("bedrooms"))
        property_type = request.form.get("property_type")

        property = Property(
            title=title, 
            description=description, 
            price=price, 
            location=location, 
            bedrooms=bedrooms,
            property_type=property_type,
            landlord=current_user
        )
        db.session.add(property)
        db.session.commit()
        flash("Your property has been listed!", "success")
        return redirect(url_for("main.dashboard"))
    return render_template("create_property.html", title="New Property")

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
        property.title = request.form.get("title")
        property.description = request.form.get("description")
        property.price = int(request.form.get("price"))
        property.location = request.form.get("location")
        property.bedrooms = int(request.form.get("bedrooms"))
        property.property_type = request.form.get("property_type")
        db.session.commit()
        flash("Your property has been updated!", "success")
        return redirect(url_for("main.dashboard"))
    return render_template("create_property.html", title="Update Property", property=property)

@bp.route("/property/<int:property_id>/delete", methods=["POST"])
@login_required
def delete_property(property_id):
    property = Property.query.get_or_404(property_id)
    if property.landlord != current_user:
        flash("You do not have permission to delete this property.", "danger")
        return redirect(url_for("main.home"))
    db.session.delete(property)
    db.session.commit()
    flash("Your property has been deleted!", "success")
    return redirect(url_for("main.dashboard"))

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

@bp.route("/message/<int:recipient_id>", methods=["GET", "POST"])
@login_required
def send_message(recipient_id):
    recipient = User.query.get_or_404(recipient_id)
    property_id = request.args.get('property_id')
    
    if request.method == "POST":
        content = request.form.get("content")
        message = Message(
            sender=current_user, 
            recipient=recipient, 
            content=content,
            property_id=property_id if property_id else None
        )
        db.session.add(message)
        db.session.commit()
        flash("Your message has been sent!", "success")
        return redirect(url_for("main.inbox"))
    
    property = Property.query.get(property_id) if property_id else None
    return render_template("send_message.html", title="Send Message", recipient=recipient, property=property)

@bp.route("/inbox")
@login_required
def inbox():
    messages = Message.query.filter_by(recipient_id=current_user.id).order_by(Message.timestamp.desc()).all()
    unread_count = Message.query.filter_by(recipient_id=current_user.id, read=False).count()
    return render_template("inbox.html", title="Inbox", messages=messages, unread_count=unread_count)

@bp.route("/conversation/<int:user_id>")
@login_required
def conversation(user_id):
    other_user = User.query.get_or_404(user_id)
    messages = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.recipient_id == user_id)) |
        ((Message.sender_id == user_id) & (Message.recipient_id == current_user.id))
    ).order_by(Message.timestamp.asc()).all()
    
    # Mark messages as read
    Message.query.filter_by(sender_id=user_id, recipient_id=current_user.id, read=False).update({'read': True})
    db.session.commit()
    
    return render_template("conversation.html", messages=messages, other_user=other_user)

@bp.route("/send_reply/<int:recipient_id>", methods=["POST"])
@login_required
def send_reply(recipient_id):
    content = request.form.get("content")
    recipient = User.query.get_or_404(recipient_id)
    
    message = Message(sender=current_user, recipient=recipient, content=content)
    db.session.add(message)
    db.session.commit()
    
    return redirect(url_for("main.conversation", user_id=recipient_id))


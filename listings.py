"""Property pages: creating and editing listings, their photos, the dashboard and reporting."""
import math
from datetime import date
from flask import abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import case, func, select
from app import db
from locations import LOCATIONS, MAX_PIN_DISTANCE_KM, TOWN_COORDS, distance_km
from models import (AMENITIES, REPORT_REASONS, STATUSES, Favorite, Message, Property, PropertyPhoto,
                    Report, utcnow)
from photos import DEFAULT_PHOTO, delete_picture, save_picture, upload_size
from routes import SIMILAR_COUNT, bp, favorite_ids_for
from search_engine import MAX_PRICE
from security import is_limited, record_hit

MAX_REPORT_NOTES = 1000


# ---------- Reading the listing form ----------

def _whole_number(raw, low, high):
    """Parse an optional whole number. Returns (value or None, ok)."""
    raw = (raw or '').strip()
    if not raw:
        return None, True
    try:
        value = int(raw)
    except ValueError:
        return None, False
    return (value, True) if low <= value <= high else (None, False)


def read_listing_form():
    """Validate the submitted listing. Returns (cleaned values, None) or (None, error message)."""
    form = request.form
    title = form.get("title", "").strip()
    description = form.get("description", "").strip()
    location = form.get("location")
    property_type = form.get("property_type")
    status = form.get("status", "available")

    if not title or not description:
        return None, "Please enter a title and description."
    if len(title) > 100:
        return None, "The title can be up to 100 characters."
    price, ok = _whole_number(form.get("price"), 1, MAX_PRICE)
    if not ok or price is None:
        return None, "Please enter a valid monthly price."
    bedrooms, ok = _whole_number(form.get("bedrooms"), 1, 10)
    if not ok or bedrooms is None:
        return None, "Bedrooms must be between 1 and 10."
    if location not in LOCATIONS:
        return None, "Please choose a location from the list."
    if property_type not in ("house", "flat"):
        return None, "Please choose a property type."
    if status not in STATUSES:
        return None, "Please choose whether the property is available, reserved or rented."

    # Optional details. Left blank they stay "not specified", which is different from zero.
    bathrooms, ok = _whole_number(form.get("bathrooms"), 0, 20)
    if not ok:
        return None, "Bathrooms must be a whole number from 0 to 20, or left blank."
    deposit, ok = _whole_number(form.get("deposit"), 0, MAX_PRICE)
    if not ok:
        return None, "The deposit must be a whole number of Pula (0 for no deposit), or left blank."
    available_from = None
    raw_date = form.get("available_from", "").strip()
    if raw_date:
        try:
            available_from = date.fromisoformat(raw_date)
        except ValueError:
            return None, "Please enter the available-from date as a valid date."

    # Optional map pin: both numbers or neither, and it has to be in or near the chosen town
    raw_lat, raw_lng = form.get("latitude", "").strip(), form.get("longitude", "").strip()
    latitude = longitude = None
    if raw_lat or raw_lng:
        try:
            latitude, longitude = float(raw_lat), float(raw_lng)
        except ValueError:
            return None, "The map pin couldn't be read. Please place it again."
        if not (math.isfinite(latitude) and math.isfinite(longitude)):
            return None, "The map pin couldn't be read. Please place it again."
        if distance_km((latitude, longitude), TOWN_COORDS[location]) > MAX_PIN_DISTANCE_KM:
            return None, f"The map pin is too far from {location}. Move the pin, or choose the town it's in."

    return {
        'title': title, 'description': description, 'price': price, 'bedrooms': bedrooms,
        'location': location, 'property_type': property_type, 'status': status,
        'bathrooms': bathrooms, 'deposit': deposit, 'available_from': available_from,
        'latitude': round(latitude, 6) if latitude is not None else None,
        'longitude': round(longitude, 6) if longitude is not None else None,
        'amenities': [key for key in AMENITIES if key in form.getlist("amenities")],
        'publish': form.get("action", "publish") != "draft",
    }, None


def _ids(name):
    return [int(value) for value in request.form.getlist(name) if value.isdigit()]


def plan_photos(property):
    """Work out the gallery the form asks for and store any new uploads.

    Returns (plan, None) or (None, error message). Nothing in the database changes here, and
    if an upload is rejected the files already stored for this request are removed again.
    The plan holds: the photos to keep, in order; new filenames; filenames to delete.
    """
    existing = list(property.photos) if property.id else []
    by_id = {photo.id: photo for photo in existing}
    removed = set(_ids("remove_photos")) & set(by_id)

    # The order the tiles were left in, then anything the form didn't mention
    kept = []
    for photo_id in _ids("photo_order") + [photo.id for photo in existing]:
        if photo_id in by_id and photo_id not in removed and by_id[photo_id] not in kept:
            kept.append(by_id[photo_id])
    cover_id = request.form.get("cover_photo", type=int)
    if cover_id in by_id and by_id[cover_id] in kept:
        kept.remove(by_id[cover_id])
        kept.insert(0, by_id[cover_id])

    # "image" is the old single-photo field, still accepted
    uploads = [f for f in request.files.getlist("photos") + request.files.getlist("image") if f and f.filename]
    max_photos = current_app.config['MAX_PHOTOS']
    if len(kept) + len(uploads) > max_photos:
        return None, (f"A listing can have up to {max_photos} photos. "
                      f"This would make {len(kept) + len(uploads)}; remove some and try again.")
    for upload in uploads:
        if upload_size(upload) > current_app.config['MAX_IMAGE_BYTES']:
            return None, f"{upload.filename} is larger than 5 MB. Please choose a smaller photo."

    new_files = []
    for upload in uploads:
        filename = save_picture(upload)
        if not filename:
            for stored in new_files:
                delete_picture(stored)
            return None, f"{upload.filename} isn't a photo we can read. Photos must be JPG, PNG, GIF or WebP."
        new_files.append(filename)

    return {'kept': kept, 'new_files': new_files,
            'delete_files': [by_id[photo_id].filename for photo_id in removed]}, None


def apply_listing(property, cleaned, plan):
    """Copy validated values and the photo plan onto the listing."""
    for field in ('title', 'description', 'price', 'bedrooms', 'location', 'property_type', 'status',
                  'bathrooms', 'deposit', 'available_from', 'latitude', 'longitude'):
        setattr(property, field, cleaned[field])
    property.is_published = cleaned['publish']
    property.set_amenities(cleaned['amenities'])

    for photo in list(property.photos):
        if photo not in plan['kept']:
            property.photos.remove(photo)
    for position, photo in enumerate(plan['kept']):
        photo.position = position
    for offset, filename in enumerate(plan['new_files']):
        property.photos.append(PropertyPhoto(filename=filename, position=len(plan['kept']) + offset))

    ordered = sorted(property.photos, key=lambda photo: photo.position)
    property.image_file = ordered[0].filename if ordered else DEFAULT_PHOTO


def save_listing(property, is_new):
    """Validate the form, then save the listing and its photos. Returns an error message or None."""
    cleaned, error = read_listing_form()
    if error:
        return error
    # Publishing needs a confirmed email. A listing that is already live may stay live.
    if cleaned['publish'] and not current_user.email_verified and (is_new or not property.is_published):
        return ("Confirm your email address before publishing. "
                "You can save this listing as a draft for now.")

    plan, error = plan_photos(property)
    if error:
        return error
    try:
        apply_listing(property, cleaned, plan)
        if is_new:
            property.landlord_id = current_user.id
            db.session.add(property)
        db.session.commit()
    except Exception:
        db.session.rollback()
        for filename in plan['new_files']:
            delete_picture(filename)
        raise
    # Only once the change is saved is it safe to remove the files it no longer uses
    for filename in plan['delete_files']:
        delete_picture(filename)
    return None


def _form_page(title, property=None):
    """The listing form, keeping whatever was typed when it is shown again after an error."""
    submitted = request.method == "POST"
    return render_template(
        "create_property.html", title=title, property=property,
        values=request.form if submitted else (property or {}),
        selected_amenities=request.form.getlist("amenities") if submitted else (property.amenities if property else []),
        selected_status=request.form.get("status") if submitted else (property.status if property else 'available'),
    )


# ---------- Landlord pages ----------

@bp.route("/dashboard")
@login_required
def dashboard():
    if current_user.role != "Landlord":
        flash("You do not have access to this page.", "danger")
        return redirect(url_for("main.home"))
    properties = Property.query.filter_by(landlord_id=current_user.id).order_by(Property.id.desc()).all()
    # One query for every listing's message count
    message_counts = dict(db.session.execute(
        select(Message.property_id, func.count(Message.id))
        .where(Message.recipient_id == current_user.id, Message.property_id.isnot(None))
        .group_by(Message.property_id)).all())
    return render_template("landlord_dashboard.html", title="Dashboard", properties=properties,
                           message_counts=message_counts)

@bp.route("/property/new", methods=["GET", "POST"])
@login_required
def new_property():
    if current_user.role != "Landlord":
        flash("You do not have permission to add properties.", "danger")
        return redirect(url_for("main.home"))
    if request.method == "POST":
        property = Property()
        error = save_listing(property, is_new=True)
        if error:
            flash(error, "danger")
            return _form_page("New Property")
        flash("Your property has been listed!" if property.is_published
              else "Your draft has been saved. It isn't visible to renters yet.", "success")
        return redirect(url_for("main.dashboard"))
    return _form_page("New Property")

@bp.route("/property/<int:property_id>/update", methods=["GET", "POST"])
@login_required
def update_property(property_id):
    property = db.get_or_404(Property, property_id)
    if property.landlord_id != current_user.id:
        flash("You do not have permission to edit this property.", "danger")
        return redirect(url_for("main.home"))
    if request.method == "POST":
        error = save_listing(property, is_new=False)
        if error:
            db.session.rollback()
            flash(error, "danger")
            return _form_page("Update Property", property)
        flash("Your property has been updated!", "success")
        return redirect(url_for("main.dashboard"))
    return _form_page("Update Property", property)

@bp.route("/property/<int:property_id>/status", methods=["POST"])
@login_required
def set_property_status(property_id):
    """Quick change from the dashboard, such as marking a listing as rented."""
    property = db.get_or_404(Property, property_id)
    if property.landlord_id != current_user.id:
        abort(404)
    status = request.form.get("status")
    if status not in STATUSES:
        flash("Please choose available, reserved or rented.", "danger")
    else:
        property.status = status
        db.session.commit()
        flash(f"\"{property.title}\" is now marked as {STATUSES[status].lower()}.", "success")
    return redirect(url_for("main.dashboard"))

@bp.route("/property/<int:property_id>/delete", methods=["POST"])
@login_required
def delete_property(property_id):
    property = db.get_or_404(Property, property_id)
    if property.landlord_id != current_user.id:
        flash("You do not have permission to delete this property.", "danger")
        return redirect(url_for("main.home"))
    filenames = [photo.filename for photo in property.photos]
    Favorite.query.filter_by(property_id=property.id).delete()
    Report.query.filter_by(property_id=property.id).delete()
    # Keep the conversation history, just detach it from the deleted listing
    Message.query.filter_by(property_id=property.id).update({'property_id': None})
    db.session.delete(property)
    db.session.commit()
    for filename in filenames:
        delete_picture(filename)
    flash("Your property has been deleted!", "success")
    return redirect(url_for("main.dashboard"))


# ---------- The property page ----------

@bp.route("/property/<int:property_id>")
def property_detail(property_id):
    property = db.get_or_404(Property, property_id)
    # Drafts and hidden listings don't exist as far as anyone else is concerned
    if not property.visible_to(current_user):
        abort(404)

    is_favorited = already_reported = False
    if current_user.is_authenticated:
        is_favorited = Favorite.query.filter_by(user_id=current_user.id, property_id=property_id).first() is not None
        already_reported = Report.query.filter_by(reporter_id=current_user.id, property_id=property_id,
                                                  status='open').first() is not None

    similar = similar_properties(property)
    return render_template("property_detail.html", title=property.title, property=property,
                           is_favorited=is_favorited, already_reported=already_reported,
                           similar=similar, favorite_ids=favorite_ids_for(similar))


def similar_properties(property):
    """Up to three public, available listings most like this one.

    Looks in the same town first, ranked by type, bedrooms and how close the rent is. Only when
    the town has too few does it widen to the listings nearest in rent elsewhere. Each step is
    one small query, so this never reads through the whole catalogue.
    """
    public = Property.public_conditions() + [Property.id != property.id]
    price_gap = func.abs(Property.price - property.price)
    same_type = case((Property.property_type == property.property_type, 1), else_=0)

    score = (same_type * 2
             + case((Property.bedrooms == property.bedrooms, 1), else_=0)
             + case((price_gap <= property.price * 0.25, 1), else_=0))
    similar = Property.query.filter(*public, Property.location == property.location)         .order_by(score.desc(), price_gap.asc(), Property.id.desc()).limit(SIMILAR_COUNT).all()

    missing = SIMILAR_COUNT - len(similar)
    if missing > 0:
        # Nearest in rent from other towns: a few just above and a few just below, read off the price index
        elsewhere = public + [Property.location != property.location]
        above = Property.query.filter(*elsewhere, Property.price >= property.price)             .order_by(Property.price.asc(), Property.id.desc()).limit(SIMILAR_COUNT).all()
        below = Property.query.filter(*elsewhere, Property.price < property.price)             .order_by(Property.price.desc(), Property.id.desc()).limit(SIMILAR_COUNT).all()
        nearest = sorted(above + below, key=lambda other: (other.property_type != property.property_type,
                                                           abs(other.price - property.price), -other.id))
        similar += nearest[:missing]
    return similar


# ---------- Reporting a listing ----------

@bp.route("/property/<int:property_id>/report", methods=["POST"])
@login_required
def report_property(property_id):
    property = db.get_or_404(Property, property_id)
    if not property.visible_to(current_user):
        abort(404)
    back = redirect(url_for("main.property_detail", property_id=property.id))

    reason = request.form.get("reason")
    notes = request.form.get("notes", "").strip()
    if property.landlord_id == current_user.id:
        flash("You can't report your own listing.", "danger")
    elif reason not in REPORT_REASONS:
        flash("Please choose a reason for the report.", "danger")
    elif len(notes) > MAX_REPORT_NOTES:
        flash(f"Please keep the notes under {MAX_REPORT_NOTES} characters.", "danger")
    elif Report.query.filter_by(reporter_id=current_user.id, property_id=property.id, status='open').first():
        flash("You've already reported this listing. We'll review it.", "info")
    elif is_limited('report', current_user.id):
        flash("You've sent several reports recently. Please try again later.", "warning")
    else:
        db.session.add(Report(property_id=property.id, reporter_id=current_user.id, reason=reason,
                              notes=notes or None, created_at=utcnow()))
        record_hit('report', current_user.id)
        db.session.commit()
        flash("Thanks. Your report has been sent to the Rent Me team for review.", "success")
    return back

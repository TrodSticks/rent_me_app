import hashlib
from datetime import datetime, timezone
from flask_login import UserMixin
from sqlalchemy import event
from sqlalchemy.orm.attributes import set_committed_value
from werkzeug.security import generate_password_hash, check_password_hash
from app import db, login_manager
from locations import approximate_position

# Choices shared by forms, filters and templates: key -> label shown to people
STATUSES = {
    'available': 'Available',
    'reserved': 'Reserved',
    'rented': 'Rented',
}

AMENITIES = {
    'parking': 'Parking',
    'wifi': 'Wi-Fi',
    'air_conditioning': 'Air conditioning',
    'furnished': 'Furnished',
    'security': 'Security',
    'pet_friendly': 'Pet-friendly',
    'water_included': 'Water included',
}

REPORT_REASONS = {
    'scam': 'Suspected scam',
    'misleading': 'Misleading information',
    'already_rented': 'Already rented',
    'inappropriate': 'Inappropriate content',
    'other': 'Something else',
}

REPORT_OUTCOMES = {
    'no_action': 'No action needed',
    'listing_hidden': 'Listing hidden',
    'other_action': 'Other action taken',
}


def utcnow():
    """Current UTC time, stored without a timezone like the existing rows."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


@login_manager.user_loader
def load_user(session_id):
    """Sessions carry "<user id>.<password fingerprint>", so changing a password signs out old sessions."""
    user_id, _, fingerprint = str(session_id).partition('.')
    if not user_id.isdigit() or not fingerprint:
        return None
    user = db.session.get(User, int(user_id))
    if user is None or user.password_fingerprint() != fingerprint:
        return None
    return user


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(10), nullable=False) # 'Renter' or 'Landlord'
    # When the owner proved they can read mail at `email`. Says nothing about who they are.
    email_verified_at = db.Column(db.DateTime, nullable=True)
    # Administrators moderate listings and landlords. Only the make-admin command sets this.
    is_admin = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    # Set by an administrator; separate from email verification.
    landlord_verified_at = db.Column(db.DateTime, nullable=True)
    landlord_verified_by_id = db.Column(
        db.Integer, db.ForeignKey('user.id', name='fk_user_landlord_verified_by'), nullable=True)

    properties = db.relationship('Property', backref='landlord', lazy=True,
                                 foreign_keys='Property.landlord_id')
    messages_sent = db.relationship('Message', foreign_keys='Message.sender_id', backref='sender', lazy=True)
    # 'dynamic' so templates can call .filter_by() on these
    messages_received = db.relationship('Message', foreign_keys='Message.recipient_id', backref='recipient', lazy='dynamic')
    favorites = db.relationship('Favorite', backref='user', lazy='dynamic')
    landlord_verified_by = db.relationship('User', remote_side=[id], foreign_keys=[landlord_verified_by_id])

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def password_fingerprint(self):
        """Changes whenever the password does. Used to expire sessions and reset links."""
        return hashlib.sha256(self.password_hash.encode()).hexdigest()[:16]

    def get_id(self):
        return f"{self.id}.{self.password_fingerprint()}"

    @property
    def email_verified(self):
        return self.email_verified_at is not None

    @property
    def landlord_verified(self):
        return self.role == 'Landlord' and self.landlord_verified_at is not None

    def __repr__(self):
        return f"User('{self.username}', '{self.email}', '{self.role}')"


class Property(db.Model):
    __table_args__ = (
        # Public pages always filter on these three together
        db.Index('ix_property_public', 'is_published', 'is_hidden', 'status'),
        db.Index('ix_property_location', 'location'),   # town filter and per-town counts
        db.Index('ix_property_price', 'price'),         # price range and price sorting
        db.Index('ix_property_map', 'map_lat', 'map_lng'),   # "what's in this part of the map"
        db.Index('ix_property_landlord', 'landlord_id'),     # a landlord's dashboard
    )

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Integer, nullable=False)   # monthly rent in Pula
    location = db.Column(db.String(50), nullable=False)
    bedrooms = db.Column(db.Integer, nullable=False)
    property_type = db.Column(db.String(20), nullable=False, default='house')
    # Filename of the cover photo, kept here so cards and map pins don't need to load the gallery
    image_file = db.Column(db.String(20), nullable=False, default='default.jpg')
    # Exact spot marked by the landlord. Empty means "somewhere in this town".
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    # Where the pin is drawn: the exact spot, or a stable approximate one near the town centre.
    # Stored so the map can ask the database for one area. Kept up to date by the events below.
    map_lat = db.Column(db.Float, nullable=True)
    map_lng = db.Column(db.Float, nullable=True)

    status = db.Column(db.String(10), nullable=False, default='available', server_default='available')
    available_from = db.Column(db.Date, nullable=True)
    deposit = db.Column(db.Integer, nullable=True)     # Pula; empty = not specified, 0 = no deposit
    bathrooms = db.Column(db.Integer, nullable=True)   # empty = not specified

    # Drafts are only visible to their owner
    is_published = db.Column(db.Boolean, nullable=False, default=True, server_default=db.true())
    # Hidden by an administrator after a report
    is_hidden = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    hidden_at = db.Column(db.DateTime, nullable=True)
    hidden_reason = db.Column(db.String(200), nullable=True)
    hidden_by_id = db.Column(db.Integer, db.ForeignKey('user.id', name='fk_property_hidden_by'), nullable=True)

    landlord_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    favorites = db.relationship('Favorite', backref='property', lazy=True)
    photos = db.relationship('PropertyPhoto', backref='property', lazy=True,
                             order_by='PropertyPhoto.position', cascade='all, delete-orphan')
    amenity_rows = db.relationship('PropertyAmenity', lazy=True, cascade='all, delete-orphan')
    hidden_by = db.relationship('User', foreign_keys=[hidden_by_id])

    @classmethod
    def public_conditions(cls, available_only=True):
        """What a listing must be to appear in public lists, the map and recommendations."""
        conditions = [cls.is_published.is_(True), cls.is_hidden.is_(False)]
        if available_only:
            conditions.append(cls.status == 'available')
        return conditions

    @property
    def is_public(self):
        return self.is_published and not self.is_hidden

    def visible_to(self, user):
        """Drafts and hidden listings can only be opened by their owner or an administrator."""
        if self.is_public:
            return True
        return user.is_authenticated and (user.id == self.landlord_id or user.is_admin)

    @property
    def has_exact_location(self):
        return self.latitude is not None and self.longitude is not None

    @property
    def amenities(self):
        """Amenity keys, in the order they are offered on the form."""
        chosen = {row.amenity for row in self.amenity_rows}
        return [key for key in AMENITIES if key in chosen]

    def set_amenities(self, keys):
        wanted = [key for key in AMENITIES if key in set(keys)]
        current = {row.amenity: row for row in self.amenity_rows}
        for key, row in current.items():
            if key not in wanted:
                self.amenity_rows.remove(row)
        for key in wanted:
            if key not in current:
                self.amenity_rows.append(PropertyAmenity(amenity=key))

    def map_position(self):
        if self.has_exact_location:
            return self.latitude, self.longitude
        return approximate_position(self.id, self.location) or (None, None)

    def __repr__(self):
        return f"Property('{self.title}', '{self.location}', '{self.price}')"


@event.listens_for(Property, 'before_update')
def _refresh_map_position(mapper, connection, target):
    target.map_lat, target.map_lng = target.map_position()


@event.listens_for(Property, 'after_insert')
def _set_map_position(mapper, connection, target):
    # An approximate position depends on the id, which only exists once the row is inserted
    lat, lng = target.map_position()
    connection.execute(
        Property.__table__.update().where(Property.__table__.c.id == target.id).values(map_lat=lat, map_lng=lng))
    set_committed_value(target, 'map_lat', lat)
    set_committed_value(target, 'map_lng', lng)


class PropertyPhoto(db.Model):
    __tablename__ = 'property_photo'
    __table_args__ = (db.Index('ix_property_photo_order', 'property_id', 'position'),)

    id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.Integer, db.ForeignKey('property.id'), nullable=False)
    filename = db.Column(db.String(40), nullable=False)
    position = db.Column(db.Integer, nullable=False, default=0)   # 0 is the cover photo
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class PropertyAmenity(db.Model):
    __tablename__ = 'property_amenity'
    # The primary key finds a listing's amenities; this index finds listings with an amenity
    __table_args__ = (db.Index('ix_property_amenity_lookup', 'amenity', 'property_id'),)

    property_id = db.Column(db.Integer, db.ForeignKey('property.id'), primary_key=True)
    amenity = db.Column(db.String(30), primary_key=True)


class Message(db.Model):
    __table_args__ = (
        db.Index('ix_message_recipient_read', 'recipient_id', 'read'),   # unread count on every page
        db.Index('ix_message_sender', 'sender_id'),
        db.Index('ix_message_property', 'property_id'),
    )

    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    property_id = db.Column(db.Integer, db.ForeignKey('property.id'), nullable=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=utcnow)
    read = db.Column(db.Boolean, default=False)
    property = db.relationship('Property', backref='messages')

    def __repr__(self):
        return f"Message('{self.sender_id}', '{self.recipient_id}', '{self.timestamp}')"


class Favorite(db.Model):
    __table_args__ = (
        db.UniqueConstraint('user_id', 'property_id', name='uq_favorite_user_property'),
        db.Index('ix_favorite_property', 'property_id'),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    property_id = db.Column(db.Integer, db.ForeignKey('property.id'), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=utcnow)

    def __repr__(self):
        return f"Favorite('{self.user_id}', '{self.property_id}')"


class Report(db.Model):
    __table_args__ = (
        db.Index('ix_report_queue', 'status', 'created_at'),          # the admin queue
        db.Index('ix_report_property', 'property_id'),
        db.Index('ix_report_reporter', 'reporter_id', 'property_id'),  # "have I already reported this?"
    )

    id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.Integer, db.ForeignKey('property.id'), nullable=False)
    reporter_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    reason = db.Column(db.String(30), nullable=False)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    status = db.Column(db.String(10), nullable=False, default='open', server_default='open')   # open or resolved
    outcome = db.Column(db.String(30), nullable=True)
    resolution_notes = db.Column(db.Text, nullable=True)
    resolved_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)

    property = db.relationship('Property', backref=db.backref('reports', lazy=True))
    reporter = db.relationship('User', foreign_keys=[reporter_id])
    resolved_by = db.relationship('User', foreign_keys=[resolved_by_id])


class RateLimitHit(db.Model):
    """One counted attempt (a failed login, a reset request...). `bucket` is a hash, never raw details."""
    __tablename__ = 'rate_limit_hit'
    __table_args__ = (db.Index('ix_rate_limit_bucket', 'bucket', 'created_at'),)

    id = db.Column(db.Integer, primary_key=True)
    bucket = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

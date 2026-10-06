"""photo gallery, listing details, verification, reports and indexes

Revision ID: 0003_gallery_details_trust
Revises: 0002_property_coordinates
Create Date: 2026-10-03 09:00:00

Existing data is kept:
- every listing stays published and becomes "available"
- a listing's single photo becomes the first (cover) photo of its gallery
- bathrooms, deposit, available-from and amenities stay empty: nothing is invented
- no account is marked as email-verified, landlord-verified or administrator
- each listing gets a stored map position: its exact pin, or the same approximate
  spot near its town centre that the map already showed
"""
import math
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0003_gallery_details_trust'
down_revision = '0002_property_coordinates'
branch_labels = None
depends_on = None

# A copy of locations.py as it was when this migration was written. Migrations must not
# depend on application code that can change later.
TOWN_COORDS = {
    'Gaborone': (-24.6282, 25.9231),
    'Phakalane': (-24.5700, 25.9800),
    'Francistown': (-21.1700, 27.5079),
    'Maun': (-19.9833, 23.4167),
    'Kasane': (-17.7980, 25.1530),
    'Serowe': (-22.3875, 26.7108),
    'Molepolole': (-24.4066, 25.4951),
    'Kanye': (-24.9667, 25.3327),
    'Mochudi': (-24.4167, 26.1500),
    'Lobatse': (-25.2167, 25.6667),
    'Palapye': (-22.5460, 27.1251),
    'Jwaneng': (-24.6017, 24.7281),
    'Ghanzi': (-21.6978, 21.6458),
    'Tsabong': (-26.0500, 22.4500),
    'Letlhakane': (-21.4149, 25.5926),
}
PIN_SPREAD_DEGREES = 0.012


def _approximate_position(property_id, town):
    centre = TOWN_COORDS.get(town)
    if not centre:
        return None, None
    angle = math.radians(property_id * 137.5)
    radius = PIN_SPREAD_DEGREES * math.sqrt(property_id % 12 + 1)
    return (round(centre[0] + radius * math.sin(angle), 5),
            round(centre[1] + radius * math.cos(angle), 5))


def upgrade():
    connection = op.get_bind()

    # ----- New tables -----
    op.create_table(
        'property_photo',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('property_id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(length=40), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['property_id'], ['property.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_property_photo_order', 'property_photo', ['property_id', 'position'])

    op.create_table(
        'property_amenity',
        sa.Column('property_id', sa.Integer(), nullable=False),
        sa.Column('amenity', sa.String(length=30), nullable=False),
        sa.ForeignKeyConstraint(['property_id'], ['property.id']),
        sa.PrimaryKeyConstraint('property_id', 'amenity'),
    )
    op.create_index('ix_property_amenity_lookup', 'property_amenity', ['amenity', 'property_id'])

    op.create_table(
        'report',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('property_id', sa.Integer(), nullable=False),
        sa.Column('reporter_id', sa.Integer(), nullable=False),
        sa.Column('reason', sa.String(length=30), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('status', sa.String(length=10), server_default='open', nullable=False),
        sa.Column('outcome', sa.String(length=30), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('resolved_by_id', sa.Integer(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['property_id'], ['property.id']),
        sa.ForeignKeyConstraint(['reporter_id'], ['user.id']),
        sa.ForeignKeyConstraint(['resolved_by_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_report_queue', 'report', ['status', 'created_at'])
    op.create_index('ix_report_property', 'report', ['property_id'])
    op.create_index('ix_report_reporter', 'report', ['reporter_id', 'property_id'])

    op.create_table(
        'rate_limit_hit',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('bucket', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_rate_limit_bucket', 'rate_limit_hit', ['bucket', 'created_at'])

    # ----- Accounts -----
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('email_verified_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('is_admin', sa.Boolean(), server_default=sa.false(), nullable=False))
        batch_op.add_column(sa.Column('landlord_verified_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('landlord_verified_by_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_user_landlord_verified_by', 'user', ['landlord_verified_by_id'], ['id'])

    # ----- Listings -----
    with op.batch_alter_table('property', schema=None) as batch_op:
        batch_op.add_column(sa.Column('map_lat', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('map_lng', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('status', sa.String(length=10), server_default='available', nullable=False))
        batch_op.add_column(sa.Column('available_from', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('deposit', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('bathrooms', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('is_published', sa.Boolean(), server_default=sa.true(), nullable=False))
        batch_op.add_column(sa.Column('is_hidden', sa.Boolean(), server_default=sa.false(), nullable=False))
        batch_op.add_column(sa.Column('hidden_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('hidden_reason', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('hidden_by_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_property_hidden_by', 'user', ['hidden_by_id'], ['id'])
        batch_op.create_index('ix_property_public', ['is_published', 'is_hidden', 'status'])
        batch_op.create_index('ix_property_location', ['location'])
        batch_op.create_index('ix_property_price', ['price'])
        batch_op.create_index('ix_property_map', ['map_lat', 'map_lng'])
        batch_op.create_index('ix_property_landlord', ['landlord_id'])

    # ----- Carry existing data over -----
    property_table = sa.table(
        'property',
        sa.column('id', sa.Integer), sa.column('location', sa.String), sa.column('image_file', sa.String),
        sa.column('latitude', sa.Float), sa.column('longitude', sa.Float),
        sa.column('map_lat', sa.Float), sa.column('map_lng', sa.Float))
    photo_table = sa.table(
        'property_photo',
        sa.column('property_id', sa.Integer), sa.column('filename', sa.String),
        sa.column('position', sa.Integer), sa.column('created_at', sa.DateTime))

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    rows = connection.execute(sa.select(
        property_table.c.id, property_table.c.location, property_table.c.image_file,
        property_table.c.latitude, property_table.c.longitude)).fetchall()
    for row in rows:
        # Stored map position: the landlord's pin if there is one, else the approximate spot
        if row.latitude is not None and row.longitude is not None:
            lat, lng = row.latitude, row.longitude
        else:
            lat, lng = _approximate_position(row.id, row.location)
        connection.execute(property_table.update().where(property_table.c.id == row.id)
                           .values(map_lat=lat, map_lng=lng))
        # The listing's one photo becomes the cover photo of its gallery
        if row.image_file and row.image_file != 'default.jpg':
            connection.execute(photo_table.insert().values(
                property_id=row.id, filename=row.image_file, position=0, created_at=now))

    # ----- Favourites: one row per person and listing -----
    connection.execute(sa.text(
        "DELETE FROM favorite WHERE id NOT IN (SELECT MIN(id) FROM favorite GROUP BY user_id, property_id)"))
    with op.batch_alter_table('favorite', schema=None) as batch_op:
        batch_op.create_unique_constraint('uq_favorite_user_property', ['user_id', 'property_id'])
        batch_op.create_index('ix_favorite_property', ['property_id'])

    # ----- Messages -----
    with op.batch_alter_table('message', schema=None) as batch_op:
        batch_op.create_index('ix_message_recipient_read', ['recipient_id', 'read'])
        batch_op.create_index('ix_message_sender', ['sender_id'])
        batch_op.create_index('ix_message_property', ['property_id'])


def downgrade():
    with op.batch_alter_table('message', schema=None) as batch_op:
        batch_op.drop_index('ix_message_property')
        batch_op.drop_index('ix_message_sender')
        batch_op.drop_index('ix_message_recipient_read')

    with op.batch_alter_table('favorite', schema=None) as batch_op:
        batch_op.drop_index('ix_favorite_property')
        batch_op.drop_constraint('uq_favorite_user_property', type_='unique')

    with op.batch_alter_table('property', schema=None) as batch_op:
        batch_op.drop_index('ix_property_landlord')
        batch_op.drop_index('ix_property_map')
        batch_op.drop_index('ix_property_price')
        batch_op.drop_index('ix_property_location')
        batch_op.drop_index('ix_property_public')
        batch_op.drop_constraint('fk_property_hidden_by', type_='foreignkey')
        for column in ('hidden_by_id', 'hidden_reason', 'hidden_at', 'is_hidden', 'is_published',
                       'bathrooms', 'deposit', 'available_from', 'status', 'map_lng', 'map_lat'):
            batch_op.drop_column(column)

    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_constraint('fk_user_landlord_verified_by', type_='foreignkey')
        for column in ('landlord_verified_by_id', 'landlord_verified_at', 'is_admin', 'email_verified_at'):
            batch_op.drop_column(column)

    op.drop_index('ix_rate_limit_bucket', table_name='rate_limit_hit')
    op.drop_table('rate_limit_hit')
    op.drop_index('ix_report_reporter', table_name='report')
    op.drop_index('ix_report_property', table_name='report')
    op.drop_index('ix_report_queue', table_name='report')
    op.drop_table('report')
    op.drop_index('ix_property_amenity_lookup', table_name='property_amenity')
    op.drop_table('property_amenity')
    op.drop_index('ix_property_photo_order', table_name='property_photo')
    op.drop_table('property_photo')

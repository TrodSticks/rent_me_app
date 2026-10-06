"""Upgrading real database files: from before migrations existed, from the previous schema, and from nothing."""
import sqlite3
import pytest
from flask_migrate import upgrade
from sqlalchemy import inspect
from app import BASELINE_REVISION, create_app, db
from config import Config
from locations import approximate_position

PREVIOUS = '0002_property_coordinates'
HEAD = '0003_gallery_details_trust'


@pytest.fixture
def file_database(tmp_path, monkeypatch):
    path = tmp_path / 'rentme.db'
    monkeypatch.setattr(Config, 'SQLALCHEMY_DATABASE_URI', f'sqlite:///{path}')
    return path


def build_at(revision, path, monkeypatch):
    """Create the database file at an older revision, without the app bringing it up to date."""
    monkeypatch.setenv('AUTO_MIGRATE', '0')
    app = create_app()
    with app.app_context():
        upgrade(revision=revision)
        db.engine.dispose()
    monkeypatch.setenv('AUTO_MIGRATE', '1')


def start_app():
    app = create_app()
    with app.app_context():
        db.engine.dispose()
    return app


def rows(path, sql):
    connection = sqlite3.connect(path)
    try:
        return connection.execute(sql).fetchall()
    finally:
        connection.close()


def run(path, statements):
    connection = sqlite3.connect(path)
    try:
        for statement in statements:
            connection.execute(statement)
        connection.commit()
    finally:
        connection.close()


def columns(path, table):
    return [row[1] for row in rows(path, f'pragma table_info("{table}")')]


def version(path):
    return rows(path, 'select version_num from alembic_version')[0][0]


OLD_DATA = [
    "insert into user (id, username, email, password_hash, role) values (1, 'owner', 'owner@test.com', 'hash-1', 'Landlord')",
    "insert into user (id, username, email, password_hash, role) values (2, 'seeker', 'seeker@test.com', 'hash-2', 'Renter')",
    # One listing with a photo and an exact pin, one with neither, one in a town the app doesn't know
    "insert into property (id, title, description, price, location, bedrooms, property_type, image_file, latitude, longitude, landlord_id) "
    "values (1, 'Pinned flat', 'd', 4500, 'Gaborone', 2, 'flat', 'abc123.jpg', -24.6541, 25.9087, 1)",
    "insert into property (id, title, description, price, location, bedrooms, property_type, image_file, latitude, longitude, landlord_id) "
    "values (2, 'Plain house', 'd', 3000, 'Maun', 3, 'house', 'default.jpg', null, null, 1)",
    "insert into property (id, title, description, price, location, bedrooms, property_type, image_file, latitude, longitude, landlord_id) "
    "values (3, 'Elsewhere', 'd', 2000, 'Atlantis', 1, 'flat', 'xyz789.jpg', null, null, 1)",
    "insert into favorite (id, user_id, property_id, timestamp) values (1, 2, 1, '2026-09-01 10:00:00')",
    "insert into favorite (id, user_id, property_id, timestamp) values (2, 2, 1, '2026-09-02 10:00:00')",   # a duplicate
    "insert into favorite (id, user_id, property_id, timestamp) values (3, 2, 2, '2026-09-03 10:00:00')",
    "insert into message (id, sender_id, recipient_id, property_id, content, timestamp, read) "
    "values (1, 2, 1, 1, 'Is it still available?', '2026-09-04 10:00:00', 0)",
    "insert into message (id, sender_id, recipient_id, property_id, content, timestamp, read) "
    "values (2, 1, 2, 1, 'Yes it is.', '2026-09-04 11:00:00', 1)",
]


@pytest.fixture
def upgraded(file_database, monkeypatch):
    """A database from the previous release, with data in it, after the app has started on it."""
    build_at(PREVIOUS, file_database, monkeypatch)
    run(file_database, OLD_DATA)
    assert 'status' not in columns(file_database, 'property')
    start_app()
    return file_database


# ---------- Upgrading from the previous schema ----------

def test_upgrade_reaches_the_latest_version(upgraded):
    assert version(upgraded) == HEAD


def test_users_are_kept_and_nobody_is_promoted(upgraded):
    assert rows(upgraded, 'select id, username, email, password_hash, role from user order by id') == [
        (1, 'owner', 'owner@test.com', 'hash-1', 'Landlord'),
        (2, 'seeker', 'seeker@test.com', 'hash-2', 'Renter'),
    ]
    # Existing accounts are not treated as verified, and nobody becomes an administrator
    assert rows(upgraded, 'select email_verified_at, is_admin, landlord_verified_at, landlord_verified_by_id from user') == \
        [(None, 0, None, None), (None, 0, None, None)]


def test_listings_are_kept_and_stay_live(upgraded):
    assert rows(upgraded, 'select id, title, price, location, bedrooms, property_type, image_file, landlord_id '
                          'from property order by id') == [
        (1, 'Pinned flat', 4500, 'Gaborone', 2, 'flat', 'abc123.jpg', 1),
        (2, 'Plain house', 3000, 'Maun', 3, 'house', 'default.jpg', 1),
        (3, 'Elsewhere', 2000, 'Atlantis', 1, 'flat', 'xyz789.jpg', 1),
    ]
    assert rows(upgraded, 'select distinct status, is_published, is_hidden from property') == [('available', 1, 0)]


def test_no_details_are_invented(upgraded):
    assert rows(upgraded, 'select distinct bathrooms, deposit, available_from from property') == [(None, None, None)]
    assert rows(upgraded, 'select count(*) from property_amenity') == [(0,)]


def test_existing_photos_become_gallery_covers(upgraded):
    assert rows(upgraded, 'select property_id, filename, position from property_photo order by property_id') == [
        (1, 'abc123.jpg', 0),
        (3, 'xyz789.jpg', 0),
    ]


def test_map_positions_are_filled_in(upgraded):
    positions = {row[0]: row[1:] for row in rows(upgraded, 'select id, latitude, longitude, map_lat, map_lng from property')}
    # An exact pin is kept as it is
    assert positions[1] == (-24.6541, 25.9087, -24.6541, 25.9087)
    # No pin: still no exact location, and the same approximate spot the map showed before
    assert positions[2] == (None, None) + approximate_position(2, 'Maun')
    # A town without coordinates stays off the map
    assert positions[3] == (None, None, None, None)


def test_favourites_are_kept_without_duplicates(upgraded):
    assert rows(upgraded, 'select id, user_id, property_id from favorite order by id') == [(1, 2, 1), (3, 2, 2)]
    with pytest.raises(sqlite3.IntegrityError):
        run(upgraded, ["insert into favorite (user_id, property_id, timestamp) values (2, 1, '2026-10-01 10:00:00')"])


def test_messages_are_kept(upgraded):
    assert rows(upgraded, 'select id, sender_id, recipient_id, property_id, content, read from message order by id') == [
        (1, 2, 1, 1, 'Is it still available?', 0),
        (2, 1, 2, 1, 'Yes it is.', 1),
    ]


def test_new_tables_and_indexes_exist(upgraded):
    tables = {row[0] for row in rows(upgraded, "select name from sqlite_master where type = 'table'")}
    assert {'property_photo', 'property_amenity', 'report', 'rate_limit_hit'} <= tables
    indexes = {row[0] for row in rows(upgraded, "select name from sqlite_master where type = 'index'")}
    assert {'ix_property_public', 'ix_property_location', 'ix_property_price', 'ix_property_map',
            'ix_property_landlord', 'ix_property_photo_order', 'ix_property_amenity_lookup',
            'ix_message_recipient_read', 'ix_favorite_property', 'ix_report_queue',
            'ix_rate_limit_bucket'} <= indexes


def test_upgraded_database_works_with_the_app(upgraded):
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    client = app.test_client()
    html = client.get('/').get_data(as_text=True)
    assert 'Pinned flat' in html and 'Plain house' in html
    assert 'abc123.jpg' in client.get('/property/1').get_data(as_text=True)
    pins = client.get('/api/map-pins?bbox=-27,19.9,-17.5,29.5').get_json()['pins']
    assert {pin['title']: pin['exact'] for pin in pins} == {'Pinned flat': True, 'Plain house': False}
    with app.app_context():
        db.engine.dispose()


def test_starting_again_changes_nothing(upgraded):
    before = rows(upgraded, 'select * from property') + rows(upgraded, 'select * from property_photo')
    start_app()
    assert rows(upgraded, 'select * from property') + rows(upgraded, 'select * from property_photo') == before
    assert version(upgraded) == HEAD


# ---------- Other starting points ----------

def test_new_database_is_created_fully_migrated(file_database):
    start_app()
    assert version(file_database) == HEAD
    assert {'latitude', 'map_lat', 'status', 'deposit', 'is_hidden'} <= set(columns(file_database, 'property'))
    assert {'email_verified_at', 'is_admin'} <= set(columns(file_database, 'user'))


def test_database_from_before_migrations_is_upgraded_and_keeps_its_data(file_database, monkeypatch):
    # Build a database the way the app made them before migrations existed: tables, no version
    build_at(BASELINE_REVISION, file_database, monkeypatch)
    run(file_database, [
        "insert into user (username, email, password_hash, role) values ('old', 'old@test.com', 'x', 'Renter')",
        'drop table alembic_version',
    ])
    assert 'latitude' not in columns(file_database, 'property')

    start_app()
    assert version(file_database) == HEAD
    assert {'latitude', 'map_lat', 'status'} <= set(columns(file_database, 'property'))
    assert rows(file_database, 'select username from user') == [('old',)]


def test_models_and_migrations_describe_the_same_tables(file_database):
    """A database built by the migrations has every table and column the models expect."""
    app = start_app()
    with app.app_context():
        inspector = inspect(db.engine)
        for table in db.metadata.sorted_tables:
            migrated = {column['name'] for column in inspector.get_columns(table.name)}
            assert migrated == {column.name for column in table.columns}, table.name
            migrated_indexes = {index['name'] for index in inspector.get_indexes(table.name)}
            assert {index.name for index in table.indexes} <= migrated_indexes, table.name
        db.engine.dispose()


def test_downgrade_and_upgrade_again(file_database, monkeypatch):
    from flask_migrate import downgrade
    build_at(HEAD, file_database, monkeypatch)
    run(file_database, [
        "insert into user (id, username, email, password_hash, role, is_admin) values (1, 'owner', 'o@test.com', 'h', 'Landlord', 0)",
        "insert into property (id, title, description, price, location, bedrooms, property_type, image_file, landlord_id, "
        "status, is_published, is_hidden) values (1, 'Kept', 'd', 1000, 'Maun', 1, 'flat', 'default.jpg', 1, 'available', 1, 0)",
    ])
    monkeypatch.setenv('AUTO_MIGRATE', '0')
    app = create_app()
    with app.app_context():
        downgrade(revision=PREVIOUS)
        db.engine.dispose()
    assert 'status' not in columns(file_database, 'property')
    assert rows(file_database, 'select title from property') == [('Kept',)]

    monkeypatch.setenv('AUTO_MIGRATE', '1')
    start_app()
    assert version(file_database) == HEAD
    assert rows(file_database, 'select title, status from property') == [('Kept', 'available')]

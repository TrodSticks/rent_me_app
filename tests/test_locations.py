import sqlite3
import pytest
from flask_migrate import upgrade
from app import BASELINE_REVISION, create_app, db
from config import Config
from models import Property

HEAD = '0002_property_coordinates'


def property_form(**overrides):
    data = {'title': 'Pinned place', 'description': 'Nice', 'price': '4000',
            'location': 'Gaborone', 'bedrooms': '2', 'property_type': 'flat'}
    data.update(overrides)
    return data


def create(client, **overrides):
    return client.post('/property/new', data=property_form(**overrides), content_type='multipart/form-data')


# ---------- Landlords marking a location ----------

def test_pin_is_saved(app, landlord_client):
    assert create(landlord_client, latitude='-24.6541', longitude='25.9087').status_code == 302
    property = Property.query.filter_by(title='Pinned place').one()
    assert (property.latitude, property.longitude) == (-24.6541, 25.9087)


def test_pin_is_optional(app, landlord_client):
    assert create(landlord_client).status_code == 302
    property = Property.query.filter_by(title='Pinned place').one()
    assert property.latitude is None and property.longitude is None


def test_pin_far_from_the_town_is_rejected(app, landlord_client):
    # Maun's coordinates on a Gaborone listing
    resp = create(landlord_client, latitude='-19.98', longitude='23.42')
    assert 'too far from Gaborone' in resp.get_data(as_text=True)
    assert Property.query.filter_by(title='Pinned place').first() is None


def test_pin_on_the_edge_of_town_is_accepted(app, landlord_client):
    # Phakalane is about 9 km from the centre of Gaborone
    assert create(landlord_client, latitude='-24.57', longitude='25.98').status_code == 302


@pytest.mark.parametrize('latitude, longitude', [
    ('-24.65', ''), ('', '25.9'), ('north', '25.9'), ('nan', '25.9'), ('inf', '25.9'),
])
def test_unreadable_pin_is_rejected(app, landlord_client, latitude, longitude):
    resp = create(landlord_client, latitude=latitude, longitude=longitude)
    assert "be read" in resp.get_data(as_text=True)
    assert Property.query.filter_by(title='Pinned place').first() is None


def test_rejected_form_keeps_the_pin(app, landlord_client):
    html = create(landlord_client, price='abc', latitude='-24.6541', longitude='25.9087').get_data(as_text=True)
    assert 'name="latitude" id="latitude" value="-24.6541"' in html
    assert 'name="longitude" id="longitude" value="25.9087"' in html


def test_edit_form_shows_the_saved_pin_and_can_remove_it(app, landlord_client):
    create(landlord_client, latitude='-24.6541', longitude='25.9087')
    property = Property.query.filter_by(title='Pinned place').one()
    url = f'/property/{property.id}/update'

    html = landlord_client.get(url).get_data(as_text=True)
    assert 'value="-24.6541"' in html and 'value="25.9087"' in html

    landlord_client.post(url, data=property_form(latitude='', longitude=''), content_type='multipart/form-data')
    property = db.session.get(Property, property.id)
    assert property.latitude is None and property.longitude is None


def test_moving_town_without_moving_the_pin_is_rejected(app, landlord_client):
    create(landlord_client, latitude='-24.6541', longitude='25.9087')
    property = Property.query.filter_by(title='Pinned place').one()
    resp = landlord_client.post(f'/property/{property.id}/update', content_type='multipart/form-data',
                                data=property_form(location='Maun', latitude='-24.6541', longitude='25.9087'))
    assert 'too far from Maun' in resp.get_data(as_text=True)
    assert db.session.get(Property, property.id).location == 'Gaborone'


# ---------- Database migrations ----------

def database_state(path):
    connection = sqlite3.connect(path)
    try:
        version = connection.execute('select version_num from alembic_version').fetchone()[0]
        columns = [row[1] for row in connection.execute('pragma table_info(property)')]
        users = connection.execute('select username from user').fetchall()
    finally:
        connection.close()
    return version, columns, users


@pytest.fixture
def file_database(tmp_path, monkeypatch):
    path = tmp_path / 'rentme.db'
    monkeypatch.setattr(Config, 'SQLALCHEMY_DATABASE_URI', f'sqlite:///{path}')
    return path


def test_new_database_is_created_fully_migrated(file_database):
    create_app()
    version, columns, _ = database_state(file_database)
    assert version == HEAD
    assert 'latitude' in columns and 'longitude' in columns


def test_database_from_before_migrations_is_upgraded_and_keeps_its_data(file_database, monkeypatch):
    # Build a database the way the app made them before migrations existed
    monkeypatch.setenv('AUTO_MIGRATE', '0')
    app = create_app()
    with app.app_context():
        upgrade(revision=BASELINE_REVISION)
        db.engine.dispose()
    connection = sqlite3.connect(file_database)
    connection.execute("insert into user (username, email, password_hash, role) values ('old', 'old@test.com', 'x', 'Renter')")
    connection.execute('drop table alembic_version')
    connection.commit()
    assert 'latitude' not in [row[1] for row in connection.execute('pragma table_info(property)')]
    connection.close()

    monkeypatch.setenv('AUTO_MIGRATE', '1')
    app = create_app()
    with app.app_context():
        db.engine.dispose()

    version, columns, users = database_state(file_database)
    assert version == HEAD
    assert 'latitude' in columns and 'longitude' in columns
    assert users == [('old',)]


def test_starting_again_changes_nothing(file_database):
    create_app()
    before = database_state(file_database)
    create_app()
    assert database_state(file_database) == before

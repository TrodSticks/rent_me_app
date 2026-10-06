import pytest
from app import db
from models import Property


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

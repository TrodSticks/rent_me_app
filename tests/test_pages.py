import pytest
from models import Property


@pytest.mark.parametrize('path', ['/', '/inbox', '/account', '/favorites'])
def test_renter_pages_load(renter_client, path):
    assert renter_client.get(path).status_code == 200


@pytest.mark.parametrize('path', ['/', '/inbox', '/account', '/dashboard', '/property/new'])
def test_landlord_pages_load(landlord_client, path):
    assert landlord_client.get(path).status_code == 200


def test_property_detail_loads_logged_in(app, renter_client):
    property = Property.query.first()
    assert renter_client.get(f'/property/{property.id}').status_code == 200


def test_account_requires_login(client):
    resp = client.get('/account')
    assert resp.status_code == 302
    assert '/login' in resp.headers['Location']

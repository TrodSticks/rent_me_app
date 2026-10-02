import re
import pytest
import config
from conftest import login
from models import Favorite, Property, User


# ---------- Secret key ----------

def test_secret_key_is_not_the_old_public_default(app):
    assert app.config['SECRET_KEY'] != 'a_very_secret_key_that_should_be_changed_in_production'
    assert len(app.config['SECRET_KEY']) >= 32


def test_secret_key_comes_from_environment(monkeypatch):
    monkeypatch.setenv('SECRET_KEY', 'from-the-environment')
    assert config._load_secret_key() == 'from-the-environment'


# ---------- Debug mode ----------

def test_debug_is_off_by_default(app):
    assert app.debug is False


# ---------- CSRF ----------

@pytest.fixture
def csrf_client(app):
    app.config['WTF_CSRF_ENABLED'] = True
    return app.test_client()


def csrf_token(client, path):
    html = client.get(path).get_data(as_text=True)
    return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)


def test_login_without_token_is_rejected(csrf_client):
    resp = csrf_client.post('/login', data={'email': 'renter@test.com', 'password': 'pw123'},
                            follow_redirects=True)
    assert 'form expired' in resp.get_data(as_text=True)
    assert csrf_client.get('/account').status_code == 302  # still logged out


def test_login_with_token_works(csrf_client):
    token = csrf_token(csrf_client, '/login')
    csrf_client.post('/login', data={'email': 'renter@test.com', 'password': 'pw123', 'csrf_token': token})
    assert csrf_client.get('/account').status_code == 200


def test_delete_property_without_token_is_rejected(app, csrf_client):
    token = csrf_token(csrf_client, '/login')
    csrf_client.post('/login', data={'email': 'landlord@test.com', 'password': 'pw123', 'csrf_token': token})
    property = Property.query.first()
    csrf_client.post(f'/property/{property.id}/delete')
    assert Property.query.count() == 4


def test_favorite_needs_token_header(app, csrf_client):
    token = csrf_token(csrf_client, '/login')
    csrf_client.post('/login', data={'email': 'renter@test.com', 'password': 'pw123', 'csrf_token': token})
    property = Property.query.first()

    assert csrf_client.post(f'/favorite/{property.id}').status_code == 400
    assert Favorite.query.count() == 0

    html = csrf_client.get('/').get_data(as_text=True)
    header = re.search(r'name="csrf-token" content="([^"]+)"', html).group(1)
    resp = csrf_client.post(f'/favorite/{property.id}', headers={'X-CSRFToken': header})
    assert resp.get_json() == {'is_favorited': True}


@pytest.mark.parametrize('path', ['/login', '/register'])
def test_public_forms_include_token(client, path):
    assert 'name="csrf_token"' in client.get(path).get_data(as_text=True)


@pytest.mark.parametrize('path', ['/account', '/property/new', '/dashboard'])
def test_landlord_forms_include_token(app, landlord_client, path):
    html = landlord_client.get(path).get_data(as_text=True)
    assert html.count('<form') == 0 or 'name="csrf_token"' in html
    # every POST form on the page carries a token
    assert len(re.findall(r'method="POST"', html)) == html.count('name="csrf_token"')


# ---------- Login redirect ----------

def test_next_to_own_page_is_followed(client):
    resp = client.post('/login?next=/account', data={'email': 'renter@test.com', 'password': 'pw123'})
    assert resp.headers['Location'].endswith('/account')


@pytest.mark.parametrize('target', [
    'https://evil.example/login', '//evil.example', '/\\evil.example', 'http:evil.example', 'javascript:alert(1)',
])
def test_next_to_other_site_goes_home(client, target):
    resp = client.post('/login', query_string={'next': target},
                       data={'email': 'renter@test.com', 'password': 'pw123'})
    assert resp.status_code == 302
    assert resp.headers['Location'] in ('/home', '/')


# ---------- Sign-up validation ----------

def signup(client, **overrides):
    data = {'username': 'newuser', 'email': 'new@test.com', 'password': 'secret1', 'role': 'Renter'}
    data.update(overrides)
    return client.post('/register', data=data)


def test_valid_signup(app, client):
    assert signup(client).status_code == 302
    assert User.query.filter_by(email='new@test.com').one().role == 'Renter'


@pytest.mark.parametrize('overrides, message', [
    ({'password': 'abc'}, 'at least 6 characters'),
    ({'email': 'not-an-email'}, 'valid email'),
    ({'email': 'a@b'}, 'valid email'),
    ({'role': 'Admin'}, 'renter or a landlord'),
    ({'username': 'x' * 21}, '1 to 20 characters'),
    ({'username': '   '}, '1 to 20 characters'),
    ({'email': 'RENTER@test.com'}, 'already registered'),
    ({'username': 'renter'}, 'already taken'),
])
def test_invalid_signup_is_rejected(app, client, overrides, message):
    resp = signup(client, **overrides)
    assert resp.status_code == 200
    assert message in resp.get_data(as_text=True)
    assert User.query.count() == 2


def test_signup_error_keeps_typed_values(client):
    html = signup(client, password='abc', role='Landlord').get_data(as_text=True)
    assert 'value="newuser"' in html
    assert 'value="new@test.com"' in html
    assert re.search(r'value="Landlord"\s+checked', html)


def test_login_email_is_case_insensitive(client):
    assert login(client, 'Renter@Test.com').status_code == 302

from conftest import login
from models import User


def test_update_profile(app, renter_client):
    resp = renter_client.post('/account', data={'username': 'newname', 'email': 'new@test.com'},
                              follow_redirects=True)
    assert 'profile has been updated' in resp.get_data(as_text=True)
    user = User.query.filter_by(email='new@test.com').one()
    assert user.username == 'newname'


def test_duplicate_username_rejected(app, renter_client):
    resp = renter_client.post('/account', data={'username': 'landlord', 'email': 'renter@test.com'},
                              follow_redirects=True)
    assert 'already taken' in resp.get_data(as_text=True)
    assert User.query.filter_by(email='renter@test.com').one().username == 'renter'


def test_duplicate_email_rejected(app, renter_client):
    resp = renter_client.post('/account', data={'username': 'renter', 'email': 'landlord@test.com'},
                              follow_redirects=True)
    assert 'already registered' in resp.get_data(as_text=True)


def change_password(client, current, new, confirm=None):
    return client.post('/account/password', follow_redirects=True, data={
        'current_password': current, 'new_password': new,
        'confirm_password': new if confirm is None else confirm,
    }).get_data(as_text=True)


def test_change_password_wrong_current(app, renter_client):
    assert 'current password is incorrect' in change_password(renter_client, 'nope', 'newpass1')


def test_change_password_too_short(app, renter_client):
    assert 'at least 6 characters' in change_password(renter_client, 'pw123', 'abc')


def test_change_password_mismatch(app, renter_client):
    assert "passwords don" in change_password(renter_client, 'pw123', 'newpass1', 'newpass2')


def test_change_password_success(app, client):
    login(client, 'renter@test.com')
    assert 'password has been changed' in change_password(client, 'pw123', 'newpass1')
    client.get('/logout')
    assert login(client, 'renter@test.com', 'pw123').status_code == 200  # old password fails
    assert login(client, 'renter@test.com', 'newpass1').status_code == 302


def test_account_shows_recent_conversations(app, renter_client):
    landlord = User.query.filter_by(role='Landlord').one()
    renter_client.post(f'/message/{landlord.id}', data={'content': 'General question'})
    html = renter_client.get('/account').get_data(as_text=True)
    assert 'General question' in html
    assert 'General message' in html

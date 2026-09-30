from conftest import login
from models import Message, Property, User


def ids():
    landlord = User.query.filter_by(role='Landlord').one()
    flat = Property.query.filter_by(title='Cozy flat').one()
    house = Property.query.filter_by(title='Family house').one()
    return landlord, flat, house


def test_renter_sees_thread_they_started(app, renter_client):
    landlord, flat, _ = ids()
    resp = renter_client.post(f'/message/{landlord.id}?property_id={flat.id}', data={'content': 'Is it free?'})
    assert resp.status_code == 302
    assert f'property_id={flat.id}' in resp.headers['Location']

    html = renter_client.get('/inbox').get_data(as_text=True)
    assert 'Is it free?' in html
    assert 'Cozy flat' in html


def test_threads_are_split_by_property(app, client):
    landlord, flat, house = ids()
    login(client, 'renter@test.com')
    client.post(f'/message/{landlord.id}?property_id={flat.id}', data={'content': 'About the flat'})
    client.post(f'/message/{landlord.id}?property_id={house.id}', data={'content': 'About the house'})
    client.get('/logout')

    login(client, 'landlord@test.com')
    html = client.get('/inbox').get_data(as_text=True)
    assert 'About the flat' in html and 'About the house' in html

    filtered = client.get(f'/inbox?property_id={flat.id}').get_data(as_text=True)
    assert 'About the flat' in filtered
    assert 'About the house' not in filtered

    thread = client.get(f'/conversation/{User.query.filter_by(role="Renter").one().id}?property_id={flat.id}')
    thread_html = thread.get_data(as_text=True)
    assert 'About the flat' in thread_html
    assert 'About the house' not in thread_html


def test_reply_stays_in_property_thread(app, client):
    landlord, flat, _ = ids()
    renter = User.query.filter_by(role='Renter').one()
    login(client, 'renter@test.com')
    client.post(f'/message/{landlord.id}?property_id={flat.id}', data={'content': 'Hello'})
    client.get('/logout')

    login(client, 'landlord@test.com')
    resp = client.post(f'/send_reply/{renter.id}', data={'content': 'Yes, available', 'property_id': flat.id})
    assert f'property_id={flat.id}' in resp.headers['Location']
    reply = Message.query.filter_by(content='Yes, available').one()
    assert reply.property_id == flat.id


def test_opening_thread_marks_only_that_thread_read(app, client):
    landlord, flat, house = ids()
    renter = User.query.filter_by(role='Renter').one()
    login(client, 'renter@test.com')
    client.post(f'/message/{landlord.id}?property_id={flat.id}', data={'content': 'flat q'})
    client.post(f'/message/{landlord.id}?property_id={house.id}', data={'content': 'house q'})
    client.get('/logout')

    login(client, 'landlord@test.com')
    client.get(f'/conversation/{renter.id}?property_id={flat.id}')
    assert Message.query.filter_by(content='flat q').one().read is True
    assert Message.query.filter_by(content='house q').one().read is False


def test_dashboard_shows_message_count_link(app, client):
    landlord, flat, _ = ids()
    login(client, 'renter@test.com')
    client.post(f'/message/{landlord.id}?property_id={flat.id}', data={'content': 'q1'})
    client.get('/logout')

    login(client, 'landlord@test.com')
    html = client.get('/dashboard').get_data(as_text=True)
    assert f'/inbox?property_id={flat.id}' in html


def test_empty_message_is_rejected(app, renter_client):
    landlord, flat, _ = ids()
    resp = renter_client.post(f'/message/{landlord.id}', data={'content': '   '})
    assert "be empty" in resp.get_data(as_text=True)
    assert Message.query.count() == 0


def test_cannot_message_yourself(app, renter_client):
    renter = User.query.filter_by(role='Renter').one()
    renter_client.post(f'/message/{renter.id}', data={'content': 'hi me'})
    assert Message.query.count() == 0

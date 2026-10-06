"""Email verification, password recovery and rate limits."""
import re
import smtplib
import pytest
from app import db
from conftest import login, make_user
from models import Message, Property, RateLimitHit, User
from security import make_reset_token, make_verify_token


def link_in(email):
    """The path of the link in an email the app sent."""
    return re.search(r'https?://[^/\s]+(/\S+)', email['body']).group(1)


def signup(client, username='newbie', role='Renter', password='secret1'):
    return client.post('/register', data={'username': username, 'email': f'{username}@test.com',
                                          'password': password, 'role': role})


def user(username):
    db.session.expire_all()
    return User.query.filter_by(username=username).one()


def listing_form(**overrides):
    data = {'title': 'Gated place', 'description': 'Nice', 'price': '4000',
            'location': 'Gaborone', 'bedrooms': '2', 'property_type': 'flat'}
    data.update(overrides)
    return data


# ---------- Verification emails ----------

def test_signup_sends_a_verification_email(app, client, outbox):
    signup(client)
    assert len(outbox) == 1
    assert outbox[0]['to'] == 'newbie@test.com'
    assert 'Confirm your email' in outbox[0]['subject']
    assert '/verify-email/' in outbox[0]['body']
    assert user('newbie').email_verified is False


def test_opening_the_link_verifies_the_account(app, client, outbox):
    signup(client)
    resp = client.get(link_in(outbox[0]), follow_redirects=True)
    assert 'Your email address is confirmed' in resp.get_data(as_text=True)
    assert user('newbie').email_verified is True


def test_link_can_be_opened_twice_without_harm(app, client, outbox):
    signup(client)
    client.get(link_in(outbox[0]))
    first = user('newbie').email_verified_at
    assert client.get(link_in(outbox[0])).status_code == 302
    assert user('newbie').email_verified_at == first


def test_expired_verification_link_is_refused(app, client, outbox):
    signup(client)
    app.config['VERIFY_TOKEN_MAX_AGE'] = -1
    resp = client.get(link_in(outbox[0]), follow_redirects=True)
    assert 'invalid or has expired' in resp.get_data(as_text=True)
    assert user('newbie').email_verified is False


@pytest.mark.parametrize('token', ['nonsense', 'a.b.c', ''])
def test_made_up_verification_link_is_refused(app, client, token):
    resp = client.get(f'/verify-email/{token}', follow_redirects=True)
    assert resp.status_code in (200, 404)
    assert 'Your email address is confirmed' not in resp.get_data(as_text=True)


def test_reset_link_cannot_be_used_to_verify(app, client):
    make_user('plain', 'Renter', verified=False)
    db.session.commit()
    token = make_reset_token(user('plain'))
    client.get(f'/verify-email/{token}')
    assert user('plain').email_verified is False


def test_link_stops_working_when_the_email_changes(app, client, outbox):
    signup(client)
    old_link = link_in(outbox[0])
    login(client, 'newbie@test.com', 'secret1')
    client.post('/account', data={'username': 'newbie', 'email': 'changed@test.com'})
    client.get(old_link)
    assert user('newbie').email_verified is False


def test_changing_email_needs_confirming_again(app, renter_client, outbox):
    assert user('renter').email_verified is True
    renter_client.post('/account', data={'username': 'renter', 'email': 'moved@test.com'})
    assert user('renter').email_verified is False
    assert outbox[-1]['to'] == 'moved@test.com'
    renter_client.get(link_in(outbox[-1]))
    assert user('renter').email_verified is True


def test_changing_only_the_username_keeps_verification(app, renter_client, outbox):
    renter_client.post('/account', data={'username': 'renamed', 'email': 'renter@test.com'})
    assert user('renamed').email_verified is True
    assert outbox == []


def test_resend_sends_another_email(app, client, outbox):
    signup(client)
    login(client, 'newbie@test.com', 'secret1')
    resp = client.post('/verify-email/resend', follow_redirects=True)
    assert "We&#39;ve sent a link" in resp.get_data(as_text=True)
    assert len(outbox) == 2


def test_resend_is_rate_limited(app, client, outbox):
    signup(client)
    login(client, 'newbie@test.com', 'secret1')
    for _ in range(6):
        client.post('/verify-email/resend')
    limit = app.config['RATE_LIMITS']['verify_resend'][0]
    assert len(outbox) == 1 + limit


def test_resend_needs_login(client, outbox):
    assert client.post('/verify-email/resend').status_code == 302
    assert outbox == []


def test_verified_account_gets_no_more_emails(app, renter_client, outbox):
    renter_client.post('/verify-email/resend')
    assert outbox == []


def test_account_page_explains_what_verification_means(app, client, outbox):
    signup(client, role='Landlord')
    login(client, 'newbie@test.com', 'secret1')
    html = client.get('/account').get_data(as_text=True)
    assert 'Confirm your email address' in html
    assert 'Not a verified landlord' in html           # the two kinds of verification are separate

    client.get(link_in(outbox[0]))
    html = client.get('/account').get_data(as_text=True)
    assert 'Email confirmed' in html
    assert 'This is not an identity check' in html
    assert 'Not a verified landlord' in html


# ---------- What an unverified account can and can't do ----------

@pytest.fixture
def unverified_landlord(app, client):
    make_user('fresh', 'Landlord', verified=False)
    db.session.commit()
    login(client, 'fresh@test.com')
    return client


@pytest.fixture
def unverified_renter(app, client):
    make_user('fresh', 'Renter', verified=False)
    db.session.commit()
    login(client, 'fresh@test.com')
    return client


def test_unverified_user_can_browse_and_manage_account(unverified_renter):
    for path in ('/', '/map', '/account', '/favorites', '/inbox'):
        assert unverified_renter.get(path).status_code == 200
    property = Property.query.first()
    assert unverified_renter.get(f'/property/{property.id}').status_code == 200
    assert unverified_renter.post(f'/favorite/{property.id}').get_json() == {'is_favorited': True}


def test_unverified_landlord_cannot_publish(unverified_landlord):
    resp = unverified_landlord.post('/property/new', data=listing_form(), content_type='multipart/form-data')
    assert 'Confirm your email address before publishing' in resp.get_data(as_text=True)
    assert Property.query.filter_by(title='Gated place').first() is None


def test_unverified_landlord_can_save_a_draft(unverified_landlord):
    resp = unverified_landlord.post('/property/new', data=listing_form(action='draft'),
                                    content_type='multipart/form-data')
    assert resp.status_code == 302
    property = Property.query.filter_by(title='Gated place').one()
    assert property.is_published is False


def test_unverified_landlord_cannot_publish_a_draft(unverified_landlord):
    unverified_landlord.post('/property/new', data=listing_form(action='draft'), content_type='multipart/form-data')
    property = Property.query.filter_by(title='Gated place').one()
    resp = unverified_landlord.post(f'/property/{property.id}/update', data=listing_form(action='publish'),
                                    content_type='multipart/form-data')
    assert 'Confirm your email address before publishing' in resp.get_data(as_text=True)
    assert db.session.get(Property, property.id).is_published is False


def test_draft_can_be_published_once_verified(unverified_landlord, outbox):
    unverified_landlord.post('/property/new', data=listing_form(action='draft'), content_type='multipart/form-data')
    property = Property.query.filter_by(title='Gated place').one()
    unverified_landlord.post('/verify-email/resend')
    unverified_landlord.get(link_in(outbox[-1]))
    unverified_landlord.post(f'/property/{property.id}/update', data=listing_form(action='publish'),
                             content_type='multipart/form-data')
    db.session.expire_all()
    assert db.session.get(Property, property.id).is_published is True


def test_existing_live_listing_stays_live_for_an_unverified_owner(app, client):
    # An account from before verification existed: its listings were already public
    landlord = user('landlord')
    landlord.email_verified_at = None
    db.session.commit()
    login(client, 'landlord@test.com')
    property = Property.query.filter_by(title='Cozy flat').one()
    resp = client.post(f'/property/{property.id}/update', content_type='multipart/form-data',
                       data=listing_form(title='Cozy flat', price='3600'))
    assert resp.status_code == 302
    db.session.expire_all()
    property = db.session.get(Property, property.id)
    assert property.is_published is True and property.price == 3600


def test_unverified_renter_cannot_start_a_conversation(unverified_renter):
    landlord = user('landlord')
    property = Property.query.first()
    resp = unverified_renter.post(f'/message/{landlord.id}?property_id={property.id}', data={'content': 'Hello'},
                                  follow_redirects=True)
    assert 'Please confirm your email address first' in resp.get_data(as_text=True)
    assert Message.query.count() == 0


def test_unverified_renter_cannot_start_one_through_the_reply_route(unverified_renter):
    landlord = user('landlord')
    unverified_renter.post(f'/send_reply/{landlord.id}', data={'content': 'Sneaky'}, follow_redirects=True)
    assert Message.query.count() == 0


def test_unverified_user_can_reply_in_an_existing_conversation(unverified_renter):
    landlord, fresh = user('landlord'), user('fresh')
    property = Property.query.first()
    db.session.add(Message(sender_id=landlord.id, recipient_id=fresh.id, property_id=property.id, content='Hi'))
    db.session.commit()
    unverified_renter.post(f'/send_reply/{landlord.id}', data={'content': 'Thanks', 'property_id': property.id})
    assert Message.query.filter_by(content='Thanks').count() == 1


def test_unverified_user_sees_how_to_confirm(unverified_renter):
    html = unverified_renter.get('/').get_data(as_text=True)
    assert 'Confirm your email address' in html
    property = Property.query.first()
    assert 'Confirm your email address to message this landlord' in \
        unverified_renter.get(f'/property/{property.id}').get_data(as_text=True)


# ---------- Password recovery ----------

GENERIC = 'If an account exists for that address'


def test_reset_email_is_sent_for_a_real_account(app, client, outbox):
    resp = client.post('/forgot-password', data={'email': 'renter@test.com'}, follow_redirects=True)
    assert GENERIC in resp.get_data(as_text=True)
    assert len(outbox) == 1 and outbox[0]['to'] == 'renter@test.com'
    assert '/reset-password/' in outbox[0]['body']


def test_unknown_address_gets_the_same_answer_and_no_email(app, client, outbox):
    known = client.post('/forgot-password', data={'email': 'renter@test.com'}, follow_redirects=True)
    unknown = client.post('/forgot-password', data={'email': 'nobody@test.com'}, follow_redirects=True)
    assert known.status_code == unknown.status_code == 200
    assert GENERIC in unknown.get_data(as_text=True)
    assert [email['to'] for email in outbox] == ['renter@test.com']

    strip = lambda html: re.sub(r'name="csrf[^>]*>|content="[^"]*"', '', html)
    assert strip(known.get_data(as_text=True)) == strip(unknown.get_data(as_text=True))


def test_reset_changes_the_password(app, client, outbox):
    client.post('/forgot-password', data={'email': 'renter@test.com'})
    path = link_in(outbox[0])
    assert client.get(path).status_code == 200
    resp = client.post(path, data={'new_password': 'brandnew1', 'confirm_password': 'brandnew1'}, follow_redirects=True)
    assert 'Your password has been changed' in resp.get_data(as_text=True)
    assert login(client, 'renter@test.com', 'pw123').status_code == 200     # old password no longer works
    assert login(client, 'renter@test.com', 'brandnew1').status_code == 302


def test_reset_link_works_only_once(app, client, outbox):
    client.post('/forgot-password', data={'email': 'renter@test.com'})
    path = link_in(outbox[0])
    client.post(path, data={'new_password': 'brandnew1', 'confirm_password': 'brandnew1'})

    resp = client.get(path, follow_redirects=True)
    assert 'already been used' in resp.get_data(as_text=True)
    client.post(path, data={'new_password': 'hijacked1', 'confirm_password': 'hijacked1'})
    assert user('renter').check_password('brandnew1')


def test_expired_reset_link_is_refused(app, client, outbox):
    client.post('/forgot-password', data={'email': 'renter@test.com'})
    app.config['RESET_TOKEN_MAX_AGE'] = -1
    resp = client.post(link_in(outbox[0]), data={'new_password': 'brandnew1', 'confirm_password': 'brandnew1'},
                       follow_redirects=True)
    assert 'invalid, has expired' in resp.get_data(as_text=True)
    assert user('renter').check_password('pw123')


def test_older_reset_link_dies_when_the_password_changes_another_way(app, client, outbox):
    client.post('/forgot-password', data={'email': 'renter@test.com'})
    path = link_in(outbox[0])
    login(client, 'renter@test.com')
    client.post('/account/password', data={'current_password': 'pw123', 'new_password': 'changed1',
                                           'confirm_password': 'changed1'})
    client.get('/logout')
    client.post(path, data={'new_password': 'hijacked1', 'confirm_password': 'hijacked1'})
    assert user('renter').check_password('changed1')


@pytest.mark.parametrize('token', ['nonsense', 'a.b.c'])
def test_made_up_reset_link_is_refused(app, client, token):
    resp = client.post(f'/reset-password/{token}', data={'new_password': 'brandnew1', 'confirm_password': 'brandnew1'})
    assert resp.status_code == 302 and '/forgot-password' in resp.headers['Location']


def test_verification_link_cannot_reset_a_password(app, client):
    token = make_verify_token(user('renter'))
    client.post(f'/reset-password/{token}', data={'new_password': 'hijacked1', 'confirm_password': 'hijacked1'})
    assert user('renter').check_password('pw123')


@pytest.mark.parametrize('new, confirm, message', [
    ('abc', 'abc', 'at least 6 characters'),
    ('x' * 200, 'x' * 200, '128 characters or fewer'),
    ('brandnew1', 'different1', 'match'),
])
def test_reset_validates_the_new_password(app, client, outbox, new, confirm, message):
    client.post('/forgot-password', data={'email': 'renter@test.com'})
    resp = client.post(link_in(outbox[0]), data={'new_password': new, 'confirm_password': confirm})
    assert message in resp.get_data(as_text=True)
    assert user('renter').check_password('pw123')


def test_password_rules_are_the_same_everywhere(app, client, renter_client):
    too_long = 'x' * 200
    resp = renter_client.post('/account/password', follow_redirects=True, data={
        'current_password': 'pw123', 'new_password': too_long, 'confirm_password': too_long})
    assert '128 characters or fewer' in resp.get_data(as_text=True)
    renter_client.get('/logout')
    assert '128 characters or fewer' in signup(client, password=too_long).get_data(as_text=True)


def test_resetting_by_email_confirms_the_address(app, client, outbox):
    make_user('late', 'Renter', verified=False)
    db.session.commit()
    client.post('/forgot-password', data={'email': 'late@test.com'})
    client.post(link_in(outbox[0]), data={'new_password': 'brandnew1', 'confirm_password': 'brandnew1'})
    assert user('late').email_verified is True


def test_reset_form_needs_a_csrf_token(app, outbox):
    app.config['WTF_CSRF_ENABLED'] = True
    client = app.test_client()
    resp = client.post('/forgot-password', data={'email': 'renter@test.com'})
    assert resp.status_code == 302
    assert outbox == []


# ---------- Sessions ----------

def test_changing_password_keeps_this_session_and_ends_others(app):
    here, elsewhere = app.test_client(), app.test_client()
    login(here, 'renter@test.com')
    login(elsewhere, 'renter@test.com')
    here.post('/account/password', data={'current_password': 'pw123', 'new_password': 'changed1',
                                         'confirm_password': 'changed1'})
    assert here.get('/account').status_code == 200
    assert elsewhere.get('/account').status_code == 302


def test_password_reset_ends_existing_sessions(app, client, outbox):
    thief = app.test_client()
    login(thief, 'renter@test.com')
    client.post('/forgot-password', data={'email': 'renter@test.com'})
    client.post(link_in(outbox[0]), data={'new_password': 'brandnew1', 'confirm_password': 'brandnew1'})
    assert thief.get('/account').status_code == 302


# ---------- Rate limits ----------

def test_login_locks_after_repeated_failures(app, client):
    limit = app.config['RATE_LIMITS']['login_email'][0]
    for _ in range(limit):
        assert login(client, 'renter@test.com', 'wrong').status_code == 200
    resp = login(client, 'renter@test.com', 'pw123')        # even the right password is refused now
    assert resp.status_code == 429
    assert 'Too many login attempts' in resp.get_data(as_text=True)


def test_login_limit_is_per_account(app, client):
    for _ in range(app.config['RATE_LIMITS']['login_email'][0]):
        login(client, 'renter@test.com', 'wrong')
    assert login(client, 'landlord@test.com').status_code == 302


def test_login_limit_per_address_catches_guessing_many_accounts(app, client):
    app.config['RATE_LIMITS'] = {**app.config['RATE_LIMITS'], 'login_ip': (4, 900)}
    for i in range(4):
        login(client, f'guess{i}@test.com', 'wrong')
    assert login(client, 'renter@test.com').status_code == 429


def test_successful_login_clears_the_count(app, client):
    limit = app.config['RATE_LIMITS']['login_email'][0]
    for _ in range(limit - 1):
        login(client, 'renter@test.com', 'wrong')
    assert login(client, 'renter@test.com').status_code == 302
    client.get('/logout')
    for _ in range(limit - 1):
        login(client, 'renter@test.com', 'wrong')
    assert login(client, 'renter@test.com').status_code == 302


def test_limit_lifts_after_the_window(app, client):
    from datetime import timedelta
    for _ in range(app.config['RATE_LIMITS']['login_email'][0]):
        login(client, 'renter@test.com', 'wrong')
    assert login(client, 'renter@test.com').status_code == 429
    for hit in RateLimitHit.query.all():
        hit.created_at -= timedelta(minutes=16)
    db.session.commit()
    assert login(client, 'renter@test.com').status_code == 302


def test_reset_requests_are_rate_limited_without_changing_the_answer(app, client, outbox):
    limit = app.config['RATE_LIMITS']['reset_email'][0]
    for _ in range(limit + 3):
        resp = client.post('/forgot-password', data={'email': 'renter@test.com'}, follow_redirects=True)
        assert GENERIC in resp.get_data(as_text=True)
    assert len(outbox) == limit


def test_rate_limit_table_holds_no_readable_details(app, client):
    login(client, 'renter@test.com', 'wrong')
    for hit in RateLimitHit.query.all():
        assert 'renter' not in hit.bucket and '127.0.0.1' not in hit.bucket


# ---------- Email delivery ----------

def test_nothing_is_sent_when_email_is_not_configured(app, client, outbox):
    app.config['MAIL_BACKEND'] = 'disabled'
    resp = signup(client)
    assert resp.status_code == 302
    assert outbox == []
    html = client.get('/login').get_data(as_text=True)
    assert "Email isn&#39;t set up on this server yet" in html
    assert "isn't available on this server yet" in client.get('/forgot-password').get_data(as_text=True)


def test_smtp_backend_hands_the_message_to_the_server(app, client, monkeypatch):
    sent = []

    class FakeSMTP:
        def __init__(self, host, port, timeout=None):
            sent.append(('connect', host, port))
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def starttls(self): sent.append(('starttls',))
        def login(self, username, password): sent.append(('login', username))
        def send_message(self, message): sent.append(('send', message['To'], message['Subject'], message.get_content()))

    monkeypatch.setattr(smtplib, 'SMTP', FakeSMTP)
    app.config.update(MAIL_BACKEND='smtp', MAIL_SERVER='smtp.test', MAIL_PORT=587, MAIL_USERNAME='mailer',
                      MAIL_PASSWORD='secret', MAIL_USE_TLS=True, MAIL_USE_SSL=False)
    client.post('/forgot-password', data={'email': 'renter@test.com'})
    assert sent[0] == ('connect', 'smtp.test', 587)
    assert ('starttls',) in sent and ('login', 'mailer') in sent
    send = sent[-1]
    assert send[1] == 'renter@test.com' and '/reset-password/' in send[3]


def test_smtp_failure_is_handled_and_never_logs_the_link(app, client, monkeypatch, caplog):
    def broken(*args, **kwargs):
        raise smtplib.SMTPException('server said no')
    monkeypatch.setattr(smtplib, 'SMTP', broken)
    app.config.update(MAIL_BACKEND='smtp', MAIL_SERVER='smtp.test')
    resp = client.post('/forgot-password', data={'email': 'renter@test.com'}, follow_redirects=True)
    assert resp.status_code == 200 and GENERIC in resp.get_data(as_text=True)
    assert '/reset-password/' not in caplog.text


def test_emailed_links_use_the_public_address_when_set(app, client, outbox):
    app.config['PUBLIC_BASE_URL'] = 'https://rentme.example'
    client.post('/forgot-password', data={'email': 'renter@test.com'})
    assert 'https://rentme.example/reset-password/' in outbox[0]['body']


def test_production_never_uses_the_development_mailbox(monkeypatch):
    import importlib
    import config
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('MAIL_BACKEND', 'file')
    try:
        assert importlib.reload(config).Config.MAIL_BACKEND == 'disabled'
        monkeypatch.delenv('MAIL_BACKEND')
        assert importlib.reload(config).Config.MAIL_BACKEND == 'disabled'
        monkeypatch.setenv('MAIL_SERVER', 'smtp.example.com')
        assert importlib.reload(config).Config.MAIL_BACKEND == 'smtp'
        assert importlib.reload(config).Config.SESSION_COOKIE_SECURE is True
    finally:
        monkeypatch.undo()
        importlib.reload(config)


def test_development_mailbox(app, client, tmp_path):
    app.config.update(MAIL_BACKEND='file', MAIL_OUTBOX_DIR=str(tmp_path / 'outbox'))
    client.post('/forgot-password', data={'email': 'renter@test.com'})
    html = client.get('/dev/mailbox').get_data(as_text=True)
    assert 'Choose a new Rent Me password' in html and 'renter@test.com' in html
    link = re.search(r'href="(http[^"]*/reset-password/[^"]+)"', html).group(1)
    assert client.get(re.sub(r'^https?://[^/]+', '', link)).status_code == 200


def test_development_mailbox_is_not_available_elsewhere(app, client, tmp_path):
    app.config.update(MAIL_BACKEND='file', MAIL_OUTBOX_DIR=str(tmp_path / 'outbox'))
    # From another computer
    assert client.get('/dev/mailbox', environ_base={'REMOTE_ADDR': '192.168.1.50'}).status_code == 404
    # On a live site
    app.config['IS_DEVELOPMENT'] = False
    assert client.get('/dev/mailbox').status_code == 404
    app.config.update(IS_DEVELOPMENT=True, MAIL_BACKEND='smtp')
    assert client.get('/dev/mailbox').status_code == 404

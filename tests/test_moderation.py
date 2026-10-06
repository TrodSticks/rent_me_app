"""Reporting listings, the admin queue, hiding listings, landlord verification and admin access."""
import json
import re
import pytest
from app import db
from conftest import login, make_user
from models import Property, Report, User

BOTSWANA = '-27,19.9,-17.5,29.5'


@pytest.fixture
def admin_client(app):
    make_user('boss', 'Renter', admin=True)
    db.session.commit()
    client = app.test_client()
    login(client, 'boss@test.com')
    return client


def get(title):
    db.session.expire_all()
    return Property.query.filter_by(title=title).one()


def user(username):
    db.session.expire_all()
    return User.query.filter_by(username=username).one()


def report(client, title='Family house', reason='scam', notes=''):
    return client.post(f'/property/{get(title).id}/report', data={'reason': reason, 'notes': notes},
                       follow_redirects=True)


def home_titles(client):
    return set(re.findall(r'<h5 class="card-title">(.*?)</h5>', client.get('/').get_data(as_text=True)))


def map_titles(client):
    return {pin['title'] for pin in client.get(f'/api/map-pins?bbox={BOTSWANA}').get_json()['pins']}


# ---------- Reporting ----------

def test_renter_can_report_a_listing(app, renter_client):
    resp = report(renter_client, reason='misleading', notes='The photos are of a different house.')
    assert 'Your report has been sent' in resp.get_data(as_text=True)
    saved = Report.query.one()
    assert saved.reason == 'misleading' and saved.status == 'open'
    assert saved.notes == 'The photos are of a different house.'
    assert saved.reporter.username == 'renter'


def test_notes_are_optional(app, renter_client):
    report(renter_client)
    assert Report.query.one().notes is None


def test_report_needs_login(app, client):
    resp = client.post(f"/property/{get('Family house').id}/report", data={'reason': 'scam'})
    assert resp.status_code == 302 and '/login' in resp.headers['Location']
    assert Report.query.count() == 0


@pytest.mark.parametrize('reason', ['', 'because', '<script>'])
def test_report_needs_a_real_reason(app, renter_client, reason):
    resp = report(renter_client, reason=reason)
    assert 'choose a reason' in resp.get_data(as_text=True)
    assert Report.query.count() == 0


def test_overlong_notes_are_rejected(app, renter_client):
    report(renter_client, notes='x' * 1001)
    assert Report.query.count() == 0


def test_cannot_report_own_listing(app, landlord_client):
    resp = report(landlord_client)
    assert "report your own listing" in resp.get_data(as_text=True)
    assert Report.query.count() == 0


def test_same_person_cannot_pile_reports_on_one_listing(app, renter_client):
    report(renter_client)
    resp = report(renter_client, reason='already_rented')
    assert "already reported this listing" in resp.get_data(as_text=True)
    assert Report.query.count() == 1


def test_reports_are_rate_limited(app, renter_client):
    app.config['RATE_LIMITS'] = {**app.config['RATE_LIMITS'], 'report': (2, 3600)}
    report(renter_client, 'Family house')
    report(renter_client, 'Small house')
    resp = report(renter_client, 'Big villa')
    assert 'several reports recently' in resp.get_data(as_text=True)
    assert Report.query.count() == 2


def test_cannot_report_a_listing_you_cannot_see(app, renter_client):
    property = get('Family house')
    property.is_published = False
    db.session.commit()
    assert renter_client.post(f'/property/{property.id}/report', data={'reason': 'scam'}).status_code == 404


def test_report_form_is_offered_on_the_property_page(app, client):
    property = get('Family house')
    assert 'Log in to report this listing' in client.get(f'/property/{property.id}').get_data(as_text=True)
    login(client, 'renter@test.com')
    html = client.get(f'/property/{property.id}').get_data(as_text=True)
    assert 'Report this listing' in html and 'Suspected scam' in html and 'Already rented' in html
    report(client)
    assert "You&#39;ve reported this listing" in client.get(f'/property/{property.id}').get_data(as_text=True) \
        or "You've reported this listing" in client.get(f'/property/{property.id}').get_data(as_text=True)


# ---------- Admin access ----------

ADMIN_PAGES = ['/admin', '/admin/reports', '/admin/reports?status=resolved', '/admin/landlords']


@pytest.mark.parametrize('path', ADMIN_PAGES)
def test_admin_pages_need_login(app, client, path):
    resp = client.get(path)
    assert resp.status_code == 302 and '/login' in resp.headers['Location']


@pytest.mark.parametrize('path', ADMIN_PAGES)
def test_admin_pages_refuse_ordinary_accounts(app, client, path):
    for email in ('renter@test.com', 'landlord@test.com'):
        login(client, email)
        assert client.get(path).status_code == 403
        client.get('/logout')


@pytest.mark.parametrize('path', ADMIN_PAGES)
def test_admin_pages_open_for_admins(admin_client, path):
    assert admin_client.get(path, follow_redirects=True).status_code == 200


def test_admin_actions_refuse_ordinary_accounts(app, renter_client):
    landlord, property = user('landlord'), get('Family house')
    db.session.add(Report(property_id=property.id, reporter_id=user('renter').id, reason='scam'))
    db.session.commit()
    report_id = Report.query.one().id

    for path, data in [
        (f'/admin/reports/{report_id}/resolve', {'outcome': 'listing_hidden'}),
        (f'/admin/listings/{property.id}/hide', {'reason': 'because'}),
        (f'/admin/listings/{property.id}/restore', {}),
        (f'/admin/landlords/{landlord.id}/verify', {}),
        (f'/admin/landlords/{landlord.id}/revoke', {}),
    ]:
        assert renter_client.post(path, data=data).status_code == 403

    assert get('Family house').is_hidden is False
    assert user('landlord').landlord_verified is False
    assert Report.query.one().status == 'open'


def test_nobody_can_make_themselves_admin_through_the_site(app, client):
    # Signing up with extra fields
    client.post('/register', data={'username': 'sneaky', 'email': 'sneaky@test.com', 'password': 'secret1',
                                   'role': 'Renter', 'is_admin': '1', 'admin': 'true'})
    assert user('sneaky').is_admin is False
    # Asking for a role that doesn't exist
    resp = client.post('/register', data={'username': 'sneaky2', 'email': 'sneaky2@test.com',
                                          'password': 'secret1', 'role': 'Admin'})
    assert User.query.filter_by(username='sneaky2').first() is None
    # Editing the profile with extra fields
    login(client, 'sneaky@test.com', 'secret1')
    client.post('/account', data={'username': 'sneaky', 'email': 'sneaky@test.com', 'is_admin': '1',
                                  'role': 'Landlord', 'landlord_verified_at': '2026-01-01'})
    sneaky = user('sneaky')
    assert sneaky.is_admin is False and sneaky.role == 'Renter' and sneaky.landlord_verified_at is None
    assert client.get('/admin/reports').status_code == 403


def test_admin_link_only_shown_to_admins(app, renter_client, admin_client):
    assert '/admin/reports' not in renter_client.get('/').get_data(as_text=True)
    assert '/admin/reports' in admin_client.get('/').get_data(as_text=True)


def test_admin_actions_need_a_csrf_token(app, admin_client):
    app.config['WTF_CSRF_ENABLED'] = True
    property = get('Family house')
    admin_client.post(f'/admin/listings/{property.id}/hide', data={'reason': 'x'})
    assert get('Family house').is_hidden is False


# ---------- The admin command ----------

def test_make_admin_command(app):
    runner = app.test_cli_runner()
    result = runner.invoke(args=['make-admin', 'RENTER@test.com'])
    assert result.exit_code == 0 and 'is now an administrator' in result.output
    assert user('renter').is_admin is True

    assert 'already an administrator' in runner.invoke(args=['make-admin', 'renter@test.com']).output
    assert 'renter@test.com' in runner.invoke(args=['list-admins']).output

    runner.invoke(args=['revoke-admin', 'renter@test.com'])
    assert user('renter').is_admin is False


def test_make_admin_needs_an_existing_account(app):
    result = app.test_cli_runner().invoke(args=['make-admin', 'nobody@test.com'])
    assert result.exit_code != 0 and 'No account with the email' in result.output
    assert User.query.filter_by(is_admin=True).count() == 0


# ---------- The report queue ----------

def test_queue_lists_open_reports(app, renter_client, admin_client):
    report(renter_client, notes='Asked for a deposit by mobile money before a viewing.')
    html = admin_client.get('/admin/reports').get_data(as_text=True)
    assert 'Family house' in html and 'Suspected scam' in html
    assert 'Asked for a deposit by mobile money' in html and 'renter' in html


def test_resolving_records_who_when_and_what(app, renter_client, admin_client):
    report(renter_client)
    report_id = Report.query.one().id
    admin_client.post(f'/admin/reports/{report_id}/resolve', data={'outcome': 'no_action', 'notes': 'Looks genuine.'})
    saved = db.session.get(Report, report_id)
    db.session.refresh(saved)
    assert saved.status == 'resolved' and saved.outcome == 'no_action'
    assert saved.resolution_notes == 'Looks genuine.'
    assert saved.resolved_by.username == 'boss' and saved.resolved_at is not None
    assert get('Family house').is_hidden is False

    assert 'Family house' not in admin_client.get('/admin/reports').get_data(as_text=True).split('Hidden listings')[0]
    resolved = admin_client.get('/admin/reports?status=resolved').get_data(as_text=True)
    assert 'No action needed' in resolved and 'Looks genuine.' in resolved and 'boss' in resolved


def test_resolving_needs_a_valid_outcome(app, renter_client, admin_client):
    report(renter_client)
    report_id = Report.query.one().id
    admin_client.post(f'/admin/reports/{report_id}/resolve', data={'outcome': 'whatever'})
    db.session.expire_all()
    assert Report.query.one().status == 'open'


def test_resolved_report_cannot_be_resolved_again(app, renter_client, admin_client):
    report(renter_client)
    report_id = Report.query.one().id
    admin_client.post(f'/admin/reports/{report_id}/resolve', data={'outcome': 'no_action'})
    admin_client.post(f'/admin/reports/{report_id}/resolve', data={'outcome': 'listing_hidden'})
    db.session.expire_all()
    assert Report.query.one().outcome == 'no_action'
    assert get('Family house').is_hidden is False


def test_reporter_can_report_again_after_resolution(app, renter_client, admin_client):
    report(renter_client)
    admin_client.post(f'/admin/reports/{Report.query.one().id}/resolve', data={'outcome': 'no_action'})
    report(renter_client, reason='already_rented')
    assert Report.query.count() == 2


# ---------- Hiding and restoring ----------

def hide(admin_client, title='Family house'):
    return admin_client.post(f'/admin/listings/{get(title).id}/hide', data={'reason': 'Suspected scam'})


def test_hiding_through_a_report(app, renter_client, admin_client):
    report(renter_client)
    admin_client.post(f'/admin/reports/{Report.query.one().id}/resolve',
                      data={'outcome': 'listing_hidden', 'notes': 'Stolen photos.'})
    property = get('Family house')
    assert property.is_hidden is True
    assert property.hidden_by.username == 'boss' and property.hidden_at is not None
    assert property.hidden_reason == 'Stolen photos.'


def test_hidden_listing_disappears_everywhere_public(app, client, admin_client):
    assert 'Family house' in home_titles(client)
    hide(admin_client)

    assert 'Family house' not in home_titles(client)
    assert 'Family house' not in map_titles(client)
    html = client.get('/map').get_data(as_text=True)
    towns = json.loads(re.search(r'<script id="map-data" type="application/json">(.*?)</script>', html, re.S).group(1))['towns']
    assert {t['name']: t['count'] for t in towns}['Gaborone'] == 1
    similar = client.get(f"/property/{get('Small house').id}").get_data(as_text=True)
    assert 'Family house' not in re.findall(r'similar-title">(.*?)</h5>', similar)
    assert client.get(f"/property/{get('Family house').id}").status_code == 404
    assert client.get(f"/map?focus={get('Family house').id}").status_code == 200
    assert 'Family house' not in client.get(f"/map?focus={get('Family house').id}").get_data(as_text=True)


def test_hidden_listing_leaves_favourites_and_cannot_be_saved(app, renter_client, admin_client):
    property = get('Family house')
    renter_client.post(f'/favorite/{property.id}')
    assert 'Family house' in renter_client.get('/favorites').get_data(as_text=True)
    hide(admin_client)
    assert 'Family house' not in renter_client.get('/favorites').get_data(as_text=True)
    assert renter_client.post(f"/favorite/{get('Small house').id}").status_code == 200
    hide(admin_client, 'Small house')
    assert renter_client.post(f"/favorite/{get('Small house').id}").status_code == 404


def test_owner_and_admin_can_still_open_a_hidden_listing(app, landlord_client, admin_client):
    hide(admin_client)
    property = get('Family house')
    for client in (landlord_client, admin_client):
        resp = client.get(f'/property/{property.id}')
        assert resp.status_code == 200
        assert 'Hidden by the Rent Me team' in resp.get_data(as_text=True)
    assert 'Hidden by Rent Me' in landlord_client.get('/dashboard').get_data(as_text=True)


def test_owner_cannot_unhide_by_editing(app, landlord_client, admin_client):
    hide(admin_client)
    property = get('Family house')
    landlord_client.post(f'/property/{property.id}/update', content_type='multipart/form-data', data={
        'title': 'Family house', 'description': 'Big garden', 'price': '8000', 'location': 'Gaborone',
        'bedrooms': '3', 'property_type': 'house', 'action': 'publish', 'status': 'available',
        'is_hidden': '0', 'hidden': 'false'})
    assert get('Family house').is_hidden is True
    assert 'Family house' not in home_titles(landlord_client)


def test_restoring_brings_a_listing_back(app, client, admin_client):
    hide(admin_client)
    assert 'Family house' in admin_client.get('/admin/reports').get_data(as_text=True)
    admin_client.post(f"/admin/listings/{get('Family house').id}/restore")
    property = get('Family house')
    assert property.is_hidden is False and property.hidden_at is None and property.hidden_reason is None
    assert 'Family house' in home_titles(client)
    assert 'Family house' in map_titles(client)


# ---------- Landlord verification ----------

def test_admin_grants_and_records_landlord_verification(app, admin_client):
    landlord = user('landlord')
    assert landlord.landlord_verified is False
    admin_client.post(f'/admin/landlords/{landlord.id}/verify')
    landlord = user('landlord')
    assert landlord.landlord_verified is True
    assert landlord.landlord_verified_by.username == 'boss' and landlord.landlord_verified_at is not None

    html = admin_client.get('/admin/landlords').get_data(as_text=True)
    assert 'Verified' in html and 'by boss' in html


def test_admin_can_revoke_landlord_verification(app, admin_client):
    landlord = user('landlord')
    admin_client.post(f'/admin/landlords/{landlord.id}/verify')
    admin_client.post(f'/admin/landlords/{landlord.id}/revoke')
    landlord = user('landlord')
    assert landlord.landlord_verified is False and landlord.landlord_verified_by_id is None


def test_only_landlords_can_be_verified(app, admin_client):
    renter = user('renter')
    resp = admin_client.post(f'/admin/landlords/{renter.id}/verify', follow_redirects=True)
    assert 'Only landlord accounts' in resp.get_data(as_text=True)
    assert user('renter').landlord_verified_at is None


def test_badge_appears_on_listings_and_says_what_it_means(app, client, admin_client):
    property = get('Family house')
    assert 'Verified landlord' not in client.get(f'/property/{property.id}').get_data(as_text=True)

    admin_client.post(f"/admin/landlords/{user('landlord').id}/verify")
    html = client.get(f'/property/{property.id}').get_data(as_text=True)
    assert 'Verified landlord' in html
    assert 'A Rent Me administrator approved this landlord' in html
    assert 'does not collect identity or ownership documents' in html


def test_email_verification_alone_gives_no_landlord_badge(app, client):
    assert user('landlord').email_verified is True
    assert 'Verified landlord' not in client.get(f"/property/{get('Family house').id}").get_data(as_text=True)


def test_landlord_verification_does_not_verify_email(app, admin_client):
    make_user('fresh', 'Landlord', verified=False)
    db.session.commit()
    admin_client.post(f"/admin/landlords/{user('fresh').id}/verify")
    fresh = user('fresh')
    assert fresh.landlord_verified is True and fresh.email_verified is False


def test_landlord_search(app, admin_client):
    make_user('zanele', 'Landlord')
    db.session.commit()
    html = admin_client.get('/admin/landlords?q=zan').get_data(as_text=True)
    assert 'zanele@test.com' in html and 'landlord@test.com' not in html
    assert 'renter@test.com' not in admin_client.get('/admin/landlords').get_data(as_text=True)

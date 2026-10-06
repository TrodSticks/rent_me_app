import re
from datetime import date, timedelta
import pytest
from app import db
from conftest import login, make_user
from models import Favorite, Property, User

BOTSWANA = '-27,19.9,-17.5,29.5'


def property_form(**overrides):
    data = {'title': 'Detailed place', 'description': 'Nice', 'price': '4000',
            'location': 'Gaborone', 'bedrooms': '2', 'property_type': 'flat'}
    data.update(overrides)
    return data


def create(client, **fields):
    return client.post('/property/new', data=property_form(**fields), content_type='multipart/form-data')


def created():
    return Property.query.filter_by(title='Detailed place').first()


def home_titles(client, query=''):
    return set(re.findall(r'<h5 class="card-title">(.*?)</h5>', client.get('/' + query).get_data(as_text=True)))


def map_titles(client, query=''):
    return {pin['title'] for pin in client.get(f'/api/map-pins?bbox={BOTSWANA}{query}').get_json()['pins']}


def get(title):
    return Property.query.filter_by(title=title).one()


# ---------- Saving the new fields ----------

def test_all_details_are_saved(app, landlord_client):
    resp = create(landlord_client, status='reserved', available_from='2027-01-15', deposit='5000',
                  bathrooms='2', amenities=['parking', 'wifi', 'pet_friendly'])
    assert resp.status_code == 302
    property = created()
    assert property.status == 'reserved'
    assert property.available_from == date(2027, 1, 15)
    assert property.deposit == 5000
    assert property.bathrooms == 2
    assert property.amenities == ['parking', 'wifi', 'pet_friendly']


def test_optional_details_default_to_not_specified(app, landlord_client):
    create(landlord_client)
    property = created()
    assert property.status == 'available'
    assert property.available_from is None
    assert property.deposit is None
    assert property.bathrooms is None
    assert property.amenities == []


def test_zero_deposit_is_different_from_not_specified(app, landlord_client):
    create(landlord_client, deposit='0', bathrooms='0')
    property = created()
    assert property.deposit == 0
    assert property.bathrooms == 0

    html = landlord_client.get(f'/property/{property.id}').get_data(as_text=True)
    assert 'No deposit' in html
    assert 'Not specified' not in html

    edit = landlord_client.get(f'/property/{property.id}/update').get_data(as_text=True)
    assert re.search(r'name="deposit"[^>]*value="0"', edit, re.S)
    assert re.search(r'name="bathrooms"[^>]*value="0"', edit, re.S)


def test_unspecified_deposit_is_labelled(app, client):
    html = client.get(f"/property/{get('Cozy flat').id}").get_data(as_text=True)
    assert 'Not specified' in html
    assert 'Bathroom' not in html      # nothing invented for old listings


@pytest.mark.parametrize('field, value, message', [
    ('bathrooms', '-1', 'Bathrooms must be a whole number'),
    ('bathrooms', '1.5', 'Bathrooms must be a whole number'),
    ('bathrooms', 'two', 'Bathrooms must be a whole number'),
    ('bathrooms', '21', 'Bathrooms must be a whole number'),
    ('deposit', '-100', 'deposit must be a whole number'),
    ('deposit', 'lots', 'deposit must be a whole number'),
    ('available_from', 'next week', 'valid date'),
    ('available_from', '2027-13-45', 'valid date'),
    ('status', 'sold', 'available, reserved or rented'),
    ('price', '0', 'valid monthly price'),
    ('price', '99999999999', 'valid monthly price'),
])
def test_invalid_details_are_rejected(app, landlord_client, field, value, message):
    resp = create(landlord_client, **{field: value})
    assert message in resp.get_data(as_text=True)
    assert created() is None


def test_unknown_amenities_are_ignored(app, landlord_client):
    create(landlord_client, amenities=['parking', 'helipad', '<script>'])
    assert created().amenities == ['parking']


def test_rejected_form_keeps_details(app, landlord_client):
    html = create(landlord_client, price='abc', deposit='2500', bathrooms='3', status='reserved',
                  available_from='2027-02-01', amenities=['furnished']).get_data(as_text=True)
    assert re.search(r'name="deposit"[^>]*value="2500"', html, re.S)
    assert re.search(r'name="bathrooms"[^>]*value="3"', html, re.S)
    assert 'value="2027-02-01"' in html
    assert '<option value="reserved" selected>' in html
    assert re.search(r'value="furnished" id="amenity-furnished" checked', html)


def test_editing_changes_amenities(app, landlord_client):
    create(landlord_client, amenities=['parking', 'wifi'])
    property = created()
    landlord_client.post(f'/property/{property.id}/update', content_type='multipart/form-data',
                         data=property_form(amenities=['wifi', 'security']))
    db.session.expire_all()
    assert created().amenities == ['wifi', 'security']


def test_detail_page_shows_rent_deposit_availability_and_amenities(app, landlord_client):
    soon = (date.today() + timedelta(days=30))
    create(landlord_client, deposit='4000', available_from=soon.isoformat(), bathrooms='1',
           amenities=['air_conditioning', 'water_included'])
    html = landlord_client.get(f'/property/{created().id}').get_data(as_text=True)
    assert 'Monthly rent' in html and 'P4,000' in html
    assert 'Security deposit' in html
    assert f"From {soon.strftime('%d %b %Y')}" in html
    assert 'Air conditioning' in html and 'Water included' in html
    assert 'Bathroom' in html


def test_past_available_date_reads_as_available_now(app, landlord_client):
    create(landlord_client, available_from='2020-01-01')
    assert 'Available now' in landlord_client.get(f'/property/{created().id}').get_data(as_text=True)


# ---------- Availability in public results ----------

@pytest.mark.parametrize('status', ['reserved', 'rented'])
def test_unavailable_listings_leave_list_map_and_recommendations(app, client, status):
    get('Family house').status = status
    db.session.commit()

    assert 'Family house' not in home_titles(client)
    assert 'Family house' not in map_titles(client)
    towns = {t['name']: t['count'] for t in _towns(client)}
    assert towns['Gaborone'] == 1
    similar = client.get(f"/property/{get('Small house').id}").get_data(as_text=True)
    assert 'Family house' not in re.findall(r'similar-title">(.*?)</h5>', similar)


def _towns(client):
    import json
    html = client.get('/map').get_data(as_text=True)
    return json.loads(re.search(r'<script id="map-data" type="application/json">(.*?)</script>', html, re.S).group(1))['towns']


def test_unavailable_listing_is_still_reachable_and_labelled(app, client):
    property = get('Family house')
    property.status = 'rented'
    db.session.commit()
    resp = client.get(f'/property/{property.id}')
    assert resp.status_code == 200
    assert 'This property has been let' in resp.get_data(as_text=True)

    property.status = 'reserved'
    db.session.commit()
    assert 'Someone is in the process of renting' in client.get(f'/property/{property.id}').get_data(as_text=True)


def test_owner_sees_unavailable_listings_on_dashboard(app, landlord_client):
    get('Family house').status = 'rented'
    db.session.commit()
    html = landlord_client.get('/dashboard').get_data(as_text=True)
    assert 'Family house' in html
    assert 'rm-tag red">Rented' in html


def test_quick_status_change_from_dashboard(app, landlord_client):
    property = get('Family house')
    resp = landlord_client.post(f'/property/{property.id}/status', data={'status': 'rented'})
    assert resp.status_code == 302
    assert db.session.get(Property, property.id).status == 'rented'
    assert 'Family house' not in home_titles(landlord_client)

    landlord_client.post(f'/property/{property.id}/status', data={'status': 'nonsense'})
    assert db.session.get(Property, property.id).status == 'rented'


def test_only_the_owner_can_change_status(app, client):
    property = get('Family house')
    make_user('other', 'Landlord')
    db.session.commit()
    login(client, 'other@test.com')
    assert client.post(f'/property/{property.id}/status', data={'status': 'rented'}).status_code == 404
    assert db.session.get(Property, property.id).status == 'available'


def test_rented_listing_takes_no_new_enquiries(app, renter_client):
    property = get('Family house')
    property.status = 'rented'
    db.session.commit()
    resp = renter_client.get(f'/message/{property.landlord_id}?property_id={property.id}', follow_redirects=True)
    assert "isn&#39;t taking new enquiries" in resp.get_data(as_text=True)


def test_saved_favourite_stays_visible_once_rented(app, renter_client):
    property = get('Family house')
    renter = User.query.filter_by(username='renter').one()
    db.session.add(Favorite(user_id=renter.id, property_id=property.id))
    property.status = 'rented'
    db.session.commit()
    html = renter_client.get('/favorites').get_data(as_text=True)
    assert 'Family house' in html and 'Rented' in html


# ---------- Drafts ----------

def test_draft_is_hidden_from_everyone_but_its_owner(app, client):
    login(client, 'landlord@test.com')
    create(client, action='draft')
    property = created()
    assert property.is_published is False
    assert 'Detailed place' not in home_titles(client)
    assert 'Detailed place' not in map_titles(client)
    assert client.get(f'/property/{property.id}').status_code == 200       # owner
    assert 'Draft' in client.get('/dashboard').get_data(as_text=True)
    client.get('/logout')

    assert client.get(f'/property/{property.id}').status_code == 404       # visitor
    login(client, 'renter@test.com')
    assert client.get(f'/property/{property.id}').status_code == 404       # another account


def test_draft_can_be_published_later(app, landlord_client):
    create(landlord_client, action='draft')
    property = created()
    landlord_client.post(f'/property/{property.id}/update', content_type='multipart/form-data',
                         data=property_form(action='publish'))
    assert 'Detailed place' in home_titles(landlord_client)


def test_published_listing_can_be_unpublished(app, landlord_client):
    property = get('Family house')
    landlord_client.post(f'/property/{property.id}/update', content_type='multipart/form-data',
                         data=property_form(title='Family house', action='draft'))
    assert 'Family house' not in home_titles(landlord_client)


# ---------- Filters ----------

@pytest.fixture
def detailed(app):
    """Give the standard listings some details to filter on."""
    flat, family, small, villa = (get(t) for t in ('Cozy flat', 'Family house', 'Small house', 'Big villa'))
    flat.bathrooms, family.bathrooms, villa.bathrooms = 1, 2, 4      # Small house: not specified
    flat.set_amenities(['wifi', 'furnished'])
    family.set_amenities(['parking', 'wifi', 'security'])
    villa.set_amenities(['parking', 'wifi', 'security', 'air_conditioning', 'pet_friendly'])
    db.session.commit()


def test_bathroom_filter_is_a_minimum(detailed, client):
    assert home_titles(client, '?bathrooms=2') == {'Family house', 'Big villa'}
    assert home_titles(client, '?bathrooms=1') == {'Cozy flat', 'Family house', 'Big villa'}
    # A listing that doesn't say how many bathrooms it has can't match
    assert 'Small house' not in home_titles(client, '?bathrooms=1')


def test_one_amenity(detailed, client):
    assert home_titles(client, '?amenities=parking') == {'Family house', 'Big villa'}
    assert home_titles(client, '?amenities=furnished') == {'Cozy flat'}


def test_several_amenities_must_all_be_present(detailed, client):
    assert home_titles(client, '?amenities=parking&amenities=wifi') == {'Family house', 'Big villa'}
    assert home_titles(client, '?amenities=parking&amenities=pet_friendly') == {'Big villa'}
    assert home_titles(client, '?amenities=furnished&amenities=parking') == set()


def test_amenity_filter_never_duplicates_a_listing(detailed, client):
    html = client.get('/?amenities=parking&amenities=wifi&amenities=security').get_data(as_text=True)
    titles = re.findall(r'<h5 class="card-title">(.*?)</h5>', html)
    assert sorted(titles) == ['Big villa', 'Family house']
    assert 'Found <strong>2</strong>' in html

    pins = client.get(f'/api/map-pins?bbox={BOTSWANA}&amenities=parking&amenities=wifi').get_json()
    assert pins['total'] == 2 and len(pins['pins']) == 2


def test_filters_work_the_same_on_the_map(detailed, client):
    assert map_titles(client, '&bathrooms=2') == {'Family house', 'Big villa'}
    assert map_titles(client, '&amenities=furnished') == {'Cozy flat'}


def test_unknown_amenity_in_url_is_ignored(detailed, client):
    assert len(home_titles(client, '?amenities=helipad')) == 4


def test_new_filters_stay_selected_and_can_be_removed(detailed, client):
    html = client.get('/?bathrooms=2&amenities=parking&amenities=wifi').get_data(as_text=True)
    assert '<option value="2" selected>2+</option>' in html
    assert re.search(r'value="parking" id="filter-amenity-parking" checked', html)
    # Removing one amenity keeps the other and the bathrooms filter
    link = re.search(r'href="([^"]+)" aria-label="Remove Parking filter"', html).group(1).replace('&amp;', '&')
    assert 'amenities=wifi' in link and 'amenities=parking' not in link and 'bathrooms=2' in link


def test_filters_survive_switching_to_the_map(detailed, client):
    html = client.get('/?amenities=parking&amenities=wifi&bathrooms=2').get_data(as_text=True)
    link = re.search(r'href="(/map[^"]*)"[^>]*>\s*<i class="far fa-map"></i>Map', html).group(1).replace('&amp;', '&')
    assert link.count('amenities=') == 2 and 'bathrooms=2' in link


# ---------- Plain-English search for the new details ----------

def test_search_understands_amenities_and_bathrooms(detailed, client):
    assert home_titles(client, '?search=furnished flat') == {'Cozy flat'}
    assert home_titles(client, '?search=house with parking and security') == {'Family house', 'Big villa'}
    assert home_titles(client, '?search=pet friendly') == {'Big villa'}
    assert home_titles(client, '?search=2 bathroom house') == {'Family house', 'Big villa'}


def test_search_and_explicit_filters_combine(detailed, client):
    assert home_titles(client, '?search=house with parking&location=Gaborone') == {'Family house'}
    assert map_titles(client, '&search=house with parking&location=Gaborone') == {'Family house'}


def test_search_words_match_titles_and_descriptions(detailed, client):
    assert home_titles(client, '?search=garden') == {'Family house'}        # in the description
    assert home_titles(client, '?search=villa with a pool') == {'Big villa'}


def test_wildcard_characters_in_search_are_not_wildcards(detailed, client):
    import routes
    assert home_titles(client, '?search=%25%25%25') == home_titles(client)       # "%%%" has no words in it
    assert home_titles(client, '?search=zzzqqq') == set()
    # Search words are letters only; if one ever did carry a wildcard it would be taken literally
    assert routes._like('50%_off') == r'%50\%\_off%'


def test_very_long_search_is_cut_off(detailed, client):
    assert client.get('/?search=' + 'house ' * 500).status_code == 200


@pytest.mark.parametrize('query', [
    '?bedrooms=abc', '?bathrooms=-3', '?min_price=1e9', '?max_price=', '?sort=;drop table',
    '?page=abc', '?page=-1', '?page=999999', '?amenities=', '?location=<script>', '?bedrooms=99999999999999999999',
])
def test_malformed_filters_are_handled(detailed, client, query):
    assert client.get('/' + query).status_code == 200
    assert client.get('/map' + query).status_code == 200
    assert client.get(f'/api/map-pins?bbox={BOTSWANA}&' + query[1:]).status_code == 200

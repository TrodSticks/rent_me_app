import json
import re
import pytest
import routes
from app import db
from models import Property, User
from search_engine import LOCATIONS, TOWN_COORDS

BOTSWANA = '-27,19.9,-17.5,29.5'
GABORONE = '-24.75,25.80,-24.50,26.05'


def page_data(client, query=''):
    html = client.get('/map' + query).get_data(as_text=True)
    return json.loads(re.search(r'<script id="map-data" type="application/json">(.*?)</script>', html, re.S).group(1))


def pins(client, bbox=BOTSWANA, extra=''):
    resp = client.get(f'/api/map-pins?bbox={bbox}{extra}')
    assert resp.status_code == 200
    return resp.get_json()


def titles(client, bbox=BOTSWANA, extra=''):
    return {pin['title'] for pin in pins(client, bbox, extra)['pins']}


def add_properties(count, **fields):
    landlord = User.query.filter_by(role='Landlord').one()
    defaults = dict(description='x', price=1000, location='Gaborone', bedrooms=1, property_type='flat')
    defaults.update(fields)
    db.session.add_all([Property(title=f'Extra {i}', landlord=landlord, **defaults) for i in range(count)])
    db.session.commit()


# ---------- Town data ----------

def test_every_town_has_coordinates_inside_botswana():
    assert set(TOWN_COORDS) == set(LOCATIONS)
    for lat, lng in TOWN_COORDS.values():
        assert -27 < lat < -17.5
        assert 19.9 < lng < 29.5


# ---------- The page ----------

def test_map_page_loads(client):
    resp = client.get('/map')
    assert resp.status_code == 200
    assert 'id="map"' in resp.get_data(as_text=True)


def test_map_loads_when_logged_in(renter_client):
    assert renter_client.get('/map').status_code == 200


def test_page_sends_town_counts_not_every_property(client):
    data = page_data(client)
    assert {(town['name'], town['count']) for town in data['towns']} == {('Maun', 1), ('Gaborone', 2), ('Kasane', 1)}
    assert 'pins' not in data
    assert 'Cozy flat' not in client.get('/map').get_data(as_text=True)


def test_town_chooser_lists_towns_with_matches(client):
    html = client.get('/map').get_data(as_text=True)
    assert set(re.findall(r'data-town="([^"]+)"', html)) == {'Maun', 'Gaborone', 'Kasane'}
    filtered = client.get('/map?property_type=flat').get_data(as_text=True)
    assert set(re.findall(r'data-town="([^"]+)"', filtered)) == {'Maun'}


def test_town_counts_follow_filters_and_text_search(client):
    assert {t['name']: t['count'] for t in page_data(client, '?max_price=3000')['towns']} == {'Gaborone': 1}
    assert {t['name']: t['count'] for t in page_data(client, '?search=house in Gaborone')['towns']} == {'Gaborone': 2}


def test_map_with_no_matches(client):
    resp = client.get('/map?min_price=999999')
    assert resp.status_code == 200
    assert page_data(client, '?min_price=999999')['towns'] == []
    assert 'No properties match' in resp.get_data(as_text=True)


def test_page_opens_on_filtered_town(client):
    assert page_data(client, '?location=Maun')['filterTown'] == 'Maun'
    assert page_data(client)['filterTown'] is None
    assert page_data(client, '?location=Atlantis')['filterTown'] is None


def test_focus_opens_on_one_property(app, client):
    property = Property.query.filter_by(title='Cozy flat').one()
    focus = page_data(client, f'?focus={property.id}')['focus']
    assert focus['id'] == property.id and focus['town'] == 'Maun'
    assert page_data(client, '?focus=99999')['focus'] is None
    assert page_data(client)['focus'] is None


def test_property_page_links_to_map(app, client):
    property = Property.query.filter_by(title='Cozy flat').one()
    html = client.get(f'/property/{property.id}').get_data(as_text=True)
    assert f'/map?focus={property.id}' in html


# ---------- Pins for the visible area ----------

def test_whole_country_returns_everything(client):
    assert titles(client) == {'Cozy flat', 'Family house', 'Small house', 'Big villa'}


def test_only_pins_inside_the_view_come_back(client):
    assert titles(client, GABORONE) == {'Family house', 'Small house'}
    result = pins(client, GABORONE)
    assert result['total'] == 2 and result['truncated'] is False


def test_empty_area_returns_nothing(client):
    assert pins(client, '-20.0,21.0,-19.9,21.1') == {'pins': [], 'total': 0, 'truncated': False}


@pytest.mark.parametrize('bbox', ['', 'abc', '1,2,3', '1,2,3,x', '-17,25,-25,26', 'nan,1,2,3'])
def test_bad_bbox_is_rejected(client, bbox):
    assert client.get(f'/api/map-pins?bbox={bbox}').status_code == 400


def test_pins_use_the_same_filters_as_the_list(client):
    assert titles(client, extra='&location=Gaborone') == {'Family house', 'Small house'}
    assert titles(client, extra='&property_type=flat') == {'Cozy flat'}
    assert titles(client, extra='&max_price=3000') == {'Small house'}
    assert titles(client, extra='&search=house in Gaborone') == {'Family house', 'Small house'}


def test_response_is_capped(app, client, monkeypatch):
    monkeypatch.setattr(routes, 'MAX_PINS_PER_REQUEST', 5)
    add_properties(10)
    result = pins(client, GABORONE)
    assert len(result['pins']) == 5
    assert result['total'] == 12
    assert result['truncated'] is True


# ---------- Approximate and exact positions ----------

def test_approximate_pins_sit_near_their_town(client):
    for pin in pins(client)['pins']:
        lat, lng = TOWN_COORDS[pin['town']]
        assert pin['exact'] is False
        assert abs(pin['lat'] - lat) < 0.05
        assert abs(pin['lng'] - lng) < 0.05


def test_approximate_pins_do_not_overlap(app, client):
    add_properties(10)
    spots = [(pin['lat'], pin['lng']) for pin in pins(client, GABORONE)['pins']]
    assert len(spots) == 12
    assert len(set(spots)) == 12


def test_pin_position_does_not_change_with_filters(client):
    everywhere = {pin['id']: (pin['lat'], pin['lng']) for pin in pins(client)['pins']}
    filtered = {pin['id']: (pin['lat'], pin['lng']) for pin in pins(client, extra='&location=Gaborone')['pins']}
    assert filtered and all(everywhere[id] == spot for id, spot in filtered.items())


def test_exact_pin_is_used_as_given(app, client):
    property = Property.query.filter_by(title='Cozy flat').one()
    property.latitude, property.longitude = -19.9712, 23.4321
    db.session.commit()
    pin = next(p for p in pins(client)['pins'] if p['title'] == 'Cozy flat')
    assert (pin['lat'], pin['lng'], pin['exact']) == (-19.9712, 23.4321, True)


def test_exact_pin_decides_whether_it_is_in_view(app, client):
    # A Gaborone listing whose landlord pinned it well north of the town centre
    property = Property.query.filter_by(title='Small house').one()
    property.latitude, property.longitude = -24.40, 25.95
    db.session.commit()
    assert 'Small house' not in titles(client, GABORONE)
    assert 'Small house' in titles(client, '-24.45,25.90,-24.35,26.00')


def test_property_in_unknown_town_is_left_off_the_map(app, client):
    add_properties(1, location='Atlantis')
    assert client.get('/map').status_code == 200
    assert 'Extra 0' not in titles(client)


def test_listing_text_cannot_inject_script(app, client):
    property = Property.query.filter_by(title='Cozy flat').one()
    property.title = '</script><script>alert(1)</script>'
    db.session.commit()
    assert '<script>alert(1)</script>' not in client.get(f'/map?focus={property.id}').get_data(as_text=True)
    assert page_data(client, f'?focus={property.id}')['focus']['title'] == '</script><script>alert(1)</script>'


# ---------- Moving between list and map ----------

def test_switch_between_list_and_map_keeps_filters(client):
    home = client.get('/?location=Maun&bedrooms=2').get_data(as_text=True)
    link = re.search(r'href="(/map[^"]*)"[^>]*>\s*<i class="far fa-map"></i>Map', home).group(1).replace('&amp;', '&')
    assert 'location=Maun' in link and 'bedrooms=2' in link

    map_page = client.get(link).get_data(as_text=True)
    back = re.search(r'href="(/[^"]*)"[^>]*>\s*<i class="fas fa-th-large"></i>List', map_page).group(1).replace('&amp;', '&')
    assert 'location=Maun' in back and 'bedrooms=2' in back and not back.startswith('/map')


def test_focus_is_dropped_when_changing_filters(app, client):
    html = client.get('/map?focus=1&location=Gaborone').get_data(as_text=True)
    chip = re.search(r'class="rm-chip\s*" href="(/map\?[^"]*property_type=house[^"]*)"', html).group(1)
    assert 'focus' not in chip and 'location=Gaborone' in chip

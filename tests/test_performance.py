"""Pagination and map queries against a large generated catalogue.

These tests don't just check that responses are short. They count how many listings the app
actually pulls out of the database, and how many SQL statements it runs, so a page that loaded
everything and then threw most of it away would fail.
"""
import json
import re
import pytest
from sqlalchemy import event, insert
from app import db
from conftest import login
from locations import LOCATIONS, approximate_position
from models import AMENITIES, Favorite, Property, PropertyAmenity, PropertyPhoto, User
import routes

TOTAL = 4000
BOTSWANA = '-27,19.9,-17.5,29.5'
GABORONE = '-24.80,25.75,-24.45,26.10'


def generated(i, landlord_id):
    """Listing number i. Deterministic, so tests can work out the right answers themselves."""
    town = 'Gaborone' if i % 2 == 0 else LOCATIONS[i % len(LOCATIONS)]
    lat, lng = approximate_position(i, town)
    return dict(
        id=i, title=f'Generated {i:05d}', description='Garden and braai area' if i % 50 == 0 else 'Tidy place',
        price=2000 + (i % 20) * 500,            # only 20 different rents, so sorting has many ties
        location=town, bedrooms=1 + i % 4, bathrooms=(i % 3) if i % 4 else None,
        property_type='house' if i % 3 else 'flat', image_file='default.jpg',
        map_lat=lat, map_lng=lng, landlord_id=landlord_id,
        status='rented' if i % 10 == 0 else 'available',
        is_published=i % 25 != 0, is_hidden=i % 40 == 1,
    )


def is_public(row):
    return row['status'] == 'available' and row['is_published'] and not row['is_hidden']


@pytest.fixture
def big(app):
    """The standard four listings are removed and replaced with TOTAL generated ones."""
    landlord = User.query.filter_by(username='landlord').one()
    Property.query.delete()
    rows = [generated(i, landlord.id) for i in range(1, TOTAL + 1)]
    db.session.execute(insert(Property), rows)
    amenities = [dict(property_id=row['id'], amenity=key)
                 for row in rows for key in list(AMENITIES)[: row['id'] % 4]]
    db.session.execute(insert(PropertyAmenity), amenities)
    db.session.commit()
    return rows


class Watch:
    """Counts the listings loaded and the statements run while it is active."""

    def __enter__(self):
        self.loaded = 0
        self.statements = []
        event.listen(Property, 'load', self._on_load)
        event.listen(db.engine, 'before_cursor_execute', self._on_execute)
        return self

    def __exit__(self, *args):
        event.remove(Property, 'load', self._on_load)
        event.remove(db.engine, 'before_cursor_execute', self._on_execute)

    def _on_load(self, target, context):
        self.loaded += 1

    def _on_execute(self, conn, cursor, statement, parameters, context, executemany):
        self.statements.append(statement)

    def listing_queries(self):
        return [s for s in self.statements if 'FROM property' in s and 'property_photo' not in s.split('FROM')[1]]


def fetch(client, url):
    """Make a request with a clean session, so every listing it uses has to come from the database."""
    db.session.expire_all()
    db.session.expunge_all()
    with Watch() as watch:
        response = client.get(url)
    assert response.status_code == 200
    return response, watch


def titles(response):
    return re.findall(r'<h5 class="card-title">(.*?)</h5>', response.get_data(as_text=True))


# ---------- List pages ----------

def test_a_page_loads_only_its_twelve_listings(big, client):
    response, watch = fetch(client, '/')
    assert len(titles(response)) == 12
    assert watch.loaded == 12
    assert len(watch.statements) <= 3          # one count, one page


def test_count_is_done_by_the_database(big, client):
    response, watch = fetch(client, '/')
    expected = sum(is_public(row) for row in big)
    assert f'{expected} available' in response.get_data(as_text=True)
    assert any('count(' in statement.lower() for statement in watch.statements)
    assert watch.loaded == 12


@pytest.mark.parametrize('url', [
    '/?page=7',
    '/?page=250',
    '/?sort=price_asc&page=3',
    '/?location=Gaborone&bedrooms=2',
    '/?search=cheap 2 bedroom house in Gaborone',
    '/?search=garden',
    '/?search=house with parking&bathrooms=1',
    '/?amenities=parking&amenities=wifi&sort=price_desc',
])
def test_every_kind_of_search_stays_bounded(big, client, url):
    response, watch = fetch(client, url)
    assert watch.loaded <= 12
    assert len(titles(response)) == watch.loaded
    assert len(watch.statements) <= 3
    for statement in watch.listing_queries():
        assert 'LIMIT' in statement or 'count(' in statement.lower()


def test_page_query_uses_limit_and_offset(big, client):
    _, watch = fetch(client, '/?page=5')
    page_query = next(s for s in watch.statements if 'LIMIT' in s)
    assert 'OFFSET' in page_query
    assert 'ORDER BY' in page_query


def test_last_page_and_beyond(big, client):
    public = sum(is_public(row) for row in big)
    pages = -(-public // 12)
    response, watch = fetch(client, f'/?page={pages}')
    assert len(titles(response)) == public - 12 * (pages - 1)
    response, watch = fetch(client, '/?page=999999')
    assert f'Page {pages} of {pages}' in response.get_data(as_text=True)
    assert watch.loaded <= 12


def test_results_match_a_plain_python_filter(big, client):
    expected = [row for row in big if is_public(row) and row['location'] == 'Maun' and row['bedrooms'] == 2]
    response, _ = fetch(client, '/?location=Maun&bedrooms=2')
    assert f'Found <strong>{len(expected)}</strong>' in response.get_data(as_text=True)
    newest_first = [row['title'] for row in sorted(expected, key=lambda row: -row['id'])[:12]]
    assert titles(response) == newest_first


def test_pages_never_repeat_or_skip_when_many_rents_are_equal(big, client):
    expected = [row for row in big if is_public(row) and row['location'] == 'Kasane']
    ordered = sorted(expected, key=lambda row: (row['price'], -row['id']))
    seen = []
    for page in range(1, -(-len(expected) // 12) + 1):
        response, _ = fetch(client, f'/?location=Kasane&sort=price_asc&page={page}')
        seen += titles(response)
    assert seen == [row['title'] for row in ordered]
    assert len(seen) == len(set(seen))


def test_same_page_is_the_same_every_time(big, client):
    first = titles(fetch(client, '/?sort=price_desc&page=4')[0])
    assert all(titles(fetch(client, '/?sort=price_desc&page=4')[0]) == first for _ in range(3))


def test_hidden_draft_and_unavailable_listings_never_appear(big, client):
    private = {row['title'] for row in big if not is_public(row)}
    for page in (1, 2, 3):
        assert not private & set(titles(fetch(client, f'/?page={page}')[0]))


def test_amenity_filter_has_no_duplicates_at_scale(big, client):
    expected = [row for row in big if is_public(row) and row['id'] % 4 == 3]      # those have the first three amenities
    response, watch = fetch(client, '/?amenities=parking&amenities=wifi&amenities=air_conditioning')
    assert f'Found <strong>{len(expected)}</strong>' in response.get_data(as_text=True)
    page = titles(response)
    assert len(page) == len(set(page)) == 12


def test_favourites_take_one_query_not_one_per_card(big, client):
    renter = User.query.filter_by(username='renter').one()
    newest = sorted((row for row in big if is_public(row)), key=lambda row: -row['id'])[:12]
    db.session.add_all([Favorite(user_id=renter.id, property_id=row['id']) for row in newest[::2]])
    db.session.commit()
    login(client, 'renter@test.com')

    response, watch = fetch(client, '/')
    assert response.get_data(as_text=True).count('fa-heart text-danger') == 6
    assert sum('FROM favorite' in statement for statement in watch.statements) == 1
    assert len(watch.statements) <= 6      # sign-in, count, page, favourites, unread messages


def test_cards_do_not_load_galleries_or_landlords(big, client):
    # Give the newest listings three photos each; the cards should still only need the cover filename
    db.session.execute(insert(PropertyPhoto), [
        dict(property_id=row['id'], filename=f"photo-{row['id']}-{n}.jpg", position=n)
        for row in big[-40:] for n in range(3)])
    db.session.commit()
    _, watch = fetch(client, '/')
    assert not any('FROM property_photo' in statement for statement in watch.statements)
    assert not any('FROM "user"' in statement or 'FROM user' in statement for statement in watch.statements)


# ---------- Map ----------

def test_map_page_counts_towns_without_loading_listings(big, client):
    response, watch = fetch(client, '/map')
    assert watch.loaded == 0
    assert len(watch.statements) <= 2
    data = json.loads(re.search(r'<script id="map-data" type="application/json">(.*?)</script>',
                                response.get_data(as_text=True), re.S).group(1))
    expected = {}
    for row in big:
        if is_public(row):
            expected[row['location']] = expected.get(row['location'], 0) + 1
    assert {town['name']: town['count'] for town in data['towns']} == expected


def test_map_town_counts_follow_search_without_loading_listings(big, client):
    response, watch = fetch(client, '/map?search=2 bedroom house&amenities=parking')
    assert watch.loaded == 0
    assert 'GROUP BY' in ' '.join(watch.statements)


def test_pins_are_capped_by_the_database(big, client):
    response, watch = fetch(client, f'/api/map-pins?bbox={BOTSWANA}')
    result = response.get_json()
    public = sum(is_public(row) for row in big)
    assert len(result['pins']) == routes.MAX_PINS_PER_REQUEST == 300
    assert result['total'] == public and result['truncated'] is True
    assert watch.loaded == 0                                  # pins are read as plain columns
    assert len(watch.statements) == 2                         # one count, one capped fetch
    pin_query = next(s for s in watch.statements if 'LIMIT' in s)
    assert 'map_lat BETWEEN' in pin_query and 'map_lng BETWEEN' in pin_query


def test_pin_count_does_not_build_pins(big, client, monkeypatch):
    built = []
    real = routes.make_pin
    monkeypatch.setattr(routes, 'make_pin', lambda row: built.append(1) or real(row))
    result = client.get(f'/api/map-pins?bbox={BOTSWANA}').get_json()
    assert result['total'] > 3000
    assert len(built) == 300


def test_viewport_returns_exactly_what_is_inside(big, client):
    south, west, north, east = (float(v) for v in GABORONE.split(','))
    inside = {row['id'] for row in big if is_public(row)
              and south <= row['map_lat'] <= north and west <= row['map_lng'] <= east}
    result = fetch(client, f'/api/map-pins?bbox={GABORONE}')[0].get_json()
    assert result['total'] == len(inside)
    assert {pin['id'] for pin in result['pins']} <= inside

    tiny = fetch(client, '/api/map-pins?bbox=-24.635,25.915,-24.620,25.930')[0].get_json()
    tiny_inside = {row['id'] for row in big if is_public(row)
                   and -24.635 <= row['map_lat'] <= -24.620 and 25.915 <= row['map_lng'] <= 25.930}
    assert {pin['id'] for pin in tiny['pins']} == tiny_inside
    assert tiny['truncated'] is False


def test_viewport_filters_combine_with_search(big, client):
    result = fetch(client, f'/api/map-pins?bbox={GABORONE}&bedrooms=3&amenities=parking')[0].get_json()
    south, west, north, east = (float(v) for v in GABORONE.split(','))
    expected = {row['id'] for row in big if is_public(row) and row['bedrooms'] == 3 and row['id'] % 4 >= 1
                and south <= row['map_lat'] <= north and west <= row['map_lng'] <= east}
    assert result['total'] == len(expected)


def test_exact_and_approximate_pins_are_told_apart(big, client):
    property = db.session.get(Property, 2)
    property.latitude, property.longitude = -24.6541, 25.9087
    db.session.commit()
    assert (property.map_lat, property.map_lng) == (-24.6541, 25.9087)

    pins = {pin['id']: pin for pin in client.get('/api/map-pins?bbox=-24.66,25.90,-24.65,25.91').get_json()['pins']}
    assert pins[2]['exact'] is True and (pins[2]['lat'], pins[2]['lng']) == (-24.6541, 25.9087)

    others = client.get(f'/api/map-pins?bbox={GABORONE}').get_json()['pins']
    assert any(pin['exact'] is False for pin in others)

    # Removing the pin puts the listing back at its stable approximate spot
    property.latitude = property.longitude = None
    db.session.commit()
    assert (property.map_lat, property.map_lng) == approximate_position(2, 'Gaborone')


# ---------- Property page ----------

def test_property_page_loads_itself_and_three_similar(big, client):
    target = next(row for row in big if is_public(row) and row['location'] == 'Gaborone')
    response, watch = fetch(client, f"/property/{target['id']}")
    assert len(re.findall(r'similar-title">', response.get_data(as_text=True))) == 3
    assert watch.loaded == 4                       # the listing and its three recommendations
    assert all('LIMIT' in s for s in watch.listing_queries() if 'ORDER BY' in s)


def test_recommendations_fill_in_from_other_towns_cheaply(big, client):
    # A town with a single listing has no neighbours, so recommendations come from elsewhere
    lonely = db.session.get(Property, 4)
    lonely.location = 'Tsabong'
    Property.query.filter(Property.location == 'Tsabong', Property.id != 4).delete()
    db.session.commit()
    response, watch = fetch(client, '/property/4')
    assert len(re.findall(r'similar-title">', response.get_data(as_text=True))) == 3
    assert watch.loaded <= 1 + 6                   # at most three above and three below in rent


# ---------- The database is using its indexes ----------

@pytest.mark.parametrize('url', [
    '/', '/?location=Maun', '/?sort=price_asc', f'/api/map-pins?bbox=-24.64,25.91,-24.62,25.93', '/map',
])
def test_listing_queries_use_an_index(big, client, url):
    statements = []

    def record(conn, cursor, statement, parameters, context, executemany):
        if 'FROM property' in statement:
            statements.append((statement, parameters))

    event.listen(db.engine, 'before_cursor_execute', record)
    try:
        client.get(url)
    finally:
        event.remove(db.engine, 'before_cursor_execute', record)

    assert statements
    raw = db.engine.raw_connection()
    try:
        for statement, parameters in statements:
            plan = ' | '.join(row[3] for row in raw.cursor().execute('EXPLAIN QUERY PLAN ' + statement, parameters))
            assert 'USING' in plan and 'INDEX' in plan, plan      # never a bare scan of the whole table
    finally:
        raw.close()

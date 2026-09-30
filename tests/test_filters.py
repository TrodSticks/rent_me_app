import re

ALL = {'Cozy flat', 'Family house', 'Small house', 'Big villa'}


def titles(client, query=''):
    html = client.get('/' + query).get_data(as_text=True)
    return [t for t in re.findall(r'<h5 class="card-title">(.*?)</h5>', html)]


def test_no_filters_shows_everything(client):
    assert set(titles(client)) == ALL


def test_filter_by_type(client):
    assert set(titles(client, '?property_type=flat')) == {'Cozy flat'}


def test_filter_by_town(client):
    assert set(titles(client, '?location=Gaborone')) == {'Family house', 'Small house'}


def test_filter_by_bedrooms(client):
    assert set(titles(client, '?bedrooms=2')) == {'Cozy flat', 'Small house'}


def test_five_plus_bedrooms(client):
    assert set(titles(client, '?bedrooms=5')) == {'Big villa'}


def test_price_range(client):
    assert set(titles(client, '?min_price=3000&max_price=9000')) == {'Cozy flat', 'Family house'}


def test_sort_by_price(client):
    assert titles(client, '?sort=price_asc') == ['Small house', 'Cozy flat', 'Family house', 'Big villa']
    assert titles(client, '?sort=price_desc') == ['Big villa', 'Family house', 'Cozy flat', 'Small house']


def test_filters_combine_with_text_search(client):
    assert set(titles(client, '?search=house&max_price=9000')) == {'Family house', 'Small house'}


def test_bad_filter_values_are_ignored(client):
    resp = client.get('/?bedrooms=abc&min_price=x&location=Nowhere&sort=bogus')
    assert resp.status_code == 200
    assert set(titles(client, '?bedrooms=abc&location=Nowhere')) == ALL


def test_filters_stay_selected(client):
    html = client.get('/?location=Maun&sort=price_desc').get_data(as_text=True)
    assert '<option value="Maun" selected>' in html
    assert '<option value="price_desc" selected>' in html

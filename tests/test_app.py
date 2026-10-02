import routes
from search_engine import PropertySearchEngine


def test_home_lists_all_properties(client):
    html = client.get('/').get_data(as_text=True)
    assert 'Cozy flat' in html
    assert 'Family house' in html
    assert 'Small house' in html


def test_search_filters_results(client):
    html = client.get('/?search=2 bedroom house in Gaborone').get_data(as_text=True)
    assert 'Small house' in html
    assert 'Family house' not in html
    assert 'Cozy flat' not in html


def test_search_uses_llm_results(client, monkeypatch):
    class FakeLLM:
        def parse(self, query):
            return {'bedrooms': 3}

    monkeypatch.setattr(routes, 'search_engine', PropertySearchEngine(llm_parser=FakeLLM()))
    html = client.get('/?search=three bedroom house').get_data(as_text=True)
    assert 'Family house' in html
    assert 'Small house' not in html


def test_search_suggestions_api(client):
    resp = client.get('/api/search-suggestions?q=Maun')
    assert resp.status_code == 200
    assert 'house in Maun' in resp.get_json()


def test_register_and_login(client):
    resp = client.post('/register', data={
        'username': 'renter1', 'email': 'r@test.com', 'password': 'pw1234', 'role': 'Renter',
    })
    assert resp.status_code == 302
    resp = client.post('/login', data={'email': 'r@test.com', 'password': 'pw1234'})
    assert resp.status_code == 302
    client.get('/logout')
    resp = client.post('/login', data={'email': 'r@test.com', 'password': 'wrong'})
    assert 'Login Unsuccessful' in resp.get_data(as_text=True)

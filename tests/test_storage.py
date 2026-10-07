"""Hosted storage: Postgres addresses and photos kept in Supabase Storage."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from app import db
from conftest import login
from models import Property
from test_photos import JPG, new_listing, post, stored, upload

import config


# ---------- Database address ----------

@pytest.mark.parametrize('given, expected', [
    ('postgres://u:p@db.example:6543/postgres', 'postgresql+psycopg://u:p@db.example:6543/postgres'),
    ('postgresql://u:p@db.example:5432/postgres', 'postgresql+psycopg://u:p@db.example:5432/postgres'),
    ('postgresql+psycopg://u:p@h/db', 'postgresql+psycopg://u:p@h/db'),
    ('sqlite:////tmp/x.db', 'sqlite:////tmp/x.db'),
])
def test_database_url_uses_psycopg_for_postgres(monkeypatch, given, expected):
    monkeypatch.setenv('DATABASE_URL', given)
    assert config._database_url() == expected


def test_database_url_defaults_to_local_sqlite(monkeypatch):
    monkeypatch.delenv('DATABASE_URL', raising=False)
    assert config._database_url().endswith('app.db')


def test_engine_options_only_for_postgres(monkeypatch):
    monkeypatch.delenv('VERCEL', raising=False)
    assert config._engine_options('sqlite:///x.db') == {}
    options = config._engine_options('postgresql+psycopg://h/db')
    assert options['pool_pre_ping'] is True
    assert options['connect_args'] == {'prepare_threshold': None}
    assert 'poolclass' not in options

    monkeypatch.setenv('VERCEL', '1')
    from sqlalchemy.pool import NullPool
    assert config._engine_options('postgresql+psycopg://h/db')['poolclass'] is NullPool


# ---------- Photos in Supabase Storage ----------

class FakeStorage:
    """A stand-in for the Supabase Storage API that remembers what it was sent."""

    def __init__(self):
        self.objects = {}
        self.requests = []
        self.fail = False
        storage = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _reply(self, status, body=b'{}'):
                self.send_response(status)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _handle(self):
                length = int(self.headers.get('Content-Length') or 0)
                body = self.rfile.read(length) if length else b''
                storage.requests.append((self.command, self.path, dict(self.headers), body))
                if storage.fail:
                    return self._reply(500, b'{"error": "down"}')
                prefix = '/storage/v1/object/property-photos'
                if self.command == 'POST' and self.path.startswith(prefix + '/'):
                    storage.objects[self.path[len(prefix) + 1:]] = body
                    return self._reply(200)
                if self.command == 'DELETE' and self.path == prefix:
                    for name in json.loads(body)['prefixes']:
                        storage.objects.pop(name, None)
                    return self._reply(200, b'[]')
                return self._reply(404)

            do_POST = do_DELETE = _handle

        self.server = HTTPServer(('127.0.0.1', 0), Handler)
        self.url = f'http://127.0.0.1:{self.server.server_port}'
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def storage(app):
    fake = FakeStorage()
    app.config.update(SUPABASE_URL=fake.url, SUPABASE_SERVICE_ROLE_KEY='service-key',
                      SUPABASE_STORAGE_BUCKET='property-photos')
    yield fake
    fake.close()


@pytest.fixture
def landlord_client(client):
    login(client, 'landlord@test.com')
    return client


def test_uploads_go_to_the_bucket_not_the_disk(app, storage, landlord_client):
    listing = new_listing(landlord_client, count=2)
    names = [photo.filename for photo in listing.photos]
    assert sorted(storage.objects) == sorted(names)
    assert stored(app) == []
    method, path, headers, body = storage.requests[0]
    assert headers['Authorization'] == 'Bearer service-key'
    assert headers['Content-Type'] == 'image/jpeg'
    assert body[:2] == b'\xff\xd8'  # a JPEG


def test_pages_load_photos_from_the_bucket(app, storage, landlord_client):
    listing = new_listing(landlord_client, count=1)
    public = f'{storage.url}/storage/v1/object/public/property-photos/{listing.image_file}'
    assert public in landlord_client.get(f'/property/{listing.id}').get_data(as_text=True)
    assert public in landlord_client.get('/').get_data(as_text=True)
    pins = landlord_client.get('/api/map-pins?bbox=-27,19,-17,30').get_json()
    assert public in [pin['photo'] for pin in pins['pins']]


def test_listing_without_photos_uses_the_bundled_default(app, storage, landlord_client):
    post(landlord_client, '/property/new', title='No photos')
    listing = Property.query.filter_by(title='No photos').one()
    html = landlord_client.get(f'/property/{listing.id}').get_data(as_text=True)
    assert '/static/property_pics/default.jpg' in html
    assert storage.requests == []


def test_removed_and_deleted_photos_leave_the_bucket(app, storage, landlord_client):
    listing = new_listing(landlord_client, count=2)
    first, second = [photo for photo in listing.photos]
    post(landlord_client, f'/property/{listing.id}/update', remove_photos=[str(first.id)],
         photo_order=[str(first.id), str(second.id)])
    assert list(storage.objects) == [second.filename]

    landlord_client.post(f'/property/{listing.id}/delete')
    assert storage.objects == {}


def test_storage_outage_shows_a_message_and_saves_nothing(app, storage, landlord_client):
    storage.fail = True
    before = Property.query.count()
    response = post(landlord_client, '/property/new', title='Outage', photos=[upload('a.jpg', JPG)])
    assert 'save your photos just now' in response.get_data(as_text=True)
    assert Property.query.count() == before
    assert stored(app) == []


def test_without_supabase_settings_photos_stay_on_disk(app, landlord_client):
    listing = new_listing(landlord_client, count=1)
    assert stored(app) == [listing.image_file]
    html = landlord_client.get(f'/property/{listing.id}').get_data(as_text=True)
    assert f'/static/property_pics/{listing.image_file}' in html
    db.session.remove()


def test_storage_errors_say_what_supabase_answered(app, storage, landlord_client, caplog):
    storage.fail = True
    post(landlord_client, '/property/new', title='Outage', photos=[upload('a.jpg', JPG)])
    message = ' '.join(record.getMessage() for record in caplog.records)
    assert '500 from POST' in message and '/storage/v1/object/property-photos/' in message
    assert '"down"' in message
    assert 'service-key' not in message


@pytest.mark.parametrize('given', [
    'https://abcd.supabase.co', 'https://abcd.supabase.co/', 'https://abcd.supabase.co/rest/v1',
    'https://abcd.supabase.co/rest/v1/', ' abcd.supabase.co '])
def test_supabase_url_keeps_only_the_project_address(monkeypatch, given):
    monkeypatch.setenv('SUPABASE_URL', given)
    assert config._supabase_url() == 'https://abcd.supabase.co'


def test_supabase_url_empty_when_unset(monkeypatch):
    monkeypatch.delenv('SUPABASE_URL', raising=False)
    assert config._supabase_url() == ''

"""Direct upload authorization, validation, atomic attachment and abandoned-file cleanup."""
import json
from datetime import timedelta
from urllib.parse import urlsplit

import pytest
from app import db
from conftest import login, make_user
from models import PhotoUpload, Property, PropertyPhoto, utcnow
from photos import StorageError
from photo_uploads import cleanup_uploads
from test_photos import make_image, property_form, new_listing


@pytest.fixture
def direct(app, monkeypatch):
    objects = {}
    buckets = {}
    app.config.update(SUPABASE_URL='https://storage.example', SUPABASE_SERVICE_ROLE_KEY='never-expose',
                      DIRECT_PHOTO_UPLOADS=True)

    def transport(method, url, body=None, content_type=None, max_bytes=None):
        parts = urlsplit(url).path.split('/')[3:]
        if parts[0] == 'bucket':
            if method == 'GET':
                return json.dumps(list(buckets.values()) if len(parts) == 1 else buckets[parts[1]]).encode()
            data = json.loads(body)
            buckets[data['id']] = data
            return b'{}'
        if parts[1:3] == ['upload', 'sign']:
            return json.dumps({'url': '/object/upload/sign/' + '/'.join(parts[3:]) + '?token=scoped'}).encode()
        bucket = parts[1]
        if method == 'DELETE':
            for name in json.loads(body)['prefixes']:
                objects.pop((bucket, name), None)
            return b'[]'
        key = (bucket, parts[2])
        if method == 'POST':
            objects[key] = body
            return b'{}'
        if key not in objects:
            raise StorageError('missing', 404)
        value = objects[key]
        if max_bytes is not None and len(value) > max_bytes:
            raise ValueError('too large')
        return value

    monkeypatch.setattr('photos._storage_request', transport)
    monkeypatch.setattr('photo_uploads._storage_request', transport)
    return objects, buckets


def start(client, listing_id=None, size=100):
    return client.post('/api/photo-uploads', json={'listing_id': listing_id, 'size': size})


def ready(client, direct, listing_id=None, data=None):
    response = start(client, listing_id)
    assert response.status_code == 201, response.data
    receipt = response.get_json()
    direct[0]['property-photo-uploads', receipt['id']] = data or make_image()
    response = client.post(f"/api/photo-uploads/{receipt['id']}/finish")
    assert response.status_code == 200, response.data
    return receipt['id']


def save(client, ids, listing_id=None, **fields):
    return client.post(f'/property/{listing_id}/update' if listing_id else '/property/new',
                       data=property_form(photo_upload_ids=ids, **fields),
                       headers={'X-Photo-Upload': 'direct'})


def test_direct_upload_and_draft_save_have_no_file_body(app, landlord_client, direct):
    receipt = ready(landlord_client, direct)
    response = save(landlord_client, [receipt], action='draft')
    assert response.status_code == 200
    assert response.get_json()['redirect'] == '/dashboard'
    listing = Property.query.filter_by(title='New place').one()
    assert not listing.is_published and len(listing.photos) == 1
    assert db.session.get(PhotoUpload, receipt).claimed
    assert ('property-photos', listing.image_file) in direct[0]
    assert 'never-expose' not in landlord_client.get('/property/new').get_data(as_text=True)


def test_receipt_cannot_be_reused(app, landlord_client, direct):
    receipt = ready(landlord_client, direct)
    assert save(landlord_client, [receipt]).status_code == 200
    assert save(landlord_client, [receipt], title='Replay').status_code == 400
    assert Property.query.filter_by(title='Replay').first() is None


def test_login_and_landlord_required(app, client, direct):
    assert start(client).status_code == 401
    login(client, 'renter@test.com')
    assert start(client).status_code == 403


def test_owner_and_listing_scope_enforced(app, landlord_client, direct):
    receipt = ready(landlord_client, direct, listing_id=1)
    assert save(landlord_client, [receipt], listing_id=2).status_code == 400
    assert save(landlord_client, [receipt]).status_code == 400
    make_user('other', 'Landlord')
    db.session.commit()
    landlord_client.get('/logout')
    login(landlord_client, 'other@test.com')
    assert start(landlord_client, 1).status_code == 404
    assert landlord_client.post(f'/api/photo-uploads/{receipt}/finish').status_code == 404
    assert save(landlord_client, [receipt]).status_code == 400


@pytest.mark.parametrize('size', [0, -1, 5*1024*1024 + 1, '100', True, None])
def test_reject_invalid_declared_sizes(app, landlord_client, direct, size):
    assert start(landlord_client, size=size).status_code == 400
    assert PhotoUpload.query.count() == 0


@pytest.mark.parametrize('data', [b'not a photo', b'x' * (5*1024*1024+1)], ids=['invalid', 'oversized'])
def test_finish_checks_actual_contents_and_size(app, landlord_client, direct, data):
    receipt = start(landlord_client).get_json()['id']
    direct[0]['property-photo-uploads', receipt] = data
    assert landlord_client.post(f'/api/photo-uploads/{receipt}/finish').status_code == 400
    assert save(landlord_client, [receipt]).status_code == 400


def test_duplicate_new_and_existing_photos_rejected(app, landlord_client, direct):
    first = ready(landlord_client, direct)
    second = ready(landlord_client, direct)
    assert 'duplicate photo' in save(landlord_client, [first, second]).get_json()['error']
    assert not db.session.get(PhotoUpload, first).claimed
    listing = new_listing(landlord_client)
    duplicate = ready(landlord_client, direct, listing.id, make_image(colour=(20, 40, 80)))
    assert 'duplicate photo' in save(landlord_client, [duplicate], listing.id).get_json()['error']
    assert len(listing.photos) == 1


def test_retry_finish_is_idempotent(app, landlord_client, direct):
    receipt = ready(landlord_client, direct)
    before = dict(direct[0])
    assert landlord_client.post(f'/api/photo-uploads/{receipt}/finish').status_code == 200
    assert direct[0] == before


def test_upload_interruption_can_retry_finish(app, landlord_client, direct):
    receipt = start(landlord_client).get_json()['id']
    assert landlord_client.post(f'/api/photo-uploads/{receipt}/finish').status_code == 503
    direct[0]['property-photo-uploads', receipt] = make_image()
    assert landlord_client.post(f'/api/photo-uploads/{receipt}/finish').status_code == 200


def test_expired_and_unfinished_receipts_rejected(app, landlord_client, direct):
    unfinished = start(landlord_client).get_json()['id']
    assert save(landlord_client, [unfinished]).status_code == 400
    receipt = ready(landlord_client, direct)
    db.session.get(PhotoUpload, receipt).created_at = utcnow() - timedelta(hours=3)
    db.session.commit()
    assert landlord_client.post(f'/api/photo-uploads/{receipt}/finish').status_code == 410
    assert save(landlord_client, [receipt]).status_code == 400


def test_ten_photos_and_more_than_old_total_limit(app, landlord_client, direct):
    ids = []
    for index in range(10):
        data = make_image(colour=(index*20, 40, 80)) + b'\0' * 600000
        ids.append(ready(landlord_client, direct, data=data))
    assert sum(len(v) for (bucket, _), v in direct[0].items() if bucket == 'property-photo-uploads') > 4500000
    assert save(landlord_client, ids + [ids[0]]).status_code == 400
    assert save(landlord_client, ids).status_code == 200
    assert len(Property.query.filter_by(title='New place').one().photos) == 10


def test_validation_failure_preserves_receipts_for_retry(app, landlord_client, direct):
    receipt = ready(landlord_client, direct)
    assert save(landlord_client, [receipt], price='bad').status_code == 400
    assert not db.session.get(PhotoUpload, receipt).claimed
    assert save(landlord_client, [receipt]).status_code == 200


def test_cleanup_keeps_claimed_photos_and_retries_failures(app, landlord_client, direct, monkeypatch):
    claimed = ready(landlord_client, direct)
    assert save(landlord_client, [claimed]).status_code == 200
    unused = ready(landlord_client, direct)
    saved_name = db.session.get(PhotoUpload, claimed).filename
    unused_name = db.session.get(PhotoUpload, unused).filename
    for row in PhotoUpload.query.all():
        row.created_at = utcnow() - timedelta(days=2)
    db.session.commit()
    with monkeypatch.context() as patch:
        def fail(*args):
            raise StorageError('outage')
        patch.setattr('photo_uploads.remove_object', fail)
        assert cleanup_uploads() == 0
        assert PhotoUpload.query.count() == 2
    assert cleanup_uploads() == 2
    assert ('property-photos', saved_name) in direct[0]
    assert ('property-photos', unused_name) not in direct[0]
    assert not any(bucket == 'property-photo-uploads' for bucket, name in direct[0])


def test_csrf_required_and_quota_enforced(app, landlord_client, direct):
    app.config['WTF_CSRF_ENABLED'] = True
    assert start(landlord_client).status_code == 400
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['RATE_LIMITS'] = {**app.config['RATE_LIMITS'], 'photo_upload': (1, 3600)}
    assert start(landlord_client).status_code == 201
    assert start(landlord_client).status_code == 429


def test_public_staging_bucket_fails_closed(app, landlord_client, direct):
    direct[1]['property-photo-uploads'] = {'id': 'property-photo-uploads', 'public': True}
    assert start(landlord_client).status_code == 503
    assert PhotoUpload.query.count() == 0


def test_remove_and_replace_same_image(app, landlord_client, direct):
    listing = new_listing(landlord_client)
    old = listing.photos[0]
    old_name = old.filename
    receipt = ready(landlord_client, direct, listing.id, make_image(colour=(20, 40, 80)))
    assert save(landlord_client, [receipt], listing.id, remove_photos=[str(old.id)]).status_code == 200
    assert ('property-photos', old_name) not in direct[0]
    assert len(db.session.get(Property, listing.id).photos) == 1

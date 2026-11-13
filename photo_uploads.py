"""Browser -> private Storage -> validated gallery photo, using Flask login and CSRF."""
import io
import json
import secrets
from datetime import timedelta

from flask import current_app, jsonify, request
from flask_login import current_user
from werkzeug.datastructures import FileStorage

from app import db
from models import PhotoUpload, Property, PropertyPhoto, User, utcnow
from photos import (StorageError, _object_url, _storage_request, remote_storage,
                    save_picture, stored_photo_digest)
from routes import bp
from security import is_limited, record_hit

UPLOAD_LIFETIME = timedelta(hours=2)
CLEANUP_AGE = timedelta(hours=24)  # Supabase upload URLs expire after two hours.


def enabled():
    return remote_storage() and current_app.config['DIRECT_PHOTO_UPLOADS']


def ensure_upload_bucket():
    """Create only our dedicated private bucket; fail closed on unsafe existing settings."""
    bucket = current_app.config['SUPABASE_UPLOAD_BUCKET']
    buckets = json.loads(_storage_request('GET', _object_url('bucket')))
    existing = next((item for item in buckets if item['id'] == bucket), None)
    if existing is None:
        try:
            _storage_request('POST', _object_url('bucket'), json.dumps({
                'id': bucket, 'name': bucket, 'public': False,
                'file_size_limit': current_app.config['MAX_IMAGE_BYTES'],
                'allowed_mime_types': ['image/jpeg', 'image/png', 'image/gif', 'image/webp'],
            }).encode(), 'application/json')
        except StorageError:
            # Another instance may have created it at the same time; verify below.
            pass
        existing = json.loads(_storage_request('GET', _object_url('bucket', bucket)))
    if (existing.get('public') is not False or
            existing.get('file_size_limit') != current_app.config['MAX_IMAGE_BYTES'] or
            set(existing.get('allowed_mime_types') or []) !=
            {'image/jpeg', 'image/png', 'image/gif', 'image/webp'}):
        raise StorageError('The private upload bucket needs its access and size limits checked.')


def remove_object(bucket, name):
    # Unlike delete_picture, raise on failure so the receipt is retained for retry.
    _storage_request('DELETE', _object_url('object', bucket),
                     json.dumps({'prefixes': [name]}).encode(), 'application/json')


def cleanup_uploads(limit=5):
    """Bounded cleanup on upload activity; CLI can also run this when the site is quiet."""
    rows = PhotoUpload.query.filter(PhotoUpload.created_at < utcnow() - CLEANUP_AGE).order_by(
        PhotoUpload.created_at).limit(limit).with_for_update(skip_locked=True).all()
    count = 0
    for row in rows:
        try:
            remove_object(current_app.config['SUPABASE_UPLOAD_BUCKET'], row.id)
            if not row.claimed and not PropertyPhoto.query.filter_by(filename=row.filename).first():
                remove_object(current_app.config['SUPABASE_STORAGE_BUCKET'], row.filename)
        except StorageError:
            current_app.logger.warning('Deferred cleanup of photo upload %s', row.id)
            continue
        db.session.delete(row)
        count += 1
    db.session.commit()
    return count


def _access():
    if not current_user.is_authenticated:
        return jsonify(error='Please sign in again, then retry.'), 401
    if current_user.role != 'Landlord':
        return jsonify(error='Only landlords can upload listing photos.'), 403
    if not enabled():
        return jsonify(error='Direct photo uploads are unavailable.'), 503
    return None


@bp.post('/api/photo-uploads')
def start_photo_upload():
    error = _access()
    if error:
        return error
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error='Invalid upload request.'), 400
    listing_id = payload.get('listing_id')
    if listing_id is not None:
        if type(listing_id) is not int:
            return jsonify(error='Invalid listing.'), 400
        listing = db.session.get(Property, listing_id)
        if not listing or listing.landlord_id != current_user.id:
            return jsonify(error='Listing not found.'), 404
    size = payload.get('size')
    if type(size) is not int or not 0 < size <= current_app.config['MAX_IMAGE_BYTES']:
        return jsonify(error='Choose a photo up to 5 MB.'), 400
    try:
        cleanup_uploads(limit=1)
        # Serialize quota checks for one account, including simultaneous browser tabs.
        db.session.execute(db.select(User.id).where(User.id == current_user.id).with_for_update())
        if is_limited('photo_upload', current_user.id):
            return jsonify(error='You have uploaded many photos. Please try again in an hour.'), 429
        ensure_upload_bucket()
        row = PhotoUpload(id=secrets.token_hex(16), user_id=current_user.id, listing_id=listing_id,
                          filename=secrets.token_hex(7) + '.jpg')
        db.session.add(row)
        record_hit('photo_upload', current_user.id)
        # Record before issuing a permission, so every possible object has a cleanup receipt.
        db.session.commit()
        result = json.loads(_storage_request('POST', _object_url(
            'object', 'upload', 'sign', current_app.config['SUPABASE_UPLOAD_BUCKET'], row.id),
            b'{}', 'application/json'))
        relative = result['url']
        if not relative.startswith('/object/upload/sign/'):
            raise StorageError('Unexpected signed upload address.')
        signed_url = current_app.config['SUPABASE_URL'] + '/storage/v1' + relative
        return jsonify(id=row.id, url=signed_url), 201
    except (StorageError, ValueError, KeyError):
        db.session.rollback()
        return jsonify(error='Photo storage is unavailable. Please retry in a moment.'), 503


@bp.post('/api/photo-uploads/<upload_id>/finish')
def finish_photo_upload(upload_id):
    error = _access()
    if error:
        return error
    row = PhotoUpload.query.filter_by(id=upload_id, user_id=current_user.id).with_for_update().first()
    if row is None or row.claimed:
        return jsonify(error='Upload not found. Select the photo again.'), 404
    if row.created_at < utcnow() - UPLOAD_LIFETIME:
        return jsonify(error='Upload expired. Select the photo again.'), 410
    if row.digest:
        return jsonify(id=row.id, ready=True)  # Lost response / safe retry.
    try:
        data = _storage_request('GET', _object_url('object', current_app.config['SUPABASE_UPLOAD_BUCKET'], row.id),
                                max_bytes=current_app.config['MAX_IMAGE_BYTES'])
        # A previous worker might have written the deterministic output but lost its DB transaction.
        # This row lock excludes finalize/claim/cleanup races while replacing that unclaimed output.
        remove_object(current_app.config['SUPABASE_STORAGE_BUCKET'], row.filename)
        filename = save_picture(FileStorage(stream=io.BytesIO(data)), filename=row.filename)
        if not filename:
            return jsonify(error='This file is not a readable JPG, PNG, GIF or WebP photo.'), 400
        row.digest = stored_photo_digest(filename)
        db.session.commit()
        # Leave the private source until URL expiry; deleting now would permit a signed-URL replay.
        return jsonify(id=row.id, ready=True)
    except ValueError:
        db.session.rollback()
        return jsonify(error='Choose a photo up to 5 MB.'), 400
    except StorageError:
        db.session.rollback()
        return jsonify(error='We could not check this upload. Please retry.'), 503


def claim_uploads(ids, property, seen):
    """Validate and consume receipts inside the same transaction as the listing save."""
    rows = []
    if len(ids) != len(set(ids)):
        return [], 'A duplicate photo was selected. Keep only one copy.'
    for upload_id in sorted(ids):
        row = PhotoUpload.query.filter_by(id=upload_id, user_id=current_user.id).with_for_update().first()
        if (row is None or row.claimed or not row.digest or row.listing_id != property.id or
                row.created_at < utcnow() - UPLOAD_LIFETIME):
            return [], 'A photo upload expired or is unavailable. Select your new photos again.'
        if row.digest in seen:
            return [], 'A duplicate photo was selected. Keep only one copy of each photo in this listing.'
        seen.add(row.digest)
        rows.append(row)
    ordered = {row.id: row for row in rows}
    return [ordered[upload_id] for upload_id in ids], None

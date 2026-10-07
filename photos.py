"""Storing listing photos: on disk, or in Supabase Storage when it is configured."""
import io
import json
import os
import secrets
import urllib.error
import urllib.parse
import urllib.request
from flask import current_app, url_for
from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_IMAGE_FORMATS = ('JPEG', 'PNG', 'GIF', 'WEBP')
MAX_IMAGE_SIDE = 1200  # pixels; larger photos are shrunk to fit
JPEG_QUALITY = 82
DEFAULT_PHOTO = 'default.jpg'
STORAGE_TIMEOUT = 15  # seconds


class StorageError(Exception):
    """A photo could not be sent to (or removed from) the photo store."""


def upload_size(file_storage):
    """Size of an uploaded file in bytes, leaving it ready to be read from the start."""
    stream = file_storage.stream
    stream.seek(0, os.SEEK_END)
    size = stream.tell()
    stream.seek(0)
    return size


def remote_storage():
    """True when photos go to Supabase Storage rather than the local upload folder."""
    config = current_app.config
    return bool(config.get('SUPABASE_URL') and config.get('SUPABASE_SERVICE_ROLE_KEY'))


def _object_url(*parts):
    """A Supabase Storage API address, e.g. object/<bucket>/<filename>."""
    path = '/'.join(urllib.parse.quote(part, safe='') for part in parts)
    return f"{current_app.config['SUPABASE_URL']}/storage/v1/{path}"


def _storage_request(method, url, body=None, content_type=None):
    key = current_app.config['SUPABASE_SERVICE_ROLE_KEY']
    headers = {'Authorization': f'Bearer {key}', 'apikey': key}
    if content_type:
        headers['Content-Type'] = content_type
    request = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=STORAGE_TIMEOUT) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        # Supabase explains the problem in the body (e.g. "Bucket not found"); the address shows
        # which project and bucket were asked. Neither contains the key.
        detail = error.read(300).decode('utf-8', 'replace')
        raise StorageError(f"{error.code} from {method} {url}: {detail}") from error
    except (urllib.error.URLError, OSError) as error:
        raise StorageError(f"{error} ({method} {url})") from error


def photo_url(filename):
    """Where a browser loads a stored photo from."""
    filename = filename or DEFAULT_PHOTO
    if filename != DEFAULT_PHOTO and remote_storage():
        return _object_url('object', 'public', current_app.config['SUPABASE_STORAGE_BUCKET'], filename)
    return url_for('static', filename='property_pics/' + filename)


def save_picture(file_storage):
    """Shrink an uploaded photo and store it as a JPEG under a random name.

    Returns the filename, or None if the upload isn't a readable image.
    Raises StorageError if the photo store can't be reached.
    """
    try:
        image = Image.open(file_storage.stream)
        if image.format not in ALLOWED_IMAGE_FORMATS:
            return None
        image = ImageOps.exif_transpose(image)  # respect phone camera rotation
        image.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
        if image.mode != 'RGB':
            # Flatten transparency onto white, since JPEG has none
            rgba = image.convert('RGBA')
            image = Image.new('RGB', rgba.size, (255, 255, 255))
            image.paste(rgba, mask=rgba.getchannel('A'))
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        return None

    filename = f"{secrets.token_hex(7)}.jpg"
    if remote_storage():
        buffer = io.BytesIO()
        image.save(buffer, 'JPEG', quality=JPEG_QUALITY, optimize=True)
        _storage_request('POST', _object_url('object', current_app.config['SUPABASE_STORAGE_BUCKET'], filename),
                         body=buffer.getvalue(), content_type='image/jpeg')
        return filename

    folder = current_app.config['UPLOAD_FOLDER']
    os.makedirs(folder, exist_ok=True)
    image.save(os.path.join(folder, filename), 'JPEG', quality=JPEG_QUALITY, optimize=True)
    return filename


def delete_picture(filename):
    """Remove a stored photo. Only ever touches plain filenames inside the upload folder or bucket.

    A photo the store fails to remove is logged and left behind rather than failing the request.
    """
    if not filename or filename == DEFAULT_PHOTO or os.path.basename(filename) != filename:
        return
    if remote_storage():
        bucket = current_app.config['SUPABASE_STORAGE_BUCKET']
        try:
            _storage_request('DELETE', _object_url('object', bucket),
                             body=json.dumps({'prefixes': [filename]}).encode(), content_type='application/json')
        except StorageError as error:
            current_app.logger.warning("Could not remove photo %s from storage: %s", filename, error)
        return
    path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    if os.path.isfile(path):
        os.remove(path)

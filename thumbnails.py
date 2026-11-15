"""Small public listing previews, using Pillow and the existing free CDN cache."""
import io
import os
import re
from flask import abort, current_app, redirect, send_file, url_for
from PIL import Image, ImageOps, UnidentifiedImageError
from photos import DEFAULT_PHOTO, StorageError, _object_url, _storage_request, photo_url, remote_storage
from routes import bp


def thumbnail_url(filename, width=640):
    if not filename or filename == DEFAULT_PHOTO:
        return photo_url(DEFAULT_PHOTO)
    return url_for('main.thumbnail', width=width, filename=filename)


@bp.get('/thumb/v1/<int:width>/<filename>')
def thumbnail(width, filename):
    if width not in (320, 640) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}\.(?:jpg|jpeg|png|webp)', filename):
        abort(404)
    try:
        if remote_storage():
            raw = _storage_request('GET', _object_url('object', current_app.config['SUPABASE_STORAGE_BUCKET'], filename),
                                   max_bytes=current_app.config['MAX_IMAGE_BYTES'])
        else:
            with open(os.path.join(current_app.config['UPLOAD_FOLDER'], filename), 'rb') as source:
                raw = source.read(current_app.config['MAX_IMAGE_BYTES'] + 1)
        if len(raw) > current_app.config['MAX_IMAGE_BYTES']:
            raise ValueError('Image too large')
        with Image.open(io.BytesIO(raw)) as original:
            if original.width * original.height > 40_000_000:
                raise ValueError('Image too large')
            image = ImageOps.exif_transpose(original)
            image.thumbnail((width, width), Image.Resampling.LANCZOS)
            image = image.convert('RGB')
            output = io.BytesIO()
            image.save(output, 'WEBP', quality=72, method=4)
        output.seek(0)
        response = send_file(output, mimetype='image/webp', max_age=86400)
        response.headers['Cache-Control'] = 'public, max-age=86400'
        response.headers['CDN-Cache-Control'] = 'public, s-maxage=86400'
        return response
    except (OSError, ValueError, StorageError, UnidentifiedImageError, Image.DecompressionBombError):
        # An unavailable preview must not hide an otherwise usable original.
        response = redirect(photo_url(filename))
        response.headers['Cache-Control'] = 'no-store'
        return response

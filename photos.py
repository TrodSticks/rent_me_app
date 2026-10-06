"""Storing listing photos on disk."""
import os
import secrets
from flask import current_app
from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_IMAGE_FORMATS = ('JPEG', 'PNG', 'GIF', 'WEBP')
MAX_IMAGE_SIDE = 1200  # pixels; larger photos are shrunk to fit
JPEG_QUALITY = 82
DEFAULT_PHOTO = 'default.jpg'


def upload_size(file_storage):
    """Size of an uploaded file in bytes, leaving it ready to be read from the start."""
    stream = file_storage.stream
    stream.seek(0, os.SEEK_END)
    size = stream.tell()
    stream.seek(0)
    return size


def save_picture(file_storage):
    """Shrink an uploaded photo and save it as a JPEG under a random name.

    Returns the filename, or None if the upload isn't a readable image.
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
    folder = current_app.config['UPLOAD_FOLDER']
    os.makedirs(folder, exist_ok=True)
    image.save(os.path.join(folder, filename), 'JPEG', quality=JPEG_QUALITY, optimize=True)
    return filename


def delete_picture(filename):
    """Remove a stored photo. Only ever touches plain filenames inside the upload folder."""
    if not filename or filename == DEFAULT_PHOTO or os.path.basename(filename) != filename:
        return
    path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    if os.path.isfile(path):
        os.remove(path)

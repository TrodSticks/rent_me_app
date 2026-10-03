import os
import secrets

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def _load_secret_key():
    """Use SECRET_KEY from the environment; otherwise keep a local key in a git-ignored file."""
    key = os.environ.get('SECRET_KEY')
    if key:
        return key
    path = os.path.join(BASE_DIR, '.secret_key')
    if os.path.exists(path):
        with open(path) as f:
            key = f.read().strip()
        if key:
            return key
    key = secrets.token_hex(32)
    with open(path, 'w') as f:
        f.write(key)
    return key


class Config:
    SECRET_KEY = _load_secret_key()
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///' + os.path.join(BASE_DIR, 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER') or os.path.join(BASE_DIR, 'static', 'property_pics')
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB upload limit
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

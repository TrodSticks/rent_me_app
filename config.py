import os
import secrets

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def _load_env_file(path):
    """Read KEY=VALUE lines from a local .env file. Real environment variables win."""
    if not os.path.exists(path):
        return
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env_file(os.path.join(BASE_DIR, '.env'))


def _flag(name, default):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ('1', 'true', 'yes', 'on')


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
    try:
        with open(path, 'w') as f:
            f.write(key)
    except OSError:
        pass  # read-only file system (e.g. Vercel without SECRET_KEY): key lasts until restart
    return key


# The app is production-safe unless told otherwise: set APP_ENV=development on your own machine.
APP_ENV = os.environ.get('APP_ENV', 'production').strip().lower()
IS_DEVELOPMENT = APP_ENV == 'development'

MAX_IMAGE_BYTES = 5 * 1024 * 1024   # per photo
MAX_PHOTOS = 10                     # per listing


def _mail_backend():
    """Where emails go: smtp, file (development mailbox), memory (tests) or disabled.

    The file backend keeps whole emails, links included, on disk. That is only safe on a
    developer's machine, so outside development anything but smtp is switched off.
    """
    backend = os.environ.get('MAIL_BACKEND', '').strip().lower()
    if not backend:
        backend = 'smtp' if os.environ.get('MAIL_SERVER') else ('file' if IS_DEVELOPMENT else 'disabled')
    if backend not in ('smtp', 'file', 'memory', 'disabled'):
        backend = 'disabled'
    if backend in ('file', 'memory') and not IS_DEVELOPMENT:
        backend = 'disabled'
    return backend


class Config:
    APP_ENV = APP_ENV
    IS_DEVELOPMENT = IS_DEVELOPMENT
    SECRET_KEY = _load_secret_key()
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///' + os.path.join(BASE_DIR, 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER') or os.path.join(BASE_DIR, 'static', 'property_pics')
    MAX_IMAGE_BYTES = MAX_IMAGE_BYTES
    MAX_PHOTOS = MAX_PHOTOS
    # A full set of photos in one request, plus room for the rest of the form
    MAX_CONTENT_LENGTH = MAX_PHOTOS * MAX_IMAGE_BYTES + 2 * 1024 * 1024

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    # Send the login cookie over https only, except while developing on http
    SESSION_COOKIE_SECURE = _flag('SESSION_COOKIE_SECURE', not IS_DEVELOPMENT)

    # Email
    MAIL_BACKEND = _mail_backend()
    MAIL_SERVER = os.environ.get('MAIL_SERVER', '')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', '587'))
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    MAIL_USE_TLS = _flag('MAIL_USE_TLS', True)
    MAIL_USE_SSL = _flag('MAIL_USE_SSL', False)
    MAIL_FROM = os.environ.get('MAIL_FROM', 'Rent Me <no-reply@localhost>')
    MAIL_OUTBOX_DIR = os.environ.get('MAIL_OUTBOX_DIR') or os.path.join(BASE_DIR, 'mail_outbox')
    # Address used in emailed links, e.g. https://rentme.example. Empty means "use the request's host".
    PUBLIC_BASE_URL = os.environ.get('PUBLIC_BASE_URL', '').rstrip('/')
    # Number of reverse proxies in front of the app, so visitor IP addresses are read correctly
    TRUSTED_PROXY_COUNT = int(os.environ.get('TRUSTED_PROXY_COUNT', '0'))

    # Links in emails
    VERIFY_TOKEN_MAX_AGE = 24 * 60 * 60   # 24 hours
    RESET_TOKEN_MAX_AGE = 60 * 60         # 1 hour

    # Rate limits: name -> (attempts allowed, within this many seconds)
    RATELIMIT_ENABLED = True
    RATE_LIMITS = {
        'login_email': (5, 15 * 60),
        'login_ip': (30, 15 * 60),
        'reset_email': (3, 60 * 60),
        'reset_ip': (10, 60 * 60),
        'verify_resend': (3, 60 * 60),
        'report': (5, 60 * 60),
    }

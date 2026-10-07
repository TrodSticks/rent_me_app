import os
import secrets
from urllib.parse import urlsplit

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


def _database_url():
    """DATABASE_URL, pointed at the psycopg driver when it is a Postgres address (as Supabase gives).

    Defaults to the local app.db SQLite file.
    """
    url = os.environ.get('DATABASE_URL', '').strip()
    if not url:
        return 'sqlite:///' + os.path.join(BASE_DIR, 'app.db')
    for prefix in ('postgres://', 'postgresql://'):
        if url.startswith(prefix):
            return 'postgresql+psycopg://' + url[len(prefix):]
    return url


def _engine_options(url):
    """Connection settings that suit a hosted Postgres database."""
    if not url.startswith('postgresql'):
        return {}
    options = {
        # Drop connections the database or its pooler has closed, rather than failing a request
        'pool_pre_ping': True,
        # Supabase's transaction pooler (port 6543) can't keep prepared statements between queries
        'connect_args': {'prepare_threshold': None},
    }
    if os.environ.get('VERCEL'):
        # Each serverless copy of the app lives briefly; leave connection pooling to Supabase
        from sqlalchemy.pool import NullPool
        options['poolclass'] = NullPool
    return options


def _supabase_url():
    """SUPABASE_URL reduced to https://<project>.supabase.co.

    Supabase shows the address with /rest/v1 on the end in places; that path breaks Storage calls.
    """
    url = os.environ.get('SUPABASE_URL', '').strip()
    if not url:
        return ''
    parts = urlsplit(url if '://' in url else 'https://' + url)
    return f"{parts.scheme}://{parts.netloc}"


DATABASE_URL = _database_url()


class Config:
    APP_ENV = APP_ENV
    IS_DEVELOPMENT = IS_DEVELOPMENT
    SECRET_KEY = _load_secret_key()
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_ENGINE_OPTIONS = _engine_options(DATABASE_URL)
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER') or os.path.join(BASE_DIR, 'static', 'property_pics')
    # Supabase Storage for photos. Without these, photos are saved in UPLOAD_FOLDER.
    # The service role key is a server-side secret: set it only in the server's environment.
    SUPABASE_URL = _supabase_url()
    SUPABASE_SERVICE_ROLE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '').strip()
    SUPABASE_STORAGE_BUCKET = os.environ.get('SUPABASE_STORAGE_BUCKET', 'property-photos').strip()
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

"""Tokens for emailed links, rate limits, password rules and permission checks."""
import hashlib
import random
from datetime import timedelta
from functools import wraps
from flask import abort, current_app, flash, redirect, request, url_for
from flask_login import current_user
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from app import db
from models import RateLimitHit, User, utcnow

MIN_PASSWORD_LENGTH = 6
MAX_PASSWORD_LENGTH = 128


def password_error(password):
    """Why a new password isn't acceptable, or None. Used everywhere a password is set."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Your password must be at least {MIN_PASSWORD_LENGTH} characters."
    if len(password) > MAX_PASSWORD_LENGTH:
        return f"Your password must be {MAX_PASSWORD_LENGTH} characters or fewer."
    return None


# ---------- Tokens for emailed links ----------
# Signed with SECRET_KEY and time-limited, so nothing needs storing. Each token is tied to
# the state it was issued for, which is what makes it single-use:
#   - a verification link names the email address, so it dies if the address changes
#   - a reset link carries the password fingerprint, so it dies once the password changes

def _serializer(purpose):
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'], salt=f'rentme-{purpose}')


def _load(purpose, token, max_age):
    try:
        return _serializer(purpose).loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None


def make_verify_token(user):
    return _serializer('verify-email').dumps({'u': user.id, 'e': user.email})


def read_verify_token(token):
    """The user a verification link belongs to, or None if it is invalid, expired or stale."""
    data = _load('verify-email', token, current_app.config['VERIFY_TOKEN_MAX_AGE'])
    if not isinstance(data, dict):
        return None
    user = db.session.get(User, data.get('u') or 0)
    if user is None or user.email != data.get('e'):
        return None
    return user


def make_reset_token(user):
    return _serializer('reset-password').dumps({'u': user.id, 'f': user.password_fingerprint()})


def read_reset_token(token):
    """The user a reset link belongs to, or None if it is invalid, expired or already used."""
    data = _load('reset-password', token, current_app.config['RESET_TOKEN_MAX_AGE'])
    if not isinstance(data, dict):
        return None
    user = db.session.get(User, data.get('u') or 0)
    if user is None or user.password_fingerprint() != data.get('f'):
        return None
    return user


# ---------- Rate limits ----------
# Attempts are counted in the database so the limit holds across server processes.

def client_ip():
    return request.remote_addr or 'unknown'


def _bucket(name, value):
    return hashlib.sha256(f"{name}:{str(value).lower()}".encode()).hexdigest()


def is_limited(name, value):
    """True once `value` has used up its attempts for the limit called `name`."""
    if not current_app.config['RATELIMIT_ENABLED']:
        return False
    limit, window = current_app.config['RATE_LIMITS'][name]
    since = utcnow() - timedelta(seconds=window)
    used = RateLimitHit.query.filter(RateLimitHit.bucket == _bucket(name, value),
                                     RateLimitHit.created_at >= since).count()
    return used >= limit


def record_hit(name, value):
    """Count one attempt. The caller commits."""
    db.session.add(RateLimitHit(bucket=_bucket(name, value)))
    if random.random() < 0.02:
        # Occasionally clear out attempts too old to matter for any limit
        RateLimitHit.query.filter(RateLimitHit.created_at < utcnow() - timedelta(days=1)).delete()


def clear_hits(name, value):
    RateLimitHit.query.filter_by(bucket=_bucket(name, value)).delete()


# ---------- Permission checks ----------

def admin_required(view):
    """Only administrators may use this route. Checked on the server for every request."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('main.login', next=request.full_path))
        if not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def verification_notice():
    flash("Please confirm your email address first. We've put the details on your account page.", "warning")
    return redirect(url_for('main.account'))

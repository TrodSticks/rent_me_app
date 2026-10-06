import os

# Must be set before the app/routes modules are imported
os.environ['APP_ENV'] = 'development'
os.environ['DATABASE_URL'] = 'sqlite://'
os.environ['USE_LLM_SEARCH'] = '0'
os.environ['MAIL_BACKEND'] = 'memory'
os.environ.pop('MAIL_SERVER', None)
os.environ.pop('PUBLIC_BASE_URL', None)

import pytest
from flask import g
from app import create_app, db
from models import User, Property, utcnow


def make_user(username, role, verified=True, admin=False, password='pw123'):
    user = User(username=username, email=f'{username}@test.com', role=role, is_admin=admin,
                email_verified_at=utcnow() if verified else None)
    user.set_password(password)
    db.session.add(user)
    return user


@pytest.fixture
def app(tmp_path):
    app = create_app()
    app.config.update(TESTING=True, UPLOAD_FOLDER=str(tmp_path), WTF_CSRF_ENABLED=False)

    @app.before_request
    def forget_previous_request_user():
        # The fixture keeps one app context open for the whole test, and Flask-Login caches the
        # signed-in user on it. Clear it so each request works out who is signed in, as it would live.
        g.pop('_login_user', None)

    with app.app_context():
        landlord = make_user('landlord', 'Landlord')
        make_user('renter', 'Renter')
        db.session.add_all([
            Property(title='Cozy flat', description='Near the mall', price=3500,
                     location='Maun', bedrooms=2, property_type='flat', landlord=landlord),
            Property(title='Family house', description='Big garden', price=8000,
                     location='Gaborone', bedrooms=3, property_type='house', landlord=landlord),
            Property(title='Small house', description='Quiet street', price=2500,
                     location='Gaborone', bedrooms=2, property_type='house', landlord=landlord),
            Property(title='Big villa', description='Pool and view', price=15000,
                     location='Kasane', bedrooms=5, property_type='house', landlord=landlord),
        ])
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def login(client, email, password='pw123'):
    return client.post('/login', data={'email': email, 'password': password})


@pytest.fixture
def landlord_client(client):
    login(client, 'landlord@test.com')
    return client


@pytest.fixture
def renter_client(client):
    login(client, 'renter@test.com')
    return client


@pytest.fixture
def outbox(app):
    """Emails the app has sent during the test, oldest first."""
    return app.extensions.setdefault('mail_outbox', [])

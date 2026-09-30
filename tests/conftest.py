import os

# Must be set before the app/routes modules are imported
os.environ['DATABASE_URL'] = 'sqlite://'
os.environ['USE_LLM_SEARCH'] = '0'

import pytest
from app import create_app, db
from models import User, Property


@pytest.fixture
def app(tmp_path):
    app = create_app()
    app.config.update(TESTING=True, UPLOAD_FOLDER=str(tmp_path))
    with app.app_context():
        landlord = User(username='landlord', email='landlord@test.com', role='Landlord')
        landlord.set_password('pw123')
        renter = User(username='renter', email='renter@test.com', role='Renter')
        renter.set_password('pw123')
        db.session.add_all([landlord, renter])
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

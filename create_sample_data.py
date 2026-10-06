#!/usr/bin/env python3
"""
Sample data script for Rent Me application
This script creates demo users and properties for testing.

WARNING: it deletes everything in the database first. Never run it against real data.
"""
from datetime import date, timedelta

from app import create_app, db
from models import User, Property, utcnow

def add_sample_data():
    """Add the demo users and properties to the current (empty) database."""
    # Create demo users. Demo accounts start with a confirmed email so every feature can be tried.
    def demo_user(username, email, role):
        user = User(username=username, email=email, role=role, email_verified_at=utcnow())
        user.set_password('demo123')
        return user

    landlord1 = demo_user('john_landlord', 'landlord@demo.com', 'Landlord')
    landlord2 = demo_user('mary_properties', 'mary@demo.com', 'Landlord')
    renter1 = demo_user('alice_renter', 'renter@demo.com', 'Renter')
    renter2 = demo_user('bob_seeker', 'bob@demo.com', 'Renter')

    # Add users to database
    db.session.add_all([landlord1, landlord2, renter1, renter2])
    db.session.commit()

    # Create sample properties
    properties = [
        Property(
            title='Modern 2 Bedroom Apartment in Gaborone',
            description='Beautiful modern apartment with all amenities. Located in the heart of Gaborone with easy access to shopping centers, restaurants, and public transport. Features include air conditioning, modern kitchen, and secure parking.',
            price=4500, deposit=4500, bathrooms=1,
            location='Gaborone',
            bedrooms=2,
            property_type='flat',
            landlord=landlord1
        ),
        Property(
            title='Spacious Family House in Phakalane',
            description='Large family home perfect for families. Features a beautiful garden, 3 bedrooms, 2 bathrooms, and a double garage. Located in the prestigious Phakalane area with excellent schools nearby.',
            price=6800, deposit=6800, bathrooms=2,
            available_from=date.today() + timedelta(days=30),
            location='Phakalane',
            bedrooms=3,
            property_type='house',
            landlord=landlord1
        ),
        Property(
            title='Affordable Studio in Francistown',
            description='Cozy studio apartment perfect for students or young professionals. Fully furnished with kitchenette and private bathroom. Close to university and city center.',
            price=2200, deposit=0, bathrooms=1,
            location='Francistown',
            bedrooms=1,
            property_type='flat',
            landlord=landlord2
        ),
        Property(
            title='Luxury Villa in Gaborone',
            description='Stunning luxury villa with 4 bedrooms, swimming pool, and beautiful landscaped gardens. Premium location with 24/7 security. Perfect for executives and diplomats.',
            price=12000, deposit=24000, bathrooms=3,
            location='Gaborone',
            bedrooms=4,
            property_type='house',
            landlord=landlord2
        ),
        Property(
            title='Budget-Friendly House in Maun',
            description='Simple but comfortable 2 bedroom house in Maun. Great for those working in the tourism industry. Close to the airport and safari operators.',
            price=2800,
            location='Maun',
            bedrooms=2,
            property_type='house',
            landlord=landlord1
        ),
        Property(
            title='Modern Apartment in Kasane',
            description='Contemporary apartment with river views. Perfect for tourism professionals. Features modern appliances and is walking distance to restaurants and shops.',
            price=3500, bathrooms=1,
            location='Kasane',
            bedrooms=2,
            property_type='flat',
            landlord=landlord2
        ),
        Property(
            title='Family Home in Serowe',
            description='Traditional family home with modern updates. 3 bedrooms, large yard, and quiet neighborhood. Great for families looking for a peaceful environment.',
            price=3200, deposit=3200, bathrooms=2,
            location='Serowe',
            bedrooms=3,
            property_type='house',
            landlord=landlord1
        ),
        Property(
            title='Executive Apartment in Gaborone',
            description='High-end apartment in prime location. Features include gym access, swimming pool, and concierge service. Perfect for business executives.',
            price=8500, deposit=8500, bathrooms=2,
            location='Gaborone',
            bedrooms=3,
            property_type='flat',
            landlord=landlord2
        )
    ]

    amenities = [
        ['parking', 'air_conditioning', 'security'],
        ['parking', 'pet_friendly', 'water_included'],
        ['furnished', 'wifi'],
        ['parking', 'security', 'air_conditioning', 'wifi'],
        [],
        ['wifi', 'air_conditioning'],
        ['parking', 'pet_friendly'],
        ['parking', 'security', 'air_conditioning', 'wifi', 'furnished'],
    ]
    for property, keys in zip(properties, amenities):
        property.set_amenities(keys)

    # Add properties to database
    db.session.add_all(properties)
    db.session.commit()
    return properties


def create_sample_data():
    app = create_app()

    with app.app_context():
        # Clear existing data
        db.drop_all()
        db.create_all()

        properties = add_sample_data()

        print("Sample data created successfully!")
        print("\nDemo Accounts:")
        print("Landlord: landlord@demo.com / demo123")
        print("Landlord: mary@demo.com / demo123")
        print("Renter: renter@demo.com / demo123")
        print("Renter: bob@demo.com / demo123")
        print(f"\nCreated {len(properties)} sample properties")
        print("\nTo try the admin pages, make one of them an administrator:")
        print("  flask --app app make-admin landlord@demo.com")

if __name__ == '__main__':
    create_sample_data()

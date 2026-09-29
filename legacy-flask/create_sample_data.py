#!/usr/bin/env python3
"""
Sample data script for Rent Me application
This script creates demo users and properties for testing
"""

from app import create_app, db
from models import User, Property

def create_sample_data():
    app = create_app()
    
    with app.app_context():
        # Clear existing data
        db.drop_all()
        db.create_all()
        
        # Create demo users
        landlord1 = User(username='john_landlord', email='landlord@demo.com', role='Landlord')
        landlord1.set_password('demo123')
        
        landlord2 = User(username='mary_properties', email='mary@demo.com', role='Landlord')
        landlord2.set_password('demo123')
        
        renter1 = User(username='alice_renter', email='renter@demo.com', role='Renter')
        renter1.set_password('demo123')
        
        renter2 = User(username='bob_seeker', email='bob@demo.com', role='Renter')
        renter2.set_password('demo123')
        
        # Add users to database
        db.session.add_all([landlord1, landlord2, renter1, renter2])
        db.session.commit()
        
        # Create sample properties
        properties = [
            Property(
                title='Modern 2 Bedroom Apartment in Gaborone',
                description='Beautiful modern apartment with all amenities. Located in the heart of Gaborone with easy access to shopping centers, restaurants, and public transport. Features include air conditioning, modern kitchen, and secure parking.',
                price=4500,
                location='Gaborone',
                bedrooms=2,
                property_type='flat',
                landlord=landlord1
            ),
            Property(
                title='Spacious Family House in Phakalane',
                description='Large family home perfect for families. Features a beautiful garden, 3 bedrooms, 2 bathrooms, and a double garage. Located in the prestigious Phakalane area with excellent schools nearby.',
                price=6800,
                location='Phakalane',
                bedrooms=3,
                property_type='house',
                landlord=landlord1
            ),
            Property(
                title='Affordable Studio in Francistown',
                description='Cozy studio apartment perfect for students or young professionals. Fully furnished with kitchenette and private bathroom. Close to university and city center.',
                price=2200,
                location='Francistown',
                bedrooms=1,
                property_type='flat',
                landlord=landlord2
            ),
            Property(
                title='Luxury Villa in Gaborone',
                description='Stunning luxury villa with 4 bedrooms, swimming pool, and beautiful landscaped gardens. Premium location with 24/7 security. Perfect for executives and diplomats.',
                price=12000,
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
                price=3500,
                location='Kasane',
                bedrooms=2,
                property_type='flat',
                landlord=landlord2
            ),
            Property(
                title='Family Home in Serowe',
                description='Traditional family home with modern updates. 3 bedrooms, large yard, and quiet neighborhood. Great for families looking for a peaceful environment.',
                price=3200,
                location='Serowe',
                bedrooms=3,
                property_type='house',
                landlord=landlord1
            ),
            Property(
                title='Executive Apartment in Gaborone',
                description='High-end apartment in prime location. Features include gym access, swimming pool, and concierge service. Perfect for business executives.',
                price=8500,
                location='Gaborone',
                bedrooms=3,
                property_type='flat',
                landlord=landlord2
            )
        ]
        
        # Add properties to database
        db.session.add_all(properties)
        db.session.commit()
        
        print("Sample data created successfully!")
        print("\nDemo Accounts:")
        print("Landlord: landlord@demo.com / demo123")
        print("Landlord: mary@demo.com / demo123")
        print("Renter: renter@demo.com / demo123")
        print("Renter: bob@demo.com / demo123")
        print(f"\nCreated {len(properties)} sample properties")

if __name__ == '__main__':
    create_sample_data()


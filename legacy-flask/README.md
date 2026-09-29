# Rent Me - Property Rental Platform

A full-stack web application for property rentals in Botswana, featuring AI-powered search, user authentication, and messaging system.

## Features

### Core Features
- **User Authentication & Roles**: Separate experiences for Renters and Landlords
- **AI-Powered Search**: Natural language property search (e.g., "cheap 2 bedroom house in Gaborone")
- **Property Management**: Full CRUD operations for landlords
- **Favorites System**: Renters can save favorite properties
- **Private Messaging**: Two-way communication between renters and landlords
- **Responsive Design**: Modern, mobile-friendly interface

### For Landlords
- Dashboard with property statistics
- Add, edit, and delete property listings
- Manage property details (type, location, bedrooms, price)
- Receive and respond to messages from potential renters

### For Renters
- Browse all available properties
- AI-powered search with natural language queries
- Save favorite properties
- View detailed property information
- Contact landlords directly through messaging system

## Technology Stack

- **Backend**: Python Flask
- **Database**: SQLite with SQLAlchemy ORM
- **Frontend**: HTML5, CSS3, JavaScript, Bootstrap 5
- **AI/NLP**: spaCy for natural language processing
- **Authentication**: Flask-Login
- **Icons**: Font Awesome

## Installation & Setup

### Prerequisites
- Python 3.11+
- pip (Python package manager)

### Installation Steps

1. **Clone or extract the project**
   ```bash
   cd rent_me_app
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Create sample data (optional)**
   ```bash
   python create_sample_data.py
   ```

4. **Run the application**
   ```bash
   python app.py
   ```

5. **Access the application**
   Open your browser and go to `http://localhost:5000`

## Demo Accounts

The sample data script creates the following demo accounts:

### Landlords
- **Email**: landlord@demo.com | **Password**: demo123
- **Email**: mary@demo.com | **Password**: demo123

### Renters
- **Email**: renter@demo.com | **Password**: demo123
- **Email**: bob@demo.com | **Password**: demo123

## AI Search Examples

The AI-powered search understands natural language queries:

- "cheap 2 bedroom house in Gaborone"
- "affordable flat under P4000"
- "3 bedroom apartment in Phakalane"
- "luxury house in Gaborone"
- "studio apartment under P2000"

### Supported Search Parameters
- **Property Type**: house, flat, apartment
- **Bedrooms**: 1-10 bedrooms
- **Location**: Major cities in Botswana (Gaborone, Phakalane, Francistown, Maun, etc.)
- **Price**: Keywords like "cheap", "affordable", or specific amounts like "under P5000"

## File Structure

```
rent_me_app/
├── app.py                 # Main Flask application
├── config.py             # Configuration settings
├── models.py             # Database models
├── routes.py             # Application routes
├── search_engine.py      # AI search functionality
├── create_sample_data.py # Sample data generator
├── requirements.txt      # Python dependencies
├── templates/            # HTML templates
│   ├── base.html
│   ├── home.html
│   ├── login.html
│   ├── register.html
│   ├── landlord_dashboard.html
│   ├── create_property.html
│   ├── property_detail.html
│   ├── favorites.html
│   ├── inbox.html
│   ├── conversation.html
│   └── send_message.html
└── static/              # Static files
    ├── style.css        # Custom CSS
    ├── script.js        # JavaScript functionality
    └── property_pics/   # Property images
        └── default.jpg  # Default property image
```

## Key Features Implementation

### 1. User Authentication
- Secure password hashing using Werkzeug
- Role-based access control (Renter/Landlord)
- Session management with Flask-Login

### 2. AI-Powered Search
- Natural language processing using spaCy
- Intelligent parsing of search queries
- Support for property type, location, bedrooms, and price filters
- Real-time search suggestions

### 3. Property Management
- Full CRUD operations for landlords
- Image upload support (with default placeholder)
- Property categorization and filtering

### 4. Messaging System
- Real-time conversation threads
- Message read status tracking
- Property-specific messaging context
- Modern chat bubble interface

### 5. Responsive Design
- Bootstrap 5 framework
- Custom CSS for enhanced styling
- Mobile-friendly interface
- Modern card-based layouts

## Database Schema

### Users Table
- id, username, email, password_hash, role

### Properties Table
- id, title, description, price, location, bedrooms, property_type, image_file, landlord_id

### Messages Table
- id, sender_id, recipient_id, property_id, content, timestamp, read

### Favorites Table
- id, user_id, property_id, timestamp

## API Endpoints

### Authentication
- `GET/POST /register` - User registration
- `GET/POST /login` - User login
- `GET /logout` - User logout

### Properties
- `GET /` - Home page with property listings
- `GET /property/<id>` - Property details
- `GET/POST /property/new` - Create new property (landlords only)
- `GET/POST /property/<id>/update` - Update property (landlords only)
- `POST /property/<id>/delete` - Delete property (landlords only)

### Dashboard
- `GET /dashboard` - Landlord dashboard

### Favorites
- `GET /favorites` - User's favorite properties
- `POST /favorite/<id>` - Toggle favorite status

### Messaging
- `GET /inbox` - User's message inbox
- `GET/POST /message/<recipient_id>` - Send message
- `GET /conversation/<user_id>` - View conversation
- `POST /send_reply/<recipient_id>` - Send reply

### Search
- `GET /api/search-suggestions` - Get search suggestions

## Deployment Notes

For production deployment:

1. **Environment Variables**
   - Set `SECRET_KEY` environment variable
   - Configure production database URL

2. **Database**
   - Consider upgrading to PostgreSQL for production
   - Set up proper database migrations

3. **Web Server**
   - Use a production WSGI server like Gunicorn
   - Configure reverse proxy with Nginx

4. **Security**
   - Enable HTTPS
   - Configure proper CORS settings
   - Set up rate limiting

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is licensed under the MIT License.

## Support

For support or questions, please contact the development team.


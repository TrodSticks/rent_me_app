# Rent Me - Property Rental Platform

A full-stack web application for property rentals in Botswana, featuring AI-powered search, user authentication, and messaging system.

## Features

### Core Features
- **User Authentication & Roles**: Separate experiences for Renters and Landlords
- **AI-Powered Search**: Natural language property search (e.g., "cheap 2 bedroom house in Gaborone")
- **Property Management**: Full CRUD operations for landlords
- **Favorites System**: Renters can save favorite properties
- **Private Messaging**: Two-way communication between renters and landlords
- **Responsive Design**: Mobile-first interface with a bottom navigation bar on phones
- **Brand**: Rent Me icon and colour palette (Electric Blue `#0D6EFD`, Deep Navy `#0F172A`); all colours are defined once at the top of `static/style.css`

### For Landlords
- Dashboard with property statistics and a message count per listing
- Add, edit, and delete property listings, with photo upload (JPG, PNG, GIF, WebP up to 5 MB)
- Mark a property's exact spot on a map (optional; without it the listing shows somewhere in its town)
- Manage property details (type, location, bedrooms, price)
- Receive and respond to messages, grouped by property, with an inbox filter per listing

### For Renters
- Browse all available properties
- Filter by type, town, bedrooms and price range, and sort by price or newest
- AI-powered search with natural language queries
- Map view: opens on your last town (or asks you to pick one), shows a price pin for each property, groups pins that overlap, and loads only the part of the map on screen. Same search and filters as the list
- Save favorite properties

### For Everyone
- Account page to edit your username and email, change your password, and see recent conversations
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
   For spaCy-based search and the optional AI model, also run `pip install -r requirements-ai.txt`. Without them, search uses the rule-based parser.

3. **AI search model (optional, currently off by default)**
   ```bash
   python download_model.py
   ```
   This saves [LiquidAI/LFM2.5-350M](https://huggingface.co/LiquidAI/LFM2.5-350M) (~700 MB) into `LFM2.5-350M/`. Set `USE_LLM_SEARCH=1` to turn it on. Without it, search uses the rule-based parser only.

4. **Create sample data (optional)**
   ```bash
   python create_sample_data.py
   ```

5. **Run the application**
   ```bash
   python app.py
   ```

6. **Access the application**
   Open your browser and go to `http://localhost:5000`

### Hosted demo (Vercel)

`vercel_app.py` is the entry point on Vercel (set in `pyproject.toml`). It keeps the database and uploads in `/tmp` and loads the demo data on start-up, so changes made on the demo are temporary. Set `SECRET_KEY` in the Vercel project's environment variables so logins survive restarts.

### Database changes (migrations)

The app keeps its database up to date by itself: every time it starts, it applies any
changes in `migrations/versions/` that the database hasn't had yet. Existing data is kept.

When you change `models.py` (for example, add a column), create a migration for it:

```bash
flask --app app db migrate -m "describe the change"
```

Check the new file in `migrations/versions/`, then start the app as usual to apply it.
Set `AUTO_MIGRATE=0` if you would rather run `flask --app app db upgrade` by hand.

### Settings (environment variables)

| Variable | What it does | Default |
|---|---|---|
| `SECRET_KEY` | Signs login cookies. **Set this on any real server.** | A random key saved to a git-ignored `.secret_key` file |
| `FLASK_DEBUG` | Set to `1` for debug mode while developing. Never use it on a public server. | Off |
| `DATABASE_URL` | Database connection string | Local `app.db` SQLite file |
| `HOST` / `PORT` | Address and port the app listens on | `0.0.0.0` / `5000` |
| `USE_LLM_SEARCH` | Set to `1` to turn on the optional AI search model | Off |
| `AUTO_MIGRATE` | Set to `0` to stop the app updating the database when it starts | On |

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
├── llm_parser.py         # Optional LLM search parser (off by default)
├── download_model.py     # Downloads the optional LLM model
├── create_sample_data.py # Sample data generator
├── requirements.txt      # Python dependencies
├── migrations/           # Database changes, applied automatically at startup
├── tests/                # Pytest test suite
├── templates/            # HTML templates
│   ├── _macros.html      # Shared pieces such as the property card
│   ├── _search_controls.html  # Search box, chips and filters (list and map)
│   ├── map.html
│   ├── base.html
│   ├── account.html
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
    ├── style.css        # Design system: palette, components
    ├── manifest.webmanifest  # Lets phones add the app to the home screen
    ├── icons/           # App icon (SVG and PNG sizes)
    ├── script.js        # JavaScript functionality
    ├── map.js           # Map view (Leaflet + OpenStreetMap)
    ├── pin_picker.js    # Property form: mark a location on a map
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


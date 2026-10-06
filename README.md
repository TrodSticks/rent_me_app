# Rent Me - Property Rental Platform

A web application for renting property in Botswana. Renters search, filter and browse listings on a list or a map and message landlords. Landlords publish listings with photo galleries. Administrators handle reports and landlord verification.

Built with Flask, SQLAlchemy and Flask-Migrate.

## Features

### For renters
- Browse available properties as a list (12 per page) or on a map
- Plain-English search ("cheap 2 bedroom house in Gaborone with parking"), plus filters for type, town, bedrooms, bathrooms, price range and amenities
- Map view that opens on your last town, shows a price pin per property, groups pins that overlap and loads only the part of the map on screen
- Property pages with a swipeable photo gallery and full-screen viewer, monthly rent, security deposit, availability, bathrooms and amenities
- Save favourites, message landlords, and report a listing

### For landlords
- Dashboard with every listing, its status and its message count
- Listings with up to 10 photos: choose the cover, reorder and remove photos
- Listing details: status (available, reserved, rented), available-from date, security deposit, bathrooms and amenities
- Mark a property's exact spot on a map (optional; without it the listing shows somewhere in its town)
- Save a listing as a draft and publish it later
- Messages grouped by property

### Trust and accounts
- **Email verification.** New accounts get a link to confirm their email address. Unverified accounts can browse, manage their account and save draft listings, but cannot publish listings or start new conversations. This only shows that someone can read mail at the address; it is not an identity check.
- **Landlord verification.** A separate badge that only an administrator can grant or remove. The app records who approved it and when, and the badge explains what it does and does not mean. Rent Me does not collect identity or ownership documents.
- **Reporting.** Signed-in users can report a listing (suspected scam, misleading information, already rented, inappropriate content, or something else) with optional notes.
- **Admin area** (`/admin`). A queue of reports, where administrators record an outcome and can hide or restore listings. Hidden listings disappear from the list, the map, recommendations and favourites.
- **Password recovery.** "Forgot password" sends a link that works for 1 hour and only once.
- **Rate limits** on login, password reset, verification resend and reporting.

### Optional AI search
The rule-based search parser always runs. An optional local model (LiquidAI LFM2.5-350M) can fill in what the rules miss. It is off by default; see `USE_LLM_SEARCH` below.

## Setup

### Prerequisites
- Python 3.11+

### Steps

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```
   For spaCy-based search and the optional AI model, also run `pip install -r requirements-ai.txt`. Without them, search uses the rule-based parser.

2. **Create your local settings file**

   Copy `.env.example` to `.env`. For work on your own computer the one line that matters is:
   ```
   APP_ENV=development
   ```
   `.env` is ignored by git. Never commit it.

3. **Create sample data (optional).** This deletes everything in the database first.
   ```bash
   python create_sample_data.py
   ```

4. **Run the application**
   ```bash
   python app.py
   ```
   Open `http://localhost:5000`. The database is created or brought up to date automatically.

5. **Create the first administrator.** The account must already exist (sign up first, or use a demo account).
   ```bash
   flask --app app make-admin you@example.com
   ```
   Other commands: `flask --app app list-admins` and `flask --app app revoke-admin EMAIL`. These commands are the only way to grant admin access; nothing on the website can.

### Demo accounts

The sample data script creates these, all with the password `demo123` and a confirmed email:

- Landlords: `landlord@demo.com`, `mary@demo.com`
- Renters: `renter@demo.com`, `bob@demo.com`

## Email

Verification and password-reset emails are plain text and are sent through one of these backends:

| Backend | When it is used | What happens |
|---|---|---|
| `smtp` | `MAIL_SERVER` is set | Emails are sent through your mail server |
| `file` | `APP_ENV=development` and no `MAIL_SERVER` | Emails are saved in `mail_outbox/` and shown at `/dev/mailbox` |
| `disabled` | Production with no `MAIL_SERVER` | Nothing is sent; the site says so on the relevant pages |

### While developing

With `APP_ENV=development`, open `http://localhost:5000/dev/mailbox` to read the emails the app would have sent and open their links. That page only opens from the computer running the app, and does not exist in production. `mail_outbox/` is ignored by git.

### In production

Set these environment variables on the server (never in the repository):

```
APP_ENV=production
SECRET_KEY=<a long random value>
MAIL_SERVER=smtp.your-provider.example
MAIL_PORT=587
MAIL_USERNAME=<from your email provider>
MAIL_PASSWORD=<from your email provider>
MAIL_USE_TLS=1
MAIL_FROM=Rent Me <no-reply@your-domain.example>
PUBLIC_BASE_URL=https://your-domain.example
```

Any provider that offers SMTP works. Use `MAIL_USE_SSL=1` and `MAIL_PORT=465` if your provider needs SSL instead of STARTTLS.

**Not yet tested against a real mail server.** The SMTP code is exercised by automated tests using a stand-in server, and the development mailbox was tested by hand. After configuring a provider, sign up with a real address and check that the email arrives before relying on it.

Email bodies contain sign-in links, so the app never writes them to its log.

## Hosted demo (Vercel)

`vercel_app.py` is the entry point on Vercel (set in `pyproject.toml`). It keeps the database and uploads in `/tmp` and loads the demo data on start-up, so changes made on the demo are temporary, unless you connect Supabase as described below: then data and photos are kept, and the demo data is only loaded into an empty database. Set `SECRET_KEY` in the Vercel project's environment variables so logins survive restarts.

## Keeping data on a hosted site (Supabase)

On a host without a lasting disk, such as Vercel, the SQLite file and uploaded photos disappear whenever the host starts a fresh copy of the app. Point the app at Supabase to keep them: a Postgres database for accounts, listings and messages, and a Storage bucket for photos. Nothing changes on your own computer unless you set these variables.

### 1. In Supabase

1. Create a project at [supabase.com](https://supabase.com) and keep the database password it asks for somewhere safe.
2. **Database address.** Click **Connect**, choose **Transaction pooler**, and copy the connection string (it uses port 6543). Replace `[YOUR-PASSWORD]` with the database password. The pooler is the right choice for Vercel: the direct connection needs IPv6, which Vercel doesn't offer.
3. **Photo bucket.** Open **Storage**, create a bucket named `property-photos` and switch on **Public bucket**, so browsers can show the photos.
4. **Keys.** Open **Project Settings → API Keys** and note the **Project URL** and a server key: either the legacy **service_role** key or a new **secret** key (starts with `sb_secret_`). Either works.

### 2. In Vercel

In the Vercel project, open **Settings → Environment Variables** and add, for Production (and Preview if you want previews to share the data):

| Variable | Value |
|---|---|
| `DATABASE_URL` | The transaction pooler connection string from step 2 |
| `SUPABASE_URL` | The Project URL, e.g. `https://abcd1234.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | The service_role key |
| `SUPABASE_STORAGE_BUCKET` | Only if you named the bucket something other than `property-photos` |
| `SECRET_KEY` | A long random value, if it isn't set already |

Then redeploy. On its first start the app creates its tables in Supabase (one copy at a time, even when Vercel starts several) and from then on keeps them up to date.

### Good to know

- **The service_role key bypasses all of Supabase's access rules.** Keep it in the server's environment only: never in the repository, in front-end JavaScript, or in the phone app. The phone app uses the separate public (anon) key.
- **The tables are closed to Supabase's Data API.** Supabase lets anyone with the public anon key read tables through its Data API unless row level security is on. The app switches it on for all of its tables (migration `0004_lock_down_data_api`) with no policies, so the public key can't read them, while the app itself, which connects as the database owner, works as before.
- **`create_sample_data.py` deletes everything.** With `DATABASE_URL` pointing at Supabase it wipes the live data, so only run it against a database you mean to reset.
- **Photos already on a server's disk are not copied** to the bucket. Listings keep their filenames, so re-upload those photos (or copy the files into the bucket under the same names).

## Database changes (migrations)

The app keeps its database up to date by itself: every time it starts, it applies any migration in `migrations/versions/` that the database has not had yet. Existing data is kept. A database from before migrations existed is adopted automatically.

Useful commands:

```bash
flask --app app db current                      # which version the database is at
flask --app app db upgrade                      # apply pending migrations by hand
flask --app app db migrate -m "describe it"     # create a migration after changing models.py
flask --app app db downgrade 0002_property_coordinates   # go back one version
```

Set `AUTO_MIGRATE=0` to stop the app upgrading the database at startup and run `db upgrade` yourself.

Back up the database file before upgrading a live site.

## Tests

```bash
python -m pytest
```

The suite uses an in-memory database and a temporary folder for photos. It includes tests that generate a few thousand listings and count how many the app reads from the database, so a page that loaded everything and then discarded most of it would fail. The two tests that run the optional AI model are skipped unless you run `python -m pytest -m model`.

## Settings (environment variables)

These can go in `.env` or in the real environment. Real environment variables win.

| Variable | What it does | Default |
|---|---|---|
| `APP_ENV` | `development` or `production`. Development turns on the local mailbox and allows login cookies over http. | `production` |
| `SECRET_KEY` | Signs login cookies and emailed links. **Set this on any real server.** | A random key saved to a git-ignored `.secret_key` file |
| `DATABASE_URL` | Database connection string. `postgres://` and `postgresql://` addresses (as Supabase gives them) are used with the psycopg driver. | Local `app.db` SQLite file |
| `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` | Store photos in Supabase Storage instead of `static/property_pics/` (see "Keeping data on a hosted site") | Not set: photos stay on disk |
| `SUPABASE_STORAGE_BUCKET` | The public Storage bucket for photos | `property-photos` |
| `AUTO_MIGRATE` | Set to `0` to stop the app updating the database when it starts | On |
| `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USERNAME`, `MAIL_PASSWORD` | SMTP server details | None; port 587 |
| `MAIL_USE_TLS` / `MAIL_USE_SSL` | STARTTLS (port 587) or SSL (port 465) | TLS on, SSL off |
| `MAIL_FROM` | The "From" address on emails | `Rent Me <no-reply@localhost>` |
| `MAIL_BACKEND` | Force `smtp`, `file` or `disabled`. `file` is ignored outside development. | Chosen automatically |
| `PUBLIC_BASE_URL` | The site's public address, used in emailed links | The address of the request |
| `SESSION_COOKIE_SECURE` | Send the login cookie over https only | On, except in development |
| `TRUSTED_PROXY_COUNT` | Number of reverse proxies in front of the app, so visitor addresses are read correctly for rate limits | `0` |
| `HOST` / `PORT` | Address and port the app listens on | `0.0.0.0` / `5000` |
| `FLASK_DEBUG` | Set to `1` for debug mode while developing. Never on a public server. | Off |
| `USE_LLM_SEARCH` | Set to `1` to turn on the optional AI search model (run `python download_model.py` first, about 700 MB) | Off |

## Going live: checklist

1. Set `APP_ENV=production`, `SECRET_KEY`, the `MAIL_*` variables and `PUBLIC_BASE_URL`.
2. Serve the site over https. Login cookies are https-only in production.
3. Run it with a production server (for example Waitress or Gunicorn) rather than `python app.py`.
4. If the app sits behind a reverse proxy, set `TRUSTED_PROXY_COUNT`, or every visitor will appear to come from the proxy and share one rate limit.
5. Create the first administrator with `flask --app app make-admin`.
6. Sign up with a real email address and confirm the verification email arrives.
7. Uploaded photos are stored in `static/property_pics/` and the default database is a single SQLite file. Make sure your host keeps both between restarts, or use Supabase (see "Keeping data on a hosted site").
8. The map uses free OpenStreetMap tiles, which are fine for testing but not for heavy traffic. Choose a tile provider before launch.

## How the main pieces work

- **Search.** `search_engine.py` turns a plain-English search into validated filters (type, town, bedrooms, bathrooms, price, amenities, leftover keywords). `routes.search_conditions` combines those with the drop-down filters into one set of database conditions used by the list, the map and the town counts.
- **Pagination.** The list page runs one count query and one query for the 12 listings on the page, sorted with the listing id as a tie-breaker so pages never overlap.
- **Map.** Each listing has a stored map position: the landlord's exact pin, or a stable approximate spot near the town centre. `/api/map-pins` asks the database for the listings inside the visible area, capped at 300, with a separate count.
- **Visibility.** A listing is public when it is published, not hidden and available. Reserved and rented listings can still be opened directly and are labelled. Drafts and hidden listings can only be opened by their owner or an administrator.
- **Photos.** Uploads are checked, turned upright, shrunk to at most 1200 pixels and saved as JPEG, on disk or in Supabase Storage. The cover photo's filename is also kept on the listing so cards and map pins do not load the gallery.
- **Tokens.** Verification and reset links are signed with `SECRET_KEY` and expire (24 hours and 1 hour). A reset link stops working once the password changes, and a verification link stops working if the email address changes. Changing a password signs out the account's other sessions.
- **Rate limits.** Attempts are counted in the database (hashed, never raw emails or addresses), so limits hold across server processes.

## File structure

```
rent_me_app/
├── app.py                 # App factory, database preparation
├── config.py              # Settings, .env loading
├── models.py              # Database models and shared choices (statuses, amenities)
├── routes.py              # Browsing, search, map, favourites, messaging
├── listings.py            # Listing form, photos, property page, dashboard, reporting
├── accounts.py            # Sign-up, sign-in, email verification, password recovery
├── admin.py               # Report queue, hiding listings, landlord verification
├── cli.py                 # make-admin, revoke-admin, list-admins
├── security.py            # Emailed-link tokens, rate limits, password rules, permission checks
├── mailer.py              # Sending email (smtp, development mailbox)
├── photos.py              # Storing and removing photos (disk or Supabase Storage)
├── locations.py           # Towns and map positions
├── search_engine.py       # Plain-English search parser
├── llm_parser.py          # Optional LLM search parser (off by default)
├── download_model.py      # Downloads the optional LLM model
├── create_sample_data.py  # Demo accounts and listings (wipes the database)
├── .env.example           # Template for local settings
├── migrations/            # Database changes, applied automatically at startup
├── tests/                 # Pytest test suite
├── templates/             # HTML templates
└── static/
    ├── style.css          # Design system: palette, components
    ├── script.js          # Shared behaviour
    ├── map.js             # Map view (Leaflet + OpenStreetMap)
    ├── gallery.js         # Property page gallery and full-screen viewer
    ├── photo_manager.js   # Listing form: reorder, cover, remove, preview
    ├── pin_picker.js      # Listing form: mark a location on a map
    ├── manifest.webmanifest
    ├── icons/             # App icon (SVG and PNG sizes)
    └── property_pics/     # Uploaded photos (ignored by git, except default.jpg)
```

## Routes

### Browsing
- `GET /` - Listings, with search, filters and pagination
- `GET /map` - Map view
- `GET /api/map-pins?bbox=south,west,north,east` - Listings inside part of the map
- `GET /api/search-suggestions` - Search suggestions
- `GET /property/<id>` - Property page

### Accounts
- `GET/POST /register`, `GET/POST /login`, `GET /logout`
- `GET/POST /account`, `POST /account/password`
- `GET /verify-email/<token>`, `POST /verify-email/resend`
- `GET/POST /forgot-password`, `GET/POST /reset-password/<token>`
- `GET /dev/mailbox` - Development only

### Landlords
- `GET /dashboard`
- `GET/POST /property/new`, `GET/POST /property/<id>/update`
- `POST /property/<id>/status`, `POST /property/<id>/delete`

### Renters
- `GET /favorites`, `POST /favorite/<id>`
- `POST /property/<id>/report`

### Messaging
- `GET /inbox`, `GET /conversation/<user_id>`
- `GET/POST /message/<recipient_id>`, `POST /send_reply/<recipient_id>`

### Administrators
- `GET /admin/reports`, `POST /admin/reports/<id>/resolve`
- `POST /admin/listings/<id>/hide`, `POST /admin/listings/<id>/restore`
- `GET /admin/landlords`, `POST /admin/landlords/<id>/verify`, `POST /admin/landlords/<id>/revoke`

## License

This project is licensed under the MIT License.

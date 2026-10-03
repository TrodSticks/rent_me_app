"""Entry point for the hosted demo on Vercel.

Vercel's file system is read-only apart from /tmp, so the database and uploaded
photos live there. /tmp is wiped whenever Vercel starts a fresh copy of the
app, so the demo data is put back each time and anything added is temporary.
SECRET_KEY must be set in the Vercel project settings.
"""
import os

os.environ.setdefault('DATABASE_URL', 'sqlite:////tmp/rentme.db')
os.environ.setdefault('UPLOAD_FOLDER', '/tmp/property_pics')

from flask import send_from_directory

from app import create_app, db
from create_sample_data import add_sample_data
from models import User

app = create_app()

with app.app_context():
    if User.query.count() == 0:
        add_sample_data()

_serve_static = app.view_functions['static']


def static_with_uploads(filename):
    """Serve uploaded photos from the upload folder, everything else from static/."""
    prefix = 'property_pics/'
    if filename.startswith(prefix):
        name = filename[len(prefix):]
        if os.path.isfile(os.path.join(app.config['UPLOAD_FOLDER'], name)):
            return send_from_directory(app.config['UPLOAD_FOLDER'], name)
    return _serve_static(filename=filename)


app.view_functions['static'] = static_with_uploads

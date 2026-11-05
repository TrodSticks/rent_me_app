"""Local durability and paired database/photo restore; not a hosted redeploy test."""
import hashlib
import io
import shutil
import sqlite3

from app import create_app, db
from config import Config
from models import Property, PropertyPhoto, User
from photos import save_picture
from test_photos import JPG
from werkzeug.datastructures import FileStorage


def test_local_restart_and_paired_restore(tmp_path, monkeypatch):
    database = tmp_path / 'source.db'
    photos = tmp_path / 'photos'
    monkeypatch.setattr(Config, 'SQLALCHEMY_DATABASE_URI', f'sqlite:///{database}')
    monkeypatch.setattr(Config, 'UPLOAD_FOLDER', str(photos))
    app = create_app()
    with app.app_context():
        filename = save_picture(FileStorage(stream=io.BytesIO(JPG), filename='fixture.jpg'))
        owner = User(username='restore-owner', email='restore@example.test', role='Landlord')
        owner.set_password('restore-test-password')
        listing = Property(title='Restore fixture', description='Test only', price=1000,
                           location='Maun', bedrooms=1, landlord=owner, image_file=filename)
        listing.photos.append(PropertyPhoto(filename=filename, position=0))
        db.session.add(listing)
        db.session.commit()
        listing_id = listing.id
        db.session.remove()
        db.engine.dispose()
    digest = hashlib.sha256((photos / filename).read_bytes()).hexdigest()

    def check_restart():
        restarted = create_app()
        with restarted.app_context():
            saved = db.session.get(Property, listing_id)
            assert saved.title == 'Restore fixture'
            assert saved.photos[0].filename == filename
            assert saved.landlord.check_password('restore-test-password')
            assert hashlib.sha256((Config.UPLOAD_FOLDER / filename).read_bytes()).hexdigest() == digest
            db.session.remove()
            db.engine.dispose()

    monkeypatch.setattr(Config, 'UPLOAD_FOLDER', photos)
    check_restart()
    restored_database = tmp_path / 'restored.db'
    with sqlite3.connect(database) as source, sqlite3.connect(restored_database) as target:
        source.backup(target)
    restored_photos = tmp_path / 'restored-photos'
    shutil.copytree(photos, restored_photos)
    monkeypatch.setattr(Config, 'SQLALCHEMY_DATABASE_URI', f'sqlite:///{restored_database}')
    monkeypatch.setattr(Config, 'UPLOAD_FOLDER', restored_photos)
    check_restart()

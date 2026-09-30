import io
import os
from app import db
from models import Property, Favorite, Message, User

PNG = b'\x89PNG\r\n\x1a\n' + b'\x00' * 32
JPG = b'\xff\xd8\xff\xe0' + b'\x00' * 32


def property_form(**overrides):
    data = {'title': 'New place', 'description': 'Nice', 'price': '4000',
            'location': 'Gaborone', 'bedrooms': '2', 'property_type': 'flat'}
    data.update(overrides)
    return data


def test_new_property_with_photo(app, landlord_client):
    data = property_form(image=(io.BytesIO(PNG), 'photo.png'))
    resp = landlord_client.post('/property/new', data=data, content_type='multipart/form-data')
    assert resp.status_code == 302
    property = Property.query.filter_by(title='New place').one()
    assert property.image_file.endswith('.png')
    assert property.image_file != 'default.jpg'
    assert os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], property.image_file))


def test_new_property_without_photo_uses_default(landlord_client):
    landlord_client.post('/property/new', data=property_form(), content_type='multipart/form-data')
    assert Property.query.filter_by(title='New place').one().image_file == 'default.jpg'


def test_non_image_upload_is_rejected(app, landlord_client):
    data = property_form(image=(io.BytesIO(b'<script>alert(1)</script>'), 'evil.jpg'))
    resp = landlord_client.post('/property/new', data=data, content_type='multipart/form-data')
    html = resp.get_data(as_text=True)
    assert 'must be a JPG, PNG, GIF or WebP' in html
    assert 'value="New place"' in html  # form keeps what was typed
    assert Property.query.filter_by(title='New place').first() is None
    assert os.listdir(app.config['UPLOAD_FOLDER']) == []


def test_invalid_form_values_are_rejected(landlord_client):
    resp = landlord_client.post('/property/new', data=property_form(price='abc'),
                                content_type='multipart/form-data')
    assert 'valid monthly price' in resp.get_data(as_text=True)
    assert Property.query.filter_by(title='New place').first() is None


def test_updating_photo_replaces_old_file(app, landlord_client):
    property = Property.query.filter_by(title='Cozy flat').one()
    url = f'/property/{property.id}/update'
    form = property_form(title='Cozy flat')

    landlord_client.post(url, data={**form, 'image': (io.BytesIO(PNG), 'a.png')}, content_type='multipart/form-data')
    first = db.session.get(Property, property.id).image_file
    landlord_client.post(url, data={**form, 'image': (io.BytesIO(JPG), 'b.jpg')}, content_type='multipart/form-data')
    second = db.session.get(Property, property.id).image_file

    assert second.endswith('.jpg')
    assert os.listdir(app.config['UPLOAD_FOLDER']) == [second]
    assert first != second


def test_too_large_upload_shows_message(app, landlord_client):
    app.config['MAX_CONTENT_LENGTH'] = 1000
    data = property_form(image=(io.BytesIO(PNG + b'\x00' * 5000), 'big.png'))
    resp = landlord_client.post('/property/new', data=data, content_type='multipart/form-data',
                                follow_redirects=True)
    assert 'too large' in resp.get_data(as_text=True)


def test_delete_property_removes_photo_and_favorites(app, landlord_client):
    landlord_client.post('/property/new', data=property_form(image=(io.BytesIO(PNG), 'p.png')),
                         content_type='multipart/form-data')
    property = Property.query.filter_by(title='New place').one()
    renter = User.query.filter_by(role='Renter').one()
    db.session.add(Favorite(user_id=renter.id, property_id=property.id))
    db.session.add(Message(sender_id=renter.id, recipient_id=property.landlord_id,
                           property_id=property.id, content='Still available?'))
    db.session.commit()

    resp = landlord_client.post(f'/property/{property.id}/delete')
    assert resp.status_code == 302
    assert db.session.get(Property, property.id) is None
    assert Favorite.query.count() == 0
    # The message is kept, just no longer linked to the deleted listing
    assert Message.query.one().property_id is None
    assert os.listdir(app.config['UPLOAD_FOLDER']) == []

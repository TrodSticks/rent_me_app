import io
import os
from app import db
from PIL import Image
from models import Property, Favorite, Message, User


def make_image(fmt='PNG', size=(60, 40), mode='RGB'):
    buffer = io.BytesIO()
    Image.new(mode, size).save(buffer, fmt)
    return buffer.getvalue()


PNG = make_image('PNG')
JPG = make_image('JPEG')


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
    assert property.image_file.endswith('.jpg')  # every upload is stored as a JPEG
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


def uploaded_image(app, landlord_client, data, name):
    form = property_form(image=(io.BytesIO(data), name))
    landlord_client.post('/property/new', data=form, content_type='multipart/form-data')
    property = Property.query.filter_by(title='New place').first()
    if property is None:
        return None
    return Image.open(os.path.join(app.config['UPLOAD_FOLDER'], property.image_file))


def test_large_photo_is_shrunk(app, landlord_client):
    image = uploaded_image(app, landlord_client, make_image('JPEG', size=(4000, 3000)), 'big.jpg')
    assert image.size == (1200, 900)
    assert image.format == 'JPEG'


def test_small_photo_is_not_enlarged(app, landlord_client):
    image = uploaded_image(app, landlord_client, make_image('PNG', size=(300, 200)), 'small.png')
    assert image.size == (300, 200)


def test_transparent_png_is_converted(app, landlord_client):
    image = uploaded_image(app, landlord_client, make_image('PNG', mode='RGBA'), 'clear.png')
    assert image.mode == 'RGB'


def test_corrupt_image_is_rejected(app, landlord_client):
    broken = bytes([0x89]) + b'PNG' + bytes([13, 10, 26, 10]) + bytes(64)  # right header, not a real image
    assert uploaded_image(app, landlord_client, broken, 'broken.png') is None
    assert os.listdir(app.config['UPLOAD_FOLDER']) == []

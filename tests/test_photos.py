import io
import os
from PIL import Image
from app import db
from conftest import login, make_user
from models import Property, PropertyPhoto, Favorite, Message, User


def make_image(fmt='PNG', size=(60, 40), mode='RGB', colour=None):
    buffer = io.BytesIO()
    Image.new(mode, size, colour).save(buffer, fmt)
    return buffer.getvalue()


PNG = make_image('PNG')
JPG = make_image('JPEG')


def property_form(**overrides):
    data = {'title': 'New place', 'description': 'Nice', 'price': '4000',
            'location': 'Gaborone', 'bedrooms': '2', 'property_type': 'flat'}
    data.update(overrides)
    return data


def upload(name='photo.png', data=PNG):
    return (io.BytesIO(data), name)


def post(client, url, **fields):
    return client.post(url, data=property_form(**fields), content_type='multipart/form-data')


def stored(app):
    return sorted(os.listdir(app.config['UPLOAD_FOLDER']))


def new_listing(client, count=1, **fields):
    """Create a listing with `count` photos and return it."""
    post(client, '/property/new', photos=[upload(f'p{i}.png') for i in range(count)], **fields)
    return Property.query.filter_by(title=fields.get('title', 'New place')).one()


def filenames(property):
    db.session.expire_all()
    return [photo.filename for photo in db.session.get(Property, property.id).photos]


# ---------- Uploading ----------

def test_new_property_with_photo(app, landlord_client):
    resp = post(landlord_client, '/property/new', photos=[upload()])
    assert resp.status_code == 302
    property = Property.query.filter_by(title='New place').one()
    assert property.image_file.endswith('.jpg')  # every upload is stored as a JPEG
    assert property.image_file != 'default.jpg'
    assert stored(app) == [property.image_file]
    assert filenames(property) == [property.image_file]


def test_new_property_without_photo_uses_default(landlord_client):
    post(landlord_client, '/property/new')
    property = Property.query.filter_by(title='New place').one()
    assert property.image_file == 'default.jpg'
    assert property.photos == []


def test_old_single_photo_field_still_works(app, landlord_client):
    post(landlord_client, '/property/new', image=upload())
    assert len(stored(app)) == 1


def test_several_photos_in_one_upload_keep_their_order(app, landlord_client):
    property = new_listing(landlord_client, count=4)
    photos = filenames(property)
    assert len(photos) == 4 and len(set(photos)) == 4
    assert [photo.position for photo in property.photos] == [0, 1, 2, 3]
    # The first one chosen is the cover, used on cards and map pins
    assert property.image_file == photos[0]


def test_ten_photos_are_allowed_and_eleven_are_not(app, landlord_client):
    property = new_listing(landlord_client, count=10)
    assert len(filenames(property)) == 10

    resp = post(landlord_client, f'/property/{property.id}/update', photos=[upload('extra.png')])
    assert 'up to 10 photos' in resp.get_data(as_text=True)
    assert len(filenames(property)) == 10
    assert len(stored(app)) == 10


def test_eleven_photos_in_a_new_listing_are_rejected(app, landlord_client):
    resp = post(landlord_client, '/property/new', photos=[upload(f'p{i}.png') for i in range(11)])
    assert 'up to 10 photos' in resp.get_data(as_text=True)
    assert Property.query.filter_by(title='New place').first() is None
    assert stored(app) == []


def test_removing_makes_room_for_new_photos(app, landlord_client):
    property = new_listing(landlord_client, count=10)
    first = property.photos[0]
    resp = post(landlord_client, f'/property/{property.id}/update',
                remove_photos=[str(first.id)], photos=[upload('new.png')])
    assert resp.status_code == 302
    assert len(filenames(property)) == 10
    assert first.filename not in stored(app)


# ---------- Validation ----------

def test_non_image_upload_is_rejected(app, landlord_client):
    resp = post(landlord_client, '/property/new', photos=[upload('evil.jpg', b'<script>alert(1)</script>')])
    html = resp.get_data(as_text=True)
    assert "isn&#39;t a photo we can read" in html
    assert 'value="New place"' in html  # form keeps what was typed
    assert Property.query.filter_by(title='New place').first() is None
    assert stored(app) == []


def test_one_bad_photo_rejects_the_whole_upload_and_leaves_no_files(app, landlord_client):
    resp = post(landlord_client, '/property/new',
                photos=[upload('good.png'), upload('bad.png', b'not an image'), upload('good2.png')])
    assert 'bad.png' in resp.get_data(as_text=True)
    assert stored(app) == []


def test_corrupt_image_is_rejected(app, landlord_client):
    broken = bytes([0x89]) + b'PNG' + bytes([13, 10, 26, 10]) + bytes(64)  # right header, not a real image
    post(landlord_client, '/property/new', photos=[upload('broken.png', broken)])
    assert Property.query.filter_by(title='New place').first() is None
    assert stored(app) == []


def test_photo_over_five_megabytes_is_rejected(app, landlord_client):
    app.config['MAX_IMAGE_BYTES'] = 2000
    big = make_image('PNG', size=(400, 400)) + bytes(3000)
    resp = post(landlord_client, '/property/new', photos=[upload('ok.png'), upload('huge.png', big)])
    assert 'huge.png is larger than 5 MB' in resp.get_data(as_text=True)
    assert stored(app) == []


def test_request_limit_fits_a_full_set_of_photos(app):
    assert app.config['MAX_CONTENT_LENGTH'] >= app.config['MAX_PHOTOS'] * app.config['MAX_IMAGE_BYTES']


def test_too_large_request_shows_message(app, landlord_client):
    app.config['MAX_CONTENT_LENGTH'] = 1000
    resp = landlord_client.post('/property/new', data=property_form(photos=[upload('big.png', PNG + bytes(5000))]),
                                content_type='multipart/form-data', follow_redirects=True)
    assert 'too large' in resp.get_data(as_text=True)


def test_invalid_form_values_are_rejected(landlord_client):
    resp = post(landlord_client, '/property/new', price='abc')
    assert 'valid monthly price' in resp.get_data(as_text=True)
    assert Property.query.filter_by(title='New place').first() is None


def test_invalid_form_does_not_store_its_photos(app, landlord_client):
    post(landlord_client, '/property/new', price='abc', photos=[upload()])
    assert stored(app) == []


# ---------- Compression and orientation ----------

def uploaded_image(app, landlord_client, data, name):
    post(landlord_client, '/property/new', photos=[upload(name, data)])
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


def test_sideways_phone_photo_is_turned_upright(app, landlord_client):
    # A landscape image tagged "rotate 90 degrees", as phone cameras save portrait photos
    source = Image.new('RGB', (80, 40), 'red')
    exif = source.getexif()
    exif[0x0112] = 6
    buffer = io.BytesIO()
    source.save(buffer, 'JPEG', exif=exif)
    image = uploaded_image(app, landlord_client, buffer.getvalue(), 'phone.jpg')
    assert image.size == (40, 80)


# ---------- Cover, order and removal ----------

def test_reordering_changes_the_cover(app, landlord_client):
    property = new_listing(landlord_client, count=3)
    a, b, c = property.photos
    post(landlord_client, f'/property/{property.id}/update', photo_order=[str(c.id), str(a.id), str(b.id)])
    assert filenames(property) == [c.filename, a.filename, b.filename]
    assert db.session.get(Property, property.id).image_file == c.filename


def test_choosing_a_cover_moves_it_first(app, landlord_client):
    property = new_listing(landlord_client, count=3)
    a, b, c = property.photos
    post(landlord_client, f'/property/{property.id}/update', cover_photo=str(b.id))
    assert filenames(property) == [b.filename, a.filename, c.filename]
    assert db.session.get(Property, property.id).image_file == b.filename


def test_removing_the_cover_promotes_the_next_photo(app, landlord_client):
    property = new_listing(landlord_client, count=3)
    a, b, c = property.photos
    post(landlord_client, f'/property/{property.id}/update', remove_photos=[str(a.id)])
    assert filenames(property) == [b.filename, c.filename]
    assert db.session.get(Property, property.id).image_file == b.filename
    assert stored(app) == sorted([b.filename, c.filename])


def test_removing_every_photo_goes_back_to_the_placeholder(app, landlord_client):
    property = new_listing(landlord_client, count=2)
    post(landlord_client, f'/property/{property.id}/update',
         remove_photos=[str(photo.id) for photo in property.photos])
    assert filenames(property) == []
    assert db.session.get(Property, property.id).image_file == 'default.jpg'
    assert stored(app) == []


def test_new_photos_are_added_after_existing_ones(app, landlord_client):
    property = new_listing(landlord_client, count=2)
    before = filenames(property)
    post(landlord_client, f'/property/{property.id}/update', photos=[upload('later.png')])
    after = filenames(property)
    assert after[:2] == before and len(after) == 3
    assert db.session.get(Property, property.id).image_file == before[0]


def test_saving_without_touching_photos_keeps_them(app, landlord_client):
    property = new_listing(landlord_client, count=3)
    before = filenames(property)
    post(landlord_client, f'/property/{property.id}/update', title='New place')
    assert filenames(property) == before
    assert stored(app) == sorted(before)


def test_failed_edit_keeps_old_photos_and_drops_new_ones(app, landlord_client):
    property = new_listing(landlord_client, count=2)
    before = filenames(property)
    post(landlord_client, f'/property/{property.id}/update', price='abc',
         remove_photos=[str(property.photos[0].id)], photos=[upload('extra.png')])
    assert filenames(property) == before
    assert stored(app) == sorted(before)


# ---------- Ownership ----------

def test_another_landlord_cannot_change_photos(app, client):
    login(client, 'landlord@test.com')
    property = new_listing(client, count=2)
    before = filenames(property)
    client.get('/logout')

    make_user('other', 'Landlord')
    db.session.commit()
    login(client, 'other@test.com')
    resp = post(client, f'/property/{property.id}/update',
                remove_photos=[str(photo.id) for photo in property.photos], photos=[upload('mine.png')])
    assert resp.status_code == 302
    assert filenames(property) == before
    assert stored(app) == sorted(before)


def test_photo_ids_from_another_listing_are_ignored(app, landlord_client):
    mine = new_listing(landlord_client, count=2, title='Mine')
    other = new_listing(landlord_client, count=2, title='Other')
    other_before = filenames(other)
    post(landlord_client, f'/property/{mine.id}/update', title='Mine',
         remove_photos=[str(photo.id) for photo in other.photos],
         photo_order=[str(other.photos[0].id)], cover_photo=str(other.photos[1].id))
    assert filenames(other) == other_before
    assert len(filenames(mine)) == 2
    assert len(stored(app)) == 4


def test_renter_cannot_upload(app, renter_client):
    resp = post(renter_client, '/property/new', photos=[upload()])
    assert resp.status_code == 302
    assert stored(app) == []


def test_logged_out_visitor_cannot_upload(app, client):
    property = Property.query.first()
    resp = post(client, f'/property/{property.id}/update', photos=[upload()])
    assert resp.status_code == 302 and '/login' in resp.headers['Location']
    assert stored(app) == []


# ---------- Deleting ----------

def test_delete_property_removes_photos_and_favorites(app, landlord_client):
    property = new_listing(landlord_client, count=3)
    renter = User.query.filter_by(role='Renter').one()
    db.session.add(Favorite(user_id=renter.id, property_id=property.id))
    db.session.add(Message(sender_id=renter.id, recipient_id=property.landlord_id,
                           property_id=property.id, content='Still available?'))
    db.session.commit()

    resp = landlord_client.post(f'/property/{property.id}/delete')
    assert resp.status_code == 302
    assert db.session.get(Property, property.id) is None
    assert Favorite.query.count() == 0
    assert PropertyPhoto.query.count() == 0
    # The message is kept, just no longer linked to the deleted listing
    assert Message.query.one().property_id is None
    assert stored(app) == []


# ---------- Showing the gallery ----------

def test_property_page_shows_every_photo_and_a_viewer(app, landlord_client):
    property = new_listing(landlord_client, count=3)
    html = landlord_client.get(f'/property/{property.id}').get_data(as_text=True)
    for filename in filenames(property):
        assert html.count(f'property_pics/{filename}') == 2   # the large photo and its thumbnail
    assert 'id="viewer"' in html and 'gallery.js' in html
    assert '1 / 3' in html


def test_single_photo_has_no_thumbnails(app, landlord_client):
    property = new_listing(landlord_client, count=1)
    html = landlord_client.get(f'/property/{property.id}').get_data(as_text=True)
    assert 'id="gallery-thumbs"' not in html
    assert 'id="viewer"' in html


def test_listing_without_photos_shows_the_placeholder(app, client):
    property = Property.query.filter_by(title='Cozy flat').one()
    html = client.get(f'/property/{property.id}').get_data(as_text=True)
    assert 'property_pics/default.jpg' in html
    assert 'id="viewer"' not in html


def test_cards_and_map_use_the_cover_photo(app, landlord_client):
    property = new_listing(landlord_client, count=3)
    a, b, c = property.photos
    post(landlord_client, f'/property/{property.id}/update', cover_photo=str(c.id))
    cover = db.session.get(Property, property.id).image_file
    assert cover == c.filename

    assert f'property_pics/{cover}' in landlord_client.get('/').get_data(as_text=True)
    pins = landlord_client.get('/api/map-pins?bbox=-27,19.9,-17.5,29.5').get_json()['pins']
    assert next(pin for pin in pins if pin['id'] == property.id)['photo'].endswith(cover)

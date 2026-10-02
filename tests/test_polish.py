import re
from app import db
from models import Property, User


def titles(html):
    return re.findall(r'<h5 class="card-title">(.*?)</h5>', html)


def add_listings(count):
    landlord = User.query.filter_by(role='Landlord').one()
    db.session.add_all([
        Property(title=f'Listing {i:02d}', description='Extra', price=1000 + i, location='Serowe',
                 bedrooms=1, property_type='flat', landlord=landlord)
        for i in range(count)
    ])
    db.session.commit()


# ---------- Pagination ----------

def test_no_page_links_when_everything_fits(client):
    html = client.get('/').get_data(as_text=True)
    assert len(titles(html)) == 4
    assert 'aria-label="Listing pages"' not in html


def test_listings_are_split_into_pages(app, client):
    add_listings(30)  # 34 in total
    assert len(titles(client.get('/').get_data(as_text=True))) == 12
    assert len(titles(client.get('/?page=2').get_data(as_text=True))) == 12
    last = client.get('/?page=3').get_data(as_text=True)
    assert len(titles(last)) == 10
    assert 'Page 3 of 3' in last


def test_pages_do_not_repeat_listings(app, client):
    add_listings(30)
    seen = []
    for page in (1, 2, 3):
        seen += titles(client.get(f'/?page={page}').get_data(as_text=True))
    assert len(seen) == len(set(seen)) == 34


def test_out_of_range_page_is_clamped(app, client):
    add_listings(30)
    assert 'Page 3 of 3' in client.get('/?page=99').get_data(as_text=True)
    assert 'Page 1 of 3' in client.get('/?page=-5').get_data(as_text=True)
    assert client.get('/?page=abc').status_code == 200


def test_page_links_keep_filters(app, client):
    add_listings(30)
    html = client.get('/?location=Serowe&sort=price_asc').get_data(as_text=True)
    assert 'Found <strong>30</strong>' in html
    link = re.search(r'href="([^"]*page=2[^"]*)"', html).group(1).replace('&amp;', '&')
    assert 'location=Serowe' in link and 'sort=price_asc' in link
    second = titles(client.get(link).get_data(as_text=True))
    assert second[0] == 'Listing 12'


# ---------- Similar properties ----------

def similar_titles(client, title):
    property = Property.query.filter_by(title=title).one()
    html = client.get(f'/property/{property.id}').get_data(as_text=True)
    return re.findall(r'similar-title">(.*?)</h5>', html)


def test_similar_ranks_same_town_first(app, client):
    # Small house: Gaborone, house, 2 bedrooms, P2500
    assert similar_titles(client, 'Small house') == ['Family house', 'Big villa', 'Cozy flat']


def test_similar_never_includes_itself(app, client):
    assert 'Family house' not in similar_titles(client, 'Family house')


def test_similar_shows_at_most_three(app, client):
    add_listings(10)
    assert len(similar_titles(client, 'Listing 00')) == 3


def test_no_similar_properties_message(app, client):
    Property.query.filter(Property.title != 'Cozy flat').delete()
    db.session.commit()
    property = Property.query.one()
    html = client.get(f'/property/{property.id}').get_data(as_text=True)
    assert 'No similar properties right now' in html

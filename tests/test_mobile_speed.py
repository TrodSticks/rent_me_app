import io
from uuid import uuid4
from PIL import Image
from sqlalchemy import event
from app import db
from models import Message, User

JSON = {'Accept': 'application/json'}


def test_retry_is_one_message_and_conflicting_reuse_rejected(app, renter_client):
    landlord = User.query.filter_by(role='Landlord').one()
    token = str(uuid4())
    url = f'/message/{landlord.id}'
    body = {'content': 'Hello', 'client_token': token}
    first = renter_client.post(url, data=body, headers=JSON)
    second = renter_client.post(url, data=body, headers=JSON)
    assert first.status_code == second.status_code == 200
    assert first.json['message']['id'] == second.json['message']['id']
    assert Message.query.count() == 1
    conflict = renter_client.post(url, data={**body, 'content': 'Changed'}, headers=JSON)
    assert conflict.status_code == 409
    assert renter_client.post(url, data={**body, 'client_token': str(uuid4())}, headers=JSON).status_code == 200
    assert Message.query.count() == 2


def test_reply_returns_small_json_and_same_id_on_retry(app, renter_client):
    landlord = User.query.filter_by(role='Landlord').one()
    renter_client.post(f'/message/{landlord.id}', data={'content': 'Start'})
    url = f'/send_reply/{landlord.id}'
    body = {'content': '<script>not executable</script>', 'client_token': str(uuid4())}
    first = renter_client.post(url, data=body, headers=JSON)
    retry = renter_client.post(url, data=body, headers=JSON)
    assert first.json['message']['id'] == retry.json['message']['id']
    assert len(first.data) < 1000
    assert first.headers['Cache-Control'] == 'private, no-store'
    assert renter_client.post(url, data={'content': 'Missing token'}, headers=JSON).status_code == 400
    assert renter_client.post(url, data={**body, 'client_token': 'bad'}, headers=JSON).status_code == 400


def test_history_is_bounded_and_older_messages_remain_available(app, renter_client):
    landlord = User.query.filter_by(role='Landlord').one()
    renter = User.query.filter_by(role='Renter').one()
    landlord_id = landlord.id
    db.session.add_all([Message(sender_id=landlord_id, recipient_id=renter.id, content=f'History {i}') for i in range(120)])
    db.session.commit()
    url = f'/conversation/{landlord_id}'
    newest = renter_client.get(url, headers=JSON).json
    assert len(newest['messages']) == 50 and newest['more']
    older = renter_client.get(url + f"?before={newest['messages'][0]['id']}", headers=JSON).json
    assert len(older['messages']) == 50
    assert {m['id'] for m in newest['messages']}.isdisjoint(m['id'] for m in older['messages'])
    assert renter_client.get(url + f"?after={newest['messages'][-1]['id']}", headers=JSON).json['messages'] == []


def test_inbox_and_account_load_only_thread_summaries(app, renter_client):
    landlord = User.query.filter_by(role='Landlord').one()
    renter = User.query.filter_by(role='Renter').one()
    db.session.add_all([Message(sender_id=landlord.id, recipient_id=renter.id, content=f'Bulk {i}') for i in range(1000)])
    db.session.commit()
    for path in ['/inbox', '/account']:
        db.session.expunge_all()
        loaded = []
        def watch(target, context):
            loaded.append(target.id)
        event.listen(Message, 'load', watch)
        try:
            response = renter_client.get(path)
        finally:
            event.remove(Message, 'load', watch)
        assert response.status_code == 200
        assert len(loaded) == 1
        assert b'Bulk 999' in response.data


def test_versioned_assets_cache_but_private_pages_do_not(app, client, renter_client):
    import re
    html = renter_client.get('/account')
    assert html.headers['Cache-Control'] == 'private, no-store'
    path = re.search(r'href="([^"]+/style.css)"', html.text).group(1)
    asset = client.get(path)
    assert asset.status_code == 200
    assert 'immutable' in asset.headers['Cache-Control']
    assert 'Set-Cookie' not in asset.headers
    assert client.get(path.replace('/assets/', '/assets/wrong')).status_code == 404


def test_thumbnail_dimensions_cache_and_fallback(app, client, tmp_path):
    image = Image.effect_noise((1200, 900), 80).convert('RGB')
    source = tmp_path / 'example.jpg'
    image.save(source, 'JPEG', quality=90)
    response = client.get('/thumb/v1/320/example.jpg')
    assert response.status_code == 200
    with Image.open(io.BytesIO(response.data)) as preview:
        assert preview.size == (320, 240)
        assert preview.format == 'WEBP'
    assert len(response.data) < source.stat().st_size / 4
    assert 'public' in response.headers['Cache-Control']
    assert 'Set-Cookie' not in response.headers
    assert client.get('/thumb/v1/200/example.jpg').status_code == 404
    missing = client.get('/thumb/v1/320/missing.jpg')
    assert missing.status_code == 302
    assert missing.headers['Cache-Control'] == 'no-store'


def test_submission_constraint_and_account_scope(app, renter_client):
    import pytest
    from sqlalchemy.exc import IntegrityError
    token = str(uuid4())
    db.session.add(Message(sender_id=1, recipient_id=2, content='First', client_token=token))
    db.session.commit()
    db.session.add(Message(sender_id=1, recipient_id=2, content='Duplicate', client_token=token))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()
    # Another account's token must neither expose nor reuse the first account's message.
    response = renter_client.post('/message/1', headers=JSON,
        data={'content': 'Separate sender', 'client_token': token})
    assert response.status_code == 200
    assert response.json['message']['content'] == 'Separate sender'
    assert Message.query.count() == 2


def test_json_send_checks_csrf_and_empty_content(app, renter_client):
    response = renter_client.post('/message/1', headers=JSON,
                                 data={'content': ' ', 'client_token': str(uuid4())})
    assert response.status_code == 400
    app.config['WTF_CSRF_ENABLED'] = True
    response = renter_client.post('/message/1', headers=JSON,
                                 data={'content': 'Hello', 'client_token': str(uuid4())})
    assert response.status_code == 400
    assert response.is_json
    assert Message.query.count() == 0

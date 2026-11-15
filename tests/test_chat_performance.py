"""Keep conversation rendering from issuing one database query per message."""
import pytest
from sqlalchemy import event
from app import db
from models import Message, User


@pytest.mark.parametrize('size', [5, 50])
@pytest.mark.parametrize('with_property', [False, True])
def test_chat_queries_do_not_grow_with_history(app, renter_client, size, with_property):
    renter = User.query.filter_by(role='Renter').one()
    landlord = User.query.filter_by(role='Landlord').one()
    recipient_id = landlord.id
    property_id = landlord.properties[0].id if with_property else None
    db.session.add_all([
        Message(sender_id=landlord.id, recipient_id=renter.id, content=f'Example {i}',
                property_id=property_id)
        for i in range(size)
    ])
    db.session.commit()
    db.session.remove()
    statements = []

    def record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(db.engine, 'before_cursor_execute', record)
    try:
        path = f'/conversation/{recipient_id}'
        if property_id:
            path += f'?property_id={property_id}'
        response = renter_client.get(path)
    finally:
        event.remove(db.engine, 'before_cursor_execute', record)
    assert response.status_code == 200
    assert f'Example {size - 1}' in response.get_data(as_text=True)
    limit = 9 if with_property else 7
    assert len(statements) <= limit, f'{size} messages caused {len(statements)} database statements'

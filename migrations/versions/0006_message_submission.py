"""Make retrying a message submission safe across workers and connections."""
from alembic import op
import sqlalchemy as sa

revision = '0006_message_submission'
down_revision = '0005_photo_uploads'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('message') as batch:
        batch.add_column(sa.Column('client_token', sa.String(36), nullable=True))
        batch.create_unique_constraint('uq_message_submission', ['sender_id', 'client_token'])


def downgrade():
    with op.batch_alter_table('message') as batch:
        batch.drop_constraint('uq_message_submission', type_='unique')
        batch.drop_column('client_token')

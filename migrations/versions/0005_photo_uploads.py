"""Track scoped, single-use direct photo uploads and abandoned objects."""
from alembic import op
import sqlalchemy as sa

revision = '0005_photo_uploads'
down_revision = '0004_lock_down_data_api'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('photo_upload',
        sa.Column('id', sa.String(32), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('listing_id', sa.Integer(), nullable=True),
        sa.Column('filename', sa.String(40), nullable=False, unique=True),
        sa.Column('digest', sa.String(64), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('claimed', sa.Boolean(), nullable=False))
    op.create_index('ix_photo_upload_user_id', 'photo_upload', ['user_id'])
    op.create_index('ix_photo_upload_created_at', 'photo_upload', ['created_at'])
    if op.get_bind().dialect.name == 'postgresql':
        op.execute('ALTER TABLE photo_upload ENABLE ROW LEVEL SECURITY')


def downgrade():
    op.drop_table('photo_upload')

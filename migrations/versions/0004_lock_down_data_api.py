"""turn on row level security on Postgres

Supabase publishes every table in the public schema through its Data API, which anyone holding
the project's public (anon) key can call. The app connects as the database owner, which row level
security doesn't restrict, so switching it on with no policies closes that door and changes
nothing for the app. SQLite has no such API, so there this migration does nothing.

Revision ID: 0004_lock_down_data_api
Revises: 0003_gallery_details_trust
Create Date: 2026-10-06 19:00:00.000000

"""
from alembic import op

from app import enable_row_level_security


# revision identifiers, used by Alembic.
revision = '0004_lock_down_data_api'
down_revision = '0003_gallery_details_trust'
branch_labels = None
depends_on = None


def upgrade():
    enable_row_level_security(op.get_bind())


def downgrade():
    # Leaving row level security on is harmless to the app and safer than opening the tables up
    pass

"""add service_suburbs to tradie_preferences

Revision ID: 003_add_service_suburbs
Revises: 002_tradie_preferences

This migration is safe to run even if tradie_preferences already exists.
It ONLY adds the service_suburbs column — does NOT recreate the table.
"""
import sqlalchemy as sa

from alembic import op

revision      = "003_add_service_suburbs"
down_revision = "002_tradie_preferences"
branch_labels = None
depends_on    = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_cols = [c['name'] for c in inspector.get_columns('tradie_preferences')]
    if 'service_suburbs' not in existing_cols:
        op.add_column(
            "tradie_preferences",
            sa.Column("service_suburbs", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("tradie_preferences", "service_suburbs")

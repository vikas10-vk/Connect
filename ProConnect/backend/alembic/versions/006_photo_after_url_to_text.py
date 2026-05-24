"""photo_after_url varchar(500) -> text (supports JSON array of up to 3 URLs)

Revision ID: 006_photo_after_url_to_text
Revises: f1e2d3c4b5a6
Create Date: 2026-05-14
"""
import sqlalchemy as sa

from alembic import op

revision = '006_photo_after_url_to_text'
down_revision = 'f1e2d3c4b5a6'
branch_labels = None
depends_on = None


def upgrade():
    # Change photo_after_url from VARCHAR(500) to TEXT so it can store a
    # JSON-encoded array of up to 3 completion photo URLs.
    op.alter_column(
        'jobs',
        'photo_after_url',
        type_=sa.Text(),
        existing_type=sa.String(500),
        existing_nullable=True,
    )


def downgrade():
    # Revert to VARCHAR(500) — truncation risk if any row already holds >500 chars.
    op.alter_column(
        'jobs',
        'photo_after_url',
        type_=sa.String(500),
        existing_type=sa.Text(),
        existing_nullable=True,
    )

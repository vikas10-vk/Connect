"""add job contact fields

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2025-01-01 00:00:00.000000

What this migration does:
  1. Adds contact_name  VARCHAR(255) NULL  — homeowner contact name for this job
  2. Adds contact_phone VARCHAR(20)  NULL  — homeowner contact phone for this job
  3. Adds contact_email VARCHAR(255) NULL  — homeowner contact email for this job

All nullable — existing job rows are unaffected.
"""

from alembic import op
import sqlalchemy as sa

revision      = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'   # ← points to add_tradie_profile_photos migration
branch_labels = None
depends_on    = None


def upgrade() -> None:
    op.add_column('jobs', sa.Column('contact_name',  sa.String(255), nullable=True))
    op.add_column('jobs', sa.Column('contact_phone', sa.String(20),  nullable=True))
    op.add_column('jobs', sa.Column('contact_email', sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column('jobs', 'contact_email')
    op.drop_column('jobs', 'contact_phone')
    op.drop_column('jobs', 'contact_name')
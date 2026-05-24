"""add tradie profile photo urls

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2025-01-01 00:00:00.000000

What this migration does:
  1. Adds avatar_url      VARCHAR(500) NULL  — tradie profile picture (R2 URL)
  2. Adds cover_photo_url VARCHAR(500) NULL  — tradie profile cover/header photo (R2 URL)

Both nullable — existing tradie rows unaffected.
"""

import sqlalchemy as sa

from alembic import op

revision    = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'   # ← points to the job wizard fields migration
branch_labels = None
depends_on    = None


def upgrade() -> None:
    # 1. Add avatar_url
    op.add_column(
        'tradie_profiles',
        sa.Column('avatar_url', sa.String(500), nullable=True)
    )

    # 2. Add cover_photo_url
    op.add_column(
        'tradie_profiles',
        sa.Column('cover_photo_url', sa.String(500), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('tradie_profiles', 'cover_photo_url')
    op.drop_column('tradie_profiles', 'avatar_url')

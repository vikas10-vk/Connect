"""add inquiries table

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2025-01-01 00:00:00.000000

What this migration does:
  Creates the inquiries table — homeowners send inquiries to tradies
  from the public profile page.
"""

from alembic import op
import sqlalchemy as sa

revision      = 'd4e5f6a7b8c9'
down_revision = 'c3d4e5f6a7b8'   # ← points to add_job_contact_fields migration
branch_labels = None
depends_on    = None


def upgrade() -> None:
    op.create_table(
        'inquiries',
        sa.Column('id',         sa.String(),     primary_key=True),
        sa.Column('tradie_id',  sa.String(),     sa.ForeignKey('tradie_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('sender_id',  sa.String(),     sa.ForeignKey('users.id',           ondelete='CASCADE'), nullable=False),
        sa.Column('name',       sa.String(255),  nullable=False),
        sa.Column('email',      sa.String(255),  nullable=False),
        sa.Column('phone',      sa.String(20),   nullable=True),
        sa.Column('message',    sa.Text(),        nullable=False),
        sa.Column('created_at', sa.DateTime(),   nullable=False),
    )
    op.create_index('ix_inquiries_tradie_id', 'inquiries', ['tradie_id'])


def downgrade() -> None:
    op.drop_index('ix_inquiries_tradie_id', table_name='inquiries')
    op.drop_table('inquiries')
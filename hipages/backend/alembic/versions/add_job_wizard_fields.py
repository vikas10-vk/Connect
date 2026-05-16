"""add job wizard fields

Revision ID: a1b2c3d4e5f6
Revises: 
Create Date: 2025-01-01 00:00:00.000000

What this migration does:
  1. Expands urgency column from VARCHAR(20) → VARCHAR(50)
     Reason: longest new value is "next_few_months" = 15 chars,
             but VARCHAR(50) gives safe headroom.
  2. Adds job_type     VARCHAR(50) NULL  (residential | commercial)
  3. Adds service_type VARCHAR(50) NULL  (new_installation | repair | replace | other)
  4. Adds job_stage    VARCHAR(50) NULL  (ready_to_hire | planning_budgeting)

All new columns are nullable so existing job rows are unaffected.
"""

from alembic import op
import sqlalchemy as sa

# ── IMPORTANT: Set this to your actual last migration revision ID ──
# Run: alembic history
# Copy the most recent revision ID and paste it below as 'down_revision'
revision = 'a1b2c3d4e5f6'
down_revision = '51f587d697cf'  # ← REPLACE with your last revision ID e.g. 'f9e8d7c6b5a4'
branch_labels = None
depends_on = None
# ──────────────────────────────────────────────────────────────────


def upgrade() -> None:
    # 1. Expand urgency column to VARCHAR(50)
    #    Using postgresql USING cast to safely convert existing values
    op.alter_column(
        'jobs',
        'urgency',
        existing_type=sa.String(20),
        type_=sa.String(50),
        existing_nullable=True,
    )

    # 2. Add job_type column
    op.add_column(
        'jobs',
        sa.Column('job_type', sa.String(50), nullable=True)
    )

    # 3. Add service_type column
    op.add_column(
        'jobs',
        sa.Column('service_type', sa.String(50), nullable=True)
    )

    # 4. Add job_stage column
    op.add_column(
        'jobs',
        sa.Column('job_stage', sa.String(50), nullable=True)
    )


def downgrade() -> None:
    # Remove new columns in reverse order
    op.drop_column('jobs', 'job_stage')
    op.drop_column('jobs', 'service_type')
    op.drop_column('jobs', 'job_type')

    # Shrink urgency back to VARCHAR(20)
    # WARNING: any rows with values longer than 20 chars will be truncated
    op.alter_column(
        'jobs',
        'urgency',
        existing_type=sa.String(50),
        type_=sa.String(20),
        existing_nullable=True,
    )
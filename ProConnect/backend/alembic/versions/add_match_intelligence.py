"""add match_intelligence to jobs

Revision ID: add_match_intelligence
Revises: add_soft_delete_cols
Create Date: 2026-04-18
"""
import sqlalchemy as sa

from alembic import op

revision = 'add_match_intelligence'
down_revision = 'add_soft_delete_cols'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    jobs_cols = [c['name'] for c in inspector.get_columns('jobs')]
    if 'match_intelligence' not in jobs_cols:
        op.add_column('jobs', sa.Column('match_intelligence', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('jobs', 'match_intelligence')

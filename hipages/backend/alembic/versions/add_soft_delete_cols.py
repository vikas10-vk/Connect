"""add soft delete and completed_at to jobs

Revision ID: add_soft_delete_cols
Revises: cb80a8f3b684
Create Date: 2026-04-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'add_soft_delete_cols'
down_revision: Union[str, Sequence[str], None] = 'cb80a8f3b684'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    jobs_cols = [c['name'] for c in inspector.get_columns('jobs')]
    if 'is_deleted' not in jobs_cols:
        op.add_column('jobs', sa.Column('is_deleted',   sa.Boolean(),  nullable=False, server_default='false'))
    if 'deleted_at' not in jobs_cols:
        op.add_column('jobs', sa.Column('deleted_at',   sa.DateTime(), nullable=True))
    if 'completed_at' not in jobs_cols:
        op.add_column('jobs', sa.Column('completed_at', sa.DateTime(), nullable=True))
    existing_indexes = [idx['name'] for idx in inspector.get_indexes('jobs')]
    if 'ix_jobs_is_deleted' not in existing_indexes:
        op.create_index('ix_jobs_is_deleted', 'jobs', ['is_deleted'])


def downgrade() -> None:
    op.drop_index('ix_jobs_is_deleted', table_name='jobs')
    op.drop_column('jobs', 'completed_at')
    op.drop_column('jobs', 'deleted_at')
    op.drop_column('jobs', 'is_deleted')

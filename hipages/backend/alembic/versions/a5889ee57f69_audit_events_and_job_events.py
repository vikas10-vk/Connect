"""audit_events_and_job_events

Revision ID: a5889ee57f69
Revises: 113e4ff34fca
Create Date: 2026-04-29 10:17:27.999604

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a5889ee57f69'
down_revision: Union[str, Sequence[str], None] = '113e4ff34fca'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── audit_events (auto-logged by middleware) ──────────────────
    op.create_table(
        'audit_events',
        sa.Column('id',          sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('entity_type', sa.String(50),   nullable=True),
        sa.Column('entity_id',   sa.String(100),  nullable=True),
        sa.Column('actor_id',    sa.String(),      nullable=True),
        sa.Column('actor_role',  sa.String(30),   nullable=True),
        sa.Column('action',      sa.String(20),   nullable=False),
        sa.Column('path',        sa.String(500),  nullable=False),
        sa.Column('status_code', sa.Integer(),     nullable=True),
        sa.Column('ip_address',  sa.String(45),   nullable=True),
        sa.Column('user_agent',  sa.String(500),  nullable=True),
        sa.Column('created_at',  sa.DateTime(),   nullable=True),
    )
    op.create_index('ix_audit_events_entity_type', 'audit_events', ['entity_type'])
    op.create_index('ix_audit_events_actor_id',    'audit_events', ['actor_id'])
    op.create_index('ix_audit_events_created_at',  'audit_events', ['created_at'])

    # ── job_events (state machine trail) ──────────────────────────
    op.create_table(
        'job_events',
        sa.Column('id',          sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('job_id',      sa.String(),     sa.ForeignKey('jobs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('actor_id',    sa.String(),     nullable=False),
        sa.Column('actor_role',  sa.String(30),   nullable=False),
        sa.Column('action',      sa.String(50),   nullable=False),
        sa.Column('old_value',   sa.JSON(),       nullable=True),
        sa.Column('new_value',   sa.JSON(),       nullable=True),
        sa.Column('note',        sa.Text(),       nullable=True),
        sa.Column('ip_address',  sa.String(45),   nullable=True),
        sa.Column('created_at',  sa.DateTime(),   nullable=True),
    )
    op.create_index('ix_job_events_job_id',     'job_events', ['job_id'])
    op.create_index('ix_job_events_created_at', 'job_events', ['created_at'])


def downgrade() -> None:
    op.drop_table('job_events')
    op.drop_table('audit_events')

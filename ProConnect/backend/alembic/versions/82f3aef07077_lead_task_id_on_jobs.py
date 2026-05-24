"""lead_task_id_on_jobs

Revision ID: 82f3aef07077
Revises: 45559f6b8664
Create Date: 2026-04-29 11:54:42.682088

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '82f3aef07077'
down_revision: str | Sequence[str] | None = '45559f6b8664'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('jobs', sa.Column('lead_task_id', sa.String(), nullable=True))

def downgrade() -> None:
    op.drop_column('jobs', 'lead_task_id')

"""add_edit_request_note_to_certs_and_insurance

Revision ID: f1e2d3c4b5a6
Revises: 4a2f8c1d9e03
Create Date: 2026-05-13 10:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'f1e2d3c4b5a6'
down_revision: Union[str, Sequence[str], None] = '4a2f8c1d9e03'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tradie_certifications',
        sa.Column('edit_request_note', sa.Text(), nullable=True)
    )
    op.add_column('insurance_policies',
        sa.Column('edit_request_note', sa.Text(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('tradie_certifications', 'edit_request_note')
    op.drop_column('insurance_policies', 'edit_request_note')

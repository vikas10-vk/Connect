"""add email_verified to users

Revision ID: 4a2f8c1d9e03
Revises: 3e7f2c9b1a40
Create Date: 2026-05-02 14:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4a2f8c1d9e03'
down_revision: Union[str, Sequence[str], None] = '3e7f2c9b1a40'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add email_verified column to users table
    op.add_column('users', sa.Column('email_verified', sa.Boolean(), nullable=False, server_default=sa.text('false')))


def downgrade() -> None:
    # Remove email_verified column from users table
    op.drop_column('users', 'email_verified')

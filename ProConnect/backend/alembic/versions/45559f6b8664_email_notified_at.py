"""email_notified_at

Revision ID: 45559f6b8664
Revises: a5889ee57f69
Create Date: 2026-04-29 11:40:56.313545

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '45559f6b8664'
down_revision: Union[str, Sequence[str], None] = 'a5889ee57f69'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tradie_profiles', sa.Column('email_notified_at', sa.DateTime(), nullable=True))
    op.add_column('reviews',         sa.Column('email_notified_at', sa.DateTime(), nullable=True))
    op.create_index('ix_tradie_profiles_email_notified', 'tradie_profiles', ['email_notified_at'])
    op.create_index('ix_reviews_email_notified',         'reviews',         ['email_notified_at'])

def downgrade() -> None:
    op.drop_index('ix_reviews_email_notified',         table_name='reviews')
    op.drop_index('ix_tradie_profiles_email_notified', table_name='tradie_profiles')
    op.drop_column('reviews',         'email_notified_at')
    op.drop_column('tradie_profiles', 'email_notified_at')

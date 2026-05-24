"""review_moderation

Revision ID: 113e4ff34fca
Revises: 005_phone_not_unique
Create Date: 2026-04-26 23:03:07.195254

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '113e4ff34fca'
down_revision: Union[str, Sequence[str], None] = '005_phone_not_unique'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('reviews', sa.Column('status',        sa.String(length=20), nullable=False, server_default='pending'))
    op.add_column('reviews', sa.Column('reviewed_at',   sa.DateTime(),        nullable=True))
    op.add_column('reviews', sa.Column('reviewed_by',   sa.String(),          nullable=True))
    op.add_column('reviews', sa.Column('response_text', sa.Text(),            nullable=True))
    op.add_column('reviews', sa.Column('responded_at',  sa.DateTime(),        nullable=True))
    op.create_index('ix_reviews_status', 'reviews', ['status'])
    op.create_foreign_key(
        'fk_reviews_reviewed_by_users', 'reviews', 'users',
        ['reviewed_by'], ['id'], ondelete='SET NULL'
    )

def downgrade() -> None:
    op.drop_constraint('fk_reviews_reviewed_by_users', 'reviews', type_='foreignkey')
    op.drop_index('ix_reviews_status', table_name='reviews')
    op.drop_column('reviews', 'responded_at')
    op.drop_column('reviews', 'response_text')
    op.drop_column('reviews', 'reviewed_by')
    op.drop_column('reviews', 'reviewed_at')
    op.drop_column('reviews', 'status')

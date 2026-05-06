"""create user insights table

Revision ID: eb3716b8c169
Revises: 9c44ebf16cec
Create Date: 2026-04-04 19:30:10.239421

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'eb3716b8c169'
down_revision: Union[str, Sequence[str], None] = '9c44ebf16cec'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("""
    CREATE TABLE IF NOT EXISTS user_insights (
        id                  VARCHAR         PRIMARY KEY,
        user_id             VARCHAR         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        home_suburb         VARCHAR(100)    DEFAULT NULL,
        home_state          VARCHAR(10)     DEFAULT NULL,
        home_postcode       VARCHAR(10)     DEFAULT NULL,
        mentioned_problems  TEXT            DEFAULT '[]',
        mentioned_assets    TEXT            DEFAULT '[]',
        trade_interests     TEXT            DEFAULT '[]',
        unresolved_issues   TEXT            DEFAULT '[]',
        key_tags            TEXT            DEFAULT '[]',
        user_intent         VARCHAR(50)     DEFAULT NULL,
        last_sentiment      VARCHAR(20)     DEFAULT NULL,
        created_at          TIMESTAMP       DEFAULT NOW(),
        updated_at          TIMESTAMP       DEFAULT NOW()
    );

    CREATE UNIQUE INDEX IF NOT EXISTS idx_user_insights_user_id ON user_insights(user_id);
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX IF EXISTS idx_user_insights_user_id;")
    op.execute("DROP TABLE IF EXISTS user_insights;")

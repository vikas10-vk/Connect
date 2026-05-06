"""remove unique constraint from users.phone

Revision ID: 005_phone_not_unique
Revises: 004_verification
Create Date: 2026-04-25

Drops the unique index/constraint on users.phone.
Phone numbers are now non-unique — multiple accounts (e.g. family members
or a homeowner + tradie with the same mobile) can share one number.
"""
from alembic import op
import sqlalchemy as sa

revision      = "005_phone_not_unique"
down_revision = "004_verification"
branch_labels = None
depends_on    = None


def upgrade() -> None:
    # Drop the unique index that enforces phone uniqueness.
    # PostgreSQL creates an index named <table>_<col>_key for unique columns,
    # but SQLAlchemy may also have created a named index; we drop both safely.
    with op.batch_alter_table("users") as batch_op:
        # Drop the unique constraint (named automatically by Postgres)
        batch_op.drop_constraint("users_phone_key", type_="unique")


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.create_unique_constraint("users_phone_key", ["phone"])

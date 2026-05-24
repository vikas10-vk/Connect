"""remove unique constraint from users.phone

Revision ID: 005_phone_not_unique
Revises: 004_verification
Create Date: 2026-04-25

Drops the unique index/constraint on users.phone.
Phone numbers are now non-unique — multiple accounts (e.g. family members
or a homeowner + tradie with the same mobile) can share one number.
"""
import sqlalchemy as sa

from alembic import op

revision      = "005_phone_not_unique"
down_revision = "004_verification"
branch_labels = None
depends_on    = None


def upgrade() -> None:
    # Drop the unique index that enforces phone uniqueness.
    # On a fresh database this constraint may not exist, so we check first.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    constraints = [c['name'] for c in inspector.get_unique_constraints('users')]
    if 'users_phone_key' in constraints:
        with op.batch_alter_table("users") as batch_op:
            batch_op.drop_constraint("users_phone_key", type_="unique")


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.create_unique_constraint("users_phone_key", ["phone"])

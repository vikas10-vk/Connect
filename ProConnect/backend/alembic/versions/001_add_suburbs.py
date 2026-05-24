"""add suburbs table

Revision ID: 001_add_suburbs
Revises: add_match_intelligence
Create Date: 2026-04-24
"""
import sqlalchemy as sa

from alembic import op

# ---------------------------------------------------------------------------
# IMPORTANT: set `down_revision` to your current latest migration ID
# e.g. down_revision = 'abc1234def56'
# ---------------------------------------------------------------------------
revision    = "001_add_suburbs"
down_revision = "add_match_intelligence"   # <-- REPLACE with your current head revision ID
branch_labels = None
depends_on    = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'suburbs' not in inspector.get_table_names():
        op.create_table(
            "suburbs",
            sa.Column("id",         sa.Integer(),     nullable=False),
            sa.Column("suburb",     sa.String(100),   nullable=False),
            sa.Column("postcode",   sa.String(10),    nullable=False),
            sa.Column("state",      sa.String(50),    nullable=False),
            sa.Column("state_code", sa.String(5),     nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_suburbs_suburb_lower", "suburbs", [sa.text("lower(suburb)")], postgresql_using="btree")
        op.create_index("ix_suburbs_postcode",     "suburbs", ["postcode"])
        op.create_index("ix_suburbs_state_code",   "suburbs", ["state_code"])


def downgrade() -> None:
    op.drop_index("ix_suburbs_state_code",   table_name="suburbs")
    op.drop_index("ix_suburbs_postcode",     table_name="suburbs")
    op.drop_index("ix_suburbs_suburb_lower", table_name="suburbs")
    op.drop_table("suburbs")

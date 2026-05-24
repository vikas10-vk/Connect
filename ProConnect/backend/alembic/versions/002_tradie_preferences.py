"""create tradie_preferences table

Revision ID: 002_tradie_preferences
Revises: 001_add_suburbs
Create Date: 2026-04-24
"""
import sqlalchemy as sa

from alembic import op

revision      = "002_tradie_preferences"
down_revision = "001_add_suburbs"   # <-- adjust to your actual current head
branch_labels = None
depends_on    = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'tradie_preferences' not in inspector.get_table_names():
        op.create_table(
            "tradie_preferences",
            sa.Column("id",                 sa.String(),   nullable=False),
            sa.Column("tradie_id",          sa.String(),   nullable=False),
            sa.Column("accept_high_intent", sa.Boolean(),  nullable=False, server_default=sa.true()),
            sa.Column("accept_planning",    sa.Boolean(),  nullable=False, server_default=sa.true()),
            sa.Column("notify_new_lead",    sa.Boolean(),  nullable=False, server_default=sa.true()),
            sa.Column("notify_email",       sa.Boolean(),  nullable=False, server_default=sa.true()),
            sa.Column("notify_sms",         sa.Boolean(),  nullable=False, server_default=sa.false()),
            sa.Column("accept_residential", sa.Boolean(),  nullable=False, server_default=sa.true()),
            sa.Column("accept_commercial",  sa.Boolean(),  nullable=False, server_default=sa.true()),
            sa.Column("service_suburbs",    sa.Text(),     nullable=True),
            sa.Column("created_at",         sa.DateTime(), nullable=False),
            sa.Column("updated_at",         sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["tradie_id"], ["tradie_profiles.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tradie_id"),
        )
        op.create_index("ix_tradie_preferences_tradie_id", "tradie_preferences", ["tradie_id"])


def downgrade() -> None:
    op.drop_index("ix_tradie_preferences_tradie_id", table_name="tradie_preferences")
    op.drop_table("tradie_preferences")

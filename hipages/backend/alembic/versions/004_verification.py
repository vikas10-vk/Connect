"""add email_otps and tradie verification fields

Revision ID: 004_verification
Revises: 003_add_service_suburbs
Create Date: 2026-04-25

Adds:
  - email_otps table (full create)
  - tradie_profiles.verification_status, verification_notes, reviewed_at, reviewed_by
  - tradie_profiles.solo_or_team, team_size
"""
from alembic import op
import sqlalchemy as sa

revision      = "004_verification"
down_revision = "003_add_service_suburbs"
branch_labels = None
depends_on    = None


def upgrade() -> None:
    # ── email_otps table ────────────────────────────────────────────
    op.create_table(
        "email_otps",
        sa.Column("id",         sa.String(),    nullable=False),
        sa.Column("user_id",    sa.String(),    nullable=False),
        sa.Column("code",       sa.String(6),   nullable=False),
        sa.Column("expires_at", sa.DateTime(),  nullable=False),
        sa.Column("attempts",   sa.Integer(),   nullable=False, server_default="0"),
        sa.Column("used_at",    sa.DateTime(),  nullable=True),
        sa.Column("created_at", sa.DateTime(),  nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_email_otps_user_id",   "email_otps", ["user_id"])
    op.create_index("ix_email_otps_user_used", "email_otps", ["user_id", "used_at"])

    # ── tradie_profiles new columns ─────────────────────────────────
    op.add_column(
        "tradie_profiles",
        sa.Column("verification_status", sa.String(30), nullable=False, server_default="pending_review"),
    )
    op.add_column(
        "tradie_profiles",
        sa.Column("verification_notes", sa.Text(), nullable=True),
    )
    op.add_column(
        "tradie_profiles",
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "tradie_profiles",
        sa.Column("reviewed_by", sa.String(), nullable=True),
    )
    op.add_column(
        "tradie_profiles",
        sa.Column("solo_or_team", sa.String(10), nullable=False, server_default="solo"),
    )
    op.add_column(
        "tradie_profiles",
        sa.Column("team_size", sa.String(10), nullable=True),
    )
    op.create_index("ix_tradie_profiles_verification_status", "tradie_profiles", ["verification_status"])

    # Backfill: any existing tradies become 'approved' so they don't get locked out
    op.execute("UPDATE tradie_profiles SET verification_status = 'approved' WHERE verification_status = 'pending_review'")


def downgrade() -> None:
    op.drop_index("ix_tradie_profiles_verification_status", table_name="tradie_profiles")
    op.drop_column("tradie_profiles", "team_size")
    op.drop_column("tradie_profiles", "solo_or_team")
    op.drop_column("tradie_profiles", "reviewed_by")
    op.drop_column("tradie_profiles", "reviewed_at")
    op.drop_column("tradie_profiles", "verification_notes")
    op.drop_column("tradie_profiles", "verification_status")

    op.drop_index("ix_email_otps_user_used", table_name="email_otps")
    op.drop_index("ix_email_otps_user_id",   table_name="email_otps")
    op.drop_table("email_otps")

"""tradie verification system

Revision ID: 5f8a3d2e7c91
Revises: 82f3aef07077
Create Date: 2026-05-01 10:03:18.009844

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '5f8a3d2e7c91'
down_revision: str | Sequence[str] | None = '82f3aef07077'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ──────────────────────────────────────────────────────────────────
    # 1. Extend `tradie_profiles`
    # ──────────────────────────────────────────────────────────────────
    op.add_column(
        "tradie_profiles",
        sa.Column("rating_avg", sa.Numeric(3, 2), nullable=True),
    )
    op.add_column(
        "tradie_profiles",
        sa.Column("rating_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "tradie_profiles",
        sa.Column("stripe_account_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "tradie_profiles",
        sa.Column(
            "platform_fee_pct",
            sa.Numeric(4, 2),
            nullable=False,
            server_default="15.00",
        ),
    )
    op.add_column(
        "tradie_profiles",
        sa.Column("verified_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "tradie_profiles",
        sa.Column("logo_url", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "tradie_profiles",
        sa.Column("selfie_url", sa.String(length=500), nullable=True),
    )

    op.create_unique_constraint(
        "uq_tradie_profiles_stripe_account_id",
        "tradie_profiles",
        ["stripe_account_id"],
    )
    op.create_index(
        "idx_tradie_profiles_active_verified",
        "tradie_profiles",
        ["is_available", "verification_status"],
    )

    # ──────────────────────────────────────────────────────────────────
    # 2. team_members
    # ──────────────────────────────────────────────────────────────────
    op.create_table(
        "team_members",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "business_id",
            sa.String(),
            sa.ForeignKey("tradie_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),

        # Identity
        sa.Column("full_name",    sa.String(length=255), nullable=False),
        sa.Column("email",        sa.String(length=255), nullable=False),
        sa.Column("phone_real",   sa.String(length=20),  nullable=False),
        sa.Column("phone_masked", sa.String(length=20),  nullable=True),
        sa.Column("avatar_url",   sa.String(length=500), nullable=True),
        sa.Column("selfie_url",   sa.String(length=500), nullable=True),
        sa.Column(
            "role",
            sa.String(length=20),
            nullable=False,
            server_default="worker",
        ),  # 'owner' | 'worker'

        # Auth (used only when user_id IS NULL — business workers)
        sa.Column("hashed_password", sa.String(length=255), nullable=True),
        sa.Column("last_login_at",   sa.DateTime(),         nullable=True),
        sa.Column("device_id",       sa.String(length=255), nullable=True),

        # Live location (updated only while on a job, on a separate Redis namespace)
        sa.Column("current_lat",         sa.Float(),    nullable=True),
        sa.Column("current_lng",         sa.Float(),    nullable=True),
        sa.Column("location_updated_at", sa.DateTime(), nullable=True),

        # Status gates
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "can_accept_jobs",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),

        # Internal performance (private; never shown to users)
        sa.Column("jobs_completed",        sa.Integer(),       nullable=False, server_default="0"),
        sa.Column("rating_avg",            sa.Numeric(3, 2),   nullable=True),
        sa.Column("no_show_count",         sa.Integer(),       nullable=False, server_default="0"),
        sa.Column("response_time_avg_min", sa.Numeric(6, 2),   nullable=True),

        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),

        sa.UniqueConstraint("email", name="uq_team_members_email"),
    )
    op.create_index("ix_team_members_business_id", "team_members", ["business_id"])
    op.create_index("ix_team_members_user_id",     "team_members", ["user_id"])
    op.create_index(
        "idx_team_members_business_active",
        "team_members",
        ["business_id", "can_accept_jobs", "is_active"],
    )

    # ──────────────────────────────────────────────────────────────────
    # 3. tradie_certifications
    # ──────────────────────────────────────────────────────────────────
    op.create_table(
        "tradie_certifications",
        sa.Column("id", sa.String(), primary_key=True),

        # XOR ownership — exactly one of these must be set
        sa.Column(
            "tradie_profile_id",
            sa.String(),
            sa.ForeignKey("tradie_profiles.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "team_member_id",
            sa.String(),
            sa.ForeignKey("team_members.id", ondelete="CASCADE"),
            nullable=True,
        ),

        # Which trade category this licence is for
        sa.Column(
            "category_id",
            sa.String(),
            sa.ForeignKey("categories.id"),
            nullable=False,
        ),

        # Licence details (no document upload required — number-only)
        sa.Column("licence_number", sa.String(length=100), nullable=False),
        sa.Column("issuing_state",  sa.String(length=20),  nullable=False),  # VIC | NSW | QLD | WA | SA | TAS | NT | ACT
        sa.Column("issuing_body",   sa.String(length=100), nullable=True),   # e.g. "VBA", "NSW Fair Trading"
        sa.Column("holder_name",    sa.String(length=255), nullable=False),  # name as printed on the card

        sa.Column("issued_at",  sa.Date(), nullable=True),
        sa.Column("expires_at", sa.Date(), nullable=True),

        # Optional photo of the licence card — speeds up admin verification
        sa.Column("photo_url", sa.String(length=500), nullable=True),

        # Verification by admin
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="pending",
        ),  # pending | in_review | verified | rejected | expired
        sa.Column("rejection_reason", sa.String(length=50), nullable=True),
        sa.Column("rejection_note",   sa.Text(),            nullable=True),
        sa.Column(
            "verified_by",
            sa.String(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("verified_at", sa.DateTime(), nullable=True),

        # Renewal reminder ledger — Celery beat fills these in
        sa.Column("reminder_30d_sent_at", sa.DateTime(), nullable=True),
        sa.Column("reminder_14d_sent_at", sa.DateTime(), nullable=True),
        sa.Column("reminder_7d_sent_at",  sa.DateTime(), nullable=True),
        sa.Column("reminder_1d_sent_at",  sa.DateTime(), nullable=True),

        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),

        sa.CheckConstraint(
            "(tradie_profile_id IS NOT NULL AND team_member_id IS NULL) OR "
            "(tradie_profile_id IS NULL AND team_member_id IS NOT NULL)",
            name="ck_tradie_certifications_owner_xor",
        ),
    )
    op.create_index("ix_tradie_certifications_tradie_profile_id", "tradie_certifications", ["tradie_profile_id"])
    op.create_index("ix_tradie_certifications_team_member_id",    "tradie_certifications", ["team_member_id"])
    op.create_index("ix_tradie_certifications_category_id",       "tradie_certifications", ["category_id"])
    op.create_index("ix_tradie_certifications_status",            "tradie_certifications", ["status"])
    op.create_index(
        "idx_tradie_certifications_expiry_verified",
        "tradie_certifications",
        ["expires_at"],
        postgresql_where=sa.text("status = 'verified'"),
    )

    # ──────────────────────────────────────────────────────────────────
    # 4. insurance_policies
    # ──────────────────────────────────────────────────────────────────
    op.create_table(
        "insurance_policies",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "tradie_profile_id",
            sa.String(),
            sa.ForeignKey("tradie_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),

        sa.Column(
            "insurance_type",
            sa.String(length=30),
            nullable=False,
            server_default="public_liability",
        ),  # public_liability | workers_compensation | professional_indemnity
        sa.Column("insurer_name",          sa.String(length=255), nullable=False),
        sa.Column("policy_number",         sa.String(length=100), nullable=False),
        sa.Column("coverage_amount_cents", sa.BigInteger(),       nullable=False),  # AU public liability often $20M → 2_000_000_000 cents
        sa.Column("holder_name",           sa.String(length=255), nullable=False),

        sa.Column("issued_at",  sa.Date(), nullable=True),
        sa.Column("expires_at", sa.Date(), nullable=False),

        # Optional certificate-of-currency upload — speeds up admin verification
        sa.Column("document_url", sa.String(length=500), nullable=True),

        # Verification by admin
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("rejection_reason", sa.String(length=50), nullable=True),
        sa.Column("rejection_note",   sa.Text(),            nullable=True),
        sa.Column(
            "verified_by",
            sa.String(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("verified_at", sa.DateTime(), nullable=True),

        # Renewal reminder ledger
        sa.Column("reminder_30d_sent_at", sa.DateTime(), nullable=True),
        sa.Column("reminder_14d_sent_at", sa.DateTime(), nullable=True),
        sa.Column("reminder_7d_sent_at",  sa.DateTime(), nullable=True),
        sa.Column("reminder_1d_sent_at",  sa.DateTime(), nullable=True),

        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_insurance_policies_tradie_profile_id", "insurance_policies", ["tradie_profile_id"])
    op.create_index("ix_insurance_policies_status",            "insurance_policies", ["status"])
    op.create_index(
        "idx_insurance_policies_expiry_verified",
        "insurance_policies",
        ["expires_at"],
        postgresql_where=sa.text("status = 'verified'"),
    )


def downgrade() -> None:
    # Insurance
    op.drop_index("idx_insurance_policies_expiry_verified", table_name="insurance_policies")
    op.drop_index("ix_insurance_policies_status",           table_name="insurance_policies")
    op.drop_index("ix_insurance_policies_tradie_profile_id", table_name="insurance_policies")
    op.drop_table("insurance_policies")

    # Certifications
    op.drop_index("idx_tradie_certifications_expiry_verified", table_name="tradie_certifications")
    op.drop_index("ix_tradie_certifications_status",            table_name="tradie_certifications")
    op.drop_index("ix_tradie_certifications_category_id",       table_name="tradie_certifications")
    op.drop_index("ix_tradie_certifications_team_member_id",    table_name="tradie_certifications")
    op.drop_index("ix_tradie_certifications_tradie_profile_id", table_name="tradie_certifications")
    op.drop_table("tradie_certifications")

    # Team members
    op.drop_index("idx_team_members_business_active", table_name="team_members")
    op.drop_index("ix_team_members_user_id",          table_name="team_members")
    op.drop_index("ix_team_members_business_id",      table_name="team_members")
    op.drop_table("team_members")

    # tradie_profiles extensions
    op.drop_index("idx_tradie_profiles_active_verified", table_name="tradie_profiles")
    op.drop_constraint(
        "uq_tradie_profiles_stripe_account_id",
        "tradie_profiles",
        type_="unique",
    )
    op.drop_column("tradie_profiles", "selfie_url")
    op.drop_column("tradie_profiles", "logo_url")
    op.drop_column("tradie_profiles", "verified_at")
    op.drop_column("tradie_profiles", "platform_fee_pct")
    op.drop_column("tradie_profiles", "stripe_account_id")
    op.drop_column("tradie_profiles", "rating_count")
    op.drop_column("tradie_profiles", "rating_avg")

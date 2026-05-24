"""job_state_machine_fields

Revision ID: 3e7f2c9b1a40
Revises: 9c1b4f6a3d82
Create Date: 2026-05-01 11:44:32.247257

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '3e7f2c9b1a40'
down_revision: str | Sequence[str] | None = '9c1b4f6a3d82'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ──────────────────────────────────────────────────────────────
    # 1. Extend jobs table
    # ──────────────────────────────────────────────────────────────

    # Scope change in progress (only one pending scope change at a time)
    op.add_column("jobs", sa.Column("pending_scope_amount_cents",   sa.Integer(),  nullable=True))
    op.add_column("jobs", sa.Column("scope_change_reason",         sa.Text(),     nullable=True))
    op.add_column("jobs", sa.Column("scope_change_category_id",    sa.String(),   nullable=True))
    # ^ NULL = same category add; set = different category (blocked by skill-boundary check)
    op.add_column("jobs", sa.Column("scope_change_requested_at",   sa.DateTime(), nullable=True))
    op.add_column("jobs", sa.Column("scope_change_expires_at",     sa.DateTime(), nullable=True))
    op.add_column("jobs", sa.Column("scope_change_task_id",        sa.String(),   nullable=True))
    # ^ Celery task ID for the 10-minute auto-reject timeout

    # Before / after photo evidence (mandatory for tradie at job start + completion)
    op.add_column("jobs", sa.Column("photo_before_url",            sa.String(500), nullable=True))
    op.add_column("jobs", sa.Column("photo_after_url",             sa.String(500), nullable=True))
    op.add_column("jobs", sa.Column("completion_note",             sa.Text(),     nullable=True))

    # Homeowner confirms job complete (starts 48h dispute window)
    op.add_column("jobs", sa.Column("confirmed_by_user_at",        sa.DateTime(), nullable=True))

    # ──────────────────────────────────────────────────────────────
    # 2. job_assignments
    # ──────────────────────────────────────────────────────────────
    op.create_table(
        "job_assignments",
        sa.Column("id",                 sa.String(),     primary_key=True),
        sa.Column(
            "job_id",
            sa.String(),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "business_id",
            sa.String(),
            sa.ForeignKey("tradie_profiles.id"),
            nullable=False,
        ),
        sa.Column(
            "assigned_worker_id",
            sa.String(),
            sa.ForeignKey("team_members.id"),
            nullable=False,
        ),
        sa.Column(
            "assigned_by_id",
            sa.String(),
            sa.ForeignKey("team_members.id"),
            nullable=True,   # NULL = system auto-dispatch
        ),
        sa.Column(
            "assignment_type",
            sa.String(20),
            nullable=False,
            server_default="manual",
        ),  # 'manual' | 'auto'
        sa.Column("assigned_at",  sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        # Only one active assignment per job at a time — enforced by this unique constraint
        sa.UniqueConstraint("job_id", "is_active", name="uq_job_assignments_one_active"),
    )
    op.create_index("ix_job_assignments_job_id",    "job_assignments", ["job_id", "is_active"])
    op.create_index("ix_job_assignments_worker_id", "job_assignments", ["assigned_worker_id", "assigned_at"])


def downgrade() -> None:
    op.drop_index("ix_job_assignments_worker_id", table_name="job_assignments")
    op.drop_index("ix_job_assignments_job_id",    table_name="job_assignments")
    op.drop_table("job_assignments")

    for col in [
        "confirmed_by_user_at",
        "completion_note",
        "photo_after_url",
        "photo_before_url",
        "scope_change_task_id",
        "scope_change_expires_at",
        "scope_change_requested_at",
        "scope_change_category_id",
        "scope_change_reason",
        "pending_scope_amount_cents",
    ]:
        op.drop_column("jobs", col)

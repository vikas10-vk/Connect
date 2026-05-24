"""phase3 realtime reliability

Revision ID: 20260523_phase3_realtime
Revises: 20260521_phase2_uniqueness
Create Date: 2026-05-23
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260523_phase3_realtime"
down_revision: str | None = "20260521_phase2_uniqueness"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


VALID_STATUSES = (
    "open",
    "quoted",
    "hired",
    "in_progress",
    "awaiting_scope_approval",
    "partial_stop",
    "disputed",
    "completed",
    "confirmed",
    "closed",
    "cancelled",
)


def upgrade() -> None:
    op.create_table(
        "realtime_notifications",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("delivered_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_realtime_notifications_user_id",
        "realtime_notifications",
        ["user_id"],
    )
    op.create_index(
        "ix_realtime_notifications_event_type",
        "realtime_notifications",
        ["event_type"],
    )
    op.create_index(
        "ix_realtime_notifications_created_at",
        "realtime_notifications",
        ["created_at"],
    )
    op.create_index(
        "ix_realtime_notifications_delivered_at",
        "realtime_notifications",
        ["delivered_at"],
    )

    op.create_table(
        "outbox_events",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_outbox_events_event_type", "outbox_events", ["event_type"])
    op.create_index("ix_outbox_events_status", "outbox_events", ["status"])
    op.create_index("ix_outbox_events_created_at", "outbox_events", ["created_at"])
    op.create_index("ix_outbox_events_processed_at", "outbox_events", ["processed_at"])

    quoted = ", ".join(f"'{status}'" for status in VALID_STATUSES)
    op.create_check_constraint(
        "ck_jobs_status_valid",
        "jobs",
        f"status IN ({quoted})",
    )


def downgrade() -> None:
    op.drop_constraint("ck_jobs_status_valid", "jobs", type_="check")
    op.drop_index("ix_outbox_events_processed_at", table_name="outbox_events")
    op.drop_index("ix_outbox_events_created_at", table_name="outbox_events")
    op.drop_index("ix_outbox_events_status", table_name="outbox_events")
    op.drop_index("ix_outbox_events_event_type", table_name="outbox_events")
    op.drop_table("outbox_events")
    op.drop_index("ix_realtime_notifications_delivered_at", table_name="realtime_notifications")
    op.drop_index("ix_realtime_notifications_created_at", table_name="realtime_notifications")
    op.drop_index("ix_realtime_notifications_event_type", table_name="realtime_notifications")
    op.drop_index("ix_realtime_notifications_user_id", table_name="realtime_notifications")
    op.drop_table("realtime_notifications")

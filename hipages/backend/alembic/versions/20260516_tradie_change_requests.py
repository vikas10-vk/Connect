"""add tradie change requests

Revision ID: 20260516_tcr
Revises: 113e4ff34fca
Create Date: 2026-05-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260516_tcr"
down_revision: Union[str, None] = "006_photo_after_url_to_text"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tradie_change_requests",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tradie_id", sa.String(), nullable=False),
        sa.Column("requested_by", sa.String(), nullable=False),
        sa.Column("request_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.String(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["tradie_id"], ["tradie_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tradie_change_requests_tradie_id", "tradie_change_requests", ["tradie_id"])
    op.create_index("ix_tradie_change_requests_requested_by", "tradie_change_requests", ["requested_by"])
    op.create_index("ix_tradie_change_requests_request_type", "tradie_change_requests", ["request_type"])
    op.create_index("ix_tradie_change_requests_status", "tradie_change_requests", ["status"])


def downgrade() -> None:
    op.drop_index("ix_tradie_change_requests_status", table_name="tradie_change_requests")
    op.drop_index("ix_tradie_change_requests_request_type", table_name="tradie_change_requests")
    op.drop_index("ix_tradie_change_requests_requested_by", table_name="tradie_change_requests")
    op.drop_index("ix_tradie_change_requests_tradie_id", table_name="tradie_change_requests")
    op.drop_table("tradie_change_requests")

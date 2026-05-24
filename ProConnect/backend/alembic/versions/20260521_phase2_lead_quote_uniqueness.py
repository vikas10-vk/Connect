"""phase2 lead and quote uniqueness

Revision ID: 20260521_phase2_uniqueness
Revises: 20260516_tcr
Create Date: 2026-05-21
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260521_phase2_uniqueness"
down_revision: str | None = "20260516_tcr"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM quotes
                GROUP BY lead_id
                HAVING COUNT(*) > 1
            ) THEN
                RAISE EXCEPTION 'Cannot add uq_quotes_lead_id: duplicate quote rows exist for at least one lead_id';
            END IF;

            IF EXISTS (
                SELECT 1
                FROM leads
                GROUP BY job_id, tradie_id
                HAVING COUNT(*) > 1
            ) THEN
                RAISE EXCEPTION 'Cannot add uq_leads_job_id_tradie_id: duplicate lead rows exist for at least one job_id/tradie_id pair';
            END IF;
        END $$;
        """
    )
    op.create_unique_constraint("uq_quotes_lead_id", "quotes", ["lead_id"])
    op.create_unique_constraint("uq_leads_job_id_tradie_id", "leads", ["job_id", "tradie_id"])


def downgrade() -> None:
    op.drop_constraint("uq_leads_job_id_tradie_id", "leads", type_="unique")
    op.drop_constraint("uq_quotes_lead_id", "quotes", type_="unique")

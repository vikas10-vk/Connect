"""skill taxonomy and service questions

Revision ID: 9c1b4f6a3d82
Revises: 5f8a3d2e7c91
Create Date: 2026-05-01 10:23:50.130139

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '9c1b4f6a3d82'
down_revision: str | Sequence[str] | None = '5f8a3d2e7c91'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ──────────────────────────────────────────────────────────────
    # 1. Extend categories
    # ──────────────────────────────────────────────────────────────
    op.add_column(
        "categories",
        sa.Column(
            "level",
            sa.SmallInteger(),
            nullable=False,
            server_default="1",   # existing rows are all level-1 trade categories
        ),
    )
    op.add_column(
        "categories",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.add_column(
        "categories",
        sa.Column("icon_slug",   sa.String(length=100), nullable=True),
    )
    op.add_column(
        "categories",
        sa.Column("description", sa.Text(),             nullable=True),
    )

    op.create_index("idx_categories_level",     "categories", ["level"])
    op.create_index("idx_categories_is_active",  "categories", ["is_active"])
    op.create_index(
        "idx_categories_level_active",
        "categories",
        ["level", "is_active"],
    )

    # ──────────────────────────────────────────────────────────────
    # 2. Extend tradie_categories
    # ──────────────────────────────────────────────────────────────
    op.add_column(
        "tradie_categories",
        sa.Column(
            "is_primary",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    # ──────────────────────────────────────────────────────────────
    # 3. service_questions
    # ──────────────────────────────────────────────────────────────
    op.create_table(
        "service_questions",
        sa.Column("id",          sa.String(),      primary_key=True),
        sa.Column(
            "category_id",
            sa.String(),
            sa.ForeignKey("categories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("question_text", sa.Text(),         nullable=False),
        sa.Column(
            "answer_type",
            sa.String(length=20),
            nullable=False,
            server_default="text",
        ),
        sa.Column("options",      sa.JSON(),         nullable=True),
        sa.Column("placeholder",  sa.String(255),    nullable=True),
        sa.Column(
            "is_required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "sort_order",
            sa.SmallInteger(),
            nullable=False,
            server_default="0",
        ),
    )
    op.create_index("ix_service_questions_category_id", "service_questions", ["category_id"])
    op.create_index(
        "idx_service_questions_category_order",
        "service_questions",
        ["category_id", "sort_order"],
    )


def downgrade() -> None:
    # service_questions
    op.drop_index("idx_service_questions_category_order", table_name="service_questions")
    op.drop_index("ix_service_questions_category_id",     table_name="service_questions")
    op.drop_table("service_questions")

    # tradie_categories
    op.drop_column("tradie_categories", "is_primary")

    # categories
    op.drop_index("idx_categories_level_active", table_name="categories")
    op.drop_index("idx_categories_is_active",    table_name="categories")
    op.drop_index("idx_categories_level",        table_name="categories")
    op.drop_column("categories", "description")
    op.drop_column("categories", "icon_slug")
    op.drop_column("categories", "is_active")
    op.drop_column("categories", "level")

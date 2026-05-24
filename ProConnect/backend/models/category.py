"""
backend/models/category.py

UPDATED — extends the existing Category model to support a 3-level
skill taxonomy:
  Level 1 — Trade category      e.g. "Plumbing"
  Level 2 — Subcategory         e.g. "Hot Water Systems"
  Level 3 — Specific task       e.g. "Hot water system replacement"

WHY 3 LEVELS MATTER:
  - Homeowners describe a specific task (level 3) → system routes to
    the correct subcategory → tradie's certification is verified against
    the parent category (level 1). This closes the skill-mismatch loophole
    where "plumber" shows up and the job needs an electrician.
  - Service questions (ServiceQuestion model) are attached at level 2
    (subcategory) so questions are specific enough to be useful but not
    so granular that we need a question tree for every task.
  - Tradie certifications are verified at level 1 (trade category)
    because Australian licences are issued at that granularity
    (e.g. VBA issues a "Plumbing Licence", not a "Hot Water Licence").
    The category_id on TradieCertification always points to a level-1 row.

EXISTING FIELDS: id, name, slug, parent_id — kept exactly as-is.
NEW FIELDS: level, is_active, icon_slug, description.
"""
import uuid
from sqlalchemy import String, SmallInteger, Boolean, Text, ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.session import Base


class CategoryLevel:
    TRADE       = 1   # e.g. Plumbing, Electrical, Carpentry
    SUBCATEGORY = 2   # e.g. Hot Water Systems, Switchboard Upgrades
    TASK        = 3   # e.g. Hot water system replacement


class Category(Base):
    __tablename__ = "categories"

    # ── Existing fields (UNCHANGED) ────────────────────────────────
    id:        Mapped[str] = mapped_column(String,      primary_key=True, default=lambda: str(uuid.uuid4()))
    name:      Mapped[str] = mapped_column(String(100), nullable=False)
    slug:      Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    parent_id: Mapped[str] = mapped_column(String,      ForeignKey("categories.id"), nullable=True)

    # ── NEW fields ─────────────────────────────────────────────────
    level: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=CategoryLevel.TRADE,
        index=True,
    )
    # Level 1 rows always have parent_id = NULL.
    # Level 2 rows point to a level-1 parent.
    # Level 3 rows point to a level-2 parent.

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
    )
    # Soft-disable a category without deleting it. Inactive categories
    # are hidden from the booking wizard but existing jobs are unaffected.

    icon_slug: Mapped[str] = mapped_column(
        String(100),
        nullable=True,
    )
    # Short key for the frontend icon set (e.g. "plumbing", "electrical").
    # Only meaningful on level-1 rows — subcategories inherit the parent icon.

    description: Mapped[str] = mapped_column(
        Text,
        nullable=True,
    )
    # One-line description shown in the booking wizard and tradie onboarding.

    # ── Relationships (existing, UNCHANGED) ────────────────────────
    parent   = relationship("Category", remote_side="Category.id", back_populates="children")
    children = relationship("Category", back_populates="parent", cascade="all, delete-orphan")

    # ── NEW relationship ────────────────────────────────────────────
    service_questions = relationship(
        "ServiceQuestion",
        back_populates="category",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Category L{self.level} {self.name}>"
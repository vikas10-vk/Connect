"""
scripts/add_pool_cleaning.py

Inserts Pool Cleaning (and two companion cleaning subcategories) into the
live database under the existing "Cleaning" parent category.

Run once from the backend directory:
    cd backend
    python -m scripts.add_pool_cleaning

Idempotent — safe to run multiple times (skips slugs that already exist).
"""
import asyncio
import uuid

from db.session import AsyncSessionLocal
from models.category import Category, CategoryLevel
from sqlalchemy import select


NEW_SUBCATEGORIES = [
    # (slug, name, description)
    (
        "cleaning-pool",
        "Pool Cleaning",
        "Swimming pool cleaning, chemical balancing and maintenance",
    ),
    (
        "cleaning-oven",
        "Oven & BBQ Cleaning",
        "Professional oven, range hood and BBQ degreasing",
    ),
    (
        "cleaning-commercial",
        "Commercial Cleaning",
        "Office, retail and commercial premises cleaning",
    ),
]


async def run() -> None:
    async with AsyncSessionLocal() as db:
        # Find the "Cleaning" L1 parent
        result = await db.execute(
            select(Category).where(Category.slug == "cleaning")
        )
        parent = result.scalar_one_or_none()
        if not parent:
            print("ERROR: 'cleaning' parent category not found.")
            print("Run the full seed first: python -m seeds.seed_categories")
            return

        print(f"Found parent: {parent.name} (id={parent.id})")

        for slug, name, description in NEW_SUBCATEGORIES:
            existing = await db.execute(
                select(Category).where(Category.slug == slug)
            )
            if existing.scalar_one_or_none():
                print(f"  [SKIP] {name} — already exists")
                continue

            cat = Category(
                id=str(uuid.uuid4()),
                name=name,
                slug=slug,
                parent_id=parent.id,
                level=CategoryLevel.SUBCATEGORY,
                is_active=True,
                icon_slug=None,
                description=description,
            )
            db.add(cat)
            print(f"  [ADD]  {name} (slug={slug})")

        await db.commit()
        print("\nDone. Pool Cleaning and companions are now in the database.")
        print("The booking wizard will show them immediately.")
        print("Tradies registered under 'Cleaning' will receive pool cleaning leads.")


if __name__ == "__main__":
    asyncio.run(run())

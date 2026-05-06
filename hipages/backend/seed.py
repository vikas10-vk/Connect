import asyncio
import uuid
import os
from dotenv import load_dotenv

load_dotenv(
    dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"),
    override=True
)

from db.session import AsyncSessionLocal
from models.category import Category
from sqlalchemy import select

CATEGORIES = [
    {"name": "Plumbing",          "slug": "plumbing"},
    {"name": "Electrical",        "slug": "electrical"},
    {"name": "Carpentry",         "slug": "carpentry"},
    {"name": "Painting",          "slug": "painting"},
    {"name": "Landscaping",       "slug": "landscaping"},
    {"name": "Roofing",           "slug": "roofing"},
    {"name": "Tiling",            "slug": "tiling"},
    {"name": "Concreting",        "slug": "concreting"},
    {"name": "Fencing",           "slug": "fencing"},
    {"name": "Air Conditioning",  "slug": "air-conditioning"},
    {"name": "Pest Control",      "slug": "pest-control"},
    {"name": "Cleaning",          "slug": "cleaning"},
    {"name": "Removalist",        "slug": "removalist"},
    {"name": "Locksmith",         "slug": "locksmith"},
    {"name": "Solar Installation","slug": "solar-installation"},
]

async def seed():
    async with AsyncSessionLocal() as db:
        inserted = 0
        skipped  = 0

        for cat in CATEGORIES:
            result = await db.execute(
                select(Category).where(Category.slug == cat["slug"])
            )
            exists = result.scalar_one_or_none()

            if exists:
                print(f"  SKIP  {cat['name']} — already exists")
                skipped += 1
                continue

            db.add(Category(id=str(uuid.uuid4()), **cat))
            print(f"  ADD   {cat['name']}")
            inserted += 1

        await db.commit()
        print(f"\nDone — {inserted} inserted, {skipped} skipped")

if __name__ == "__main__":
    asyncio.run(seed())
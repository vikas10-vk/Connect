"""
backend/scripts/fix_orphan_categories.py

ONE-TIME repair script for the "Plumber ≠ Plumbing" matching bug.

ROOT CAUSE
----------
The old seed (scripts/seed_categories.py) created 148+ agent-noun categories
("Plumber", "Electrician", etc.) as separate level-1 DB rows alongside the
canonical 24 ("Plumbing", "Electrical", etc.).

A tradie who selected "Plumber" during onboarding has:
    TradieCategory.category_id → UUID of "Plumber" row

A job posted by a homeowner gets resolved to:
    Job.category_id → UUID of "Plumbing" row

These UUIDs are different → lead distribution SQL filter finds no match → job
is never sent to the tradie even though they ARE the right person.

WHAT THIS SCRIPT DOES
---------------------
1. Reads the SYNONYM_TO_CANONICAL_SLUG map from category_resolver.py.
2. Finds all orphan level-1 categories whose normalised names appear in the map.
3. For each orphan:
   a. Finds the canonical category (e.g. "Plumbing").
   b. Updates all TradieCategory rows pointing at the orphan to point at the
      canonical category instead (skipping any that would create a duplicate).
   c. Marks the orphan category as is_active=False so it disappears from pickers.
4. Prints a full audit trail of every change made.

SAFE TO RE-RUN: idempotent — skips already-remapped rows.

RUN FROM BACKEND DIRECTORY:
    cd ProConnect/backend
    python scripts/fix_orphan_categories.py
"""
import asyncio
import os
import re
import sys
from pathlib import Path


# ── Load .env before importing any project modules ───────────────────────────
# The .env lives at ProConnect/.env (one level above ProConnect/backend/).
# Walk up from this script's location until we find it so the script works
# regardless of which directory it is invoked from.
def _find_and_load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return  # python-dotenv not installed — rely on env vars already set
    script_dir = Path(__file__).resolve().parent
    for parent in [script_dir, *script_dir.parents]:
        candidate = parent / ".env"
        if candidate.is_file():
            load_dotenv(dotenv_path=candidate, override=True)
            print(f"  Loaded env from: {candidate}")
            return
    print("  ⚠ No .env file found — relying on environment variables already set.")

_find_and_load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from db.session import AsyncSessionLocal
from models.category import Category, CategoryLevel
from models.tradie_category import TradieCategory


def _normalise(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


async def fix_orphan_categories():
    from services.category_resolver import SYNONYM_TO_CANONICAL_SLUG

    async with AsyncSessionLocal() as db:
        # ── 1. Load all level-1 categories ───────────────────────────────────
        all_l1_res = await db.execute(
            select(Category).where(Category.level == CategoryLevel.TRADE)
        )
        all_l1 = all_l1_res.scalars().all()

        # Build slug → category map for canonical lookups
        slug_to_cat: dict[str, Category] = {c.slug: c for c in all_l1}

        print(f"\n{'='*60}")
        print("  Orphan Category Repair Script")
        print(f"{'='*60}\n")
        print(f"  Total level-1 categories in DB: {len(all_l1)}")

        # ── 2. Identify orphans ───────────────────────────────────────────────
        orphans: list[tuple[Category, Category]] = []  # (orphan, canonical)
        for cat in all_l1:
            key = _normalise(cat.name)
            canonical_slug = SYNONYM_TO_CANONICAL_SLUG.get(key)
            if not canonical_slug:
                slug_key = _normalise(cat.slug.replace("-", " "))
                canonical_slug = SYNONYM_TO_CANONICAL_SLUG.get(slug_key)
            if not canonical_slug:
                continue
            canonical = slug_to_cat.get(canonical_slug)
            if not canonical:
                print(f"  ⚠ Canonical slug '{canonical_slug}' not in DB — skipping '{cat.name}'")
                continue
            if canonical.id == cat.id:
                continue  # Already the canonical — skip
            orphans.append((cat, canonical))

        print(f"  Orphan categories found: {len(orphans)}\n")

        if not orphans:
            print("  ✓ No orphans to fix. Database is clean.\n")
            return

        # ── 3. Fix TradieCategory records + deactivate orphans ────────────────
        total_remapped = 0
        total_deactivated = 0

        for orphan, canonical in orphans:
            print(f"  Orphan: '{orphan.name}' (slug={orphan.slug}, id={orphan.id})")
            print(f"  → Canonical: '{canonical.name}' (slug={canonical.slug}, id={canonical.id})")

            # Find all TradieCategory rows pointing at this orphan
            tc_res = await db.execute(
                select(TradieCategory).where(TradieCategory.category_id == orphan.id)
            )
            tc_rows = tc_res.scalars().all()

            if tc_rows:
                print(f"    TradieCategory rows to remap: {len(tc_rows)}")
            else:
                print("    TradieCategory rows to remap: 0")

            for tc in tc_rows:
                # Check if this tradie already has the canonical category
                existing_res = await db.execute(
                    select(TradieCategory).where(
                        TradieCategory.tradie_id == tc.tradie_id,
                        TradieCategory.category_id == canonical.id,
                    )
                )
                if existing_res.scalar_one_or_none():
                    # Tradie already has the canonical — just delete the orphan link
                    await db.delete(tc)
                    print(f"    ✓ Tradie {tc.tradie_id}: orphan link removed (canonical already exists)")
                else:
                    # Remap the orphan link to the canonical category
                    tc.category_id = canonical.id
                    db.add(tc)
                    print(f"    ✓ Tradie {tc.tradie_id}: remapped {orphan.slug} → {canonical.slug}")
                total_remapped += 1

            # Deactivate the orphan so it no longer appears in pickers
            if orphan.is_active:
                orphan.is_active = False
                db.add(orphan)
                total_deactivated += 1
                print(f"    ✓ Orphan '{orphan.name}' marked is_active=False")
            else:
                print(f"    — Orphan '{orphan.name}' already inactive")

            print()

        await db.commit()

        print(f"{'='*60}")
        print("  DONE")
        print(f"  TradieCategory rows remapped: {total_remapped}")
        print(f"  Orphan categories deactivated: {total_deactivated}")
        print(f"{'='*60}\n")
        print("  Next step: restart the FastAPI server so the category")
        print("  picker and resolver use the updated is_active flags.\n")


if __name__ == "__main__":
    asyncio.run(fix_orphan_categories())

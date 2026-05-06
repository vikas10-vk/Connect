"""
Seed suburbs table from CSV.

Run from backend directory:
    python scripts/seed_suburbs.py

Requires the CSV at: scripts/aus_postcode_new.csv
(copy the CSV file into backend/scripts/ first)
"""
import csv
import os
import sys
import asyncio

# Allow running from backend/ root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, func
from db.session import AsyncSessionLocal as SessionLocal, engine
from models.suburb import Suburb, Base

CSV_PATH = os.path.join(os.path.dirname(__file__), "aus_postcode_new.csv")

async def seed():
    async with SessionLocal() as db:
        try:
            result = await db.execute(select(func.count(Suburb.id)))
            existing = result.scalar()
            if existing > 0:
                print(f"[seed_suburbs] Table already has {existing} rows. Skipping.")
                print("  To re-seed: DELETE FROM suburbs; then re-run this script.")
                return

            print(f"[seed_suburbs] Reading {CSV_PATH} ...")
            rows = []
            with open(CSV_PATH, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    state_code = row["state_code"].strip() or "OT"   # Other Territories
                    rows.append(
                        Suburb(
                            suburb     = row["suburb"].strip(),
                            postcode   = row["postcode"].strip(),
                            state      = row["state"].strip(),
                            state_code = state_code,
                        )
                    )

            db.add_all(rows)
            await db.commit()
            print(f"[seed_suburbs] [OK] Inserted {len(rows)} suburbs successfully.")

            # Quick sanity check
            result = await db.execute(select(func.count(Suburb.id)))
            total = result.scalar()
            print(f"[seed_suburbs] DB count: {total}")

        except Exception as e:
            await db.rollback()
            print(f"[seed_suburbs] [ERROR] Error: {e}")
            raise
        finally:
            await db.close()

if __name__ == "__main__":
    asyncio.run(seed())
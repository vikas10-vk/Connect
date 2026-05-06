"""
Run this once to manually create leads for John for existing jobs.
Usage: python create_test_leads.py
"""
import asyncio
import uuid
from db.session import AsyncSessionLocal
from sqlalchemy import text

async def create_leads():
    async with AsyncSessionLocal() as db:

        # Get John's tradie profile
        result = await db.execute(text(
            "SELECT id, business_name, lat, lng, radius_km FROM tradie_profiles LIMIT 1"
        ))
        tradie = result.fetchone()
        if not tradie:
            print("ERROR: No tradie profile found. Complete onboarding first.")
            return

        tradie_id, business_name, t_lat, t_lng, radius = tradie
        print(f"Tradie: {business_name} (id={tradie_id[:8]}...) @ {t_lat}, {t_lng} radius={radius}km")

        # Get jobs that don't already have a lead for this tradie
        result = await db.execute(text("""
            SELECT j.id, j.title, j.suburb, j.state, j.lat, j.lng
            FROM jobs j
            WHERE j.is_deleted = false
              AND j.lat IS NOT NULL
              AND j.lng IS NOT NULL
              AND NOT EXISTS (
                SELECT 1 FROM leads l
                WHERE l.job_id = j.id AND l.tradie_id = :tradie_id
              )
            ORDER BY j.created_at DESC
            LIMIT 10
        """), {"tradie_id": tradie_id})
        jobs = result.fetchall()

        print(f"\nJobs without a lead for {business_name}: {len(jobs)}")

        import math
        def dist(lat1, lng1, lat2, lng2):
            R = 6371
            lat1, lng1, lat2, lng2 = map(math.radians, [lat1, lng1, lat2, lng2])
            a = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((lng2-lng1)/2)**2
            return R * 2 * math.asin(math.sqrt(a))

        created = 0
        for job in jobs:
            job_id, title, suburb, state, j_lat, j_lng = job
            d = dist(t_lat, t_lng, j_lat, j_lng)
            print(f"  {title} | {suburb}, {state} | {d:.0f}km away", end="")

            if d <= radius:
                lead_id = str(uuid.uuid4())
                await db.execute(text("""
                    INSERT INTO leads (id, job_id, tradie_id, credits_charged, status, sent_at)
                    VALUES (:id, :job_id, :tradie_id, 0, 'sent', NOW())
                """), {
                    "id": lead_id,
                    "job_id": job_id,
                    "tradie_id": tradie_id,
                })
                print(" → ✓ Lead created")
                created += 1
            else:
                print(f" → ✗ Out of range ({d:.0f}km > {radius}km)")

        await db.commit()
        print(f"\nDone — {created} lead(s) created for {business_name}")
        print("Refresh the tradie dashboard to see them.")

asyncio.run(create_leads())
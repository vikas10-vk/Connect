"""
Diagnostic script — run from the backend/ directory:

    python scripts/diagnose_lead.py [tradie_email] [job_id_optional]

Examples:
    python scripts/diagnose_lead.py virat_18@gmail.com
    python scripts/diagnose_lead.py virat_18@gmail.com abc123-job-id

It checks EVERY condition that the lead-distribution engine needs and
tells you exactly what is blocking the lead from reaching this tradie.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# ── Load .env so DATABASE_URL etc. are available ─────────────────────────────
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / ".env", override=True)

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DATABASE_URL = os.getenv("DATABASE_URL", "")
IS_DEV = os.getenv("ENVIRONMENT", "development") == "development"

engine  = create_async_engine(DATABASE_URL, pool_pre_ping=True)
Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

TRADIE_EMAIL = sys.argv[1] if len(sys.argv) > 1 else "virat_18@gmail.com"
JOB_ID       = sys.argv[2] if len(sys.argv) > 2 else None


def ok(msg):  print(f"  ✅  {msg}")
def warn(msg): print(f"  ⚠️  {msg}")
def fail(msg): print(f"  ❌  {msg}")
def info(msg): print(f"  ℹ️  {msg}")


async def main():
    async with Session() as db:
        print(f"\n{'='*60}")
        print(f" LEAD DIAGNOSTIC — {TRADIE_EMAIL}")
        print(f"{'='*60}\n")

        # ── 1. User ───────────────────────────────────────────────────────────
        print("─── 1. USER ACCOUNT ───")
        result = await db.execute(
            text("SELECT id, email, role, is_active, is_verified FROM users WHERE email = :e"),
            {"e": TRADIE_EMAIL}
        )
        user = result.mappings().fetchone()
        if not user:
            fail(f"No user found with email {TRADIE_EMAIL}")
            return
        info(f"User ID: {user['id']}")
        ok(f"Email: {user['email']}") if user['email'] else fail("No email")
        ok("Role = tradie") if user['role'] == 'tradie' else fail(f"Role is '{user['role']}' — must be 'tradie'")
        ok("is_active = True") if user['is_active'] else fail("is_active = False — account is disabled")
        ok("is_verified = True") if user['is_verified'] else warn("is_verified = False — email not confirmed (OK in dev)")
        user_id = user['id']

        # ── 2. Tradie profile ─────────────────────────────────────────────────
        print("\n─── 2. TRADIE PROFILE ───")
        result = await db.execute(
            text("SELECT id, business_name, verification_status, is_available, lat, lng, radius_km FROM tradie_profiles WHERE user_id = :uid"),
            {"uid": user_id}
        )
        profile = result.mappings().fetchone()
        if not profile:
            fail("No tradie_profile row found — tradie needs to complete onboarding")
            return
        info(f"Profile ID: {profile['id']}")
        info(f"Business: {profile['business_name'] or '(unnamed)'}")
        ok("is_available = True") if profile['is_available'] else fail("is_available = False — tradie has turned off availability")
        if IS_DEV:
            info(f"verification_status = '{profile['verification_status']}' (approval check skipped in DEV mode)")
        else:
            ok("verification_status = approved") if profile['verification_status'] == 'approved' else fail(f"verification_status = '{profile['verification_status']}' — must be 'approved' in production")
        if profile['lat'] and profile['lng']:
            ok(f"Geocoded: ({profile['lat']:.4f}, {profile['lng']:.4f}), radius = {profile['radius_km'] or 25} km")
        else:
            warn("No lat/lng on profile — radius matching disabled, suburb-name matching only")
        profile_id = profile['id']

        # ── 3. Categories ─────────────────────────────────────────────────────
        print("\n─── 3. TRADIE CATEGORIES ───")
        result = await db.execute(
            text("""
                SELECT tc.category_id, c.name, c.slug
                FROM tradie_categories tc
                JOIN categories c ON c.id = tc.category_id
                WHERE tc.tradie_id = :pid
            """),
            {"pid": profile_id}
        )
        cats = result.mappings().fetchall()
        if not cats:
            fail("No categories linked — tradie must add trade categories in onboarding")
        else:
            for c in cats:
                ok(f"Category: {c['name']} (id={c['category_id']}, slug={c['slug']})")
        cat_ids = [c['category_id'] for c in cats]

        # ── 4. Latest jobs ────────────────────────────────────────────────────
        print("\n─── 4. RECENT JOBS ───")
        if JOB_ID:
            result = await db.execute(
                text("SELECT id, title, category_id, suburb, state, lat, lng, match_intelligence, created_at FROM jobs WHERE id = :jid"),
                {"jid": JOB_ID}
            )
        else:
            result = await db.execute(
                text("SELECT id, title, category_id, suburb, state, lat, lng, match_intelligence, created_at FROM jobs ORDER BY created_at DESC LIMIT 3")
            )
        jobs = result.mappings().fetchall()
        if not jobs:
            fail("No jobs found in database")
            return

        for job in jobs:
            print(f"\n  Job: {job['title']} (id={job['id']})")
            info(f"  Created: {job['created_at']}")
            info(f"  Category ID: {job['category_id']}")
            info(f"  Suburb: {job['suburb']}, {job['state']}")
            if job['lat'] and job['lng']:
                ok(f"  Geocoded: ({job['lat']:.4f}, {job['lng']:.4f})")
            else:
                warn(f"  No coordinates — Nominatim geocoding failed for '{job['suburb']}, {job['state']}'")

            # Check category match
            if cat_ids and job['category_id'] in cat_ids:
                ok("  Category MATCHES tradie's registered category ✓")
            else:
                # Get the job's category name for better error message
                cat_result = await db.execute(
                    text("SELECT name, slug FROM categories WHERE id = :cid"),
                    {"cid": job['category_id']}
                )
                job_cat = cat_result.mappings().fetchone()
                job_cat_name = job_cat['name'] if job_cat else job['category_id']
                fail(f"  Category MISMATCH — job needs '{job_cat_name}' but tradie has: {[c['name'] for c in cats] or 'none'}")

            # Check match_intelligence
            if job['match_intelligence']:
                mi = json.loads(job['match_intelligence'])
                info(f"  match_intelligence: {mi}")
                if mi.get('matched', 0) == 0:
                    warn("  Lead distribution ran but matched 0 tradies")
                else:
                    ok(f"  Lead distribution ran — matched {mi['matched']} tradie(s)")
            else:
                warn("  match_intelligence is NULL — lead distribution has NOT run yet for this job")
                warn("  This means either Celery is down and background task hasn't fired yet, or job was never queued")

        # ── 5. Existing leads ─────────────────────────────────────────────────
        print("\n─── 5. LEADS FOR THIS TRADIE ───")
        result = await db.execute(
            text("SELECT id, job_id, status, sent_at FROM leads WHERE tradie_id = :pid ORDER BY sent_at DESC LIMIT 10"),
            {"pid": profile_id}
        )
        leads = result.mappings().fetchall()
        if leads:
            for l in leads:
                ok(f"Lead: job={l['job_id']}, status={l['status']}, sent={l['sent_at']}")
        else:
            fail("No leads found for this tradie at all")

        # ── 6. Quick fix instructions ─────────────────────────────────────────
        print(f"\n{'='*60}")
        print(" QUICK FIX")
        print(f"{'='*60}")

        issues = []
        if not profile:
            issues.append("Complete tradie onboarding at /tradie/onboarding")
        elif not profile['is_available']:
            issues.append("Set is_available=True: UPDATE tradie_profiles SET is_available=true WHERE id='" + str(profile_id) + "';")
        if not cats:
            issues.append("Add Electrician category via onboarding or Django admin")
        elif jobs and jobs[0]['category_id'] not in cat_ids:
            issues.append(f"Add category id='{jobs[0]['category_id']}' to tradie_categories for tradie id='{profile_id}'")

        if not issues:
            print("\n  All checks passed. Run the re-distribute script below to force-send the lead:\n")
        else:
            print("\n  Fix these issues first:")
            for i, issue in enumerate(issues, 1):
                print(f"  {i}. {issue}")
            print()

        # ── 7. Force re-distribute command ────────────────────────────────────
        if jobs:
            latest_job_id = jobs[0]['id']
            print("  To force re-distribute leads for the latest job, run:")
            print(f"\n    python scripts/force_distribute.py {latest_job_id}\n")

    await engine.dispose()


asyncio.run(main())

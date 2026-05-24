import asyncio

from sqlalchemy import select

from db.session import AsyncSessionLocal
from models.job import Job


async def main():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Job).order_by(Job.created_at.desc()).limit(1))
        job = res.scalar_one_or_none()
        if not job:
            print("No jobs found")
            return
        job_id = job.id
        print(f"Triggering lead distribution for {job_id}")

    from tasks.lead_tasks import _distribute_leads
    await _distribute_leads(job_id)

asyncio.run(main())

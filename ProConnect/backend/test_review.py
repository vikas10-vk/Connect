import asyncio
import os
from dotenv import load_dotenv

load_dotenv(dotenv_path=r"C:\Users\Capstone\Intership_main\ProConnect\.env", override=True)

from db.session import AsyncSessionLocal
from sqlalchemy import select
from models.user import User
from models.category import Category
from models.tradie_profile import TradieProfile
from models.job import Job
from models.lead import Lead
from models.quote import Quote
from models.review import Review

async def main():
    async with AsyncSessionLocal() as db:
        job_id = "efc7099f-1970-4f16-9e05-493d9e0afd5d"
        tradie_id_from_req = "07fac6d9-3f5a-4f16-9db5-26aeebe38f23"
        correct_tradie = "07fac6d9-3f5a-4f61-9db5-26aeebe38f23"
        
        job = await db.scalar(select(Job).where(Job.id == job_id))
        print(f"Job: {job}")
        if job:
            print(f"Job status: {job.status}")
            print(f"Job homeowner_id: {job.homeowner_id}")
            
        tradie1 = await db.scalar(select(TradieProfile).where(TradieProfile.id == tradie_id_from_req))
        print(f"Tradie from user request (4f16): {tradie1}")

        tradie2 = await db.scalar(select(TradieProfile).where(TradieProfile.id == correct_tradie))
        print(f"Tradie returned by /profile/me (4f61): {tradie2}")

if __name__ == "__main__":
    asyncio.run(main())

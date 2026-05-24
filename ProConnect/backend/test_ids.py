import asyncio
import json
import os

import asyncpg
from dotenv import load_dotenv

load_dotenv(dotenv_path=r"C:\Users\Capstone\Intership_main\ProConnect\.env", override=True)

async def check():
    url = os.getenv("DATABASE_URL").replace("+asyncpg", "")
    conn = await asyncpg.connect(url)

    with open("db_out.txt", "w") as f:
        f.write("Tradies:\n")
        tradies = await conn.fetch("SELECT id, user_id, business_name FROM tradie_profiles")
        for t in tradies:
            f.write(json.dumps(dict(t)) + "\n")

        f.write("\nJobs:\n")
        jobs = await conn.fetch("SELECT id, homeowner_id, title, status FROM jobs")
        for j in jobs:
            f.write(json.dumps(dict(j)) + "\n")

    await conn.close()

asyncio.run(check())

import asyncio
from db.session import engine
from sqlalchemy import text

async def main():
    async with engine.begin() as conn:
        print("--- ALL USERS ---")
        res = await conn.execute(text("SELECT email, role, is_verified FROM users"))
        for row in res.fetchall():
            print(row)
            
        print("\n--- TRADIE PROFILES ---")
        res = await conn.execute(text("SELECT user_id, verification_status, business_name FROM tradie_profiles"))
        for row in res.fetchall():
            print(row)

asyncio.run(main())

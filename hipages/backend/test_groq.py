from main import *
from db.session import AsyncSessionLocal
from models.user import User
from sqlalchemy import select
from services.ai_agent_service import run_agent
import asyncio

async def test():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).limit(1))
        user = result.scalar_one_or_none()
        if user:
            print("Running agent...")
            res = await run_agent("I need an electrician urgently", [], user, db, "test-1234")
            print(res)
        else:
            print("No user.")

asyncio.run(test())

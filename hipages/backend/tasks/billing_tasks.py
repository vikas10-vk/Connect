from celery import shared_task
from db.session import AsyncSessionLocal
from models.tradie_profile import TradieProfile
from sqlalchemy import select
import asyncio


async def _sweep_expired_subscriptions():
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(TradieProfile).where(TradieProfile.credits <= 0)
        )
        tradies = result.scalars().all()
        count = 0
        for tradie in tradies:
            if tradie.is_available:
                tradie.is_available = False
                db.add(tradie)
                count += 1
        await db.commit()
        print(f"Swept {count} tradies with zero credits")


@shared_task
def sweep_expired_subscriptions():
    asyncio.run(_sweep_expired_subscriptions())
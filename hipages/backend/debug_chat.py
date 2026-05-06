import asyncio
import os
import json
from sqlalchemy.ext.asyncio import AsyncSession
from db.session import get_db, AsyncSessionLocal

# Import ALL mapping classes first
from models.user import User
from models.tradie_profile import TradieProfile
from models.category import Category
from models.tradie_category import TradieCategory
from models.job import Job
from models.lead import Lead
from models.quote import Quote
from models.review import Review
from models.job_photo import JobPhoto
from models.inquiry import Inquiry
from models.home_asset import HomeAsset
from models.tradie_pass import TradiePass
from models.tradie_preference import TradiePreference
from models.earnings_record import EarningsRecord
from models.swms_document import SWMSDocument
from models.chat_conversation import ChatConversation

from services.ai_agent_service import run_agent
from sqlalchemy import select

async def simulate_chat():
    os.environ["GROQ_API_KEY"] = "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"
    
    async with AsyncSessionLocal() as db:
        # Get a homeowner user
        result = await db.execute(select(User).where(User.role == "homeowner").limit(1))
        user = result.scalar_one_or_none()
        if not user:
            print("No homeowner found")
            return

        print(f"Simulating chat for user: {user.email}")
        
        try:
            result = await run_agent(
                message="I need an electrician urgently",
                history=[],
                user=user,
                db=db,
                session_id="test-session"
            )
            print("Result:")
            print(json.dumps(result, indent=2))
        except Exception as e:
            print(f"ERROR OCCURRED: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(simulate_chat())

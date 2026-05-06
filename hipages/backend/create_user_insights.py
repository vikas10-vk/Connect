import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from db.session import get_db

async def create_table():
    async for db in get_db():
        try:
            await db.execute(text("""
            CREATE TABLE IF NOT EXISTS user_insights (
                id VARCHAR PRIMARY KEY,
                user_id VARCHAR REFERENCES users(id) ON DELETE CASCADE,
                home_suburb VARCHAR,
                home_state VARCHAR,
                home_postcode VARCHAR,
                mentioned_problems TEXT,
                mentioned_assets TEXT,
                trade_interests TEXT,
                unresolved_issues TEXT,
                key_tags TEXT,
                user_intent VARCHAR,
                last_sentiment VARCHAR,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            );
            """))
            await db.commit()
            print("Table user_insights created.")
        except Exception as e:
            print(f"Error: {e}")
            await db.rollback()

if __name__ == "__main__":
    asyncio.run(create_table())

import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv(dotenv_path=r"C:\Users\Capstone\Intership_main\ProConnect\.env")

async def test_conn():
    url = os.getenv("DATABASE_URL")
    print(f"URL: {url}")
    # asyncpg expects the URL to be postgresql:// instead of postgresql+asyncpg://
    url = url.replace("+asyncpg", "")
    try:
        conn = await asyncpg.connect(url)
        print("Success!")
        await conn.close()
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(test_conn())

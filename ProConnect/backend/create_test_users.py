import asyncio
import os
import uuid
import sys

from dotenv import load_dotenv

load_dotenv(
    dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"),
    override=True
)

from main import *
from db.session import AsyncSessionLocal
from models.user import User, UserRole
from sqlalchemy import select
from services.auth_service import hash_password

async def create_users():
    async with AsyncSessionLocal() as db:
        users_to_create = [
            {
                "email": "test@gmail.com",
                "full_name": "Test Homeowner",
                "role": UserRole.HOMEOWNER,
                "password": "password123"
            },
            {
                "email": "tradie@gmail.com",
                "full_name": "Test Tradie",
                "role": UserRole.TRADIE,
                "password": "password123"
            }
        ]

        for user_data in users_to_create:
            email = user_data["email"]
            result = await db.execute(select(User).where(User.email == email))
            existing_user = result.scalar_one_or_none()

            if existing_user:
                print(f"User {email} already exists. Skipping.")
                continue

            new_user = User(
                id=str(uuid.uuid4()),
                email=email,
                full_name=user_data["full_name"],
                role=user_data["role"],
                hashed_password=hash_password(user_data["password"])
            )
            db.add(new_user)
            print(f"Created user: {email} with role {user_data['role']}")

        await db.commit()

if __name__ == "__main__":
    asyncio.run(create_users())

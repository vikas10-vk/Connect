import asyncio
import uuid
from db.session import AsyncSessionLocal
from sqlalchemy import text

async def main():
    async with AsyncSessionLocal() as db:
        # 1. Get User
        res = await db.execute(text("SELECT id FROM users WHERE email = 'john@tradie.com'"))
        user = res.fetchone()
        if not user:
            print("Tradie user not found!")
            return
        user_id = user.id
        
        # Verify user
        await db.execute(text(f"UPDATE users SET is_verified = true WHERE id = '{user_id}'"))
        await db.commit()
        
        # 2. Check or create Profile
        res = await db.execute(text(f"SELECT id FROM tradie_profiles WHERE user_id = '{user_id}'"))
        profile = res.fetchone()
        
        if not profile:
            profile_id = str(uuid.uuid4())
            await db.execute(text(f"""
                INSERT INTO tradie_profiles (id, user_id, business_name, abn, verification_status, is_available, radius_km, lat, lng, solo_or_team, credits, created_at, updated_at)
                VALUES ('{profile_id}', '{user_id}', 'Tradie Carpentry', '12345678901', 'approved', true, 50, -33.8688, 151.2093, 'solo', 0, NOW(), NOW())
            """))
            await db.commit()
            print(f"Created profile {profile_id}")
        else:
            profile_id = profile.id
            await db.execute(text(f"UPDATE tradie_profiles SET verification_status = 'approved', is_available = true, lat = -33.8688, lng = 151.2093, radius_km = 50 WHERE id = '{profile_id}'"))
            await db.commit()
            print(f"Updated profile {profile_id}")
            
        # 3. Check or create category link for Carpenter
        res = await db.execute(text("SELECT id, name FROM categories WHERE name ILIKE '%Carpenter%' OR name ILIKE '%Carpentry%' LIMIT 1"))
        cat = res.fetchone()
        if not cat:
            print("Carpenter category not found in DB!")
        else:
            cat_id = cat.id
            res = await db.execute(text(f"SELECT * FROM tradie_categories WHERE tradie_id = '{profile_id}' AND category_id = '{cat_id}'"))
            if not res.fetchone():
                await db.execute(text(f"INSERT INTO tradie_categories (tradie_id, category_id) VALUES ('{profile_id}', '{cat_id}')"))
                await db.commit()
                print(f"Added category {cat.name} to tradie")
            else:
                print(f"Tradie already has category {cat.name}")
                
        print("Done fixing tradie@gmail.com")

asyncio.run(main())
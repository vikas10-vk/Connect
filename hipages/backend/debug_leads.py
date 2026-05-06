import asyncio
from db.session import engine
from sqlalchemy import text
import math

def haversine_distance(lat1, lng1, lat2, lng2):
    R = 6371
    if not lat1 or not lng1 or not lat2 or not lng2: return float('inf')
    lat1, lng1, lat2, lng2 = map(math.radians, [lat1, lng1, lat2, lng2])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))

async def main():
    async with engine.begin() as conn:
        res = await conn.execute(text("SELECT id, title, category_id, lat, lng, suburb FROM jobs ORDER BY created_at DESC LIMIT 1"))
        job = res.fetchone()
        if not job:
            print("No jobs!")
            return
        print(f"Job: {job.title} | Suburb: {job.suburb} | Lat/Lng: {job.lat}, {job.lng}")
        
        res = await conn.execute(text("SELECT id FROM users WHERE email = 'john@tradie.com'"))
        john_user = res.fetchone()
        if not john_user:
            print("John not found")
            return
            
        res = await conn.execute(text(f"SELECT id, radius_km, lat, lng, is_available FROM tradie_profiles WHERE user_id = '{john_user.id}'"))
        john_prof = res.fetchone()
        print(f"John Prof: lat={john_prof.lat}, lng={john_prof.lng}, radius={john_prof.radius_km}, available={john_prof.is_available}")
        if not john_prof: return
        
        dist = haversine_distance(job.lat, job.lng, john_prof.lat, john_prof.lng)
        print(f"Distance to job: {dist} km (Radius: {john_prof.radius_km} km)")
        
        if dist > john_prof.radius_km:
            print("Job is OUTSIDE of John's radius!")
        else:
            print("Job is INSIDE John's radius.")
            
        res = await conn.execute(text(f"SELECT service_suburbs FROM tradie_preferences WHERE tradie_id = '{john_prof.id}'"))
        pref = res.fetchone()
        print(f"Service Suburbs: {pref.service_suburbs if pref else 'None'}")
        
asyncio.run(main())

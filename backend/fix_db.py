import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def main():
    client = AsyncIOMotorClient('mongodb://localhost:27017')
    db = client.taxpilot
    res = await db.users.update_one({'email': 'admin@taxpilot.com'}, {'$set': {'firm_id': 'firm-demo-001'}})
    print(f"Matched: {res.matched_count}, Modified: {res.modified_count}")

asyncio.run(main())

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def main():
    client = AsyncIOMotorClient('mongodb://localhost:27017')
    db = client.taxpilot
    users = await db.users.find().to_list(100)
    print("USERS:", users)
    
    firms = await db.firms.find().to_list(100)
    print("FIRMS:", firms)

asyncio.run(main())

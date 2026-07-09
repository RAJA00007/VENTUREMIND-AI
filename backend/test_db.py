import asyncio

from database.database import engine


async def test():
    async with engine.begin() as conn:
        print("Database connected successfully 🚀")


asyncio.run(test())
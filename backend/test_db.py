import asyncio

from database.database import engine


async def check_db():
    async with engine.begin() as conn:
        print("Database connected successfully 🚀")


if __name__ == '__main__':
    asyncio.run(check_db())
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker
)

from core.config import settings



engine = create_async_engine(

    settings.DATABASE_URL,

    echo=True

)



AsyncSessionLocal = async_sessionmaker(

    bind=engine,

    expire_on_commit=False

)



async def get_db():


    async with AsyncSessionLocal() as session:


        try:


            yield session


        finally:


            await session.close()
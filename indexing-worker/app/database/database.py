from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine
)

from app.config import settings

print("WORKER DATABASE URL:", settings.database_url)
engine = create_async_engine(
    settings.database_url,
    echo=False
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

engine = create_async_engine(
    settings.database_url,
    echo=True
)
print("DATABASE:", settings.database_url)
print("DIALECT:", engine.dialect.name)
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.config import settings
from database.base import Base
# Import every mapped model before creating tables.  Otherwise a fresh database
# misses tables whose modules have not yet been imported by an API route.
from models import Analysis, Company, User  # noqa: F401

db_url = settings.DATABASE_URL or ""
connect_args = {}

if db_url.startswith("postgresql+asyncpg://"):
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql+psycopg://")

# Fallback to SQLite if DATABASE_URL is not set or Postgres is not available
if not db_url or "sqlite" in db_url:
    db_url = "sqlite:///./venturemind.db"
    connect_args = {"check_same_thread": False}

try:
    if "postgresql" in db_url:
        connect_args["connect_timeout"] = 2
    engine = create_engine(
        db_url,
        echo=settings.DEBUG,
        connect_args=connect_args,
    )
    # Test connection; if postgres fails, fallback to local sqlite
    with engine.connect() as conn:
        pass
except Exception:
    db_url = "sqlite:///./venturemind.db"
    engine = create_engine(
        db_url,
        echo=settings.DEBUG,
        connect_args={"check_same_thread": False},
    )

# Ensure tables are created
Base.metadata.create_all(bind=engine)

SessionLocal = sessionmaker(
    bind=engine,
    expire_on_commit=False
)

def get_db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

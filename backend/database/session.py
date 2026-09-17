import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.config import settings
from core.logging import app_logger
from database.base import Base
# Import every mapped model before creating tables.
from models import Analysis, Company, User, AnalysisJob  # noqa: F401
from models.company import Founder, FundingRound, CompanyFinancial  # noqa: F401


db_url = settings.DATABASE_URL or ""
connect_args = {}

if db_url.startswith("postgresql+asyncpg://"):
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql+psycopg://")

# Fallback to SQLite if DATABASE_URL is not set or Postgres is not available
if not db_url or "sqlite" in db_url:
    db_url = "sqlite:///./venturemind.db"
    connect_args = {"check_same_thread": False}

try:
    engine = create_engine(
        db_url,
        echo=settings.DEBUG,
        connect_args=connect_args,
    )
except Exception:
    db_url = "sqlite:///./venturemind.db"
    engine = create_engine(
        db_url,
        echo=settings.DEBUG,
        connect_args={"check_same_thread": False},
    )

SessionLocal = sessionmaker(
    bind=engine,
    expire_on_commit=False
)

_db_initialized = False


def _migrate_columns(eng):
    """Deprecated runtime migration helper. Schema is now authoritatively managed via Alembic."""
    try:
        from sqlalchemy import text
        with eng.connect() as conn:
            if "sqlite" in str(eng.url):
                # Check analyses
                res = conn.execute(text("PRAGMA table_info(analyses)")).fetchall()
                analysis_cols = [r[1] for r in res]
                if analysis_cols and "user_id" not in analysis_cols:
                    conn.execute(text("ALTER TABLE analyses ADD COLUMN user_id INTEGER REFERENCES users(id)"))
                    conn.commit()

                # Check companies
                res = conn.execute(text("PRAGMA table_info(companies)")).fetchall()
                company_cols = [r[1] for r in res]
                if company_cols and "created_by_user_id" not in company_cols:
                    conn.execute(text("ALTER TABLE companies ADD COLUMN created_by_user_id INTEGER REFERENCES users(id)"))
                    conn.commit()
    except Exception as e:
        app_logger.warning(f"[Database] Column migration note: {e}")


def init_db():
    """Initializes database tables safely without blocking module import time."""
    global engine, SessionLocal, _db_initialized
    if _db_initialized:
        return

    try:
        if "postgresql" in str(engine.url):
            with engine.connect():
                pass
        Base.metadata.create_all(bind=engine)
        _migrate_columns(engine)
        app_logger.info(f"[Database] Verified tables successfully on {engine.url.drivername}")
    except Exception as exc:
        app_logger.warning(f"[Database] Primary database connection failed ({exc}) — falling back to SQLite.")
        fallback_url = "sqlite:///./venturemind.db"
        engine = create_engine(
            fallback_url,
            echo=settings.DEBUG,
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(bind=engine)
        _migrate_columns(engine)
        SessionLocal.configure(bind=engine)

    _db_initialized = True


def get_db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


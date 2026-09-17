import sys
from pathlib import Path
from logging.config import fileConfig

from sqlalchemy import create_engine, pool
from alembic import context

# Ensure backend root is in sys.path regardless of invocation directory
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from core.config import settings
from database.base import Base
# Import all canonical models so target_metadata represents the complete schema
from models.user import User  # noqa: F401
from models.company import Company, Founder, FundingRound, CompanyFinancial  # noqa: F401
from models.analysis import Analysis  # noqa: F401
from models.analysis_job import AnalysisJob  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_database_url() -> str:
    """Dynamically resolves the target database URL."""
    # Check for CLI -x db_url=<url> override
    cmd_kwargs = context.get_x_argument(as_dictionary=True)
    if "db_url" in cmd_kwargs and cmd_kwargs["db_url"]:
        url = cmd_kwargs["db_url"]
    elif settings.DATABASE_URL and settings.DATABASE_URL.strip():
        url = settings.DATABASE_URL
    else:
        url = config.get_main_option("sqlalchemy.url") or "sqlite:///./venturemind.db"

    # Normalize PostgreSQL drivers for Alembic synchronous migration engine
    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql+psycopg://")
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://")

    return url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_database_url()
    is_sqlite = "sqlite" in url
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=is_sqlite,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    url = get_database_url()
    connect_args = {}
    is_sqlite = "sqlite" in url
    if is_sqlite:
        connect_args["check_same_thread"] = False

    connectable = create_engine(
        url,
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=is_sqlite,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()


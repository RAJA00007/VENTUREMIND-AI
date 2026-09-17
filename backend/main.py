from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.logging import app_logger

from api.company import router as company_router
from api.analysis import router as analysis_router
from api.chat import router as chat_router
from api.document import router as document_router
from api.auth import router as auth_router
from api.jobs import router as jobs_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    app_logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}....")
    try:
        from database.session import init_db
        init_db()
        from services.job_service import job_service
        job_service.reap_stale_jobs()
    except Exception as e:
        app_logger.warning(f"Database startup initialization note: {e}")
    yield

    app_logger.info(f"Shutting down {settings.APP_NAME}....")
    try:
        from workflows.chat_workflow import close_checkpointer_pool
        close_checkpointer_pool()
    except Exception as e:
        app_logger.warning(f"Error closing checkpointer pool on shutdown: {e}")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan
)

allowed_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {
        "project": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running"
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy"
    }


app.include_router(
    auth_router,
    prefix="/api/v1"
)

app.include_router(
    company_router,
    prefix="/api/v1"
)

app.include_router(
    analysis_router,
    prefix="/api/v1"
)

app.include_router(
    document_router,
    prefix="/api/v1"
)

app.include_router(
    chat_router,
    prefix="/api/v1"
)

app.include_router(
    jobs_router,
    prefix="/api/v1"
)


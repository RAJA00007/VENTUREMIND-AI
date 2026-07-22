from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


from api.company import router as company_router
from api.analysis import router as analysis_router
from api.chat import router as chat_router


from core.config import settings
from core.logging import app_logger

# pyrefly: ignore [missing-import]
from api.document import router as document_router

app = FastAPI(

    title=settings.APP_NAME,

    version=settings.APP_VERSION

)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



# ==========================
# Startup Event
# ==========================


@app.on_event("startup")
async def startup_event():

    app_logger.info(
        "Starting VentureMind AI...."
    )



# ==========================
# Health Routes
# ==========================


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

        "status":"healthy"

    }



# ==========================
# API Routes
# ==========================


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
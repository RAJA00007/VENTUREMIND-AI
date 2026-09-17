import os
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    APP_NAME: str = "VentureMind AI"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    OPENAI_API_KEY: Optional[str] = None
    TAVILY_API_KEY: Optional[str] = None
    GITHUB_TOKEN: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None
    OPENROUTER_API_KEY: Optional[str] = None
    CEREBRAS_API_KEY: Optional[str] = None
    TOGETHER_API_KEY: Optional[str] = None
    DEEPSEEK_API_KEY: Optional[str] = None

    # Local Ollama Provider Configuration
    OLLAMA_BASE_URL: str = "http://localhost:11434/v1"
    OLLAMA_MODEL: str = "llama3.2"

    DATABASE_URL: str = ""
    JWT_SECRET_KEY: Optional[str] = None

    # Caching Layer Configuration
    REDIS_URL: Optional[str] = None
    CACHE_BACKEND: str = "sqlite"
    SEARCH_CACHE_TTL_SECONDS: int = 172800
    GITHUB_CACHE_TTL_SECONDS: int = 43200
    LLM_CACHE_TTL_SECONDS: int = 86400
    CHROMA_PERSIST_DIRECTORY: Optional[str] = None

    # Provider Failover & Cooldown Tracker
    PROVIDER_COOLDOWN_SECONDS: int = 60
    PROVIDER_TRANSIENT_COOLDOWN_SECONDS: float = 15.0
    LLM_PROVIDER_TIMEOUT_SECONDS: int = 8
    LLM_CLOUD_TIMEOUT_SECONDS: float = 8.0
    LLM_LOCAL_TIMEOUT_SECONDS: float = 30.0
    ALLOW_MOCK_FALLBACK: bool = False

    # Chat Settings
    CHAT_HISTORY_MESSAGES: int = 8

    # Asynchronous Analysis Jobs
    MAX_CONCURRENT_ANALYSIS_JOBS: int = 2
    ANALYSIS_JOB_TIMEOUT_SECONDS: int = 600


    @property
    def jwt_secret(self) -> str:
        if self.JWT_SECRET_KEY:
            return self.JWT_SECRET_KEY
        if self.DEBUG:
            return "venturemind-dev-insecure-secret-key-32bytes-fallback"
        raise ValueError("JWT_SECRET_KEY must be configured in production (DEBUG=False)")

    model_config = SettingsConfigDict(
        env_file=str(ENV_PATH) if ENV_PATH.exists() else ".env",
        extra="ignore",
    )


settings = Settings()

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

    DATABASE_URL: str = ""

    # Caching Layer Configuration
    REDIS_URL: Optional[str] = None
    CACHE_BACKEND: str = "sqlite"
    SEARCH_CACHE_TTL_SECONDS: int = 172800
    GITHUB_CACHE_TTL_SECONDS: int = 43200
    LLM_CACHE_TTL_SECONDS: int = 86400

    # Provider Failover & Cooldown Tracker
    PROVIDER_COOLDOWN_SECONDS: int = 60
    LLM_PROVIDER_TIMEOUT_SECONDS: int = 8
    ALLOW_MOCK_FALLBACK: bool = True

    # Chat Settings
    CHAT_HISTORY_MESSAGES: int = 8

    model_config = SettingsConfigDict(
        env_file=str(ENV_PATH) if ENV_PATH.exists() else ".env",
        extra="ignore",
    )


settings = Settings()
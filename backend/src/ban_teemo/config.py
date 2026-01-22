"""Application configuration via pydantic-settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API Settings
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000

    # CORS - comma-separated origins
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Database
    database_url: str = "sqlite+aiosqlite:///../data/draft_assistant.db"

    # LLM Providers
    groq_api_key: str = ""
    together_api_key: str = ""

    # Feature flags
    enable_llm: bool = True


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()

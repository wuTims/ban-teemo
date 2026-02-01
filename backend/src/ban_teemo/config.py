"""Application configuration via pydantic-settings."""

from functools import lru_cache

from pydantic import computed_field
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

    # CORS - comma-separated origins (env var: CORS_ORIGINS)
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @computed_field
    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins as a list."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    # Database path (DuckDB file)
    database_path: str = "data/draft_data.duckdb"

    # LLM Provider (Nebius AI Studio)
    nebius_api_key: str = ""

    # Feature flags
    enable_llm: bool = True


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()

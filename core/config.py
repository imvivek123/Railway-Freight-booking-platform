"""Validated application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """RailRo runtime settings.

    Environment variables override values from the local ``.env`` file.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "RailRo API"
    app_version: str = "1.0.0"
    environment: str = "development"
    app_debug: bool = False
    log_level: str = "INFO"

    database_url: str = Field(min_length=1)
    database_echo: bool = False
    database_pool_size: int = Field(default=5, ge=1)
    database_max_overflow: int = Field(default=10, ge=0)
    database_pool_timeout: int = Field(default=30, ge=1)
    database_pool_recycle: int = Field(default=1800, ge=1)

    redis_url: str | None = None
    cors_allowed_origins: str = (
        "http://localhost:8000,http://127.0.0.1:8000"
    )

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        """Require PostgreSQL through SQLAlchemy's asyncpg dialect."""
        if not value.startswith("postgresql+asyncpg://"):
            raise ValueError(
                "DATABASE_URL must start with postgresql+asyncpg://"
            )
        return value

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        """Normalize and validate the configured logging level."""
        normalized = value.upper()
        if normalized not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("LOG_LEVEL is invalid")
        return normalized

    @property
    def cors_origins(self) -> list[str]:
        """Return the comma-separated CORS setting as normalized origins."""
        return [
            origin.strip()
            for origin in self.cors_allowed_origins.split(",")
            if origin.strip()
        ]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide validated settings singleton."""
    return Settings()


settings = get_settings()

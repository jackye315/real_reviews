from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Real Reviews API"
    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"

    database_url: str = "postgresql+psycopg://real_reviews:real_reviews@postgres:5432/real_reviews"
    frontend_origin: str = "http://localhost:5173"

    google_maps_server_api_key: str | None = None
    serpapi_api_key: str | None = None
    serpapi_default_review_limit: int = Field(default=50, ge=1, le=500)
    serpapi_review_sort: str = "newestFirst"
    serpapi_language: str = "en"
    serpapi_monthly_request_budget: int = Field(default=225, ge=0, le=100000)
    refresh_known_streak_limit: int = Field(default=10, ge=0, le=1000)

    review_provider: str = "serpapi"
    review_fallback_provider: str = "google_places"

    llm_base_url: AnyHttpUrl | None = None
    llm_model: str | None = None
    llm_api_key: str | None = None
    llm_timeout_seconds: int = Field(default=60, ge=1, le=300)
    llm_max_concurrency: int = Field(default=2, ge=1, le=20)
    llm_batch_max_chars: int = Field(default=18000, ge=1000, le=100000)

    http_timeout_seconds: int = Field(default=20, ge=1, le=120)

    @model_validator(mode="before")
    @classmethod
    def empty_strings_are_unset(cls, values):
        if isinstance(values, dict):
            return {key: (None if value == "" else value) for key, value in values.items()}
        return values

    @field_validator("database_url")
    @classmethod
    def normalize_async_database_url(cls, value: str) -> str:
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

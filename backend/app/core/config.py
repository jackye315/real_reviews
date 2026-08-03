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
    serpapi_review_sort: Literal["qualityScore", "newestFirst"] = "qualityScore"
    serpapi_language: str = "en"
    serpapi_monthly_request_budget: int = Field(default=225, ge=0, le=100000)
    serpapi_max_concurrency: int = Field(default=2, ge=1, le=20)
    serpapi_account_snapshot_ttl_seconds: int = Field(default=60, ge=1, le=3600)
    provider_hourly_request_limit: int | None = Field(default=None, ge=1, le=100000)
    provider_reservation_lease_seconds: int = Field(default=600, ge=30, le=3600)
    refresh_known_streak_limit: int = Field(default=10, ge=0, le=1000)
    review_cursor_signing_key: str = "development-review-cursor-signing-key"
    reviewer_context_enabled: bool = True
    reviewer_context_stale_after_days: int = Field(default=30, ge=1, le=3650)
    google_review_summary_enabled: bool = False
    google_review_summary_monthly_request_budget: int = Field(default=25, ge=0, le=100000)
    google_review_summary_max_concurrency: int = Field(default=1, ge=1, le=20)
    google_review_summary_language_code: str = "en"
    google_review_summary_region_code: str = "US"

    review_provider: str = "serpapi"
    review_fallback_provider: str = "google_places"

    llm_base_url: AnyHttpUrl | None = None
    llm_model: str | None = None
    llm_api_key: str | None = None
    llm_timeout_seconds: int = Field(default=60, ge=1, le=300)
    llm_max_concurrency: int = Field(default=2, ge=1, le=20)
    llm_batch_max_chars: int = Field(default=18000, ge=1000, le=100000)
    llm_name_batch_max_candidates: int = Field(default=100, ge=1, le=1000)
    # Development-only diagnostics. Logs review UUIDs and LLM-selected UUIDs, never names or review text.
    llm_filter_debug_logging: bool = False
    local_dish_summary_enabled: bool = False
    local_dish_summary_max_reviews: int = Field(default=50, ge=1, le=50)
    local_dish_summary_max_review_chars: int = Field(default=4000, ge=1, le=20000)
    local_dish_summary_max_total_chars: int = Field(default=20000, ge=1, le=100000)
    local_dish_summary_max_request_bytes: int = Field(default=131072, ge=1024, le=1048576)
    local_dish_summary_max_output_chars: int = Field(default=800, ge=1, le=10000)
    local_dish_summary_log_content: bool = False

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

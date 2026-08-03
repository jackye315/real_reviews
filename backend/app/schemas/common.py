from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ErrorResponse(APIModel):
    code: str
    message: str


class Viewport(APIModel):
    low: dict[str, float] | None = None
    high: dict[str, float] | None = None
    raw: dict[str, Any] | None = None


class PlaceResponse(APIModel):
    id: UUID
    google_place_id: str
    display_name: str
    formatted_address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    viewport: dict[str, Any] | None = None
    place_types: list[str] | None = None
    google_maps_url: str | None = None
    llm_dish_summary: str | None = None
    created_at: datetime
    updated_at: datetime


class Pagination(APIModel):
    next_page_token: str | None = None


class ConstrainedPlaceIdMixin(APIModel):
    @field_validator("place_id", check_fields=False)
    @classmethod
    def validate_place_id(cls, value: str) -> str:
        value = value.strip()
        if not value or len(value) > 255:
            raise ValueError("invalid place_id")
        return value


class MessageResponse(APIModel):
    ok: bool = True
    message: str | None = None

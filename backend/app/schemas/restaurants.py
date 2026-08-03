from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas.common import APIModel, PlaceResponse


class Coordinates(APIModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class PlaceSelectionRequest(APIModel):
    google_place_id: str = Field(min_length=1, max_length=255)
    display_name: str = Field(min_length=1, max_length=500)
    formatted_address: str | None = Field(default=None, max_length=2000)
    location: Coordinates | None = None
    viewport: dict[str, Any] | None = None
    place_types: list[str] = Field(default_factory=list, max_length=50)
    google_maps_url: str | None = Field(default=None, max_length=4000)

    @field_validator("place_types")
    @classmethod
    def limit_type_lengths(cls, value: list[str]) -> list[str]:
        return [item[:100] for item in value[:50]]


class RestaurantSearchRequest(APIModel):
    query: str = Field(min_length=1, max_length=200)
    page_token: str | None = Field(default=None, max_length=2000)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    radius_meters: int | None = Field(default=5000, ge=100, le=50000)
    page_size: int = Field(default=10, ge=1, le=10)


class RestaurantSearchResult(APIModel):
    google_place_id: str
    display_name: str
    formatted_address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    viewport: dict[str, Any] | None = None
    place_types: list[str] | None = None
    google_maps_url: str | None = None
    rating: float | None = None
    user_rating_count: int | None = None
    distance_meters: int | None = None


class RestaurantSearchPage(APIModel):
    results: list[RestaurantSearchResult]
    next_page_token: str | None = None


class RestaurantDetailResponse(APIModel):
    place: PlaceResponse
    stored_review_count: int
    last_fetch_time: str | None = None


class DishSummaryRequest(APIModel):
    review_texts: list[str] = Field(min_length=1, max_length=50)


class DishSummaryResponse(APIModel):
    summary: str


class GoogleReviewSummaryRequest(APIModel):
    confirm_cost: bool = False


class GoogleSummaryLocalizedText(APIModel):
    text: str
    language_code: str | None = None


class GoogleReviewSummaryOperation(APIModel):
    id: UUID
    settled_units: int


class GoogleReviewSummaryResponse(APIModel):
    status: Literal["available", "unavailable"]
    text: GoogleSummaryLocalizedText | None = None
    disclosure: GoogleSummaryLocalizedText | None = None
    reviews_uri: str | None = None
    flag_content_uri: str | None = None
    operation: GoogleReviewSummaryOperation

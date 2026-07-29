from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas.common import APIModel


class ReviewResponse(APIModel):
    id: UUID
    rating: int | None = None
    text: str | None = None
    original_text: str | None = None
    publication_timestamp: datetime | None = None
    last_edit_timestamp: datetime | None = None
    canonical_source_url: str | None = None
    author_display_name: str | None = None
    author_avatar_url: str | None = None
    source_labels: list[str] = Field(default_factory=list)
    first_fetched_at: datetime
    last_seen_at: datetime
    suspected_duplicate: bool = False


class ReviewTopicResponse(APIModel):
    provider_topic_id: str
    keyword: str
    mentions: int | None = None
    language_code: str | None = None
    rank: int


class ReviewListResponse(APIModel):
    reviews: list[ReviewResponse]
    total: int
    topics: list[ReviewTopicResponse] = Field(default_factory=list)
    topics_fetched_at: datetime | None = None


class ReviewSyncRequest(APIModel):
    target_count: int | None = Field(default=None, ge=1, le=500)
    force: bool = False
    confirm_cost: bool = False
    cursor: str | None = Field(default=None, max_length=4000)


class ReviewSyncResponse(APIModel):
    place_id: str
    status: str
    collected_unique_count: int
    successful_request_count: int
    pagination_cursor: str | None = None
    stop_reason: str | None = None
    reviews: list[ReviewResponse]
    topics: list[ReviewTopicResponse] = Field(default_factory=list)
    topics_fetched_at: datetime | None = None
    fallback_used: bool = False
    message: str | None = None


class ReviewFilterItem(APIModel):
    id: UUID
    text: str = Field(max_length=10000)
    rating: int | None = Field(default=None, ge=1, le=5)
    publication_date: datetime | None = None


class ReviewFilterRequest(APIModel):
    filter_text: str = Field(min_length=1, max_length=500)
    reviews: list[ReviewFilterItem] = Field(min_length=1, max_length=500)

    @field_validator("filter_text")
    @classmethod
    def reject_sensitive_trait_requests(cls, value: str) -> str:
        lowered = value.lower()
        forbidden = [
            "race",
            "ethnicity",
            "ethnic",
            "nationality",
            "religion",
            "politics",
            "political",
            "sexual orientation",
            "gender identity",
            "pregnant",
            "disability status",
        ]
        if any(term in lowered for term in forbidden):
            raise ValueError("Sensitive-trait filtering is not allowed")
        return value.strip()


class ReviewFilterResponse(APIModel):
    selected_review_ids: list[UUID]
    llm_used: bool
    message: str | None = None

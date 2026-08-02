from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas.common import APIModel


class ReviewSort(StrEnum):
    RELEVANT = "relevant"
    RECENT = "recent"
    OLDEST = "oldest"
    RATING_HIGH = "rating_high"
    RATING_LOW = "rating_low"


class ReviewImageResponse(APIModel):
    url: str
    position: int
    provider: str


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
    reviewer_id: UUID | None = None
    source_labels: list[str] = Field(default_factory=list)
    details: dict = Field(default_factory=dict)
    translated_details: dict = Field(default_factory=dict)
    images: list[ReviewImageResponse] = Field(default_factory=list)
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
    page_size: int = 20
    next_cursor: str | None = None
    has_more: bool = False
    review_corpus_version: int = 1
    total: int
    filtered_total: int
    topics: list[ReviewTopicResponse] = Field(default_factory=list)
    topics_fetched_at: datetime | None = None
    relevance_available: bool = False
    relevance_fetched_at: datetime | None = None
    relevance_ranked_count: int = 0
    relevance_status: str | None = None


class LoadMoreRequest(APIModel):
    additional_target_count: int = Field(ge=20, le=100)
    restart_from_newest: bool = False
    confirm_cost: bool = False

    @field_validator("additional_target_count")
    @classmethod
    def fixed_target(cls, value: int) -> int:
        if value not in {20, 50, 100}:
            raise ValueError("additional_target_count must be 20, 50, or 100")
        return value


class LoadMoreChoiceResponse(APIModel):
    provider_record_count: int
    estimated_request_count: int
    allowed: bool


class LoadMoreOptionsResponse(APIModel):
    cursor_available: bool
    active_operation_id: str | None = None
    remaining_effective_budget: int
    account_snapshot_age_seconds: int | None = None
    choices: list[LoadMoreChoiceResponse]


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
    operation_id: UUID | None = None
    estimated_request_count: int = 0
    cached_response_count: int = 0
    failed_request_count: int = 0
    uncertain_request_count: int = 0
    released_reserved_count: int = 0
    remaining_local_budget: int | None = None
    pagination_cursor: str | None = None
    stop_reason: str | None = None
    reviews: list[ReviewResponse]
    topics: list[ReviewTopicResponse] = Field(default_factory=list)
    topics_fetched_at: datetime | None = None
    fallback_used: bool = False
    message: str | None = None


REVIEWER_LABEL_OPTIONS = {
    "chinese": "Chinese",
    "korean": "Korean",
    "japanese": "Japanese",
    "american": "American",
    "italian": "Italian",
}

FORBIDDEN_FILTER_TERMS = [
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

class ReviewerLabelOption(APIModel):
    value: str
    label: str


class ReviewFilterOptionsResponse(APIModel):
    reviewer_label_options: list[ReviewerLabelOption]


class RestaurantReviewFilterRequest(APIModel):
    rating: int | None = Field(default=None, ge=1, le=5)
    reviewer_label: str | None = Field(default=None, max_length=50)
    content_filter: str | None = Field(default=None, max_length=500)
    sort: ReviewSort = ReviewSort.RECENT

    @field_validator("reviewer_label")
    @classmethod
    def validate_reviewer_label(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        normalized = value.strip().lower()
        if normalized not in REVIEWER_LABEL_OPTIONS:
            raise ValueError("Unknown reviewer-label filter")
        return normalized

    @field_validator("content_filter")
    @classmethod
    def validate_content_filter(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            return None
        lowered = stripped.lower()
        if any(term in lowered for term in FORBIDDEN_FILTER_TERMS):
            raise ValueError("Sensitive-trait filtering is not allowed")
        return stripped


class ReviewFilterResponse(APIModel):
    reviews: list[ReviewResponse]
    total: int
    candidate_count: int
    filtered_total: int
    selected_review_ids: list[UUID]
    skipped_missing_label_count: int = 0
    rating_filter: int | None = None
    reviewer_label_filter: str | None = None
    content_filter: str | None = None
    sort: ReviewSort = ReviewSort.RECENT
    llm_used: bool
    topics: list[ReviewTopicResponse] = Field(default_factory=list)
    topics_fetched_at: datetime | None = None
    message: str | None = None

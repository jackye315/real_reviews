from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.schemas.common import APIModel
from app.schemas.reviews import ReviewResponse


TimeWindow = Literal["six_months", "one_year", "two_years", "all_observed"]
MatchLevel = Literal["exact_type", "comparison_family"]


class ReviewerResponse(APIModel):
    id: UUID
    display_name: str | None = None
    avatar_url: str | None = None
    profile_url: str | None = None
    local_guide: bool | None = None
    provider_review_count: int | None = None
    provider_photo_count: int | None = None
    level: int | None = None
    points: int | None = None
    provider_rating_count: int | None = None
    context_status: str
    context_fetched_at: datetime | None = None
    context_generation: int = 0
    provider_results_returned: int | None = None
    accepted_food_and_drink_count: int | None = None
    rejected_non_food_count: int | None = None
    rejected_unknown_type_count: int | None = None
    rejected_missing_required_data_count: int | None = None


class ReviewerCurrentReviewResponse(APIModel):
    review: ReviewResponse
    restaurant_name: str
    restaurant_place_id: str | None = None
    normalized_venue_type: str | None = None
    comparison_family: str | None = None


class ReviewerRelevantReviewResponse(APIModel):
    id: UUID
    place_name: str
    rating: int
    text: str | None = None
    original_text: str | None = None
    provider_date_text: str | None = None
    publication_date_is_approximate: bool = False
    source_url: str | None = None


class ReviewerComparisonResponse(APIModel):
    current_rating: int
    match_level: MatchLevel
    normalized_venue_type: str | None = None
    comparison_family: str | None = None
    time_window: TimeWindow
    sample_size: int
    average_rating: float | None = None
    median_rating: float | None = None
    sample_variance: float | None = None
    standard_deviation: float | None = None
    difference_from_average: float | None = None
    rating_distribution: dict[str, int] = Field(default_factory=dict)
    individual_ratings: list[int] = Field(default_factory=list)
    contains_approximate_dates: bool = False
    snapshot_fetched_at: datetime | None = None
    context_generation: int = 0
    relevant_reviews: list[ReviewerRelevantReviewResponse] = Field(default_factory=list)


class ReviewerContextResponse(APIModel):
    reviewer: ReviewerResponse
    current: ReviewerCurrentReviewResponse
    comparison: ReviewerComparisonResponse | None = None
    broader_comparison: ReviewerComparisonResponse | None = None
    active_operation_id: UUID | None = None
    stale: bool = False


class ReviewerContextRequest(APIModel):
    current_review_id: UUID
    confirm_cost: bool = False
    force_refresh: bool = False


class ReviewerContextDeleteResponse(APIModel):
    contributor_only_reviews_removed: int
    observed_places_removed: int
    restaurant_confirmed_reviews_preserved: int


class ReviewerComparisonQuery(APIModel):
    current_review_id: UUID
    time_window: TimeWindow = "two_years"
    match_level: MatchLevel = "exact_type"

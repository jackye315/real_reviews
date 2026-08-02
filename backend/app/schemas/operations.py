from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.schemas.common import APIModel
from app.schemas.reviewers import ReviewerContextResponse


class HealthResponse(APIModel):
    status: str
    database: str
    app: str


class ProviderUsageResponse(APIModel):
    id: UUID
    provider: str
    plan_period: str
    operation_type: str = "serpapi_reviews"
    successful_request_count: int
    cached_response_count: int
    failed_request_count: int
    updated_at: datetime


class ProviderUsageListResponse(APIModel):
    usage: list[ProviderUsageResponse]


class ProviderOperationResponse(APIModel):
    operation_id: UUID
    provider: str
    operation_type: str
    place_id: str | None = None
    restaurant_name: str | None = None
    reviewer_id: UUID | None = None
    reviewer_name: str | None = None
    status: str
    estimated_request_count: int
    reserved_request_count: int
    successful_request_count: int
    cached_response_count: int
    failed_request_count: int
    uncertain_request_count: int
    released_reserved_count: int
    collected_unique_count: int
    remaining_local_budget: int | None = None
    stop_reason: str | None = None
    error_code: str | None = None
    recovery_available: bool = False
    recovery_estimated_request_count: int | None = None
    provider_sort: str | None = None
    requested_provider_record_count: int | None = None
    processed_provider_record_count: int | None = None
    new_canonical_review_count: int | None = None
    updated_existing_review_count: int | None = None
    unchanged_review_count: int | None = None
    total_stored_review_count: int | None = None
    recovery_scanned_record_count: int | None = None
    provider_results_returned: int | None = None
    accepted_food_and_drink_count: int | None = None
    rejected_non_food_count: int | None = None
    rejected_unknown_type_count: int | None = None
    rejected_missing_required_data_count: int | None = None
    duplicate_result_count: int | None = None
    context_generation: int | None = None
    reviewer_context: ReviewerContextResponse | None = None
    cancel_requested_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


class ProviderOperationListResponse(APIModel):
    operations: list[ProviderOperationResponse]


class ProviderOperationListQuery(APIModel):
    limit: int = Field(default=20, ge=1, le=20)

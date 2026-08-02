from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.schemas.operations import ProviderOperationResponse
from app.schemas.reviewers import (
    MatchLevel,
    ReviewerComparisonResponse,
    ReviewerContextDeleteResponse,
    ReviewerContextRequest,
    ReviewerContextResponse,
    TimeWindow,
)
from app.services.reviewer_context import ReviewerContextService

router = APIRouter()


@router.get("/reviewers/{reviewer_id}", response_model=ReviewerContextResponse)
async def get_reviewer_context(
    reviewer_id: UUID,
    current_review_id: UUID = Query(),
    session: AsyncSession = Depends(get_session),
):
    return await ReviewerContextService(session).profile(reviewer_id, current_review_id)


@router.get("/reviewers/{reviewer_id}/comparison", response_model=ReviewerComparisonResponse)
async def get_reviewer_comparison(
    reviewer_id: UUID,
    current_review_id: UUID = Query(),
    time_window: TimeWindow = "two_years",
    match_level: MatchLevel = "exact_type",
    session: AsyncSession = Depends(get_session),
):
    return await ReviewerContextService(session).comparison(reviewer_id, current_review_id, time_window, match_level)


@router.delete("/reviewers/{reviewer_id}/context", response_model=ReviewerContextDeleteResponse)
async def delete_reviewer_context(reviewer_id: UUID, session: AsyncSession = Depends(get_session)):
    return await ReviewerContextService(session).delete_context(reviewer_id)


@router.post("/reviewers/{reviewer_id}/context", response_model=ReviewerContextResponse | ProviderOperationResponse)
async def start_reviewer_context(
    reviewer_id: UUID,
    request: ReviewerContextRequest,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    session: AsyncSession = Depends(get_session),
):
    result = await ReviewerContextService(session).start_context(
        reviewer_id, request.current_review_id, request.confirm_cost, request.force_refresh, idempotency_key
    )
    if isinstance(result, ProviderOperationResponse) and result.status in {"reserved", "running"}:
        return JSONResponse(
            status_code=202,
            headers={"Location": f"/api/v1/provider-operations/{result.operation_id}", "Retry-After": "2"},
            content=result.model_dump(mode="json"),
        )
    return result

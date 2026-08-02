from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.schemas.common import MessageResponse
from app.schemas.operations import ProviderOperationResponse
from app.schemas.reviews import (
    LoadMoreOptionsResponse,
    LoadMoreRequest,
    RestaurantReviewFilterRequest,
    ReviewFilterOptionsResponse,
    ReviewFilterResponse,
    ReviewListResponse,
    ReviewSort,
    ReviewSyncRequest,
    ReviewSyncResponse,
)
from app.services.filtering import ReviewFilterService
from app.services.reviews import ReviewService

router = APIRouter()


@router.get("/restaurants/{place_id}/reviews", response_model=ReviewListResponse)
async def list_reviews(
    place_id: str,
    rating: Annotated[int | None, Query(ge=1, le=5)] = None,
    sort: ReviewSort | None = None,
    page_size: Annotated[int, Query(ge=1, le=50)] = 20,
    cursor: str | None = Query(default=None, max_length=4000),
    session: AsyncSession = Depends(get_session),
):
    return await ReviewService(session).list_reviews(place_id, rating=rating, sort=sort, page_size=page_size, cursor=cursor)


@router.get("/restaurants/{place_id}/reviews/load-more/options", response_model=LoadMoreOptionsResponse)
async def load_more_options(place_id: str, session: AsyncSession = Depends(get_session)):
    return await ReviewService(session).load_more_options(place_id)


@router.post("/restaurants/{place_id}/reviews/load-more", response_model=ProviderOperationResponse)
async def load_more_reviews(
    place_id: str,
    request: LoadMoreRequest,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    session: AsyncSession = Depends(get_session),
):
    return _operation_replay_response(await ReviewService(session).start_load_more(place_id, request, idempotency_key))


@router.post(
    "/restaurants/{place_id}/reviews/sync",
    response_model=ReviewSyncResponse | ProviderOperationResponse,
)
async def sync_reviews(
    place_id: str,
    request: ReviewSyncRequest | None = None,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    session: AsyncSession = Depends(get_session),
):
    result = await ReviewService(session).start_sync(
        place_id, request or ReviewSyncRequest(), idempotency_key
    )
    return _operation_replay_response(result)


@router.post(
    "/restaurants/{place_id}/reviews/check-new",
    response_model=ReviewSyncResponse | ProviderOperationResponse,
)
async def check_new_reviews(
    place_id: str,
    request: ReviewSyncRequest | None = None,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    session: AsyncSession = Depends(get_session),
):
    result = await ReviewService(session).start_check_new(
        place_id, request or ReviewSyncRequest(force=True), idempotency_key
    )
    return _operation_replay_response(result)


@router.post(
    "/restaurants/{place_id}/reviews/refresh",
    response_model=ReviewSyncResponse | ProviderOperationResponse,
)
async def refresh_reviews(
    place_id: str,
    request: ReviewSyncRequest | None = None,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    session: AsyncSession = Depends(get_session),
):
    result = await ReviewService(session).start_refresh(
        place_id, request or ReviewSyncRequest(force=True), idempotency_key
    )
    return _operation_replay_response(result)


def _operation_replay_response(result: ReviewSyncResponse | ProviderOperationResponse):
    if isinstance(result, ProviderOperationResponse) and result.status in {"reserved", "running"}:
        return JSONResponse(
            status_code=202,
            headers={
                "Location": f"/api/v1/provider-operations/{result.operation_id}",
                "Retry-After": "2",
            },
            content=result.model_dump(mode="json"),
        )
    return result


@router.delete("/restaurants/{place_id}/reviews", response_model=MessageResponse)
async def delete_reviews(place_id: str, session: AsyncSession = Depends(get_session)):
    count = await ReviewService(session).delete_reviews(place_id)
    return MessageResponse(message=f"Deleted {count} reviews.")


@router.get("/reviews/filter-options", response_model=ReviewFilterOptionsResponse)
async def filter_options():
    return ReviewFilterService().options()


@router.post("/restaurants/{place_id}/reviews/filter", response_model=ReviewFilterResponse)
async def filter_restaurant_reviews(
    place_id: str,
    request: RestaurantReviewFilterRequest,
    session: AsyncSession = Depends(get_session),
):
    return await ReviewFilterService(session).filter_restaurant(place_id, request)

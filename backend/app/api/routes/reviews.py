from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.schemas.common import MessageResponse
from app.schemas.reviews import (
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
    sort: ReviewSort = ReviewSort.RECENT,
    session: AsyncSession = Depends(get_session),
):
    return await ReviewService(session).list_reviews(place_id, rating=rating, sort=sort)


@router.post("/restaurants/{place_id}/reviews/sync", response_model=ReviewSyncResponse)
async def sync_reviews(
    place_id: str,
    request: ReviewSyncRequest | None = None,
    session: AsyncSession = Depends(get_session),
):
    return await ReviewService(session).sync(place_id, request or ReviewSyncRequest())


@router.post("/restaurants/{place_id}/reviews/refresh", response_model=ReviewSyncResponse)
async def refresh_reviews(
    place_id: str,
    request: ReviewSyncRequest | None = None,
    session: AsyncSession = Depends(get_session),
):
    return await ReviewService(session).refresh(place_id, request or ReviewSyncRequest(force=True))


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

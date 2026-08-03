from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import StreamingResponse
from typing import Annotated
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.schemas.common import PlaceResponse
from app.schemas.restaurants import (
    PlaceSelectionRequest,
    DishSummaryRequest,
    DishSummaryResponse,
    GoogleReviewSummaryRequest,
    GoogleReviewSummaryResponse,
    RestaurantDetailResponse,
    RestaurantSearchPage,
    RestaurantSearchRequest,
)
from app.services.insights import RestaurantInsightService
from app.services.restaurants import RestaurantService

router = APIRouter()


@router.post("/selection", response_model=PlaceResponse)
async def persist_selection(
    request: PlaceSelectionRequest, session: AsyncSession = Depends(get_session)
):
    return await RestaurantService(session).persist_selection(request)


@router.get("/search", response_model=RestaurantSearchPage)
async def search_restaurants(
    query: str = Query(min_length=1, max_length=200),
    page_token: str | None = Query(default=None, max_length=2000),
    latitude: float | None = Query(default=None, ge=-90, le=90),
    longitude: float | None = Query(default=None, ge=-180, le=180),
    radius_meters: int | None = Query(default=5000, ge=100, le=50000),
    page_size: int = Query(default=10, ge=1, le=10),
    session: AsyncSession = Depends(get_session),
):
    request = RestaurantSearchRequest(
        query=query,
        page_token=page_token,
        latitude=latitude,
        longitude=longitude,
        radius_meters=radius_meters,
        page_size=page_size,
    )
    return await RestaurantService(session).search(request)


@router.post("/search", response_model=RestaurantSearchPage)
async def search_restaurants_post(
    request: RestaurantSearchRequest, session: AsyncSession = Depends(get_session)
):
    # Frontend uses POST so browser coordinates are not written into access-log URLs.
    return await RestaurantService(session).search(request)


@router.post("/{place_id}/dish-summary", response_model=DishSummaryResponse)
async def generate_dish_summary(
    place_id: str,
    body: Request,
    request: DishSummaryRequest,
    session: AsyncSession = Depends(get_session),
):
    return await RestaurantInsightService(session).generate_dish_summary(place_id, request, len(await body.body()))


@router.post("/{place_id}/dish-summary/stream")
async def stream_dish_summary(
    place_id: str,
    body: Request,
    request: DishSummaryRequest,
    session: AsyncSession = Depends(get_session),
):
    events = await RestaurantInsightService(session).prepare_dish_summary_stream(
        place_id, request, len(await body.body())
    )
    return StreamingResponse(
        events,
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@router.post("/{place_id}/insights/google-review-summary", response_model=GoogleReviewSummaryResponse)
async def google_review_summary(
    place_id: str,
    request: GoogleReviewSummaryRequest,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    session: AsyncSession = Depends(get_session),
):
    return await RestaurantInsightService(session).fetch_google_review_summary(
        place_id, request.confirm_cost, idempotency_key
    )


@router.get("/{place_id}", response_model=RestaurantDetailResponse)
async def restaurant_detail(place_id: str, session: AsyncSession = Depends(get_session)):
    return await RestaurantService(session).detail(place_id)

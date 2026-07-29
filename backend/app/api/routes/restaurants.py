from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.schemas.common import PlaceResponse
from app.schemas.restaurants import (
    PlaceSelectionRequest,
    RestaurantDetailResponse,
    RestaurantSearchPage,
    RestaurantSearchRequest,
)
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


@router.get("/{place_id}", response_model=RestaurantDetailResponse)
async def restaurant_detail(place_id: str, session: AsyncSession = Depends(get_session)):
    return await RestaurantService(session).detail(place_id)

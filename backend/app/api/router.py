from fastapi import APIRouter

from app.api.routes import operations, restaurants, reviews

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(restaurants.router, prefix="/restaurants", tags=["restaurants"])
api_router.include_router(reviews.router, tags=["reviews"])
api_router.include_router(operations.router, tags=["operations"])

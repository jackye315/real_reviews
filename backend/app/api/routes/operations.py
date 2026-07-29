from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_session
from app.repositories.usage import UsageRepository
from app.schemas.operations import HealthResponse, ProviderUsageListResponse

router = APIRouter()


@router.get("/providers/usage", response_model=ProviderUsageListResponse)
async def provider_usage(session: AsyncSession = Depends(get_session)):
    usage = await UsageRepository(session).list()
    return ProviderUsageListResponse(usage=usage)


@router.get("/health", response_model=HealthResponse, include_in_schema=False)
async def api_health(session: AsyncSession = Depends(get_session)):
    await session.execute(text("select 1"))
    return HealthResponse(status="ok", database="ok", app=settings.app_name)

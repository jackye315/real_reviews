from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError
from app.db.session import get_session
from app.repositories.usage import UsageRepository
from app.schemas.operations import (
    HealthResponse,
    ProviderOperationListResponse,
    ProviderOperationResponse,
    ProviderUsageListResponse,
)
from app.services.provider_operations import ProviderOperationService

router = APIRouter()


@router.get("/providers/usage", response_model=ProviderUsageListResponse)
async def provider_usage(session: AsyncSession = Depends(get_session)):
    usage = await UsageRepository(session).list()
    return ProviderUsageListResponse(usage=usage)


@router.get("/provider-operations", response_model=ProviderOperationListResponse)
async def provider_operations(
    limit: Annotated[int, Query(ge=1, le=20)] = 20,
    session: AsyncSession = Depends(get_session),
):
    return ProviderOperationListResponse(
        operations=await ProviderOperationService(session).list_recent(limit)
    )


@router.get("/provider-operations/{operation_id}", response_model=ProviderOperationResponse)
async def provider_operation(operation_id: UUID, session: AsyncSession = Depends(get_session)):
    result = await ProviderOperationService(session).get(operation_id)
    if result is None:
        raise AppError("PROVIDER_OPERATION_NOT_FOUND", "Provider operation was not found.", 404)
    return result


@router.post("/provider-operations/{operation_id}/cancel", response_model=ProviderOperationResponse)
async def cancel_provider_operation(
    operation_id: UUID,
    response: Response,
    session: AsyncSession = Depends(get_session),
):
    result = await ProviderOperationService(session).request_cancel(operation_id)
    if result is None:
        raise AppError("PROVIDER_OPERATION_NOT_FOUND", "Provider operation was not found.", 404)
    if result.status in {"reserved", "running"}:
        response.status_code = 202
    return result


@router.get("/health", response_model=HealthResponse, include_in_schema=False)
async def api_health(session: AsyncSession = Depends(get_session)):
    await session.execute(text("select 1"))
    return HealthResponse(status="ok", database="ok", app=settings.app_name)

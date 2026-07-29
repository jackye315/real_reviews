from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.schemas.common import APIModel


class HealthResponse(APIModel):
    status: str
    database: str
    app: str


class ProviderUsageResponse(APIModel):
    id: UUID
    provider: str
    plan_period: str
    successful_request_count: int
    cached_response_count: int
    failed_request_count: int
    updated_at: datetime


class ProviderUsageListResponse(APIModel):
    usage: list[ProviderUsageResponse]

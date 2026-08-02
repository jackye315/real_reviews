from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

import httpx

from app.core.config import settings
from app.core.errors import upstream_unconfigured
from app.utils.dates import parse_datetime

SERPAPI_ACCOUNT_URL = "https://serpapi.com/account.json"


@dataclass(frozen=True, slots=True)
class SerpApiAccountSnapshot:
    total_searches_left: int | None
    this_hour_searches: int | None
    account_rate_limit_per_hour: int | None
    plan_renewal_date: date | None
    fetched_at: datetime


class SerpApiAccountClient:
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or settings.serpapi_api_key

    async def fetch_snapshot(self) -> SerpApiAccountSnapshot:
        if not self.api_key:
            raise upstream_unconfigured("serpapi")
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            response = await client.get(SERPAPI_ACCOUNT_URL, params={"api_key": self.api_key})
            response.raise_for_status()
            payload: dict[str, Any] = response.json()
        # Deliberately parse only the documented fields. The raw payload contains the API key.
        renewal = parse_datetime(payload.get("plan_renewal_date"))
        return SerpApiAccountSnapshot(
            total_searches_left=_non_negative_int(payload.get("total_searches_left")),
            this_hour_searches=_non_negative_int(payload.get("this_hour_searches")),
            account_rate_limit_per_hour=_non_negative_int(payload.get("account_rate_limit_per_hour")),
            plan_renewal_date=renewal.date() if renewal else _date_value(payload.get("plan_renewal_date")),
            fetched_at=datetime.now(timezone.utc),
        )


def _non_negative_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return max(0, int(value))
    if isinstance(value, str) and value.strip().replace(",", "").isdigit():
        return int(value.strip().replace(",", ""))
    return None


def _date_value(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None

from datetime import date, datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.models.provider_budget_period import ProviderBudgetPeriod
from app.providers.serpapi_account import SerpApiAccountSnapshot, _non_negative_int
from app.repositories.provider_operations import _hourly_limit, _plan_period
from app.services.provider_operations import ProviderOperationService


def test_account_parser_accepts_only_non_negative_numeric_values():
    assert _non_negative_int(12) == 12
    assert _non_negative_int("1,234") == 1234
    assert _non_negative_int(-1) == 0
    assert _non_negative_int(True) is None
    assert _non_negative_int("unknown") is None


def test_provider_plan_period_uses_renewal_date_then_utc_fallback():
    snapshot = SerpApiAccountSnapshot(
        total_searches_left=10,
        this_hour_searches=1,
        account_rate_limit_per_hour=5,
        plan_renewal_date=date(2026, 8, 15),
        fetched_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
    )
    assert _plan_period(snapshot) == "renews-2026-08-15"
    assert _plan_period(None).count("-") == 1


@pytest.mark.asyncio
async def test_operation_view_loads_place_explicitly_without_relationship_lazy_io():
    place_id = uuid4()
    place = SimpleNamespace(google_place_id="google-place", display_name="Pizza Sam")

    class Result:
        def scalar_one_or_none(self):
            return place

    class Session:
        async def execute(self, _statement):
            return Result()

    async def remaining(_operation):
        return 10

    now = datetime.now(timezone.utc)
    operation = SimpleNamespace(
        id=uuid4(), provider="serpapi", operation_type="refresh", place_id=place_id,
        status="reserved", requested_units=4, released_reserved_count=0,
        successful_request_count=0, cached_response_count=0, failed_request_count=0,
        uncertain_request_count=0, collected_unique_count=0, result_metadata=None,
        stop_reason=None, cancel_requested_at=None, created_at=now, updated_at=now, completed_at=None,
    )
    service = ProviderOperationService(Session())
    service.repository = SimpleNamespace(remaining_local_budget=remaining)
    response = await service.view(operation)
    assert response.place_id == "google-place"
    assert response.restaurant_name == "Pizza Sam"


def test_hourly_limit_uses_the_lower_available_limit(monkeypatch):
    from app.repositories import provider_operations

    monkeypatch.setattr(provider_operations.settings, "provider_hourly_request_limit", 3)
    period = ProviderBudgetPeriod(
        provider="serpapi",
        plan_period="renews-2026-08-15",
        configured_local_budget=225,
        provider_hourly_limit=5,
    )
    assert _hourly_limit(period) == 3

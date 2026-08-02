from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.core.errors import AppError
from app.models.review import Review
from app.schemas.reviews import LoadMoreRequest, ReviewSort
from app.services.reviews import estimate_load_more_requests, estimate_serpapi_requests
from app.utils.review_cursors import decode_cursor, encode_cursor


def review() -> Review:
    return Review(id=uuid4(), rating=5, publication_timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc))


def test_cursor_binds_place_filter_sort_and_version():
    cursor = encode_cursor("place", 5, ReviewSort.RECENT, 2, review())
    assert decode_cursor(cursor, place_id="place", rating=5, sort=ReviewSort.RECENT, version=2)["p"] == "place"
    with pytest.raises(AppError) as mismatch:
        decode_cursor(cursor, place_id="other", rating=5, sort=ReviewSort.RECENT, version=2)
    assert mismatch.value.detail["code"] == "CURSOR_MISMATCH"
    with pytest.raises(AppError) as stale:
        decode_cursor(cursor, place_id="place", rating=5, sort=ReviewSort.RECENT, version=3)
    assert stale.value.detail["code"] == "CURSOR_STALE"


def test_load_more_fixed_targets_and_valid_cursor_estimates():
    assert [LoadMoreRequest(additional_target_count=value).additional_target_count for value in (20, 50, 100)] == [20, 50, 100]
    with pytest.raises(ValueError):
        LoadMoreRequest(additional_target_count=25)
    assert [estimate_load_more_requests(value) for value in (20, 50, 100)] == [1, 3, 5]
    assert estimate_serpapi_requests(50) == 4  # Initial sync remains a different provider flow.


def test_cursor_rejects_tampering():
    cursor = encode_cursor("place", None, ReviewSort.OLDEST, 1, review())
    with pytest.raises(AppError) as invalid:
        decode_cursor(cursor[:-1] + "x", place_id="place", rating=None, sort=ReviewSort.OLDEST, version=1)
    assert invalid.value.detail["code"] == "INVALID_CURSOR"

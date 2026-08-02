from uuid import uuid4

from app.models.review import Review
from app.repositories.reviews import ReviewRepository
from app.schemas.reviews import ReviewSort


def _cursor(*, rating=5, timestamp="2026-01-01T00:00:00+00:00"):
    return {"id": str(uuid4()), "rating": rating, "ts": timestamp}


def test_keyset_predicates_keep_nulls_last_and_id_tiebreaker():
    recent = str(ReviewRepository._after_cursor(ReviewSort.RECENT, _cursor()))
    oldest = str(ReviewRepository._after_cursor(ReviewSort.OLDEST, _cursor()))
    assert str(Review.publication_timestamp.is_(None)) in recent
    assert str(Review.publication_timestamp.is_(None)) in oldest
    assert str(Review.id > _cursor()["id"]).split()[0] in recent
    assert "<" in recent
    assert ">" in oldest


def test_rating_keyset_predicates_include_rating_nulls_after_rated_values():
    high = str(ReviewRepository._after_cursor(ReviewSort.RATING_HIGH, _cursor(rating=4)))
    low = str(ReviewRepository._after_cursor(ReviewSort.RATING_LOW, _cursor(rating=4)))
    assert str(Review.rating.is_(None)) in high
    assert str(Review.rating.is_(None)) in low
    assert "reviews.rating <" in high
    assert "reviews.rating >" in low


def test_null_rating_cursor_stays_with_null_rating_partition():
    predicate = str(ReviewRepository._after_cursor(ReviewSort.RATING_HIGH, _cursor(rating=None, timestamp=None)))
    assert str(Review.rating.is_(None)) in predicate
    assert str(Review.publication_timestamp.is_(None)) in predicate

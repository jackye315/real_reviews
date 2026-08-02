from app.models.review import Review
from app.repositories.reviews import REVIEW_SORTS
from app.schemas.reviews import ReviewSort


def expression_text(expressions):
    return [str(expression) for expression in expressions]


def test_review_sort_allowlist_contains_only_supported_modes():
    assert set(REVIEW_SORTS) == {
        ReviewSort.RELEVANT,
        ReviewSort.RECENT,
        ReviewSort.OLDEST,
        ReviewSort.RATING_HIGH,
        ReviewSort.RATING_LOW,
    }


def test_review_sort_modes_use_documented_stable_tie_breakers():
    assert expression_text(REVIEW_SORTS[ReviewSort.RECENT]) == [
        str(Review.publication_timestamp.desc().nullslast()),
        str(Review.id.asc()),
    ]
    assert expression_text(REVIEW_SORTS[ReviewSort.OLDEST]) == [
        str(Review.publication_timestamp.asc().nullslast()),
        str(Review.id.asc()),
    ]
    assert expression_text(REVIEW_SORTS[ReviewSort.RATING_HIGH]) == [
        str(Review.rating.desc().nullslast()),
        str(Review.publication_timestamp.desc().nullslast()),
        str(Review.id.asc()),
    ]
    assert expression_text(REVIEW_SORTS[ReviewSort.RATING_LOW]) == [
        str(Review.rating.asc().nullslast()),
        str(Review.publication_timestamp.desc().nullslast()),
        str(Review.id.asc()),
    ]

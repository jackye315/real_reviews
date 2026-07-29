from app.utils.text import normalize_review_text, stable_text_hash


def test_normalize_review_text_stabilizes_unicode_and_whitespace():
    assert normalize_review_text("  great\n\tfood  ") == "great food"
    assert stable_text_hash("great food") == stable_text_hash(" great\nfood ")

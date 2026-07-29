from app.providers.serpapi import SerpApiReviewProvider


def test_serpapi_topic_normalization_preserves_valid_order_and_mentions():
    provider = SerpApiReviewProvider(api_key="test")

    topics = provider._normalize_topics(
        [
            {"id": "/m/outdoor", "keyword": "outdoor seating", "mentions": "24"},
            {"id": "", "keyword": "ignored", "mentions": 3},
            {"id": "/m/no-mentions", "keyword": "service", "mentions": -1},
            {"id": "/m/outdoor", "keyword": "duplicate", "mentions": 99},
        ]
    )

    assert [topic.provider_topic_id for topic in topics] == ["/m/outdoor", "/m/no-mentions"]
    assert [topic.keyword for topic in topics] == ["outdoor seating", "service"]
    assert [topic.mentions for topic in topics] == [24, None]
    assert [topic.rank for topic in topics] == [0, 1]

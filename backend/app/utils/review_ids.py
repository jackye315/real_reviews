from __future__ import annotations

from urllib.parse import parse_qs, unquote, urlparse


def google_review_id_from_resource_name(value: str | None) -> str | None:
    if not value:
        return None
    candidate = value.strip()
    if not candidate:
        return None
    if "/reviews/" in candidate:
        return candidate.rsplit("/reviews/", 1)[-1]
    return candidate.rsplit("/", 1)[-1]


def google_review_id_from_url(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = urlparse(value)
    except ValueError:
        return None
    query = parse_qs(parsed.query)
    for key in ("review_id", "reviewId", "rlfi"):
        if query.get(key):
            return query[key][0]
    decoded = unquote(value)
    markers = ("/reviews/", "review_id:", "reviewId:")
    for marker in markers:
        if marker in decoded:
            return decoded.split(marker, 1)[1].split("/", 1)[0].split("&", 1)[0]
    return None

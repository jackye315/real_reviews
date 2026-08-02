from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime
from uuid import UUID

from app.core.config import settings
from app.core.errors import AppError
from app.models.review import Review
from app.schemas.reviews import ReviewSort


def encode_cursor(place_id: str, rating: int | None, sort: ReviewSort, version: int, review: Review, relevance_rank: int | None = None) -> str:
    payload = {"p": place_id, "r": rating, "s": sort.value, "v": version, "id": str(review.id), "ts": review.publication_timestamp.isoformat() if review.publication_timestamp else None, "rating": review.rating, "rank": relevance_rank}
    encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()).rstrip(b"=").decode()
    signature = hmac.new(settings.review_cursor_signing_key.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def decode_cursor(cursor: str, *, place_id: str, rating: int | None, sort: ReviewSort, version: int) -> dict:
    try:
        encoded, signature = cursor.split(".", 1)
        expected = hmac.new(settings.review_cursor_signing_key.encode(), encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError
        payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        UUID(payload["id"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        raise AppError("INVALID_CURSOR", "The saved-review cursor is invalid.", 400) from None
    if (payload.get("p"), payload.get("r"), payload.get("s")) != (place_id, rating, sort.value):
        raise AppError("CURSOR_MISMATCH", "The saved-review cursor does not match this request.", 400)
    if payload.get("v") != version:
        raise AppError("CURSOR_STALE", "The review collection changed; restart from the first page.", 409)
    return payload


def cursor_timestamp(payload: dict) -> datetime | None:
    return datetime.fromisoformat(payload["ts"]) if payload.get("ts") else None

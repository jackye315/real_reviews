from __future__ import annotations

import json
import math
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import urlparse

RichState = Literal["omitted", "valid", "malformed"]
DetailValue = str | int | float | bool | list[str | int | float | bool]

MAX_DETAIL_FIELDS = 32
MAX_DETAIL_KEY_LENGTH = 80
MAX_DETAIL_STRING_LENGTH = 1000
MAX_DETAIL_LIST_ITEMS = 20
MAX_DETAIL_LIST_STRING_LENGTH = 250
MAX_DETAIL_JSON_BYTES = 16 * 1024
MAX_REVIEW_IMAGES = 20
MAX_IMAGE_URL_LENGTH = 4096
SUPPORTED_IMAGE_HOSTS = {
    "lh3.googleusercontent.com",
    "lh4.googleusercontent.com",
    "lh5.googleusercontent.com",
    "lh6.googleusercontent.com",
}


@dataclass(frozen=True, slots=True)
class RichSection:
    state: RichState
    value: dict[str, DetailValue] | list[str] | None = None
    reason: str | None = None


def normalize_detail_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).strip().lower()
    normalized = re.sub(r"[\s-]+", "_", normalized)
    return re.sub(r"_+", "_", normalized)


def parse_details(value: Any, *, present: bool) -> RichSection:
    if not present:
        return RichSection("omitted")
    if not isinstance(value, dict):
        return RichSection("malformed", reason="details_not_object")
    if len(value) > MAX_DETAIL_FIELDS:
        return RichSection("malformed", reason="too_many_detail_fields")
    normalized_keys: set[str] = set()
    accepted: dict[str, DetailValue] = {}
    for key, raw in value.items():
        if not isinstance(key, str):
            return RichSection("malformed", reason="detail_key_not_string")
        normalized_key = normalize_detail_key(key)
        if not normalized_key or len(normalized_key) > MAX_DETAIL_KEY_LENGTH:
            return RichSection("malformed", reason="invalid_detail_key")
        if normalized_key in normalized_keys:
            return RichSection("malformed", reason="duplicate_normalized_detail_key")
        normalized_keys.add(normalized_key)
        if raw is None:
            continue
        parsed = _parse_detail_value(raw)
        if parsed is None:
            return RichSection("malformed", reason="invalid_detail_value")
        accepted[key] = parsed
    try:
        encoded = json.dumps(
            {normalize_detail_key(key): item for key, item in accepted.items()},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError):
        return RichSection("malformed", reason="invalid_detail_json")
    if len(encoded) > MAX_DETAIL_JSON_BYTES:
        return RichSection("malformed", reason="detail_json_too_large")
    return RichSection("valid", accepted)


def parse_images(value: Any, *, present: bool) -> RichSection:
    if not present:
        return RichSection("omitted")
    if not isinstance(value, list) or len(value) > MAX_REVIEW_IMAGES:
        return RichSection("malformed", reason="invalid_image_list")
    images: list[str] = []
    seen: set[str] = set()
    for raw in value:
        if not isinstance(raw, str) or len(raw) > MAX_IMAGE_URL_LENGTH or not _safe_image_url(raw):
            return RichSection("malformed", reason="invalid_image_url")
        if raw not in seen:
            seen.add(raw)
            images.append(raw)
    return RichSection("valid", images)


def _parse_detail_value(value: Any) -> DetailValue | None:
    if _valid_scalar(value, MAX_DETAIL_STRING_LENGTH):
        return value
    if not isinstance(value, list) or len(value) > MAX_DETAIL_LIST_ITEMS:
        return None
    parsed: list[str | int | float | bool] = []
    for item in value:
        if not _valid_scalar(item, MAX_DETAIL_LIST_STRING_LENGTH):
            return None
        parsed.append(item)
    return parsed


def _valid_scalar(value: Any, max_string_length: int) -> bool:
    if isinstance(value, bool):
        return True
    if isinstance(value, str):
        return len(value) <= max_string_length
    if isinstance(value, int):
        return True
    return isinstance(value, float) and math.isfinite(value)


def _safe_image_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
        hostname = parsed.hostname
        if (
            parsed.scheme != "https"
            or not hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port is not None
        ):
            return False
        normalized_host = hostname.rstrip(".").encode("idna").decode("ascii").lower()
    except (UnicodeError, ValueError):
        return False
    return normalized_host in SUPPORTED_IMAGE_HOSTS

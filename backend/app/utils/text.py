from __future__ import annotations

import hashlib
import re
import unicodedata

_WHITESPACE = re.compile(r"\s+")


def normalize_review_text(text: str | None) -> str:
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKC", text)
    normalized = _WHITESPACE.sub(" ", normalized).strip()
    return normalized


def stable_text_hash(text: str | None) -> str:
    normalized = normalize_review_text(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def normalize_author_name(name: str | None) -> str:
    return normalize_review_text(name).casefold()

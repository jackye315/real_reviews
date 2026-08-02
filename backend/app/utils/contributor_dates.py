from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True, slots=True)
class ContributorDate:
    lower: datetime | None
    upper: datetime | None
    precision: str
    approximate: bool
    basis: str


def parse_contributor_date(value: str | None, observed_at: datetime) -> ContributorDate:
    if not value:
        return ContributorDate(None, None, "unknown", False, "unknown")
    text = value.strip()
    edited = text.lower().startswith("edited ")
    if edited:
        text = text[7:].strip()
    match = re.fullmatch(r"(?:(a|an)|([0-9]+))\s+(day|week|month|year)s?\s+ago", text, re.IGNORECASE)
    if not match:
        return ContributorDate(None, None, "unknown", False, "unknown")
    count = 1 if match.group(1) else int(match.group(2))
    unit = match.group(3).lower()
    days = count * {"day": 1, "week": 7, "month": 30, "year": 365}[unit]
    point = observed_at - timedelta(days=days)
    precision = "day" if unit == "day" else "week" if unit == "week" else "month" if unit == "month" else "year"
    return ContributorDate(point - timedelta(days=1), point + timedelta(days=1), precision, True, "edited_or_displayed" if edited else "published")

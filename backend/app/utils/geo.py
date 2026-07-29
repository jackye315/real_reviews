from __future__ import annotations

from math import asin, cos, radians, sin, sqrt

EARTH_RADIUS_METERS = 6_371_000


def distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> int:
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    rlat1 = radians(lat1)
    rlat2 = radians(lat2)
    a = sin(dlat / 2) ** 2 + cos(rlat1) * cos(rlat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return round(EARTH_RADIUS_METERS * c)

"""
SafeCycle Sofia — Geospatial utility helpers.
Haversine distance, bounding box checks, coordinate conversion.
"""
from __future__ import annotations

from math import asin, cos, radians, sin, sqrt


# Earth's mean radius in metres — used across all haversine calculations
EARTH_RADIUS_M: float = 6_371_000.0


def haversine_metres(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """
    Calculate the great-circle distance in metres between two coordinates
    using the Haversine formula.

    Parameters
    ----------
    lat1, lon1 : float  — origin in decimal degrees
    lat2, lon2 : float  — destination in decimal degrees

    Returns
    -------
    float — distance in metres
    """
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * asin(sqrt(a))


def is_within_bbox(
    lat: float,
    lon: float,
    north: float,
    south: float,
    east: float,
    west: float,
) -> bool:
    """Return True if the coordinate lies within the bounding box."""
    return south <= lat <= north and west <= lon <= east


def metres_to_degrees(metres: float, latitude: float = 42.68) -> float:
    """
    Approximate conversion from metres to decimal degrees at a given latitude.
    Used for shapely buffer operations that expect degree units.

    Sofia is at ~42.68°N; 1° latitude ≈ 111 320 m everywhere.
    1° longitude at 42.68°N ≈ 81 900 m.
    We use the latitude approximation for conservative buffers.
    """
    return metres / 111_320.0


def bbox_from_point(
    lat: float, lon: float, radius_m: float
) -> tuple[float, float, float, float]:
    """
    Return a (north, south, east, west) bounding box around a point.
    Useful for quick spatial pre-filtering before precise haversine checks.
    """
    delta_lat = radius_m / 111_320.0
    delta_lon = radius_m / (111_320.0 * cos(radians(lat)))
    return (
        lat + delta_lat,  # north
        lat - delta_lat,  # south
        lon + delta_lon,  # east
        lon - delta_lon,  # west
    )

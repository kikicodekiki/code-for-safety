"""
SafeCycle Sofia — Douglas-Peucker path coordinate simplification.

Reduces the number of coordinates in a path for efficient transfer to the
mobile client while preserving the visual shape of the route.
"""
from __future__ import annotations

from shapely.geometry import LineString

from app.utils.geo import metres_to_degrees


def simplify_path(
    coordinates: list[tuple[float, float]],
    tolerance_m: float = 5.0,
) -> list[tuple[float, float]]:
    """
    Simplify a list of (lat, lon) coordinates using Douglas-Peucker.

    Parameters
    ----------
    coordinates : list[tuple[float, float]]
        Input path as (lat, lon) pairs.
    tolerance_m : float
        Simplification tolerance in metres (default 5 m — preserves
        all meaningful turns while removing collinear intermediate points).

    Returns
    -------
    list[tuple[float, float]]
        Simplified path as (lat, lon) pairs.
        Always retains first and last points unchanged.
    """
    if len(coordinates) <= 2:
        return coordinates

    # Shapely uses (x, y) = (lon, lat) convention
    line = LineString([(lon, lat) for lat, lon in coordinates])
    tolerance_deg = metres_to_degrees(tolerance_m)
    simplified = line.simplify(tolerance_deg, preserve_topology=False)

    if simplified.is_empty:
        return coordinates

    # Convert back to (lat, lon)
    return [(y, x) for x, y in simplified.coords]

"""
SafeCycle Sofia — Crossroad proximity detection.

Detects when a cyclist's GPS position is within CROSSROAD_ALERT_RADIUS_M
of an intersection node. Includes a 30-second debounce to avoid spamming.
"""
from __future__ import annotations

from datetime import datetime

from app.models.schemas.common import Coordinate
from app.utils.geo import haversine_metres

# Minimum seconds between two crossroad alerts for the same session.
CROSSROAD_DEBOUNCE_SECONDS: float = 30.0


def is_near_crossroad(
    lat: float,
    lon: float,
    crossroad_nodes: list[Coordinate],
    radius_m: float,
) -> Coordinate | None:
    """
    Return the nearest crossroad within radius_m, or None.

    Parameters
    ----------
    lat, lon : float — cyclist's current GPS position
    crossroad_nodes : list[Coordinate] — intersections on the active route
    radius_m : float — alert trigger radius (CROSSROAD_ALERT_RADIUS_M)

    Returns
    -------
    Coordinate | None — the nearest qualifying crossroad, or None
    """
    nearest: Coordinate | None = None
    nearest_dist = float("inf")

    for node in crossroad_nodes:
        dist = haversine_metres(lat, lon, node.lat, node.lon)
        if dist <= radius_m and dist < nearest_dist:
            nearest = node
            nearest_dist = dist

    return nearest


def crossroad_debounce_ok(
    last_alert_time: datetime | None,
    now: datetime,
) -> bool:
    """
    Return True if enough time has elapsed since the last crossroad alert.
    Prevents the cyclist from receiving repeated alerts at the same intersection.
    """
    if last_alert_time is None:
        return True
    elapsed = (now - last_alert_time).total_seconds()
    return elapsed >= CROSSROAD_DEBOUNCE_SECONDS

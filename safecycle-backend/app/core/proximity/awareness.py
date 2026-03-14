"""
SafeCycle Sofia — Awareness zone proximity detection.

Detects when a cyclist is within an awareness zone radius and produces
an alert payload. Includes debouncing to prevent repeated notifications.
"""
from __future__ import annotations

from datetime import datetime

from app.models.schemas.common import AwarenessZoneSchema
from app.utils.geo import haversine_metres

AWARENESS_DEBOUNCE_SECONDS: float = 30.0


def find_nearest_awareness_zone(
    lat: float,
    lon: float,
    awareness_zones: list[AwarenessZoneSchema],
    search_radius_m: float,
) -> tuple[AwarenessZoneSchema, float] | None:
    """
    Return the nearest awareness zone within search_radius_m, plus distance.

    Parameters
    ----------
    lat, lon : float — cyclist's current GPS position
    awareness_zones : list[AwarenessZoneSchema] — pre-loaded from app state
    search_radius_m : float — AWARENESS_ZONE_RADIUS_M from settings

    Returns
    -------
    (zone, distance_m) if a zone is within range, else None
    """
    nearest_zone: AwarenessZoneSchema | None = None
    nearest_dist = float("inf")

    for zone in awareness_zones:
        dist = haversine_metres(lat, lon, zone.center.lat, zone.center.lon)
        effective_radius = zone.radius_m + search_radius_m
        if dist <= effective_radius and dist < nearest_dist:
            nearest_zone = zone
            nearest_dist = dist

    if nearest_zone is None:
        return None
    return (nearest_zone, nearest_dist)


def awareness_debounce_ok(
    last_alert_time: datetime | None,
    now: datetime,
) -> bool:
    """
    Return True if enough time has elapsed since the last awareness zone alert.
    """
    if last_alert_time is None:
        return True
    elapsed = (now - last_alert_time).total_seconds()
    return elapsed >= AWARENESS_DEBOUNCE_SECONDS

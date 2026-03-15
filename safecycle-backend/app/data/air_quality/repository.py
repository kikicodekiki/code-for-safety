"""
AirQualityRepository — in-memory spatial lookup for PM2.5 readings.

Stores the latest sensor readings and provides get_pm25(lat, lon)
which returns the PM2.5 value of the nearest sensor within a
configurable radius.  Used by the routing algorithm to assign a
per-edge air quality cost factor.

Design notes:
- Sensor count for Sofia is small (~10–60 sensors), so a linear
  nearest-neighbour scan is fast enough (O(n) with n ≤ 60).
- If no sensor is within MAX_SENSOR_RADIUS_KM, returns 0.0 (no penalty)
  so routing continues safely when coverage is sparse.
- Thread/async safety: updates replace the whole list atomically —
  no partial-read risk.
"""
from __future__ import annotations

import math
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# Ignore sensors further than this from the edge midpoint (km)
MAX_SENSOR_RADIUS_KM: float = 3.0

# Fallback PM2.5 when no sensors are loaded (µg/m³ — treated as clean air)
FALLBACK_PM25: float = 0.0


class AirQualityRepository:
    """
    In-memory store of Sofia air quality sensor readings.

    Call update(payload) after every successful fetch.
    Call get_pm25(lat, lon) during edge weight computation.
    """

    def __init__(self) -> None:
        # List of {"lat": float, "lon": float, "pm25": float | None, ...}
        self._sensors: list[dict[str, Any]] = []
        self._fetched_at: str | None = None

    # ── Public API ────────────────────────────────────────────────────────────

    def update(self, payload: dict) -> None:
        """Replace in-memory sensor list with fresh data."""
        sensors = payload.get("sensors", [])
        self._sensors = [s for s in sensors if s.get("pm25") is not None]
        self._fetched_at = payload.get("fetched_at")
        logger.info(
            "air_quality_repository_updated",
            total_sensors=len(payload.get("sensors", [])),
            sensors_with_pm25=len(self._sensors),
            fetched_at=self._fetched_at,
        )

    def get_pm25(self, lat: float, lon: float) -> float:
        """
        Return PM2.5 (µg/m³) of the nearest sensor within MAX_SENSOR_RADIUS_KM.

        Returns FALLBACK_PM25 (0.0 = no penalty) when:
        - No sensors are loaded
        - No sensor is within MAX_SENSOR_RADIUS_KM
        """
        if not self._sensors:
            return FALLBACK_PM25

        best_dist = math.inf
        best_pm25 = FALLBACK_PM25

        for sensor in self._sensors:
            dist_km = _haversine_km(lat, lon, sensor["lat"], sensor["lon"])
            if dist_km < best_dist:
                best_dist = dist_km
                best_pm25 = float(sensor["pm25"])

        if best_dist > MAX_SENSOR_RADIUS_KM:
            return FALLBACK_PM25

        return best_pm25

    @property
    def sensor_count(self) -> int:
        return len(self._sensors)

    @property
    def fetched_at(self) -> str | None:
        return self._fetched_at

    def to_dict(self) -> dict:
        """Snapshot for the /air-quality API endpoint."""
        return {
            "fetched_at": self._fetched_at,
            "sensor_count": len(self._sensors),
            "sensors": self._sensors,
        }


# ── Haversine helper (no external deps) ──────────────────────────────────────

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance in kilometres."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.asin(math.sqrt(a))

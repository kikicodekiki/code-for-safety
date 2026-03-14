"""
SafeCycle Sofia — OSRM routing service.

Uses the public OSRM demo server to compute cycling routes.
No API key required.  Returns normalised geometry, ETA, and distance
in the same shape the frontend expects.
"""
from __future__ import annotations

from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)

# Public OSRM demo server — free, no key needed.
# For production, deploy your own OSRM instance.
OSRM_BASE = "https://router.project-osrm.org"


class RoutingServiceError(Exception):
    """Raised when an OSRM request fails."""


class OSRMService:
    """Thin wrapper around the OSRM HTTP API (bicycle profile)."""

    def __init__(self, base_url: str = OSRM_BASE) -> None:
        self.base_url = base_url.rstrip("/")

    async def calculate_route(
        self,
        origin_lat: float,
        origin_lon: float,
        dest_lat: float,
        dest_lon: float,
        *,
        alternatives: int = 2,
    ) -> dict[str, Any]:
        """
        Call OSRM /route and return a normalised result dict.

        Returns
        -------
        {
            "path":         { "type": "LineString", "coordinates": [[lon,lat], …] },
            "distance_m":   float,
            "duration_min":  float,
            "alternatives":  [ { path, distance_m, duration_min }, … ],
        }
        """
        # OSRM expects  /route/v1/{profile}/{lon1},{lat1};{lon2},{lat2}
        coords_str = f"{origin_lon},{origin_lat};{dest_lon},{dest_lat}"
        url = f"{self.base_url}/route/v1/bike/{coords_str}"

        params: dict[str, str] = {
            "overview": "full",
            "geometries": "geojson",
            "steps": "false",
            "alternatives": "true" if alternatives else "false",
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "osrm_api_error",
                    status=exc.response.status_code,
                    body=exc.response.text[:500],
                )
                raise RoutingServiceError(
                    f"OSRM returned HTTP {exc.response.status_code}"
                ) from exc
            except httpx.RequestError as exc:
                logger.error("osrm_network_error", error=str(exc))
                raise RoutingServiceError("Network error calling OSRM") from exc

        data = resp.json()

        if data.get("code") != "Ok":
            msg = data.get("message", "Unknown OSRM error")
            raise RoutingServiceError(f"OSRM error: {msg}")

        routes = data.get("routes", [])
        if not routes:
            raise RoutingServiceError("OSRM returned no routes")

        primary = self._normalise(routes[0])
        alts = [self._normalise(r) for r in routes[1 : 1 + alternatives]]

        primary["alternatives"] = alts
        return primary

    # ------------------------------------------------------------------
    @staticmethod
    def _normalise(route: dict[str, Any]) -> dict[str, Any]:
        """Convert one OSRM route object into our internal format."""
        geom = route.get("geometry", {})
        coords = geom.get("coordinates", [])
        distance_m = route.get("distance", 0)  # metres
        duration_s = route.get("duration", 0)   # seconds
        return {
            "path": {"type": "LineString", "coordinates": coords},
            "distance_m": round(distance_m, 1),
            "duration_min": round(duration_s / 60, 1),
        }

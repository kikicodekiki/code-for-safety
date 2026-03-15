"""
SafeCycle Sofia — Real-time crowd density estimation service.

Fetches real-time crowd density data for a given location and translates
it into a density score (0–100) and edge weight factor for the routing
algorithm.

Data source priority:
  1. Google Maps Places API — "currentPopularity" / "live busyness"
  2. Time-of-day + day-of-week heuristic fallback for Sofia

Density score:
  0   = completely deserted
  100 = gridlock / maximum pedestrian capacity

Edge weight mapping (for external consumers):
  edge_weight = 1.0 + (density_score / 100) * 9.0   → [1.0, 10.0]

Internal routing factor (feeds into compute_edge_weight):
  density_factor = 1.0 + (density_score / 100) * 1.0 → [1.0, 2.0]
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
import structlog

from app.config import Settings

logger = structlog.get_logger(__name__)


# ── Sofia-specific time-of-day pedestrian density heuristic ──────────────────
# Based on typical Sofia pedestrian patterns.
# Maps hour (0–23) → estimated density score (0-100) for weekdays vs weekends.

WEEKDAY_DENSITY: dict[int, int] = {
    0: 3, 1: 2, 2: 2, 3: 1, 4: 2, 5: 5,
    6: 10, 7: 25, 8: 45, 9: 40, 10: 35, 11: 35,
    12: 40, 13: 45, 14: 40, 15: 35, 16: 40, 17: 55,
    18: 60, 19: 50, 20: 35, 21: 25, 22: 15, 23: 8,
}

WEEKEND_DENSITY: dict[int, int] = {
    0: 8, 1: 5, 2: 3, 3: 2, 4: 1, 5: 2,
    6: 3, 7: 5, 8: 10, 9: 15, 10: 30, 11: 45,
    12: 50, 13: 50, 14: 45, 15: 45, 16: 50, 17: 55,
    18: 55, 19: 50, 20: 45, 21: 35, 22: 25, 23: 15,
}

# Zone type multipliers — some areas are inherently busier
ZONE_MULTIPLIERS: dict[str, float] = {
    "city_center":    1.4,   # Vitosha Blvd, Serdika area
    "transit_hub":    1.3,   # Near metro stations, bus terminals
    "park":           0.8,   # Borisova Gradina, South Park
    "residential":    0.6,   # Quiet neighbourhoods
    "industrial":     0.3,   # Factory/warehouse zones
    "default":        1.0,
}

# Sofia city center approximate bounding box
SOFIA_CENTER_BBOX = {
    "north": 42.705,
    "south": 42.685,
    "east":  23.340,
    "west":  23.305,
}


@dataclass
class DensityResult:
    """Result of a crowd density estimation."""
    lat: float
    lon: float
    radius_meters: int
    density_score: int          # 0–100
    edge_weight: float          # 1.0–10.0 (for external API consumers)
    people_density: float       # 0–100 (feeds into compute_density_factor)
    data_sources_used: list[str]
    is_real_time: bool
    timestamp: str

    def to_dict(self) -> dict:
        return {
            "location": {"lat": self.lat, "lng": self.lon},
            "radius_meters": self.radius_meters,
            "density_score": self.density_score,
            "edge_weight": self.edge_weight,
            "people_density": self.people_density,
            "data_sources_used": self.data_sources_used,
            "is_real_time": self.is_real_time,
            "timestamp": self.timestamp,
        }


class DensityService:
    """
    Estimates real-time crowd density for a given location.

    Tries Google Maps Places API first, then falls back to
    time-of-day heuristics specific to Sofia.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.api_key = settings.GOOGLE_MAPS_API_KEY

    async def estimate_density(
        self,
        lat: float,
        lon: float,
        radius_m: int = 100,
        timestamp: datetime | None = None,
    ) -> DensityResult:
        """
        Estimate crowd density at a specific location.

        Parameters
        ----------
        lat, lon : float — coordinates
        radius_m : int — radius to consider (default 100m)
        timestamp : datetime — when the reading applies (default: now)

        Returns
        -------
        DensityResult with density_score, edge_weight, and people_density
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        data_sources: list[str] = []
        is_real_time = False
        density_score = 0

        # ── Attempt 1: Google Maps Places API ────────────────────────────────
        if self.api_key:
            try:
                google_score = await self._fetch_google_popularity(lat, lon)
                if google_score is not None:
                    density_score = google_score
                    data_sources.append("google_maps_places_api")
                    is_real_time = True
                    logger.info(
                        "density_google_success",
                        lat=lat, lon=lon,
                        density_score=density_score,
                    )
            except Exception as exc:
                logger.warning(
                    "density_google_failed",
                    lat=lat, lon=lon,
                    error=str(exc),
                )

        # ── Attempt 2: Time-of-day heuristic fallback ────────────────────────
        if not is_real_time:
            density_score = self._heuristic_density(lat, lon, timestamp)
            data_sources.append("sofia_time_heuristic")
            is_real_time = False
            logger.info(
                "density_heuristic_fallback",
                lat=lat, lon=lon,
                density_score=density_score,
                hour=timestamp.hour,
                weekday=timestamp.weekday(),
            )

        # Clamp to valid range
        density_score = max(0, min(100, density_score))

        # ── Compute edge weight (1.0–10.0 scale for external API) ────────────
        edge_weight = round(1.0 + (density_score / 100.0) * 9.0, 2)

        # ── people_density (0–100 scale for compute_density_factor) ──────────
        people_density = float(density_score)

        return DensityResult(
            lat=lat,
            lon=lon,
            radius_meters=radius_m,
            density_score=density_score,
            edge_weight=edge_weight,
            people_density=people_density,
            data_sources_used=data_sources,
            is_real_time=is_real_time,
            timestamp=timestamp.isoformat(),
        )

    async def _fetch_google_popularity(
        self, lat: float, lon: float
    ) -> int | None:
        """
        Query Google Maps Places API for live popularity / busyness.

        Uses the Nearby Search to find places within 100m, then checks
        their current_opening_hours and popularity data.

        Returns density score 0–100, or None if unavailable.
        """
        url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        params = {
            "location": f"{lat},{lon}",
            "radius": 100,
            "key": self.api_key,
        }

        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        results = data.get("results", [])
        if not results:
            return None

        # Collect "user_ratings_total" and "business_status" as density proxies
        # Google doesn't always expose "currentPopularity" in the basic API,
        # so we approximate based on the number and type of active businesses
        popularity_scores: list[int] = []

        for place in results[:10]:  # sample up to 10 nearby places
            # Some places report a popularity percentage
            # (requires Places API v2 / paid plan)
            current_pop = place.get("current_popularity")
            if current_pop is not None:
                popularity_scores.append(int(current_pop))
                continue

            # Fallback: estimate from user_ratings_total (more reviews = busier area)
            ratings_total = place.get("user_ratings_total", 0)
            if ratings_total > 1000:
                popularity_scores.append(65)
            elif ratings_total > 500:
                popularity_scores.append(50)
            elif ratings_total > 100:
                popularity_scores.append(35)
            elif ratings_total > 10:
                popularity_scores.append(20)
            else:
                popularity_scores.append(10)

        if not popularity_scores:
            return None

        # Average of sampled places, weighted toward the busiest ones
        avg_score = sum(popularity_scores) / len(popularity_scores)
        return int(min(100, avg_score))

    def _heuristic_density(
        self, lat: float, lon: float, timestamp: datetime
    ) -> int:
        """
        Estimate density using time-of-day + location zone heuristics.

        This is the fallback when no real-time API data is available.
        Uses Sofia-specific patterns for weekdays vs weekends.
        """
        hour = timestamp.hour
        weekday = timestamp.weekday()  # 0=Monday, 6=Sunday

        # Pick base density from time lookup
        if weekday < 5:  # Monday–Friday
            base_density = WEEKDAY_DENSITY.get(hour, 20)
        else:  # Saturday–Sunday
            base_density = WEEKEND_DENSITY.get(hour, 20)

        # Apply zone multiplier based on location
        zone = self._classify_zone(lat, lon)
        multiplier = ZONE_MULTIPLIERS.get(zone, 1.0)

        return int(min(100, base_density * multiplier))

    def _classify_zone(self, lat: float, lon: float) -> str:
        """
        Classify a location into a zone type for density estimation.

        Simple bounding box check — can be enhanced with actual
        Sofia district boundaries later.
        """
        # Check if in Sofia city center
        if (SOFIA_CENTER_BBOX["south"] <= lat <= SOFIA_CENTER_BBOX["north"]
                and SOFIA_CENTER_BBOX["west"] <= lon <= SOFIA_CENTER_BBOX["east"]):
            return "city_center"

        # Could add more zones here (parks, transit hubs, etc.)
        # For now, everything outside center is "default"
        return "default"

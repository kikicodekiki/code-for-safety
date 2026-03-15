"""
AirQualityFetcher — downloads PM2.5/PM10 readings from sensor.community
for the Sofia area and persists them to data/sofia_air_quality.json.

Data source:
    https://maps.sensor.community/#11/42.7113/23.3948
    API: https://data.sensor.community/airrohr/v1/filter/area={lat},{lon},{radius_km}

Sensor.community returns a list of sensor readings. Each entry includes:
    - location.latitude / location.longitude
    - sensordatavalues list:
        - value_type "P1" → PM10  (µg/m³)
        - value_type "P2" → PM2.5 (µg/m³)
        - value_type "temperature", "humidity" (ignored for routing)

Only sensors inside the Sofia bounding box are kept.
A disk copy is always written so the app can recover after a restart
without waiting for a live API call.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from math import inf
from pathlib import Path
from typing import Any

import httpx
import structlog

from app.config import Settings

logger = structlog.get_logger(__name__)

# Sofia geographic centre — used as the API query anchor
SOFIA_CENTER_LAT: float = 42.6977
SOFIA_CENTER_LON: float = 23.3219

# Sensor.community REST endpoint
# area=lat,lon,radius_km — returns all sensors within <radius_km> km of the point
SENSOR_COMMUNITY_URL = (
    "https://data.sensor.community/airrohr/v1/filter/"
    f"area={SOFIA_CENTER_LAT},{SOFIA_CENTER_LON},20"
)

FETCH_TIMEOUT_S: float = 20.0
# Default disk path — overridable via AIR_QUALITY_JSON_PATH in .env
DEFAULT_JSON_PATH: Path = Path("data/sofia_air_quality.json")


class AirQualityFetcher:
    """
    Fetches PM2.5/PM10 readings for Sofia from sensor.community,
    filters them to the Sofia bbox, and saves to a JSON file.

    Call fetch() on startup and every AIR_QUALITY_REFRESH_INTERVAL_S seconds.
    Falls back to the cached JSON file when the network call fails.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._json_path = Path(
            getattr(settings, "AIR_QUALITY_JSON_PATH", DEFAULT_JSON_PATH)
        )

    async def fetch(self) -> dict[str, Any]:
        """
        Fetch sensor data, filter to Sofia bbox, persist to disk, return parsed dict.

        Returns
        -------
        dict with keys: fetched_at, sensors, sensor_count, city, bbox
        Raises on complete failure (network + no disk cache).
        """
        try:
            raw = await self._fetch_from_api()
            data = self._process(raw)
            self._save(data)
            logger.info(
                "air_quality_fetched",
                sensor_count=data["sensor_count"],
                source="sensor.community",
            )
            return data

        except Exception as exc:
            logger.warning(
                "air_quality_fetch_failed",
                error=str(exc),
                fallback="disk_cache",
            )
            cached = self._load_cache()
            if cached is not None:
                logger.info(
                    "air_quality_cache_loaded",
                    sensor_count=cached.get("sensor_count", 0),
                    cached_at=cached.get("fetched_at"),
                )
                return cached
            # Return empty structure so the app starts without air quality data
            logger.error("air_quality_no_data_available")
            return _empty_payload()

    async def _fetch_from_api(self) -> list[dict]:
        async with httpx.AsyncClient(timeout=FETCH_TIMEOUT_S) as client:
            response = await client.get(
                SENSOR_COMMUNITY_URL,
                headers={"Accept": "application/json"},
            )
        response.raise_for_status()
        return response.json()

    def _process(self, raw: list[dict]) -> dict[str, Any]:
        """
        Filter to Sofia bbox, extract PM2.5/PM10, deduplicate by sensor id.
        Sensors with no PM2.5 reading are still included (pm25=None).
        """
        north = self.settings.SOFIA_BBOX_NORTH
        south = self.settings.SOFIA_BBOX_SOUTH
        east = self.settings.SOFIA_BBOX_EAST
        west = self.settings.SOFIA_BBOX_WEST

        sensors: list[dict] = []
        seen_ids: set[int] = set()

        for entry in raw:
            loc = entry.get("location", {})
            try:
                lat = float(loc.get("latitude", 0))
                lon = float(loc.get("longitude", 0))
            except (TypeError, ValueError):
                continue

            # Restrict to Sofia bounding box
            if not (south <= lat <= north and west <= lon <= east):
                continue

            sensor_id = entry.get("id") or entry.get("sensor", {}).get("id")
            if sensor_id in seen_ids:
                continue
            seen_ids.add(sensor_id)

            pm25: float | None = None
            pm10: float | None = None
            for sdv in entry.get("sensordatavalues", []):
                vtype = sdv.get("value_type", "")
                try:
                    val = float(sdv.get("value", 0))
                except (TypeError, ValueError):
                    continue
                if vtype == "P2":
                    pm25 = round(val, 2)
                elif vtype == "P1":
                    pm10 = round(val, 2)

            sensors.append(
                {
                    "sensor_id": sensor_id,
                    "lat": lat,
                    "lon": lon,
                    "pm25": pm25,
                    "pm10": pm10,
                    "timestamp": entry.get("timestamp"),
                }
            )

        return {
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "city": "Sofia, Bulgaria",
            "bbox": {
                "north": north,
                "south": south,
                "east": east,
                "west": west,
            },
            "sensor_count": len(sensors),
            "sensors": sensors,
        }

    def _save(self, data: dict) -> None:
        self._json_path.parent.mkdir(parents=True, exist_ok=True)
        self._json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        logger.debug("air_quality_saved_to_disk", path=str(self._json_path))

    def _load_cache(self) -> dict | None:
        if self._json_path.exists():
            try:
                return json.loads(self._json_path.read_text())
            except Exception:
                pass
        return None


def _empty_payload() -> dict:
    return {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "city": "Sofia, Bulgaria",
        "bbox": {},
        "sensor_count": 0,
        "sensors": [],
    }

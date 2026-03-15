"""
GET /air-quality — returns current PM2.5/PM10 readings for Sofia sensors.

Response includes the raw per-sensor readings loaded from
data/sofia_air_quality.json (refreshed every 30 minutes from
sensor.community).  Clients can display this on a map overlay or use
it to understand why certain routes have an air-quality penalty.
"""
from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(prefix="/air-quality", tags=["air-quality"])


class SensorReading(BaseModel):
    sensor_id: int | str | None = None
    lat: float
    lon: float
    pm25: float | None = None
    pm10: float | None = None
    timestamp: str | None = None


class AirQualityResponse(BaseModel):
    fetched_at: str | None
    city: str = "Sofia, Bulgaria"
    sensor_count: int
    sensors: list[SensorReading]
    source: str = "sensor.community"


@router.get("", response_model=AirQualityResponse, summary="Current Sofia air quality")
async def get_air_quality(request: Request) -> AirQualityResponse:
    """
    Return the latest PM2.5/PM10 sensor readings for Sofia.

    Data is fetched from [sensor.community](https://maps.sensor.community)
    every 30 minutes and cached in `data/sofia_air_quality.json`.
    Only sensors inside the Sofia bounding box are included.

    PM2.5 thresholds (WHO 2021 annual guideline = 5 µg/m³):
    - 0–12  µg/m³ — Good
    - 12–35 µg/m³ — Moderate
    - 35–55 µg/m³ — Unhealthy for sensitive groups
    - 55+   µg/m³ — Unhealthy / Very Unhealthy
    """
    repo = getattr(request.app.state, "air_quality_repository", None)
    if repo is None:
        return AirQualityResponse(fetched_at=None, sensor_count=0, sensors=[])

    data = repo.to_dict()
    return AirQualityResponse(
        fetched_at=data.get("fetched_at"),
        sensor_count=data.get("sensor_count", 0),
        sensors=[SensorReading(**s) for s in data.get("sensors", [])],
    )

"""
SafeCycle Sofia — Common Pydantic schemas shared across modules.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class Coordinate(BaseModel):
    """A single geographic point."""
    lat: float = Field(..., ge=-90.0, le=90.0, description="Latitude in decimal degrees")
    lon: float = Field(..., ge=-180.0, le=180.0, description="Longitude in decimal degrees")


class GeoJSONLineString(BaseModel):
    """A GeoJSON LineString geometry."""
    type: str = "LineString"
    coordinates: list[list[float]]  # Each item is [lon, lat]


class AwarenessZoneSchema(BaseModel):
    """
    An awareness zone — a location where cyclists should slow down
    because vulnerable road users (children, elderly, pedestrians) may be present.
    """
    id: str
    name: str | None = None
    type: str  # kindergarten | playground | bus_stop | accident_hotspot
    center: Coordinate
    radius_m: float = 30.0
    source: str = "osm"  # osm | manual | sofia_open_data

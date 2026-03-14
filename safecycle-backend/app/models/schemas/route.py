"""
SafeCycle Sofia — Route request and response Pydantic schemas.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, computed_field

from app.models.schemas.common import AwarenessZoneSchema, Coordinate, GeoJSONLineString


class RouteRequest(BaseModel):
    """Query parameters for the GET /route endpoint (also used internally)."""
    origin_lat: float = Field(..., ge=-90, le=90)
    origin_lon: float = Field(..., ge=-180, le=180)
    dest_lat: float = Field(..., ge=-90, le=90)
    dest_lon: float = Field(..., ge=-180, le=180)


class RouteResponse(BaseModel):
    """
    Full safe-route response returned to the mobile client.

    The `surface_defaulted` and `speed_limit_defaulted` flags indicate
    that some edges used default values because OSM data was missing.
    The mobile client displays a chip with an explanation tooltip when
    either of these is True — transparency is a core UX principle.
    """
    path: GeoJSONLineString
    crossroad_nodes: list[Coordinate]
    distance_m: float
    duration_min: float
    safety_score: float = Field(..., ge=0.0, le=1.0, description="0.0 = dangerous, 1.0 = fully safe")
    surface_defaulted: bool = Field(
        False,
        description="True if any edge used the default asphalt surface assumption"
    )
    speed_limit_defaulted: bool = Field(
        False,
        description="True if any edge used the default 50 km/h speed assumption"
    )
    awareness_zones: list[AwarenessZoneSchema] = Field(
        default_factory=list,
        description="Awareness zones (schools, bus stops) the path passes near"
    )
    edge_count: int
    excluded_edges_count: int = Field(
        0,
        description="Number of edges excluded because weight=inf (for diagnostics)"
    )
    computed_at: datetime

    @computed_field  # type: ignore[misc]
    @property
    def distance_km(self) -> float:
        """Distance in kilometres — derived from distance_m."""
        return round(self.distance_m / 1000.0, 3)

    @computed_field  # type: ignore[misc]
    @property
    def safety_label(self) -> str:
        """
        Human-readable safety classification.

        Thresholds:
          >= 0.7 → Safe     (mostly bike paths and quiet streets)
          >= 0.4 → Moderate (mix of infrastructure and standard roads)
          <  0.4 → Risky    (predominantly high-traffic roads)
        """
        if self.safety_score >= 0.7:
            return "Safe"
        elif self.safety_score >= 0.4:
            return "Moderate"
        return "Risky"

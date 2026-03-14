"""
SafeCycle Sofia — Pydantic schemas for VeloBG KML pipeline.
All data structures that flow through the VeloBG pipeline.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, computed_field
from datetime import datetime


class VeloBGPathType(str, Enum):
    """
    Cycling infrastructure classification inferred from KML style data.
    Maps to the edge weight multipliers in the routing engine.
    """
    DEDICATED_LANE = "dedicated_lane"    # Physically separated bike lane
    PAINTED_LANE   = "painted_lane"      # Painted marking on road surface
    SHARED_PATH    = "shared_path"       # Shared with pedestrians
    GREENWAY       = "greenway"          # Off-road recreational path
    OFF_ROAD       = "off_road"          # Unpaved or trail
    PROPOSED       = "proposed"          # Planned, not yet built — exclude from routing
    UNKNOWN        = "unknown"           # Could not classify


class VeloBGCoordinate(BaseModel):
    lat: float
    lon: float
    alt: float = 0.0


class VeloBGPath(BaseModel):
    """
    A single cycling path extracted from the VeloBG My Map KML.
    Represents one <Placemark> with a LineString geometry.
    """
    id:               str
    name:             str | None
    description:      str | None
    path_type:        VeloBGPathType
    coordinates:      list[VeloBGCoordinate]
    layer_name:       str | None              # KML <Folder> name this belongs to
    style_id:         str | None              # Raw KML styleUrl reference
    colour_hex:       str | None              # Extracted fill/stroke colour
    length_m:         float                   # Computed from coordinates
    is_bidirectional: bool = True
    source_placemark_id: str | None = None    # KML <Placemark> id attribute

    @computed_field
    @property
    def is_usable(self) -> bool:
        """False for PROPOSED paths — excluded from routing."""
        return self.path_type != VeloBGPathType.PROPOSED

    @computed_field
    @property
    def edge_weight_multiplier(self) -> float:
        """
        The routing weight multiplier for this path type.
        Must align with the values in app/core/graph/weighting.py.
        """
        multipliers = {
            VeloBGPathType.DEDICATED_LANE: 0.3,
            VeloBGPathType.PAINTED_LANE:   0.6,
            VeloBGPathType.SHARED_PATH:    0.65,
            VeloBGPathType.GREENWAY:       0.35,
            VeloBGPathType.OFF_ROAD:       0.7,
            VeloBGPathType.PROPOSED:       1.0,   # No bonus — not built yet
            VeloBGPathType.UNKNOWN:        0.75,  # Conservative partial bonus
        }
        return multipliers[self.path_type]


class VeloBGPoint(BaseModel):
    """
    A single point of interest from the VeloBG My Map.
    Bike repair stations, rental points, notable landmarks.
    """
    id:          str
    name:        str | None
    description: str | None
    lat:         float
    lon:         float
    layer_name:  str | None
    point_type:  str = "unknown"    # "repair", "rental", "parking", "landmark"


class VeloBGLayer(BaseModel):
    """One KML <Folder> from the My Map."""
    id:     str
    name:   str
    paths:  list[VeloBGPath]  = Field(default_factory=list)
    points: list[VeloBGPoint] = Field(default_factory=list)


class VeloBGMapData(BaseModel):
    """Complete parsed result from one KML fetch."""
    map_id:           str
    fetched_at:       datetime
    layers:           list[VeloBGLayer]
    total_paths:      int
    total_points:     int
    kml_size_bytes:   int
    fetch_duration_s: float

    @computed_field
    @property
    def all_paths(self) -> list[VeloBGPath]:
        return [p for layer in self.layers for p in layer.paths]

    @computed_field
    @property
    def usable_paths(self) -> list[VeloBGPath]:
        return [p for p in self.all_paths if p.is_usable]


class VeloBGFetchResult(BaseModel):
    """Result of one complete fetch-and-parse cycle."""
    success:       bool
    map_data:      VeloBGMapData | None
    error:         str | None
    fallback_used: bool = False
    fetched_at:    datetime

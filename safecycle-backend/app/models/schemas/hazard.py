"""
SafeCycle Sofia — Hazard report Pydantic schemas.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class HazardType(str, Enum):
    """Enumeration of reportable hazard types."""
    POTHOLE = "pothole"
    BROKEN_GLASS = "broken_glass"
    WET_SURFACE = "wet_surface"
    CONSTRUCTION = "construction"
    PARKED_VEHICLE = "parked_vehicle"   # vehicle blocking the bike lane
    POOR_VISIBILITY = "poor_visibility"
    AGGRESSIVE_DRIVER = "aggressive_driver"
    ROAD_DAMAGE = "road_damage"
    OBSTACLE = "obstacle"
    OTHER = "other"


class HazardReportCreate(BaseModel):
    """Payload for POST /hazard."""
    lat: float = Field(..., ge=42.62, le=42.73, description="Must be within Sofia bbox")
    lon: float = Field(..., ge=23.23, le=23.42, description="Must be within Sofia bbox")
    type: HazardType
    description: str | None = Field(None, max_length=500)


class HazardResponse(BaseModel):
    """
    Hazard as returned from GET /hazards or embedded in WebSocket events.

    age_hours and is_recent/is_active are computed from the stored timestamp
    at query time — they are never stored, so they always reflect real-time age.
    """
    id: str
    lat: float
    lon: float
    type: HazardType
    description: str | None
    timestamp: datetime
    age_hours: float
    is_recent: bool = Field(description="True if age_hours < HAZARD_RECENT_THRESHOLD_HOURS (1h)")
    is_active: bool = Field(description="True if age_hours < HAZARD_ACTIVE_THRESHOLD_HOURS (10h)")


class HazardReportResponse(BaseModel):
    """Response body for POST /hazard."""
    id: str
    timestamp: datetime
    message: str = "Hazard reported successfully. Thank you for keeping Sofia safe!"

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class HazardType(str, Enum):
    ROUGH_ROAD      = "rough_road"
    DOG             = "dog"
    TRAFFIC         = "traffic"
    CONSTRUCTION    = "construction"
    CLOSED_ROAD     = "closed_road"
    OTHER           = "other"


class NotificationType(str, Enum):
    DISMOUNT        = "dismount"          # approaching crossroad
    AWARENESS_ZONE  = "awareness_zone"   # school / playground / bus stop
    HAZARD_NEARBY   = "hazard_nearby"    # user-reported hazard on route
    LIGHTS_ON       = "lights_on"        # darkness / tunnel detection


class ZoneType(str, Enum):
    SCHOOL          = "school"
    PLAYGROUND      = "playground"
    BUS_STOP        = "bus_stop"
    HIGH_TRAFFIC    = "high_traffic"


# ---------------------------------------------------------------------------
# REST — POST /hazard
# ---------------------------------------------------------------------------

class HazardReportIn(BaseModel):
    """Payload the mobile client sends when a user files a hazard report."""

    hazard_type: HazardType
    lat: float  = Field(..., ge=-90,  le=90)
    lon: float  = Field(..., ge=-180, le=180)
    description: Optional[str] = Field(None, max_length=280)
    # FCM token so we can ACK the reporter
    fcm_token:  Optional[str] = None

    model_config = {"json_schema_extra": {
        "example": {
            "hazard_type": "rough_road",
            "lat": 42.6977,
            "lon": 23.3219,
            "description": "Large pothole at the tram crossing",
            "fcm_token": "eXaMpLeFcMtOkEn..."
        }
    }}


class HazardReportOut(BaseModel):
    """Response returned after storing a hazard report."""

    hazard_id:  str
    hazard_type: HazardType
    lat:        float
    lon:        float
    description: Optional[str]
    created_at: datetime
    expires_at: datetime
    redis_key:  str


# ---------------------------------------------------------------------------
# WebSocket — GPS stream
# ---------------------------------------------------------------------------

class GPSFrame(BaseModel):
    """
    Single GPS frame the phone sends over the WebSocket every ~2 seconds.
    Includes the active route_id so the backend can resolve upcoming zones.
    """

    lat:         float  = Field(..., ge=-90,  le=90)
    lon:         float  = Field(..., ge=-180, le=180)
    accuracy_m:  float  = Field(default=10.0, ge=0)
    bearing_deg: Optional[float] = Field(None, ge=0, le=360)
    speed_kmh:   Optional[float] = Field(None, ge=0)
    route_id:    Optional[str]   = None
    ts:          Optional[datetime] = None

    @field_validator("ts", mode="before")
    @classmethod
    def default_ts(cls, v):
        return v or datetime.utcnow()


class NotificationEvent(BaseModel):
    """
    Outbound message pushed back to the client over the WebSocket
    (and/or via FCM for background state).
    """

    event_id:         str            = Field(default_factory=lambda: str(uuid.uuid4()))
    notification_type: NotificationType
    title:            str
    body:             str
    # Extra context for the mobile UI (distance, zone name, etc.)
    payload:          dict           = Field(default_factory=dict)
    ts:               datetime       = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Internal proximity results (not serialised over the wire)
# ---------------------------------------------------------------------------

class CrossroadHit(BaseModel):
    node_id:    int
    lat:        float
    lon:        float
    distance_m: float


class ZoneHit(BaseModel):
    zone_id:    str
    zone_type:  ZoneType
    name:       str
    lat:        float
    lon:        float
    distance_m: float
    radius_m:   float
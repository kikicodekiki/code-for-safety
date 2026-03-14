"""
SafeCycle Sofia — GPS WebSocket Pydantic schemas.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class GPSUpdate(BaseModel):
    """
    Inbound message from the mobile client on the WebSocket.
    Sent every GPS_POLL_INTERVAL_S seconds while navigating.
    """
    lat: float = Field(..., ge=-90, le=90, description="Current latitude")
    lon: float = Field(..., ge=-180, le=180, description="Current longitude")
    heading: float = Field(0.0, ge=0, le=360, description="Compass heading in degrees (0=North)")
    speed_kmh: float = Field(0.0, ge=0, le=100, description="GPS speed in km/h")
    accuracy_m: float | None = Field(None, description="GPS accuracy radius in metres")
    timestamp: datetime | None = Field(None, description="Client-side GPS timestamp")


class WSServerEvent(BaseModel):
    """
    Outbound event pushed from server to client on the WebSocket.

    event types:
      - crossroad       : cyclist is approaching an intersection
      - awareness_zone  : cyclist is near a school/playground/bus stop
      - hazard_nearby   : user-reported hazard is close
      - ping            : keepalive
    """
    event: str
    payload: dict[str, Any]

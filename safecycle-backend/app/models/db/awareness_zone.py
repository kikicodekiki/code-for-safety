"""
SafeCycle Sofia — AwarenessZone ORM model.
Seeded from OSM data for kindergartens, playgrounds, bus stops, etc.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.db.base import Base


def _now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


class AwarenessZone(Base):
    """
    An awareness zone is a location where cyclists should slow down
    and be extra vigilant. Unlike danger/exclusion zones, these are
    NOT removed from the routing graph — instead they appear in the
    route response so the mobile UI can display alerts.

    Types:
      - kindergarten    : children entering/exiting throughout the day
      - playground      : unpredictable child movement
      - bus_stop        : passengers stepping into the road
      - accident_hotspot: historically dangerous intersection/stretch
    """
    __tablename__ = "awareness_zones"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    radius_m: Mapped[float] = mapped_column(Float, nullable=False, default=30.0)
    source: Mapped[str | None] = mapped_column(
        String(100), nullable=True, default="osm"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now_utc, nullable=False
    )

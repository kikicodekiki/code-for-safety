"""
SafeCycle Sofia — HazardReport ORM model.
PostgreSQL is the permanent record; Redis is the TTL-expiring fast path.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy import DateTime, String, Text, Float
from sqlalchemy.orm import Mapped, mapped_column

from app.models.db.base import Base


def _now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


def _expires_utc() -> datetime:
    return datetime.now(tz=timezone.utc) + timedelta(hours=10)


class HazardReport(Base):
    __tablename__ = "hazard_reports"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now_utc, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_expires_utc, nullable=False
    )

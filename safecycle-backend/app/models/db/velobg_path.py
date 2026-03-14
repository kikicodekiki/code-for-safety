"""
SafeCycle Sofia — SQLAlchemy ORM model for VeloBG cycling paths.
Maps to the velobg_paths table created by migration 006_velobg_paths.sql.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Double, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.models.db.base import Base


class VeloBGPathRecord(Base):
    __tablename__ = "velobg_paths"

    id                     = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name                   = Column(Text, nullable=True)
    description            = Column(Text, nullable=True)
    path_type              = Column(String(50), nullable=False)
    layer_name             = Column(Text, nullable=True)
    style_id               = Column(Text, nullable=True)
    colour_hex             = Column(String(7), nullable=True)
    length_m               = Column(Double, nullable=False, default=0.0)
    is_bidirectional       = Column(Boolean, nullable=False, default=True)
    is_usable              = Column(Boolean, nullable=False, default=True)
    edge_weight_multiplier = Column(Double, nullable=False, default=1.0)
    source_placemark_id    = Column(Text, nullable=True)
    # geom column managed by PostGIS — not mapped as ORM column to avoid
    # requiring GeoAlchemy2 as a hard dependency; spatial queries use raw SQL.
    fetched_at             = Column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    created_at             = Column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

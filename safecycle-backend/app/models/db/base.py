"""
SafeCycle Sofia — SQLAlchemy declarative base and shared metadata.
All ORM models must inherit from Base.
"""
from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared base for all SafeCycle ORM models."""
    pass

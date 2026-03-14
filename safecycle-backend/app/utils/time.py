"""
SafeCycle Sofia — UTC time utilities.
Centralised so that all timestamps are consistently timezone-aware.
"""
from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""
    return datetime.now(tz=timezone.utc)


def age_hours(timestamp: datetime) -> float:
    """
    Return how many hours ago a timestamp occurred.

    Parameters
    ----------
    timestamp : datetime
        Must be timezone-aware. If naive, assumed to be UTC.

    Returns
    -------
    float — hours elapsed since the timestamp (always >= 0)
    """
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    delta = utc_now() - timestamp
    return max(0.0, delta.total_seconds() / 3600.0)

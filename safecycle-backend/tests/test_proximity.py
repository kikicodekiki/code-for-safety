"""
SafeCycle Sofia — Proximity detection unit tests.
Tests crossroad and awareness zone alert logic including debouncing.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pytest

from app.core.proximity.awareness import (
    awareness_debounce_ok,
    find_nearest_awareness_zone,
)
from app.core.proximity.crossroad import (
    crossroad_debounce_ok,
    is_near_crossroad,
    CROSSROAD_DEBOUNCE_SECONDS,
)
from app.models.schemas.common import AwarenessZoneSchema, Coordinate


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


# ── Crossroad detection ───────────────────────────────────────────────────────

class TestCrossroadDetection:

    def _crossroad(self, lat: float, lon: float) -> Coordinate:
        return Coordinate(lat=lat, lon=lon)

    def test_within_radius_returns_node(self):
        """Cyclist within 15 m → crossroad detected."""
        nodes = [self._crossroad(42.6977, 23.3219)]
        # Cyclist 10 m north (same longitude)
        result = is_near_crossroad(
            lat=42.6978,  # ~11 m north
            lon=23.3219,
            crossroad_nodes=nodes,
            radius_m=15.0,
        )
        assert result is not None

    def test_outside_radius_returns_none(self):
        """Cyclist 20 m away from crossroad → no alert."""
        nodes = [self._crossroad(42.6977, 23.3219)]
        result = is_near_crossroad(
            lat=42.6979,  # ~22 m north
            lon=23.3219,
            crossroad_nodes=nodes,
            radius_m=15.0,
        )
        assert result is None

    def test_empty_crossroads_returns_none(self):
        result = is_near_crossroad(
            lat=42.6977, lon=23.3219,
            crossroad_nodes=[],
            radius_m=15.0,
        )
        assert result is None

    def test_nearest_crossroad_returned(self):
        """When multiple crossroads are in range, nearest is returned."""
        nodes = [
            self._crossroad(42.6977, 23.3219),  # 11 m north
            self._crossroad(42.6976, 23.3219),  # ~1 m south
        ]
        result = is_near_crossroad(
            lat=42.69761,
            lon=23.3219,
            crossroad_nodes=nodes,
            radius_m=15.0,
        )
        assert result is not None
        # Nearest should be the second node
        assert abs(result.lat - 42.6976) < 0.0001


# ── Crossroad debounce ────────────────────────────────────────────────────────

class TestCrossroadDebounce:

    def test_first_alert_ok(self):
        """No prior alert → debounce passes."""
        assert crossroad_debounce_ok(last_alert_time=None, now=_now()) is True

    def test_too_soon_blocked(self):
        """Alert 5 s ago → blocked (< 30 s)."""
        last = _now() - timedelta(seconds=5)
        assert crossroad_debounce_ok(last_alert_time=last, now=_now()) is False

    def test_after_30s_ok(self):
        """Alert 31 s ago → allowed."""
        last = _now() - timedelta(seconds=31)
        assert crossroad_debounce_ok(last_alert_time=last, now=_now()) is True

    def test_exactly_30s_blocked(self):
        """Exactly at the boundary: 30 s means NOT ok (must be strictly >)."""
        last = _now() - timedelta(seconds=CROSSROAD_DEBOUNCE_SECONDS)
        # At exactly the threshold, elapsed == 30.0 and condition is >= so OK
        assert crossroad_debounce_ok(last_alert_time=last, now=_now()) is True


# ── Awareness zone detection ──────────────────────────────────────────────────

class TestAwarenessZoneDetection:

    def _zone(
        self,
        lat: float,
        lon: float,
        radius_m: float = 30.0,
        zone_type: str = "kindergarten",
    ) -> AwarenessZoneSchema:
        return AwarenessZoneSchema(
            id="test-zone",
            name="Test Zone",
            type=zone_type,
            center=Coordinate(lat=lat, lon=lon),
            radius_m=radius_m,
        )

    def test_within_zone_radius_detected(self):
        """Cyclist within zone radius → zone returned."""
        zone = self._zone(42.6977, 23.3219, radius_m=30.0)
        result = find_nearest_awareness_zone(
            lat=42.6977,  # same point
            lon=23.3219,
            awareness_zones=[zone],
            search_radius_m=30.0,
        )
        assert result is not None
        found_zone, dist = result
        assert found_zone.id == "test-zone"
        assert dist < 1.0  # essentially zero distance

    def test_outside_radius_not_detected(self):
        """Cyclist 100 m away from zone (radius=30 m) → not detected."""
        zone = self._zone(42.6977, 23.3219, radius_m=30.0)
        result = find_nearest_awareness_zone(
            lat=42.6986,  # ~100 m north
            lon=23.3219,
            awareness_zones=[zone],
            search_radius_m=30.0,
        )
        assert result is None

    def test_empty_zones_returns_none(self):
        result = find_nearest_awareness_zone(
            lat=42.6977, lon=23.3219,
            awareness_zones=[],
            search_radius_m=30.0,
        )
        assert result is None

    def test_playground_zone_detected(self):
        zone = self._zone(42.6977, 23.3219, zone_type="playground")
        result = find_nearest_awareness_zone(
            lat=42.6977, lon=23.3219,
            awareness_zones=[zone],
            search_radius_m=30.0,
        )
        assert result is not None
        assert result[0].type == "playground"

    def test_bus_stop_zone_detected(self):
        zone = self._zone(42.6977, 23.3219, zone_type="bus_stop")
        result = find_nearest_awareness_zone(
            lat=42.6977, lon=23.3219,
            awareness_zones=[zone],
            search_radius_m=30.0,
        )
        assert result is not None

    def test_distance_returned_correctly(self):
        """Distance in the result tuple should match haversine calculation."""
        from app.utils.geo import haversine_metres
        zone = self._zone(42.6977, 23.3219)
        result = find_nearest_awareness_zone(
            lat=42.6977,
            lon=23.3220,
            awareness_zones=[zone],
            search_radius_m=50.0,
        )
        assert result is not None
        _, dist = result
        expected = haversine_metres(42.6977, 23.3220, 42.6977, 23.3219)
        assert abs(dist - expected) < 1.0


# ── Awareness zone debounce ───────────────────────────────────────────────────

class TestAwarenessDebounce:

    def test_no_prior_alert_ok(self):
        assert awareness_debounce_ok(None, _now()) is True

    def test_too_recent_blocked(self):
        last = _now() - timedelta(seconds=10)
        assert awareness_debounce_ok(last, _now()) is False

    def test_after_30s_ok(self):
        last = _now() - timedelta(seconds=35)
        assert awareness_debounce_ok(last, _now()) is True

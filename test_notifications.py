from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from notifications.hazard_service    import HazardService, HAZARD_TTL_SECONDS
from notifications.models            import (
    GPSFrame, HazardReportIn, HazardType, NotificationType,
)
from notifications.proximity_service import ProximityService, haversine_m
from notifications.gps_processor     import GPSProcessor


# ---------------------------------------------------------------------------
# Haversine helper
# ---------------------------------------------------------------------------

def test_haversine_known_distance():
    """NDK to Vitosha Monument is ~1 km as the crow flies."""
    lat1, lon1 = 42.6850, 23.3190   # NDK
    lat2, lon2 = 42.6739, 23.3194   # Vitosha Monument area
    d = haversine_m(lat1, lon1, lat2, lon2)
    assert 1000 < d < 1400, f"Unexpected distance: {d}"


def test_haversine_zero():
    d = haversine_m(42.0, 23.0, 42.0, 23.0)
    assert d == pytest.approx(0.0, abs=1e-6)


# ---------------------------------------------------------------------------
# ProximityService — crossroad detection
# ---------------------------------------------------------------------------

class TestCrossroadDetection:
    @pytest.fixture
    def svc(self):
        prox = ProximityService()
        prox.build_crossroad_index([
            {"node_id": 1, "lat": 42.6977, "lon": 23.3219},   # exact match target
            {"node_id": 2, "lat": 42.7000, "lon": 23.3300},   # 300 m away
        ])
        return prox

    def test_hit_within_15m(self, svc):
        # 5 m offset → should trigger
        hit = svc.nearest_crossroad(42.6977 + 0.00004, 23.3219)
        assert hit is not None
        assert hit.node_id == 1
        assert hit.distance_m < 15.0

    def test_miss_outside_15m(self, svc):
        # ~200 m offset → no hit
        hit = svc.nearest_crossroad(42.6977 + 0.002, 23.3219)
        assert hit is None

    def test_empty_index(self):
        prox = ProximityService()
        prox.build_crossroad_index([])
        assert prox.nearest_crossroad(42.6977, 23.3219) is None


# ---------------------------------------------------------------------------
# ProximityService — zone detection
# ---------------------------------------------------------------------------

class TestZoneDetection:
    @pytest.fixture
    def svc(self):
        prox = ProximityService()
        prox.build_zone_index([
            {
                "zone_id":   "school-001",
                "zone_type": "school",
                "name":      "Test School",
                "lat":       42.6977,
                "lon":       23.3219,
                "radius_m":  100.0,
            }
        ])
        return prox

    def test_inside_zone(self, svc):
        hits = svc.zones_within_radius(42.6977 + 0.0005, 23.3219)  # ~55 m
        assert len(hits) == 1
        assert hits[0].name == "Test School"

    def test_outside_zone(self, svc):
        hits = svc.zones_within_radius(42.6977 + 0.002, 23.3219)   # ~220 m
        assert len(hits) == 0

    def test_sorted_by_distance(self):
        prox = ProximityService()
        prox.build_zone_index([
            {"zone_id": "z1", "zone_type": "school",    "name": "Far",   "lat": 42.6990, "lon": 23.3219, "radius_m": 200},
            {"zone_id": "z2", "zone_type": "bus_stop",  "name": "Close", "lat": 42.6980, "lon": 23.3219, "radius_m": 200},
        ])
        hits = prox.zones_within_radius(42.6977, 23.3219)
        assert hits[0].name == "Close"


# ---------------------------------------------------------------------------
# HazardService
# ---------------------------------------------------------------------------

class TestHazardService:
    @pytest.fixture
    def mock_redis(self):
        r = AsyncMock()
        pipe = AsyncMock()
        pipe.__aenter__ = AsyncMock(return_value=pipe)
        pipe.__aexit__  = AsyncMock(return_value=False)
        pipe.execute    = AsyncMock(return_value=[1, True, 1, 0])
        r.pipeline      = MagicMock(return_value=pipe)
        return r

    @pytest.mark.asyncio
    async def test_store_report_returns_out(self, mock_redis):
        svc = HazardService(mock_redis)
        report = HazardReportIn(
            hazard_type=HazardType.DOG,
            lat=42.6977,
            lon=23.3219,
            description="Aggressive dog near the park",
        )
        result = await svc.store_report(report)
        assert result.hazard_type == HazardType.DOG
        assert result.lat == 42.6977
        assert result.redis_key.startswith("hazard:")
        # TTL should be exactly 10 h
        delta = (result.expires_at - result.created_at).total_seconds()
        assert delta == pytest.approx(HAZARD_TTL_SECONDS, abs=1)

    @pytest.mark.asyncio
    async def test_get_report_not_found(self):
        r = AsyncMock()
        r.hgetall = AsyncMock(return_value={})
        svc = HazardService(r)
        result = await svc.get_report("nonexistent-id")
        assert result is None


# ---------------------------------------------------------------------------
# GPSProcessor integration (mocked services)
# ---------------------------------------------------------------------------

class TestGPSProcessor:
    def _make_processor(
        self,
        crossroad_hit=None,
        zone_hits=None,
        hazards=None,
        fcm_event=None,
    ) -> GPSProcessor:
        prox_svc = MagicMock()
        prox_svc.nearest_crossroad    = MagicMock(return_value=crossroad_hit)
        prox_svc.zones_within_radius  = MagicMock(return_value=zone_hits or [])
        ProximityService.hazards_within_radius = staticmethod(
            lambda lat, lon, h, **kw: hazards or []
        )

        hazard_svc  = AsyncMock()
        hazard_svc.get_hazards_near = AsyncMock(return_value=[])

        notif_svc   = AsyncMock()
        notif_svc.send_dismount_alert       = AsyncMock(return_value=fcm_event)
        notif_svc.send_awareness_zone_alert = AsyncMock(return_value=None)
        notif_svc.send_hazard_nearby_alert  = AsyncMock(return_value=None)
        notif_svc.send_lights_on_alert      = AsyncMock(return_value=None)

        return GPSProcessor(
            user_id="test-user",
            fcm_token="test-fcm-token",
            hazard_service=hazard_svc,
            notification_service=notif_svc,
            proximity_service=prox_svc,
        )

    @pytest.mark.asyncio
    async def test_no_events_when_clear(self):
        proc   = self._make_processor()
        frame  = GPSFrame(lat=42.6977, lon=23.3219, speed_kmh=15, ts=datetime(2025, 6, 15, 14, 0, 0))
        events = await proc.process(frame)
        assert events == []

    @pytest.mark.asyncio
    async def test_lights_on_at_night(self):
        from notifications.models import NotificationEvent, NotificationType

        notif_event = NotificationEvent(
            notification_type=NotificationType.LIGHTS_ON,
            title="💡 Включете светлините",
            body="Намалена видимост",
            payload={},
        )

        proc = self._make_processor()
        # Override lights service to return an event
        proc._notif_svc.send_lights_on_alert = AsyncMock(return_value=notif_event)

        frame  = GPSFrame(lat=42.6977, lon=23.3219, speed_kmh=18, ts=datetime(2025, 6, 15, 21, 0, 0))
        events = await proc.process(frame)

        lights_events = [e for e in events if e.notification_type == NotificationType.LIGHTS_ON]
        assert len(lights_events) == 1


# ---------------------------------------------------------------------------
# WebSocket protocol smoke test (FastAPI TestClient)
# ---------------------------------------------------------------------------

def test_websocket_gps_endpoint():
    """
    Verify the WebSocket endpoint accepts a connection and returns the
    'connected' acknowledgement JSON.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from unittest.mock import MagicMock

    from notifications.router import router as notif_router

    app = FastAPI()
    app.include_router(notif_router)

    # Wire minimal mock services onto app.state
    prox = ProximityService()
    prox.build_crossroad_index([])
    prox.build_zone_index([])

    app.state.hazard_service       = MagicMock(spec=HazardService)
    app.state.notification_service = MagicMock(spec=type)
    app.state.proximity_service    = prox

    client = TestClient(app)
    with client.websocket_connect("/notifications/ws/gps/user-42") as ws:
        ack = ws.receive_json()
        assert ack["status"] == "connected"
        assert ack["user_id"] == "user-42"

        # Send a valid GPS frame
        ws.send_json({
            "lat": 42.6977,
            "lon": 23.3219,
            "speed_kmh": 15.0,
        })
        # No notifications expected with empty indexes — connection stays alive
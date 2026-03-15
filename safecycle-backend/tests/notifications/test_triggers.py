"""
Tests for notification triggers — crossroad, zone, hazard, route.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.notifications.triggers.crossroad import CrossroadTrigger
from app.notifications.triggers.zone import ZoneTrigger
from app.notifications.triggers.hazard import HazardTrigger
from app.notifications.triggers.route import RouteTrigger
from app.notifications.types import NotificationResult, NotificationChannel


def make_dispatcher(sent: bool = True):
    d = AsyncMock()
    d.dispatch = AsyncMock(return_value=NotificationResult(
        sent=sent,
        channels=[NotificationChannel.WEBSOCKET] if sent else [],
    ))
    return d


# ── CrossroadTrigger ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestCrossroadTrigger:

    async def test_fires_when_within_radius(self):
        dispatcher = make_dispatcher(sent=True)
        trigger    = CrossroadTrigger(dispatcher, alert_radius_m=15.0)

        result = await trigger.check(
            device_id="dev",
            session_id="sess_abc",
            lat=42.6977,
            lon=23.3219,
            crossroad_nodes=[{"lat": 42.6977, "lon": 23.3220}],  # ~7m away
            is_navigating=True,
        )

        assert result is True
        dispatcher.dispatch.assert_awaited_once()

    async def test_does_not_fire_when_beyond_radius(self):
        dispatcher = make_dispatcher(sent=False)
        trigger    = CrossroadTrigger(dispatcher, alert_radius_m=15.0)

        result = await trigger.check(
            device_id="dev",
            session_id="sess_abc",
            lat=42.6977,
            lon=23.3219,
            crossroad_nodes=[{"lat": 42.8, "lon": 23.5}],  # far away
            is_navigating=True,
        )

        assert result is False
        dispatcher.dispatch.assert_not_awaited()

    async def test_does_not_fire_when_not_navigating(self):
        dispatcher = make_dispatcher()
        trigger    = CrossroadTrigger(dispatcher, alert_radius_m=15.0)

        result = await trigger.check(
            device_id="dev",
            session_id="sess_abc",
            lat=42.6977,
            lon=23.3219,
            crossroad_nodes=[{"lat": 42.6977, "lon": 23.3219}],
            is_navigating=False,
        )

        assert result is False
        dispatcher.dispatch.assert_not_awaited()

    async def test_does_not_fire_with_empty_nodes(self):
        dispatcher = make_dispatcher()
        trigger    = CrossroadTrigger(dispatcher, alert_radius_m=15.0)

        result = await trigger.check(
            device_id="dev",
            session_id="sess",
            lat=42.6977,
            lon=23.3219,
            crossroad_nodes=[],
            is_navigating=True,
        )

        assert result is False


# ── ZoneTrigger ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestZoneTrigger:

    async def test_fires_when_inside_zone(self):
        dispatcher = make_dispatcher(sent=True)
        trigger    = ZoneTrigger(dispatcher, zone_radius_m=30.0)

        result = await trigger.check(
            device_id="dev",
            session_id="sess",
            lat=42.6977,
            lon=23.3219,
            awareness_zones=[{
                "center": {"lat": 42.6977, "lon": 23.3220},
                "type": "playground",
                "name": "Test Playground",
            }],
            is_navigating=True,
        )

        assert result is True

    async def test_does_not_fire_when_outside_zone(self):
        dispatcher = make_dispatcher()
        trigger    = ZoneTrigger(dispatcher, zone_radius_m=30.0)

        result = await trigger.check(
            device_id="dev",
            session_id="sess",
            lat=42.6977,
            lon=23.3219,
            awareness_zones=[{
                "center": {"lat": 42.8, "lon": 23.5},
                "type": "school",
            }],
            is_navigating=True,
        )

        assert result is False

    async def test_uses_flat_lat_lon_structure(self):
        dispatcher = make_dispatcher(sent=True)
        trigger    = ZoneTrigger(dispatcher, zone_radius_m=30.0)

        result = await trigger.check(
            device_id="dev",
            session_id="sess",
            lat=42.6977,
            lon=23.3219,
            awareness_zones=[{"lat": 42.6977, "lon": 23.3220, "type": "bus_stop"}],
            is_navigating=True,
        )

        assert result is True


# ── HazardTrigger ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestHazardTrigger:

    async def test_fires_hazard_nearby(self):
        dispatcher = make_dispatcher(sent=True)
        trigger    = HazardTrigger(dispatcher, hazard_radius_m=20.0)

        result = await trigger.check_nearby(
            device_id="dev",
            session_id="sess",
            lat=42.6977,
            lon=23.3219,
            hazards=[{
                "id": "h1",
                "lat": 42.6977,
                "lon": 23.3220,
                "hazard_type": "pothole",
                "consensus_severity": 2,
            }],
            is_navigating=True,
        )

        assert result is True

    async def test_fires_road_closed_for_closed_road_high_severity(self):
        from app.notifications.types import NotificationType
        dispatcher = make_dispatcher(sent=True)
        trigger    = HazardTrigger(dispatcher, hazard_radius_m=20.0)

        await trigger.check_nearby(
            device_id="dev",
            session_id="sess",
            lat=42.6977,
            lon=23.3219,
            hazards=[{
                "lat": 42.6977,
                "lon": 23.3220,
                "hazard_type": "road_closed",
                "consensus_severity": 4,
            }],
        )

        call_payload = dispatcher.dispatch.call_args[0][0]
        assert call_payload.type == NotificationType.ROAD_CLOSED_AHEAD

    async def test_no_fire_when_hazards_empty(self):
        dispatcher = make_dispatcher()
        trigger    = HazardTrigger(dispatcher, hazard_radius_m=20.0)

        result = await trigger.check_nearby(
            device_id="dev",
            session_id="sess",
            lat=42.6977,
            lon=23.3219,
            hazards=[],
        )

        assert result is False


# ── RouteTrigger ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestRouteTrigger:

    async def test_notify_safety_degraded_fires_when_drop_significant(self):
        dispatcher = make_dispatcher(sent=True)
        trigger    = RouteTrigger(dispatcher)

        sent = await trigger.notify_safety_degraded(
            device_tokens=["tok1", "tok2"],
            old_score=0.85,
            new_score=0.65,
            route_id="route_123",
        )

        assert sent == 2
        assert dispatcher.dispatch.await_count == 2

    async def test_notify_safety_degraded_no_fire_when_drop_small(self):
        dispatcher = make_dispatcher()
        trigger    = RouteTrigger(dispatcher)

        sent = await trigger.notify_safety_degraded(
            device_tokens=["tok1"],
            old_score=0.85,
            new_score=0.80,  # only 0.05 drop
            route_id="route_123",
        )

        assert sent == 0
        dispatcher.dispatch.assert_not_awaited()

    async def test_notify_hazard_confirmed_sends_to_all_tokens(self):
        dispatcher = make_dispatcher(sent=True)
        trigger    = RouteTrigger(dispatcher)

        sent = await trigger.notify_hazard_confirmed(
            device_tokens=["tok1", "tok2", "tok3"],
            hazard_type="pothole",
            route_id="route_abc",
        )

        assert sent == 3

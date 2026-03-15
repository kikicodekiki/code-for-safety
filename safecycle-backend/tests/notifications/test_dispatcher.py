"""
Tests for NotificationDispatcher — the central dispatch pipeline.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.notifications.dispatcher import NotificationDispatcher
from app.notifications.types import (
    NotificationType, NotificationUrgency, NotificationChannel, build_payload
)


@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    redis.exists = AsyncMock(return_value=0)
    redis.ttl    = AsyncMock(return_value=0)
    redis.setex  = AsyncMock()
    redis.delete = AsyncMock()
    redis.get    = AsyncMock(return_value=None)
    return redis


@pytest.fixture
def dispatcher(mock_redis):
    d = NotificationDispatcher(redis=mock_redis, connection_manager=None)
    return d


def make_payload(
    ntype=NotificationType.CROSSROAD_DISMOUNT,
    device_id="test_device_session_123",
    **kwargs,
):
    return build_payload(
        device_id=device_id,
        ntype=ntype,
        data=kwargs.get("data", {"distance_m": 12.0}),
        session_id=device_id,
        latitude=42.6977,
        longitude=23.3219,
    )


@pytest.mark.asyncio
class TestDispatcherPreferenceGating:

    async def test_suppressed_when_preference_disabled(self, dispatcher, mock_redis):
        # Preferences stored in Redis as JSON — return a JSON blob with crossroad disabled
        import json
        prefs = {"crossroad_alerts": False}
        mock_redis.get.return_value = json.dumps(prefs)

        payload = make_payload(NotificationType.CROSSROAD_DISMOUNT)
        result  = await dispatcher.dispatch(payload)

        assert result.sent is False
        assert result.suppressed is True

    async def test_passes_when_preference_enabled(self, dispatcher, mock_redis):
        mock_redis.get.return_value = None  # default prefs → all enabled

        with patch(
            "app.notifications.channels.websocket.send_via_websocket",
            new_callable=AsyncMock,
            return_value=True,
        ):
            payload = make_payload(NotificationType.CROSSROAD_DISMOUNT)
            result  = await dispatcher.dispatch(payload)

        assert result.sent is True


@pytest.mark.asyncio
class TestDispatcherDebounceGating:

    async def test_debounced_when_key_exists(self, dispatcher, mock_redis):
        mock_redis.get.return_value  = None   # prefs = default (enabled)
        mock_redis.exists.return_value = 1    # debounce key present

        payload = make_payload(NotificationType.CROSSROAD_DISMOUNT)
        result  = await dispatcher.dispatch(payload)

        assert result.sent is False
        assert result.debounced is True

    async def test_not_debounced_when_key_absent(self, dispatcher, mock_redis):
        mock_redis.get.return_value    = None  # prefs = default (enabled)
        mock_redis.exists.return_value = 0     # no debounce key

        with patch(
            "app.notifications.channels.websocket.send_via_websocket",
            new_callable=AsyncMock,
            return_value=True,
        ):
            payload = make_payload(NotificationType.CROSSROAD_DISMOUNT)
            result  = await dispatcher.dispatch(payload)

        assert result.sent is True
        assert result.debounced is False


@pytest.mark.asyncio
class TestDispatcherSuppressionGating:

    async def test_suppressed_when_not_navigating(self, dispatcher, mock_redis):
        mock_redis.get.return_value    = None
        mock_redis.exists.return_value = 0

        payload = make_payload(NotificationType.ROUTE_SAFETY_DEGRADED)
        result  = await dispatcher.dispatch(payload, is_navigating=False)

        assert result.sent is False
        assert result.suppressed is True
        assert "navigating" in result.reason

    async def test_quiet_hours_suppresses_medium(self, dispatcher, mock_redis):
        import json
        mock_redis.get.return_value    = json.dumps({"quiet_hours_enabled": True})
        mock_redis.exists.return_value = 0

        payload = make_payload(NotificationType.AWARENESS_ZONE_ENTER)
        result  = await dispatcher.dispatch(
            payload, is_navigating=True, device_local_hour=23
        )

        assert result.sent is False
        assert result.suppressed is True

    async def test_quiet_hours_does_not_suppress_high(self, dispatcher, mock_redis):
        import json
        mock_redis.get.return_value    = json.dumps({"quiet_hours_enabled": True})
        mock_redis.exists.return_value = 0

        with patch(
            "app.notifications.channels.websocket.send_via_websocket",
            new_callable=AsyncMock,
            return_value=True,
        ):
            payload = make_payload(NotificationType.HAZARD_NEARBY)
            result  = await dispatcher.dispatch(
                payload, is_navigating=True, device_local_hour=23
            )

        assert result.sent is True


@pytest.mark.asyncio
class TestDispatcherChannelSelection:

    async def test_debounce_recorded_after_successful_send(self, dispatcher, mock_redis):
        mock_redis.get.return_value    = None
        mock_redis.exists.return_value = 0

        with patch(
            "app.notifications.channels.websocket.send_via_websocket",
            new_callable=AsyncMock,
            return_value=True,
        ):
            payload = make_payload(NotificationType.CROSSROAD_DISMOUNT)
            await dispatcher.dispatch(payload)

        # setex should have been called for debounce recording
        mock_redis.setex.assert_awaited()

    async def test_fcm_only_for_route_degraded(self, dispatcher, mock_redis):
        mock_redis.get.return_value    = None
        mock_redis.exists.return_value = 0

        with patch(
            "app.notifications.channels.fcm.send_via_fcm",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_fcm:
            payload = make_payload(
                NotificationType.ROUTE_SAFETY_DEGRADED,
                data={"old_score": 0.8, "new_score": 0.6},
            )
            result = await dispatcher.dispatch(payload, is_navigating=True)

        assert NotificationChannel.FCM in result.channels

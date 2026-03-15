"""
Tests for NotificationDebouncer — Redis TTL-based debounce logic.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.notifications.rules.debounce import NotificationDebouncer, _spatial_key
from app.notifications.types import NotificationType, DEBOUNCE_SECONDS


@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    redis.exists = AsyncMock(return_value=0)
    redis.ttl    = AsyncMock(return_value=25)
    redis.setex  = AsyncMock()
    redis.delete = AsyncMock()
    redis.scan_iter = AsyncMock(return_value=aiter([]))
    return redis


async def aiter(items):
    for item in items:
        yield item


@pytest.fixture
def debouncer(mock_redis):
    return NotificationDebouncer(mock_redis)


class TestSpatialKey:
    def test_returns_global_when_no_coords(self):
        assert _spatial_key(None, None) == "global"
        assert _spatial_key(None, 23.3) == "global"
        assert _spatial_key(42.7, None) == "global"

    def test_returns_deterministic_bucket(self):
        key1 = _spatial_key(42.6977, 23.3219)
        key2 = _spatial_key(42.6977, 23.3219)
        assert key1 == key2

    def test_same_bucket_for_nearby_coords(self):
        # Coords less than 10m apart should produce the same bucket
        key1 = _spatial_key(42.6977, 23.3219)
        key2 = _spatial_key(42.6978, 23.3220)
        assert key1 == key2

    def test_different_bucket_for_distant_coords(self):
        # Coords ~2km apart should produce different buckets
        key1 = _spatial_key(42.6977, 23.3219)
        key2 = _spatial_key(42.72, 23.36)
        assert key1 != key2


@pytest.mark.asyncio
class TestNotificationDebouncer:

    async def test_not_debounced_when_key_absent(self, debouncer, mock_redis):
        mock_redis.exists.return_value = 0
        result = await debouncer.is_debounced(
            "device_abc", NotificationType.CROSSROAD_DISMOUNT, 42.7, 23.3
        )
        assert result is False

    async def test_debounced_when_key_present(self, debouncer, mock_redis):
        mock_redis.exists.return_value = 1
        result = await debouncer.is_debounced(
            "device_abc", NotificationType.CROSSROAD_DISMOUNT, 42.7, 23.3
        )
        assert result is True

    async def test_record_uses_correct_ttl(self, debouncer, mock_redis):
        await debouncer.record(
            "device_abc", NotificationType.HAZARD_NEARBY, 42.7, 23.3
        )
        mock_redis.setex.assert_awaited_once()
        args = mock_redis.setex.call_args[0]
        assert args[1] == DEBOUNCE_SECONDS[NotificationType.HAZARD_NEARBY]

    async def test_record_key_contains_type_and_spatial(self, debouncer, mock_redis):
        await debouncer.record(
            "device_abc", NotificationType.CROSSROAD_DISMOUNT, 42.7, 23.3
        )
        key = mock_redis.setex.call_args[0][0]
        assert "crossroad_dismount" in key
        assert "device_abc" in key

    async def test_clear_deletes_key(self, debouncer, mock_redis):
        await debouncer.clear(
            "device_abc", NotificationType.CROSSROAD_DISMOUNT, 42.7, 23.3
        )
        mock_redis.delete.assert_awaited_once()

    async def test_global_spatial_key_for_no_coords(self, debouncer, mock_redis):
        await debouncer.record(
            "device_abc", NotificationType.ROUTE_SAFETY_DEGRADED
        )
        key = mock_redis.setex.call_args[0][0]
        assert "global" in key

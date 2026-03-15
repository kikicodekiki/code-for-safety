"""
Tests for NotificationPreferencesManager — per-device opt-in/out settings.
"""
from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock

from app.notifications.rules.preferences import (
    NotificationPreferencesManager, DevicePreferences
)
from app.notifications.types import NotificationType


@pytest.fixture
def mock_redis():
    r = AsyncMock()
    r.get   = AsyncMock(return_value=None)
    r.setex = AsyncMock()
    return r


@pytest.fixture
def manager(mock_redis):
    return NotificationPreferencesManager(mock_redis)


@pytest.mark.asyncio
class TestPreferencesManager:

    async def test_default_all_enabled_when_no_stored_prefs(self, manager, mock_redis):
        mock_redis.get.return_value = None
        for ntype in NotificationType:
            enabled = await manager.is_enabled("device_xyz", ntype)
            assert enabled is True, f"{ntype} should be enabled by default"

    async def test_disabled_when_preference_set_to_false(self, manager, mock_redis):
        mock_redis.get.return_value = json.dumps({"crossroad_alerts": False})
        result = await manager.is_enabled("device_xyz", NotificationType.CROSSROAD_DISMOUNT)
        assert result is False

    async def test_enabled_when_preference_explicitly_true(self, manager, mock_redis):
        mock_redis.get.return_value = json.dumps({"crossroad_alerts": True})
        result = await manager.is_enabled("device_xyz", NotificationType.CROSSROAD_DISMOUNT)
        assert result is True

    async def test_set_persists_to_redis(self, manager, mock_redis):
        prefs = DevicePreferences(crossroad_alerts=False)
        await manager.set("device_xyz", prefs)
        mock_redis.setex.assert_awaited_once()
        stored = json.loads(mock_redis.setex.call_args[0][2])
        assert stored["crossroad_alerts"] is False

    async def test_set_from_dict_validates_and_stores(self, manager, mock_redis):
        prefs = await manager.set_from_dict(
            "device_xyz",
            {"hazard_nearby_alerts": False, "unknown_key": True},
        )
        assert prefs.hazard_nearby_alerts is False
        assert prefs.crossroad_alerts is True   # default

    async def test_quiet_hours_overnight_window(self, manager, mock_redis):
        # 22:00 → 07:00 window
        mock_redis.get.return_value = json.dumps({
            "quiet_hours_enabled": True,
            "quiet_hours_start": 22,
            "quiet_hours_end": 7,
        })
        assert await manager.is_in_quiet_hours("dev", 23) is True
        assert await manager.is_in_quiet_hours("dev", 0)  is True
        assert await manager.is_in_quiet_hours("dev", 6)  is True
        assert await manager.is_in_quiet_hours("dev", 7)  is False
        assert await manager.is_in_quiet_hours("dev", 12) is False
        assert await manager.is_in_quiet_hours("dev", 22) is True

    async def test_quiet_hours_disabled_always_returns_false(self, manager, mock_redis):
        mock_redis.get.return_value = json.dumps({"quiet_hours_enabled": False})
        for hour in range(24):
            assert await manager.is_in_quiet_hours("dev", hour) is False

    async def test_invalid_stored_json_returns_defaults(self, manager, mock_redis):
        mock_redis.get.return_value = "not_valid_json{{{"
        prefs = await manager.get("device_xyz")
        assert prefs.crossroad_alerts is True

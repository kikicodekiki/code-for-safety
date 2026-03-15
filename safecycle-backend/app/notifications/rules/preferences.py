"""
NotificationPreferences — per-device notification opt-in/opt-out settings.

Stored in Redis as a JSON blob per device_id with a 30-day TTL.
Synced from mobile on every app open and on settings change via
POST /device/preferences.

Default: all notification types enabled.
"""
from __future__ import annotations

import json
import structlog
from dataclasses import dataclass, asdict
from redis.asyncio import Redis

from app.notifications.types import NotificationType

logger = structlog.get_logger(__name__)

PREFS_PREFIX = "safecycle:prefs:"
PREFS_TTL_S  = 86400 * 30    # 30 days — outlasts any ride


@dataclass
class DevicePreferences:
    crossroad_alerts:        bool = True
    awareness_zone_alerts:   bool = True
    hazard_nearby_alerts:    bool = True
    road_closed_alerts:      bool = True
    route_degraded_alerts:   bool = True
    hazard_confirmed_alerts: bool = True
    quiet_hours_enabled:     bool = False
    quiet_hours_start:       int  = 22   # Hour in 24h local time (inclusive)
    quiet_hours_end:         int  = 7    # Hour in 24h local time (exclusive)


# Maps notification type → preference field name
TYPE_TO_PREF: dict[NotificationType, str] = {
    NotificationType.CROSSROAD_DISMOUNT:     "crossroad_alerts",
    NotificationType.AWARENESS_ZONE_ENTER:   "awareness_zone_alerts",
    NotificationType.HAZARD_NEARBY:          "hazard_nearby_alerts",
    NotificationType.ROAD_CLOSED_AHEAD:      "road_closed_alerts",
    NotificationType.ROUTE_SAFETY_DEGRADED:  "route_degraded_alerts",
    NotificationType.HAZARD_CONFIRMED_AHEAD: "hazard_confirmed_alerts",
}


class NotificationPreferencesManager:

    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    async def is_enabled(
        self,
        device_id:         str,
        notification_type: NotificationType,
    ) -> bool:
        """
        Returns True if the device has not opted out of this notification type.
        Returns True (default enabled) if no preferences are stored yet.
        """
        prefs      = await self.get(device_id)
        pref_field = TYPE_TO_PREF.get(notification_type)
        if pref_field is None:
            return True
        return getattr(prefs, pref_field, True)

    async def get(self, device_id: str) -> DevicePreferences:
        key  = f"{PREFS_PREFIX}{device_id}"
        data = await self.redis.get(key)
        if data is None:
            return DevicePreferences()
        try:
            raw = json.loads(data)
            return DevicePreferences(**{
                k: v for k, v in raw.items()
                if k in DevicePreferences.__dataclass_fields__
            })
        except Exception:
            return DevicePreferences()

    async def set(
        self,
        device_id:   str,
        preferences: DevicePreferences,
    ) -> None:
        key = f"{PREFS_PREFIX}{device_id}"
        await self.redis.setex(
            key,
            PREFS_TTL_S,
            json.dumps(asdict(preferences)),
        )
        logger.info("device_preferences_updated", device_id=device_id[:8])

    async def set_from_dict(
        self,
        device_id: str,
        raw:       dict,
    ) -> DevicePreferences:
        """
        Called from POST /device/preferences endpoint.
        Validates and stores the preference dict sent from the mobile client.
        Unknown keys are silently ignored.
        """
        prefs = DevicePreferences(**{
            k: v for k, v in raw.items()
            if k in DevicePreferences.__dataclass_fields__
        })
        await self.set(device_id, prefs)
        return prefs

    async def is_in_quiet_hours(
        self,
        device_id:   str,
        local_hour:  int,
    ) -> bool:
        """
        Returns True if the current local hour falls within the device's
        configured quiet hours window.
        """
        prefs = await self.get(device_id)
        if not prefs.quiet_hours_enabled:
            return False
        start = prefs.quiet_hours_start
        end   = prefs.quiet_hours_end
        # Handle overnight windows (e.g. 22 → 7)
        if start > end:
            return local_hour >= start or local_hour < end
        return start <= local_hour < end

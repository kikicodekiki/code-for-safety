"""
NotificationDebouncer — prevents alert spam using Redis TTL keys.

Each (device_id, notification_type, spatial_key) triple gets a Redis key
with TTL equal to the debounce window for that type. While the key exists,
subsequent notifications of the same type for the same device at the same
location are suppressed.

The spatial_key is a coarse grid cell (~1km) so a cyclist moving through
the same zone does not re-trigger on every GPS tick, but will re-trigger
when they return to the area after leaving.

Key schema:
    safecycle:debounce:{device_id}:{notification_type}:{spatial_key}
    TTL: DEBOUNCE_SECONDS[notification_type]
"""
from __future__ import annotations

import structlog
from redis.asyncio import Redis

from app.notifications.types import NotificationType, DEBOUNCE_SECONDS

logger = structlog.get_logger(__name__)

DEBOUNCE_PREFIX = "safecycle:debounce:"


def _spatial_key(lat: float | None, lon: float | None) -> str:
    """
    Computes a coarse spatial bucket (~1km cells) for debounce grouping.
    Falls back to 'global' for non-spatial notification types.
    """
    if lat is None or lon is None:
        return "global"
    # ~1km cells around Sofia's coordinate range
    lat_bucket = int((lat - 42.0) / 0.01)
    lon_bucket = int((lon - 23.0) / 0.01)
    return f"{lat_bucket}_{lon_bucket}"


class NotificationDebouncer:

    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    async def is_debounced(
        self,
        device_id:         str,
        notification_type: NotificationType,
        lat:               float | None = None,
        lon:               float | None = None,
    ) -> bool:
        """
        Returns True if this (device, type, location) combination is
        within its debounce window and the notification should be suppressed.
        """
        key    = self._make_key(device_id, notification_type, lat, lon)
        exists = await self.redis.exists(key)
        if exists:
            ttl = await self.redis.ttl(key)
            logger.debug(
                "notification_debounced",
                device_id=device_id[:8],
                type=notification_type.value,
                ttl_remaining_s=ttl,
            )
            return True
        return False

    async def record(
        self,
        device_id:         str,
        notification_type: NotificationType,
        lat:               float | None = None,
        lon:               float | None = None,
    ) -> None:
        """
        Records that a notification was sent, starting the debounce window.
        Call this AFTER a successful dispatch, not before.
        """
        key = self._make_key(device_id, notification_type, lat, lon)
        ttl = DEBOUNCE_SECONDS[notification_type]
        await self.redis.setex(key, ttl, "1")
        logger.debug(
            "notification_debounce_recorded",
            device_id=device_id[:8],
            type=notification_type.value,
            debounce_window_s=ttl,
        )

    async def clear(
        self,
        device_id:         str,
        notification_type: NotificationType,
        lat:               float | None = None,
        lon:               float | None = None,
    ) -> None:
        """
        Clears the debounce window early.
        Used when a road_closed hazard is dismissed so the cyclist can
        receive a fresh alert if the situation changes.
        """
        key = self._make_key(device_id, notification_type, lat, lon)
        await self.redis.delete(key)

    async def clear_all_for_device(self, device_id: str) -> int:
        """
        Clears all debounce keys for a device.
        Called when navigation ends — fresh start for the next ride.
        """
        pattern = f"{DEBOUNCE_PREFIX}{device_id}:*"
        count   = 0
        async for key in self.redis.scan_iter(match=pattern, count=50):
            await self.redis.delete(key)
            count += 1
        logger.info(
            "debounce_cleared_for_device",
            device_id=device_id[:8],
            keys_cleared=count,
        )
        return count

    def _make_key(
        self,
        device_id:         str,
        notification_type: NotificationType,
        lat:               float | None,
        lon:               float | None,
    ) -> str:
        geo = _spatial_key(lat, lon)
        return f"{DEBOUNCE_PREFIX}{device_id}:{notification_type.value}:{geo}"

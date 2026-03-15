"""
NotificationSuppressor — additional suppression rules beyond debounce.

Rules applied in order:
1. Quiet hours — if the device has quiet hours enabled and it's within them,
   MEDIUM and LOW urgency notifications are suppressed.
   CRITICAL and HIGH always fire regardless of quiet hours.
2. Navigation state — ROUTE_SAFETY_DEGRADED and HAZARD_CONFIRMED_AHEAD are
   suppressed if the device is not currently navigating.
3. Duplicate channel suppression — if a notification was already delivered
   via WebSocket in the last 5 seconds, suppress redundant FCM fallback.
"""
from __future__ import annotations

import hashlib
import structlog
from redis.asyncio import Redis

from app.notifications.types import (
    NotificationType, NotificationUrgency, NotificationPayload,
)

logger = structlog.get_logger(__name__)

DELIVERED_PREFIX = "safecycle:delivered:"
DELIVERED_TTL_S  = 5    # suppress FCM if WS delivered within 5 s

# Notification types that only make sense during active navigation
_NAV_ONLY_TYPES = frozenset({
    NotificationType.ROUTE_SAFETY_DEGRADED,
    NotificationType.HAZARD_CONFIRMED_AHEAD,
})


class NotificationSuppressor:

    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    async def should_suppress(
        self,
        payload:           NotificationPayload,
        is_navigating:     bool = True,
        in_quiet_hours:    bool = False,
    ) -> tuple[bool, str]:
        """
        Returns (should_suppress: bool, reason: str).
        Evaluates all suppression rules in order.
        """
        # ── Rule 1: Quiet hours ──────────────────────────────────────────────
        if in_quiet_hours and payload.urgency in (
            NotificationUrgency.MEDIUM, NotificationUrgency.LOW
        ):
            return True, "quiet_hours"

        # ── Rule 2: Navigation state ─────────────────────────────────────────
        if payload.type in _NAV_ONLY_TYPES and not is_navigating:
            return True, "device_not_navigating"

        # ── Rule 3: Already delivered via faster channel ─────────────────────
        if await self._already_delivered(payload):
            return True, "already_delivered_via_ws"

        return False, ""

    async def record_delivered(
        self,
        notification_id: str,
        device_id:       str,
    ) -> None:
        """
        Records that a notification was successfully delivered via WebSocket.
        Prevents redundant FCM delivery for the same event within 5 seconds.
        """
        key = f"{DELIVERED_PREFIX}{device_id}:{notification_id}"
        await self.redis.setex(key, DELIVERED_TTL_S, "1")

    async def _already_delivered(self, payload: NotificationPayload) -> bool:
        """Checks if this exact notification was already delivered via WS."""
        nid = _make_notification_id(payload)
        key = f"{DELIVERED_PREFIX}{payload.device_id}:{nid}"
        return bool(await self.redis.exists(key))


def _make_notification_id(payload: NotificationPayload) -> str:
    """
    Deterministic ID for a notification event.
    Same event → same ID regardless of which channel delivers it.
    Used to suppress duplicate cross-channel delivery.
    """
    lat_part = f"{payload.latitude:.3f}" if payload.latitude is not None else "x"
    lon_part = f"{payload.longitude:.3f}" if payload.longitude is not None else "x"
    raw = (
        f"{payload.type.value}:{payload.device_id}:"
        f"{payload.route_id}:{lat_part}:{lon_part}"
    )
    return hashlib.sha256(raw.encode()).hexdigest()[:16]

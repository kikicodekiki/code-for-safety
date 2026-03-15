"""
NotificationDispatcher — the single entry point for all notification dispatch.

Every trigger in the system calls dispatcher.dispatch(payload).
The dispatcher:
1. Checks if the notification type is enabled for this device (preferences)
2. Checks if it is within the debounce window (debouncer)
3. Checks suppression rules (suppressor: quiet hours, nav state, duplicate WS)
4. Attempts delivery via each required channel in priority order
5. Records successful delivery and sets the debounce window
6. Writes to the notification audit log (async, fire-and-forget)

The dispatcher never raises — it catches all errors per channel.
A failed FCM send does not prevent a WebSocket send from being attempted.
"""
from __future__ import annotations

import asyncio
import uuid
import structlog
from redis.asyncio import Redis

from app.notifications.types import (
    NotificationPayload, NotificationResult,
    NotificationChannel, REQUIRED_CHANNELS,
)
from app.notifications.channels import fcm as fcm_channel
from app.notifications.channels import websocket as ws_channel
from app.notifications.channels import log as log_channel
from app.notifications.rules.debounce import NotificationDebouncer
from app.notifications.rules.preferences import NotificationPreferencesManager
from app.notifications.rules.suppression import NotificationSuppressor, _make_notification_id

logger = structlog.get_logger(__name__)


class NotificationDispatcher:
    """
    Central dispatcher for all notification delivery.
    Instantiated once at app startup and injected into triggers.
    """

    def __init__(
        self,
        redis:              Redis,
        connection_manager=None,  # GPSConnectionManager — injected to break circular import
    ) -> None:
        self.debouncer    = NotificationDebouncer(redis)
        self.preferences  = NotificationPreferencesManager(redis)
        self.suppressor   = NotificationSuppressor(redis)
        self.connection_manager = connection_manager

    async def dispatch(
        self,
        payload:           NotificationPayload,
        is_navigating:     bool = True,
        device_local_hour: int | None = None,
    ) -> NotificationResult:
        """
        Main dispatch entry point. Returns a NotificationResult.
        Never raises — all errors are caught and reflected in the result.
        """
        # ── Gate 1: Preferences ──────────────────────────────────────────────
        enabled = await self.preferences.is_enabled(
            payload.device_id, payload.type
        )
        if not enabled:
            logger.debug(
                "notification_suppressed_preference",
                type=payload.type.value,
                device_id=payload.device_id[:8],
            )
            return NotificationResult(sent=False, channels=[], suppressed=True, reason="preference_disabled")

        # ── Gate 2: Debounce ─────────────────────────────────────────────────
        debounced = await self.debouncer.is_debounced(
            payload.device_id,
            payload.type,
            payload.latitude,
            payload.longitude,
        )
        if debounced:
            return NotificationResult(sent=False, channels=[], debounced=True, reason="debounce_window")

        # ── Gate 3: Suppression rules ────────────────────────────────────────
        in_quiet_hours = False
        if device_local_hour is not None:
            in_quiet_hours = await self.preferences.is_in_quiet_hours(
                payload.device_id, device_local_hour
            )
        suppressed, reason = await self.suppressor.should_suppress(
            payload,
            is_navigating=is_navigating,
            in_quiet_hours=in_quiet_hours,
        )
        if suppressed:
            logger.debug(
                "notification_suppressed",
                type=payload.type.value,
                reason=reason,
                device_id=payload.device_id[:8],
            )
            return NotificationResult(sent=False, channels=[], suppressed=True, reason=reason)

        # ── Dispatch to required channels ────────────────────────────────────
        channels       = REQUIRED_CHANNELS[payload.type]
        sent_channels: list[NotificationChannel] = []
        any_success    = False
        notification_id = _make_notification_id(payload)

        for channel in channels:
            success = await self._dispatch_to_channel(channel, payload, notification_id)
            if success:
                sent_channels.append(channel)
                any_success = True

                if channel == NotificationChannel.WEBSOCKET:
                    # Record WS delivery to suppress redundant FCM
                    await self.suppressor.record_delivered(
                        notification_id, payload.device_id
                    )

                # Set debounce on first successful delivery
                if len(sent_channels) == 1:
                    await self.debouncer.record(
                        payload.device_id,
                        payload.type,
                        payload.latitude,
                        payload.longitude,
                    )

        # ── Audit log (fire-and-forget) ──────────────────────────────────────
        asyncio.create_task(
            log_channel.write_notification_log(
                payload=payload,
                channels_sent=sent_channels,
                suppressed=False,
                debounced=False,
            )
        )

        logger.info(
            "notification_dispatched",
            type=payload.type.value,
            urgency=payload.urgency.value,
            device_id=payload.device_id[:8],
            channels_attempted=len(channels),
            channels_succeeded=len(sent_channels),
        )

        return NotificationResult(
            sent=any_success,
            channels=sent_channels,
            notification_id=notification_id,
        )

    async def _dispatch_to_channel(
        self,
        channel:         NotificationChannel,
        payload:         NotificationPayload,
        notification_id: str,
    ) -> bool:
        """Dispatches to one channel. Returns True on success."""
        try:
            if channel == NotificationChannel.WEBSOCKET:
                return await ws_channel.send_via_websocket(
                    payload, self.connection_manager
                )
            elif channel == NotificationChannel.FCM:
                if not payload.device_id:
                    return False
                return await fcm_channel.send_via_fcm(
                    token=payload.device_id,
                    title=payload.title,
                    body=payload.body,
                    data={
                        "type":     payload.type.value,
                        "urgency":  payload.urgency.value,
                        "sound":    "1" if payload.sound else "0",
                        "latitude":  str(payload.latitude or ""),
                        "longitude": str(payload.longitude or ""),
                        **{k: str(v) for k, v in payload.data.items()},
                    },
                    priority=(
                        "high"
                        if payload.sound
                        else "normal"
                    ),
                )
            elif channel == NotificationChannel.LOCAL_PUSH:
                # LOCAL_PUSH is handled entirely on the mobile side.
                # The background GPS task fires the local notification
                # independently. Backend marks it as delegated.
                return True

        except Exception as exc:
            logger.error(
                "channel_dispatch_error",
                channel=channel.value,
                type=payload.type.value,
                error=str(exc),
            )
        return False

    async def broadcast_to_nearby_devices(
        self,
        payload: NotificationPayload,
        tokens:  list[str],
    ) -> int:
        """
        Broadcasts a notification to multiple nearby devices via FCM multicast.
        Used for HAZARD_NEARBY events triggered by a new report.
        Each device gets its own debounce + preference check first.
        Returns the number of devices successfully notified.
        """
        eligible_tokens: list[str] = []

        for token in tokens:
            debounced = await self.debouncer.is_debounced(
                token, payload.type, payload.latitude, payload.longitude
            )
            enabled = await self.preferences.is_enabled(token, payload.type)
            if not debounced and enabled:
                eligible_tokens.append(token)

        if not eligible_tokens:
            return 0

        sent = await fcm_channel.send_via_fcm_multicast(
            tokens=eligible_tokens,
            title=payload.title,
            body=payload.body,
            data={
                "type":    payload.type.value,
                "urgency": payload.urgency.value,
                **{k: str(v) for k, v in payload.data.items()},
            },
            priority="high" if payload.sound else "normal",
        )

        for token in eligible_tokens:
            await self.debouncer.record(
                token, payload.type, payload.latitude, payload.longitude
            )

        return sent

"""
FCM notification channel.

Thin wrapper over the existing NotificationService FCM logic.
Uses the app-level singleton; lazy-initialises Firebase on first call.
"""
from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger(__name__)


async def send_via_fcm(
    token: str,
    title: str,
    body: str,
    data: dict[str, Any] | None = None,
    priority: str = "high",
) -> bool:
    """Send a single FCM message. Returns True on success."""
    try:
        from app.config import settings
        if not settings.FIREBASE_ENABLED:
            logger.debug("fcm_skipped", reason="firebase_disabled")
            return False

        from firebase_admin import messaging

        android = messaging.AndroidConfig(
            priority="high" if priority == "high" else "normal",
        )
        apns = messaging.APNSConfig(
            payload=messaging.APNSPayload(
                aps=messaging.Aps(
                    content_available=True,
                    sound="default" if priority == "high" else None,
                )
            )
        )
        msg = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            data={k: str(v) for k, v in (data or {}).items()},
            token=token,
            android=android,
            apns=apns,
        )
        messaging.send(msg)
        logger.info("fcm_sent", title=title)
        return True

    except Exception as exc:
        logger.error("fcm_send_failed", error=str(exc), title=title)
        return False


async def send_via_fcm_multicast(
    tokens: list[str],
    title: str,
    body: str,
    data: dict[str, Any] | None = None,
    priority: str = "high",
) -> int:
    """Send FCM multicast. Returns number of successful sends."""
    if not tokens:
        return 0
    try:
        from app.config import settings
        if not settings.FIREBASE_ENABLED:
            return 0

        from firebase_admin import messaging

        android = messaging.AndroidConfig(
            priority="high" if priority == "high" else "normal",
        )
        apns = messaging.APNSConfig(
            payload=messaging.APNSPayload(
                aps=messaging.Aps(
                    content_available=True,
                    sound="default" if priority == "high" else None,
                )
            )
        )
        batch_size = 500
        total_success = 0
        for i in range(0, len(tokens), batch_size):
            batch = tokens[i : i + batch_size]
            msg = messaging.MulticastMessage(
                notification=messaging.Notification(title=title, body=body),
                data={k: str(v) for k, v in (data or {}).items()},
                tokens=batch,
                android=android,
                apns=apns,
            )
            response = messaging.send_each_for_multicast(msg)
            total_success += response.success_count
            logger.info(
                "fcm_multicast_sent",
                title=title,
                success=response.success_count,
                failure=response.failure_count,
            )
        return total_success

    except Exception as exc:
        logger.error("fcm_multicast_failed", error=str(exc), title=title)
        return 0

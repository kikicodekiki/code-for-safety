"""
SafeCycle Sofia — Firebase FCM push notification service.

Handles three alert types:
  1. crossroad       — approaching an intersection (dismount advisory)
  2. awareness_zone  — near school / playground / bus stop
  3. hazard_nearby   — user-reported hazard close to cyclist
"""
from __future__ import annotations

import structlog

from app.config import settings
from app.models.schemas.common import AwarenessZoneSchema
from app.models.schemas.hazard import HazardResponse

logger = structlog.get_logger(__name__)


class NotificationService:
    """
    Wraps Firebase Admin SDK for FCM push notifications.
    Gracefully degrades when FIREBASE_ENABLED=False (e.g. in testing).
    """

    def __init__(self) -> None:
        self._firebase_app = None
        if settings.FIREBASE_ENABLED:
            try:
                import firebase_admin
                from firebase_admin import credentials
                cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
                self._firebase_app = firebase_admin.initialize_app(cred)
                logger.info("firebase_initialised")
            except Exception as exc:
                logger.warning(
                    "firebase_init_failed",
                    error=str(exc),
                    note="Push notifications disabled",
                )

    async def send_crossroad_alert(self, device_tokens: list[str]) -> None:
        """
        Notify cyclists they are approaching an intersection.
        Title: "⚠️ Intersection ahead"
        Body: "Consider dismounting for safety"
        Priority: high (wakes screen on Android)
        """
        await self._send_multicast(
            tokens=device_tokens,
            title="⚠️ Intersection ahead",
            body="Consider dismounting for safety",
            data={"alert_type": "crossroad"},
            priority="high",
        )

    async def send_awareness_zone_alert(
        self,
        device_tokens: list[str],
        zone: AwarenessZoneSchema,
    ) -> None:
        """
        Notify cyclists they are entering an awareness zone.
        Title: "👁 Awareness zone"
        Priority: normal (informational — does not wake screen)
        """
        zone_label = zone.name or zone.type.replace("_", " ").title()
        await self._send_multicast(
            tokens=device_tokens,
            title="👁 Awareness zone",
            body=f"Children may be present — {zone_label}",
            data={"alert_type": "awareness_zone", "zone_type": zone.type},
            priority="normal",
        )

    async def broadcast_hazard_nearby(
        self,
        hazard: HazardResponse,
        device_tokens: list[str],
    ) -> None:
        """
        Notify all devices in range of a newly reported hazard.
        Title: "🚨 Hazard reported nearby"
        Priority: high
        """
        hazard_label = hazard.type.value.replace("_", " ").title()
        await self._send_multicast(
            tokens=device_tokens,
            title="🚨 Hazard reported nearby",
            body=f"{hazard_label} reported on your route",
            data={
                "alert_type": "hazard_nearby",
                "hazard_type": hazard.type.value,
                "hazard_lat": str(hazard.lat),
                "hazard_lon": str(hazard.lon),
            },
            priority="high",
        )

    async def _send_multicast(
        self,
        tokens: list[str],
        title: str,
        body: str,
        data: dict[str, str],
        priority: str,
    ) -> None:
        """
        Send a multicast FCM message to a list of device tokens.
        Processes in batches of 500 (FCM limit).
        """
        if not tokens:
            return
        if not settings.FIREBASE_ENABLED or self._firebase_app is None:
            logger.debug(
                "fcm_skipped",
                reason="firebase_disabled",
                tokens_count=len(tokens),
                title=title,
            )
            return

        try:
            from firebase_admin import messaging

            # FCM allows max 500 tokens per multicast
            batch_size = 500
            for i in range(0, len(tokens), batch_size):
                batch = tokens[i : i + batch_size]
                android_config = messaging.AndroidConfig(
                    priority="high" if priority == "high" else "normal"
                )
                apns_config = messaging.APNSConfig(
                    payload=messaging.APNSPayload(
                        aps=messaging.Aps(
                            content_available=True,
                            sound="default" if priority == "high" else None,
                        )
                    )
                )
                message = messaging.MulticastMessage(
                    tokens=batch,
                    notification=messaging.Notification(title=title, body=body),
                    data=data,
                    android=android_config,
                    apns=apns_config,
                )
                response = messaging.send_each_for_multicast(message)
                logger.info(
                    "fcm_sent",
                    title=title,
                    success_count=response.success_count,
                    failure_count=response.failure_count,
                )
        except Exception as exc:
            logger.error("fcm_failed", error=str(exc), title=title)

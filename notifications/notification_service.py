from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from functools import lru_cache
from typing import Optional

import firebase_admin
from firebase_admin import credentials, messaging

import redis.asyncio as aioredis

from .models import NotificationEvent, NotificationType

log = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Cooldown TTLs (seconds)
# --------------------------------------------------------------------------

COOLDOWN: dict[NotificationType, int] = {
    NotificationType.DISMOUNT:       30,
    NotificationType.AWARENESS_ZONE: 60,
    NotificationType.HAZARD_NEARBY:  120,
    NotificationType.LIGHTS_ON:      300,
}

COOLDOWN_KEY_PREFIX = "notif:cooldown:"


# --------------------------------------------------------------------------
# Firebase initialisation (idempotent — safe to call multiple times)
# --------------------------------------------------------------------------

def init_firebase(service_account_path: str) -> None:
    """Call once at application startup."""
    if not firebase_admin._apps:
        cred = credentials.Certificate(service_account_path)
        firebase_admin.initialize_app(cred)
        log.info("Firebase Admin SDK initialised from %s", service_account_path)


# --------------------------------------------------------------------------
# Payload builders
# --------------------------------------------------------------------------

def _build_dismount_message(
    fcm_token: str,
    distance_m: float,
    node_lat: float,
    node_lon: float,
) -> messaging.Message:
    return messaging.Message(
        token=fcm_token,
        notification=messaging.Notification(
            title="⚠️ Пресичане наближава",
            body=f"Слезте от колелото след ~{int(distance_m)} м",
        ),
        data={
            "type":      NotificationType.DISMOUNT.value,
            "distance":  str(round(distance_m, 1)),
            "node_lat":  str(node_lat),
            "node_lon":  str(node_lon),
        },
        android=messaging.AndroidConfig(
            priority="high",
            notification=messaging.AndroidNotification(
                channel_id="safecycle_alerts",
                sound="default",
            ),
        ),
        apns=messaging.APNSConfig(
            payload=messaging.APNSPayload(
                aps=messaging.Aps(sound="default", badge=1),
            ),
        ),
    )


def _build_awareness_zone_message(
    fcm_token: str,
    zone_type: str,
    zone_name: str,
    distance_m: float,
) -> messaging.Message:
    icons = {
        "school":       "🏫",
        "playground":   "🛝",
        "bus_stop":     "🚌",
        "high_traffic": "🚦",
    }
    icon = icons.get(zone_type, "⚠️")

    return messaging.Message(
        token=fcm_token,
        notification=messaging.Notification(
            title=f"{icon} Внимание — {zone_name}",
            body=f"Намалете скоростта — {int(distance_m)} м напред",
        ),
        data={
            "type":       NotificationType.AWARENESS_ZONE.value,
            "zone_type":  zone_type,
            "zone_name":  zone_name,
            "distance":   str(round(distance_m, 1)),
        },
        android=messaging.AndroidConfig(
            priority="high",
            notification=messaging.AndroidNotification(
                channel_id="safecycle_alerts",
                sound="default",
            ),
        ),
    )


def _build_hazard_nearby_message(
    fcm_token: str,
    hazard_type: str,
    distance_m: float,
    description: Optional[str],
) -> messaging.Message:
    labels = {
        "rough_road":   "Неравен път",
        "dog":          "Куче",
        "traffic":      "Трафик",
        "construction": "Строителен обект",
        "closed_road":  "Затворен път",
        "other":        "Опасност",
    }
    label = labels.get(hazard_type, "Опасност")
    body  = description or f"{label} на {int(distance_m)} м напред — карайте внимателно"

    return messaging.Message(
        token=fcm_token,
        notification=messaging.Notification(
            title=f"🚧 {label} докладван",
            body=body,
        ),
        data={
            "type":         NotificationType.HAZARD_NEARBY.value,
            "hazard_type":  hazard_type,
            "distance":     str(round(distance_m, 1)),
        },
        android=messaging.AndroidConfig(
            priority="normal",
            notification=messaging.AndroidNotification(
                channel_id="safecycle_info",
            ),
        ),
    )


def _build_lights_on_message(fcm_token: str) -> messaging.Message:
    return messaging.Message(
        token=fcm_token,
        notification=messaging.Notification(
            title="💡 Включете светлините",
            body="Намалена видимост — пуснете фара и задната светлина",
        ),
        data={"type": NotificationType.LIGHTS_ON.value},
        android=messaging.AndroidConfig(
            priority="normal",
            notification=messaging.AndroidNotification(
                channel_id="safecycle_info",
            ),
        ),
    )


# --------------------------------------------------------------------------
# Service
# --------------------------------------------------------------------------

class NotificationService:
    """
    Sends FCM push notifications with per-user cooldown enforcement.
    Designed to be used by the WebSocket GPS processor and the REST layer.
    """

    def __init__(self, redis: aioredis.Redis) -> None:
        self._r = redis

    # ------------------------------------------------------------------
    # Cooldown helpers
    # ------------------------------------------------------------------

    def _cooldown_key(self, user_id: str, notif_type: NotificationType, context: str) -> str:
        return f"{COOLDOWN_KEY_PREFIX}{user_id}:{notif_type.value}:{context}"

    async def _is_on_cooldown(
        self,
        user_id: str,
        notif_type: NotificationType,
        context: str,
    ) -> bool:
        key = self._cooldown_key(user_id, notif_type, context)
        return bool(await self._r.exists(key))

    async def _set_cooldown(
        self,
        user_id: str,
        notif_type: NotificationType,
        context: str,
    ) -> None:
        key = self._cooldown_key(user_id, notif_type, context)
        ttl = COOLDOWN.get(notif_type, 60)
        await self._r.set(key, "1", ex=ttl)

    # ------------------------------------------------------------------
    # Core send (wraps synchronous firebase SDK in executor)
    # ------------------------------------------------------------------

    async def _send(self, message: messaging.Message) -> Optional[str]:
        """
        firebase_admin.messaging.send() is synchronous.
        We offload it to a thread so we don't block the event loop.
        """
        loop = asyncio.get_event_loop()
        try:
            msg_id = await loop.run_in_executor(
                None, messaging.send, message
            )
            log.debug("FCM sent: %s", msg_id)
            return msg_id
        except messaging.UnregisteredError:
            log.warning("FCM token unregistered — skipping")
        except Exception as exc:
            log.error("FCM send failed: %s", exc)
        return None

    # ------------------------------------------------------------------
    # Public notification methods (called by GPS processor)
    # ------------------------------------------------------------------

    async def send_dismount_alert(
        self,
        user_id:   str,
        fcm_token: str,
        node_id:   int,
        node_lat:  float,
        node_lon:  float,
        distance_m: float,
    ) -> Optional[NotificationEvent]:
        context = str(node_id)
        if await self._is_on_cooldown(user_id, NotificationType.DISMOUNT, context):
            return None

        msg = _build_dismount_message(fcm_token, distance_m, node_lat, node_lon)
        await self._send(msg)
        await self._set_cooldown(user_id, NotificationType.DISMOUNT, context)

        return NotificationEvent(
            notification_type=NotificationType.DISMOUNT,
            title="⚠️ Пресичане наближава",
            body=f"Слезте от колелото след ~{int(distance_m)} м",
            payload={
                "node_id":   node_id,
                "node_lat":  node_lat,
                "node_lon":  node_lon,
                "distance_m": round(distance_m, 1),
            },
        )

    async def send_awareness_zone_alert(
        self,
        user_id:    str,
        fcm_token:  str,
        zone_id:    str,
        zone_type:  str,
        zone_name:  str,
        distance_m: float,
    ) -> Optional[NotificationEvent]:
        if await self._is_on_cooldown(user_id, NotificationType.AWARENESS_ZONE, zone_id):
            return None

        msg = _build_awareness_zone_message(fcm_token, zone_type, zone_name, distance_m)
        await self._send(msg)
        await self._set_cooldown(user_id, NotificationType.AWARENESS_ZONE, zone_id)

        return NotificationEvent(
            notification_type=NotificationType.AWARENESS_ZONE,
            title=f"Внимание — {zone_name}",
            body=f"Намалете скоростта — {int(distance_m)} м напред",
            payload={
                "zone_id":   zone_id,
                "zone_type": zone_type,
                "zone_name": zone_name,
                "distance_m": round(distance_m, 1),
            },
        )

    async def send_hazard_nearby_alert(
        self,
        user_id:     str,
        fcm_token:   str,
        hazard_id:   str,
        hazard_type: str,
        distance_m:  float,
        description: Optional[str] = None,
    ) -> Optional[NotificationEvent]:
        if await self._is_on_cooldown(user_id, NotificationType.HAZARD_NEARBY, hazard_id):
            return None

        msg = _build_hazard_nearby_message(fcm_token, hazard_type, distance_m, description)
        await self._send(msg)
        await self._set_cooldown(user_id, NotificationType.HAZARD_NEARBY, hazard_id)

        return NotificationEvent(
            notification_type=NotificationType.HAZARD_NEARBY,
            title=f"🚧 {hazard_type}",
            body=description or f"Докладвана опасност на {int(distance_m)} м",
            payload={
                "hazard_id":   hazard_id,
                "hazard_type": hazard_type,
                "distance_m":  round(distance_m, 1),
            },
        )

    async def send_lights_on_alert(
        self,
        user_id:   str,
        fcm_token: str,
    ) -> Optional[NotificationEvent]:
        if await self._is_on_cooldown(user_id, NotificationType.LIGHTS_ON, "global"):
            return None

        msg = _build_lights_on_message(fcm_token)
        await self._send(msg)
        await self._set_cooldown(user_id, NotificationType.LIGHTS_ON, "global")

        return NotificationEvent(
            notification_type=NotificationType.LIGHTS_ON,
            title="💡 Включете светлините",
            body="Намалена видимост — пуснете фара и задната светлина",
            payload={},
        )
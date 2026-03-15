"""
SafeCycle Sofia — Notification type definitions.

Centralises all notification types, urgency levels, channels, and per-type
configuration used by the dispatcher and trigger modules.

These types are the contract between every part of the system that
produces or consumes notifications. Never use raw strings for
notification types — always use NotificationType enum values.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class NotificationType(str, Enum):
    CROSSROAD_DISMOUNT     = "crossroad_dismount"
    AWARENESS_ZONE_ENTER   = "awareness_zone_enter"
    HAZARD_NEARBY          = "hazard_nearby"
    ROAD_CLOSED_AHEAD      = "road_closed_ahead"
    ROUTE_SAFETY_DEGRADED  = "route_safety_degraded"
    HAZARD_CONFIRMED_AHEAD = "hazard_confirmed_ahead"
    LIGHTS_ON              = "lights_on"


class NotificationUrgency(str, Enum):
    CRITICAL = "critical"   # always fires — bypasses quiet hours, repeat vibration
    HIGH     = "high"       # sound on, strong vibration
    MEDIUM   = "medium"     # no sound, light vibration
    LOW      = "low"        # informational, easily suppressed


class NotificationChannel(str, Enum):
    WEBSOCKET  = "websocket"    # Foreground: in-app banner
    LOCAL_PUSH = "local_push"   # Background: local expo-notifications
    FCM        = "fcm"          # Killed/offline: Firebase push


# ── Debounce windows per type (seconds) ──────────────────────────────────────
DEBOUNCE_SECONDS: dict[NotificationType, int] = {
    NotificationType.CROSSROAD_DISMOUNT:     30,
    NotificationType.AWARENESS_ZONE_ENTER:   60,
    NotificationType.HAZARD_NEARBY:          45,
    NotificationType.ROAD_CLOSED_AHEAD:     120,
    NotificationType.ROUTE_SAFETY_DEGRADED: 300,
    NotificationType.HAZARD_CONFIRMED_AHEAD: 180,
    NotificationType.LIGHTS_ON:             600,   # once per 10 min max
}

# ── Sound profile per type ────────────────────────────────────────────────────
SOUND_ENABLED: dict[NotificationType, bool] = {
    NotificationType.CROSSROAD_DISMOUNT:     True,
    NotificationType.AWARENESS_ZONE_ENTER:   False,
    NotificationType.HAZARD_NEARBY:          True,
    NotificationType.ROAD_CLOSED_AHEAD:      True,
    NotificationType.ROUTE_SAFETY_DEGRADED:  False,
    NotificationType.HAZARD_CONFIRMED_AHEAD: False,
    NotificationType.LIGHTS_ON:             False,
}

# ── Urgency per type ──────────────────────────────────────────────────────────
URGENCY: dict[NotificationType, NotificationUrgency] = {
    NotificationType.CROSSROAD_DISMOUNT:     NotificationUrgency.HIGH,
    NotificationType.AWARENESS_ZONE_ENTER:   NotificationUrgency.MEDIUM,
    NotificationType.HAZARD_NEARBY:          NotificationUrgency.HIGH,
    NotificationType.ROAD_CLOSED_AHEAD:      NotificationUrgency.CRITICAL,
    NotificationType.ROUTE_SAFETY_DEGRADED:  NotificationUrgency.MEDIUM,
    NotificationType.HAZARD_CONFIRMED_AHEAD: NotificationUrgency.MEDIUM,
    NotificationType.LIGHTS_ON:             NotificationUrgency.LOW,
}

# ── Required delivery channels per type (priority order) ─────────────────────
REQUIRED_CHANNELS: dict[NotificationType, list[NotificationChannel]] = {
    NotificationType.CROSSROAD_DISMOUNT: [
        NotificationChannel.WEBSOCKET,
        NotificationChannel.LOCAL_PUSH,
    ],
    NotificationType.AWARENESS_ZONE_ENTER: [
        NotificationChannel.WEBSOCKET,
        NotificationChannel.LOCAL_PUSH,
    ],
    NotificationType.HAZARD_NEARBY: [
        NotificationChannel.WEBSOCKET,
        NotificationChannel.LOCAL_PUSH,
        NotificationChannel.FCM,
    ],
    NotificationType.ROAD_CLOSED_AHEAD: [
        NotificationChannel.FCM,
        NotificationChannel.WEBSOCKET,
        NotificationChannel.LOCAL_PUSH,
    ],
    NotificationType.ROUTE_SAFETY_DEGRADED: [
        NotificationChannel.FCM,
    ],
    NotificationType.HAZARD_CONFIRMED_AHEAD: [
        NotificationChannel.FCM,
    ],
    NotificationType.LIGHTS_ON: [
        NotificationChannel.WEBSOCKET,
        NotificationChannel.LOCAL_PUSH,
    ],
}

# ── Copy strings per type ─────────────────────────────────────────────────────
_TITLES: dict[NotificationType, str] = {
    NotificationType.CROSSROAD_DISMOUNT:     "Intersection ahead",
    NotificationType.AWARENESS_ZONE_ENTER:   "Awareness zone",
    NotificationType.HAZARD_NEARBY:          "Hazard ahead",
    NotificationType.ROAD_CLOSED_AHEAD:      "Road closed on your route",
    NotificationType.ROUTE_SAFETY_DEGRADED:  "Route safety changed",
    NotificationType.HAZARD_CONFIRMED_AHEAD: "Hazard confirmed ahead",
    NotificationType.LIGHTS_ON:             "Turn on your lights",
}

# Bulgarian TTS strings for expo-speech (bg-BG)
VOICE_TEXT: dict[NotificationType, str] = {
    NotificationType.CROSSROAD_DISMOUNT:
        "Предстои кръстовище. Помислете за слизане от колелото.",
    NotificationType.AWARENESS_ZONE_ENTER:
        "Внимание: зона с деца. Намалете скоростта.",
    NotificationType.HAZARD_NEARBY:
        "Внимание: препятствие на пътя. Карайте внимателно.",
    NotificationType.ROAD_CLOSED_AHEAD:
        "Маршрутът ви е затворен. Препоръчваме ново маршрутизиране.",
    NotificationType.ROUTE_SAFETY_DEGRADED:
        "Безопасността на маршрута е намалена. Помислете за нов маршрут.",
    NotificationType.HAZARD_CONFIRMED_AHEAD:
        "Потвърдено препятствие по маршрута. Бъдете внимателни.",
    NotificationType.LIGHTS_ON:
        "Включете предната и задната светлина на колелото.",
}


def _build_body(ntype: NotificationType, data: dict[str, Any]) -> str:
    """Constructs the notification body string from per-type templates."""
    if ntype == NotificationType.CROSSROAD_DISMOUNT:
        dist = data.get("distance_m", "")
        return (
            f"Consider dismounting — intersection {int(dist)}m ahead"
            if dist else
            "Consider dismounting at the upcoming intersection"
        )

    if ntype == NotificationType.AWARENESS_ZONE_ENTER:
        zone_name = data.get("zone_name") or data.get("zone_type", "sensitive area")
        return f"Children may be present — {zone_name.replace('_', ' ')}"

    if ntype == NotificationType.HAZARD_NEARBY:
        htype     = data.get("hazard_type", "hazard").replace("_", " ")
        dist      = data.get("distance_m")
        sev       = data.get("severity", "")
        sev_labels = ["", "minor", "moderate", "serious", "severe", "critical"]
        sev_label = sev_labels[int(sev)] if sev and str(sev).isdigit() and int(sev) < len(sev_labels) else ""
        dist_str  = f" — {int(dist)}m ahead" if dist else ""
        prefix    = f"{sev_label.title()} " if sev_label else ""
        return f"{prefix}{htype}{dist_str}"

    if ntype == NotificationType.ROAD_CLOSED_AHEAD:
        desc = data.get("description", "")
        base = "Your route has a road closure. Rerouting recommended."
        return f"{base} {desc}".strip() if desc else base

    if ntype == NotificationType.ROUTE_SAFETY_DEGRADED:
        old = data.get("old_score", 0)
        new = data.get("new_score", 0)
        return f"Safety score dropped from {old:.0%} to {new:.0%}. Consider requesting a new route."

    if ntype == NotificationType.HAZARD_CONFIRMED_AHEAD:
        htype = data.get("hazard_type", "hazard").replace("_", " ")
        return f"Multiple cyclists confirm: {htype} ahead on your route"

    if ntype == NotificationType.LIGHTS_ON:
        sunset_time = data.get("sunset_time", "")
        if sunset_time:
            return f"Sunset at {sunset_time} — turn on your front and rear lights"
        return "Visibility is reduced — turn on your front and rear lights"

    return "Stay alert on your route"


# ── Payload and result ────────────────────────────────────────────────────────

@dataclass
class NotificationPayload:
    """
    The canonical notification payload passed between all parts of the system.
    Every notification — regardless of channel — is created as one of these.
    """
    device_id:  str
    type:       NotificationType
    title:      str
    body:       str
    urgency:    NotificationUrgency
    data:       dict[str, Any]            = field(default_factory=dict)
    sound:      bool                      = True
    channels:   list[NotificationChannel] = field(default_factory=list)
    # Optional contextual fields
    session_id: str | None                = None   # WS session if known
    route_id:   str | None                = None   # active route if relevant
    latitude:   float | None              = None   # event location
    longitude:  float | None              = None
    created_at: datetime                  = field(default_factory=lambda: datetime.utcnow())


@dataclass
class NotificationResult:
    """Result of one notification dispatch attempt."""
    sent:            bool
    channels:        list[NotificationChannel]
    suppressed:      bool = False
    debounced:       bool = False
    reason:          str  = ""
    notification_id: str  = ""


def build_payload(
    device_id:  str,
    ntype:      NotificationType,
    data:       dict[str, Any] | None = None,
    session_id: str | None = None,
    latitude:   float | None = None,
    longitude:  float | None = None,
    route_id:   str | None = None,
    # Legacy positional args kept for backward compat — title/body now auto-generated
    title:      str | None = None,
    body:       str | None = None,
) -> NotificationPayload:
    """
    Factory function that constructs a NotificationPayload with the correct
    title, body, urgency, sound profile, and channel list for each type.
    Centralises all copy so UI strings are never scattered across triggers.
    """
    _data  = data or {}
    _title = title if title is not None else _TITLES[ntype]
    _body  = body  if body  is not None else _build_body(ntype, _data)

    return NotificationPayload(
        device_id  = device_id,
        type       = ntype,
        title      = _title,
        body       = _body,
        urgency    = URGENCY[ntype],
        data       = _data,
        sound      = SOUND_ENABLED[ntype],
        channels   = list(REQUIRED_CHANNELS[ntype]),
        session_id = session_id,
        latitude   = latitude,
        longitude  = longitude,
        route_id   = route_id,
    )

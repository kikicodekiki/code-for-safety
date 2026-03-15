"""
WebSocket notification channel.

Sends a notification event to a specific session via the GPSConnectionManager.
Returns True if the session was found and the send succeeded.
"""
from __future__ import annotations

import structlog

from app.notifications.types import NotificationPayload, NotificationType

logger = structlog.get_logger(__name__)

# Maps our NotificationType to the WS event name the mobile client expects
_EVENT_NAME: dict[NotificationType, str] = {
    NotificationType.CROSSROAD_DISMOUNT:     "crossroad",
    NotificationType.AWARENESS_ZONE_ENTER:   "awareness_zone",
    NotificationType.HAZARD_NEARBY:          "hazard_nearby",
    NotificationType.ROAD_CLOSED_AHEAD:      "hazard_nearby",
    NotificationType.ROUTE_SAFETY_DEGRADED:  "hazard_nearby",
    NotificationType.HAZARD_CONFIRMED_AHEAD: "hazard_nearby",
}


async def send_via_websocket(
    payload: NotificationPayload,
    connection_manager,  # GPSConnectionManager — injected to avoid circular import
) -> bool:
    """
    Find the active WS session for payload.device_id and push the event.

    device_id here is the session_id assigned at WS connect time.
    Returns True on successful send, False if session not found or send failed.
    """
    if connection_manager is None:
        return False

    session = connection_manager.active_sessions.get(payload.device_id)
    if session is None:
        return False

    event_name = _EVENT_NAME.get(payload.type, "notification")
    message = {
        "event": event_name,
        "payload": {
            "notification_type": payload.type.value,
            "title":   payload.title,
            "body":    payload.body,
            "urgency": payload.urgency.value,
            **payload.data,
        },
    }

    try:
        await session.websocket.send_json(message)
        logger.debug(
            "ws_notification_sent",
            session_id=payload.device_id,
            ntype=payload.type.value,
        )
        return True
    except Exception as exc:
        logger.warning(
            "ws_notification_failed",
            session_id=payload.device_id,
            ntype=payload.type.value,
            error=str(exc),
        )
        return False

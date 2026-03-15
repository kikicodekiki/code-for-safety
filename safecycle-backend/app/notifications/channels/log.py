"""
Notification audit log channel.

Writes every dispatched notification (sent, suppressed, or debounced)
to the notification_log table. Falls back to structured logging if no
DB connection is provided.
"""
from __future__ import annotations

import structlog

from app.notifications.types import NotificationChannel, NotificationPayload

logger = structlog.get_logger(__name__)


async def write_notification_log(
    payload: NotificationPayload,
    channels_sent: list[NotificationChannel],
    suppressed: bool,
    debounced: bool,
    db=None,  # asyncpg connection or pool — optional
) -> None:
    entry = {
        "device_id":     payload.device_id,
        "type":          payload.type.value,
        "title":         payload.title,
        "urgency":       payload.urgency.value,
        "channels_sent": [c.value for c in channels_sent],
        "suppressed":    suppressed,
        "debounced":     debounced,
    }

    if db is not None:
        try:
            await db.execute(
                """
                INSERT INTO notification_log
                    (device_id, notification_type, title, urgency,
                     channels_sent, suppressed, debounced)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                payload.device_id,
                payload.type.value,
                payload.title,
                payload.urgency.value,
                [c.value for c in channels_sent],
                suppressed,
                debounced,
            )
            return
        except Exception as exc:
            logger.error("notification_log_db_failed", error=str(exc))

    # Fallback to structured log
    logger.info("notification_dispatched", **entry)

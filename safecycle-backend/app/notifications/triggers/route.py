"""
RouteTrigger — fires ROUTE_SAFETY_DEGRADED and HAZARD_CONFIRMED_AHEAD.

These are fired not from GPS position but from changes in the data layer:
  - ROUTE_SAFETY_DEGRADED: a new hazard has reduced a route's safety score
    by more than SCORE_DROP_THRESHOLD.
  - HAZARD_CONFIRMED_AHEAD: a hazard on the current route has been confirmed
    by a second cyclist.

Called from:
  - HazardService.submit_report() after a new report is processed
  - PATCH /hazard/{id}/confirm after a confirmation action
"""
from __future__ import annotations

import structlog

from app.notifications.types import NotificationType, build_payload
from app.notifications.dispatcher import NotificationDispatcher

logger = structlog.get_logger(__name__)

SCORE_DROP_THRESHOLD = 0.15   # Min score drop to trigger ROUTE_SAFETY_DEGRADED


class RouteTrigger:

    def __init__(self, dispatcher: NotificationDispatcher) -> None:
        self.dispatcher = dispatcher

    async def notify_safety_degraded(
        self,
        device_tokens: list[str],
        old_score:     float,
        new_score:     float,
        route_id:      str,
        hazard_type:   str = "",
        lat:           float | None = None,
        lon:           float | None = None,
    ) -> int:
        """
        Notifies all devices on the affected route that its safety score
        has dropped by more than SCORE_DROP_THRESHOLD due to a new hazard.

        Returns the count of devices successfully notified.
        """
        score_drop = old_score - new_score
        if score_drop < SCORE_DROP_THRESHOLD:
            return 0

        sent  = 0
        for token in device_tokens:
            payload = build_payload(
                device_id = token,
                ntype     = NotificationType.ROUTE_SAFETY_DEGRADED,
                data      = {
                    "old_score":   round(old_score, 3),
                    "new_score":   round(new_score, 3),
                    "score_drop":  round(score_drop, 3),
                    "hazard_type": hazard_type,
                },
                route_id  = route_id,
                latitude  = lat,
                longitude = lon,
            )
            result = await self.dispatcher.dispatch(
                payload,
                is_navigating=True,   # Only sent to active navigators
            )
            if result.sent:
                sent += 1

        logger.info(
            "route_safety_degraded_notified",
            route_id=route_id,
            score_drop=round(score_drop, 3),
            devices_notified=sent,
            devices_total=len(device_tokens),
        )
        return sent

    async def notify_hazard_confirmed(
        self,
        device_tokens: list[str],
        hazard_type:   str,
        route_id:      str,
        lat:           float | None = None,
        lon:           float | None = None,
        hazard_id:     str = "",
    ) -> int:
        """
        Notifies devices on a route that a hazard has been confirmed
        by a second cyclist report.

        Returns the count of devices successfully notified.
        """
        sent = 0
        for token in device_tokens:
            payload = build_payload(
                device_id = token,
                ntype     = NotificationType.HAZARD_CONFIRMED_AHEAD,
                data      = {
                    "hazard_type": hazard_type,
                    "hazard_id":   hazard_id,
                },
                route_id  = route_id,
                latitude  = lat,
                longitude = lon,
            )
            result = await self.dispatcher.dispatch(
                payload,
                is_navigating=True,
            )
            if result.sent:
                sent += 1

        logger.info(
            "hazard_confirmed_notified",
            route_id=route_id,
            hazard_type=hazard_type,
            devices_notified=sent,
        )
        return sent

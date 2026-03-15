"""
HazardTrigger — fires HAZARD_NEARBY and ROAD_CLOSED_AHEAD notifications.

HAZARD_NEARBY:     fired when the cyclist is within HAZARD_ALERT_RADIUS_M of
                   an active user-reported hazard.
ROAD_CLOSED_AHEAD: fired when a ROAD_CLOSED type hazard with severity >= 3
                   is on the cyclist's current route within look-ahead distance.

Called from the GPS WebSocket handler on every GPS update.
"""
from __future__ import annotations

import structlog

from app.notifications.types import NotificationType, build_payload
from app.notifications.dispatcher import NotificationDispatcher
from app.utils.geo import haversine_metres

logger = structlog.get_logger(__name__)

DEFAULT_HAZARD_RADIUS_M    = 20.0
DEFAULT_ROAD_CLOSED_SEV    = 3       # Severity threshold for ROAD_CLOSED_AHEAD
ROAD_CLOSED_HAZARD_TYPES   = {"road_closed", "closed_road"}


class HazardTrigger:

    def __init__(
        self,
        dispatcher:      NotificationDispatcher,
        hazard_radius_m: float = DEFAULT_HAZARD_RADIUS_M,
    ) -> None:
        self.dispatcher      = dispatcher
        self.hazard_radius_m = hazard_radius_m

    async def check_nearby(
        self,
        device_id:     str,
        session_id:    str,
        lat:           float,
        lon:           float,
        hazards:       list,    # list of AggregatedHazardResponse or dicts
        is_navigating: bool = True,
    ) -> bool:
        """
        Checks if any active hazard is within the alert radius.
        Fires HAZARD_NEARBY for the nearest qualifying hazard.
        Fires ROAD_CLOSED_AHEAD if the nearest hazard is a road closure
        with severity >= DEFAULT_ROAD_CLOSED_SEV.

        Returns True if any notification was dispatched.
        """
        if not hazards:
            return False

        # Find nearest hazard within radius
        nearest       = None
        nearest_dist  = float("inf")

        for hazard in hazards:
            h_lat = _get(hazard, "lat")
            h_lon = _get(hazard, "lon")
            if h_lat is None or h_lon is None:
                continue
            dist = haversine_metres(lat, lon, h_lat, h_lon)
            if dist < nearest_dist:
                nearest_dist = dist
                nearest      = hazard

        if nearest is None or nearest_dist > self.hazard_radius_m:
            return False

        hazard_type = str(_get(nearest, "hazard_type") or _get(nearest, "type") or "hazard")
        severity    = _get(nearest, "consensus_severity") or _get(nearest, "effective_severity") or _get(nearest, "severity") or 1
        description = _get(nearest, "description") or ""

        # Determine notification type
        is_road_closed = (
            hazard_type.lower().replace(" ", "_") in ROAD_CLOSED_HAZARD_TYPES
            and int(severity) >= DEFAULT_ROAD_CLOSED_SEV
        )
        ntype = NotificationType.ROAD_CLOSED_AHEAD if is_road_closed else NotificationType.HAZARD_NEARBY

        payload = build_payload(
            device_id  = session_id,
            ntype      = ntype,
            data       = {
                "hazard_type": hazard_type,
                "distance_m":  round(nearest_dist, 1),
                "severity":    severity,
                "description": description,
                "hazard_id":   str(_get(nearest, "id") or ""),
            },
            session_id = session_id,
            latitude   = lat,
            longitude  = lon,
        )

        result = await self.dispatcher.dispatch(payload, is_navigating=is_navigating)

        if result.sent:
            logger.info(
                "hazard_alert_fired",
                session_id=session_id[:8],
                ntype=ntype.value,
                hazard_type=hazard_type,
                distance_m=round(nearest_dist, 1),
                severity=severity,
            )
        return result.sent


def _get(obj, key: str):
    """Safely get an attribute from a dict or object."""
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)

"""
CrossroadTrigger — fires CROSSROAD_DISMOUNT notifications.

Called from the GPS WebSocket handler on every GPS update when the
device is actively navigating a route.

Checks the cyclist's position against all crossroad nodes on the
active route. If within CROSSROAD_ALERT_RADIUS_M, dispatches a
CROSSROAD_DISMOUNT notification.
"""
from __future__ import annotations

import structlog

from app.notifications.types import NotificationType, build_payload
from app.notifications.dispatcher import NotificationDispatcher
from app.utils.geo import haversine_metres

logger = structlog.get_logger(__name__)

# Default radius if not provided via settings
DEFAULT_CROSSROAD_RADIUS_M = 15.0


class CrossroadTrigger:

    def __init__(
        self,
        dispatcher: NotificationDispatcher,
        alert_radius_m: float = DEFAULT_CROSSROAD_RADIUS_M,
    ) -> None:
        self.dispatcher     = dispatcher
        self.alert_radius_m = alert_radius_m

    async def check(
        self,
        device_id:       str,
        session_id:      str,
        lat:             float,
        lon:             float,
        crossroad_nodes: list[dict],
        is_navigating:   bool = True,
    ) -> bool:
        """
        Checks if the cyclist is within the crossroad alert radius of any
        intersection node on the active route.

        crossroad_nodes: list of dicts with 'lat' and 'lon' keys.
        Returns True if a notification was dispatched.
        """
        if not is_navigating or not crossroad_nodes:
            return False

        nearest_dist = float("inf")
        nearest_node = None

        for node in crossroad_nodes:
            dist = haversine_metres(lat, lon, node["lat"], node["lon"])
            if dist < nearest_dist:
                nearest_dist = dist
                nearest_node = node

        if nearest_dist > self.alert_radius_m:
            return False

        payload = build_payload(
            device_id  = session_id,   # WS session is the device key
            ntype      = NotificationType.CROSSROAD_DISMOUNT,
            data       = {
                "distance_m": round(nearest_dist, 1),
                "node_lat":   nearest_node["lat"],
                "node_lon":   nearest_node["lon"],
            },
            session_id = session_id,
            latitude   = lat,
            longitude  = lon,
        )

        result = await self.dispatcher.dispatch(payload, is_navigating=True)

        if result.sent:
            logger.info(
                "crossroad_alert_fired",
                session_id=session_id[:8],
                distance_m=round(nearest_dist, 1),
            )
        return result.sent

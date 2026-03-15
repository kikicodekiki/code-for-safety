"""
ZoneTrigger — fires AWARENESS_ZONE_ENTER notifications.

Called from the GPS WebSocket handler when the cyclist enters the
proximity radius of a school, playground, bus stop, or similar
awareness zone defined in the active route.
"""
from __future__ import annotations

import structlog

from app.notifications.types import NotificationType, build_payload
from app.notifications.dispatcher import NotificationDispatcher
from app.utils.geo import haversine_metres

logger = structlog.get_logger(__name__)

DEFAULT_ZONE_RADIUS_M = 30.0


class ZoneTrigger:

    def __init__(
        self,
        dispatcher:    NotificationDispatcher,
        zone_radius_m: float = DEFAULT_ZONE_RADIUS_M,
    ) -> None:
        self.dispatcher   = dispatcher
        self.zone_radius_m = zone_radius_m

    async def check(
        self,
        device_id:      str,
        session_id:     str,
        lat:            float,
        lon:            float,
        awareness_zones: list[dict],
        is_navigating:  bool = True,
    ) -> bool:
        """
        Checks if the cyclist has entered any awareness zone.
        Each zone dict should have: center.lat, center.lon, type, name (optional).
        Alternatively accepts flat dicts with lat/lon at top level.

        Returns True if a notification was dispatched.
        """
        if not is_navigating or not awareness_zones:
            return False

        for zone in awareness_zones:
            # Support both nested (center.lat) and flat (lat) structures
            if "center" in zone:
                zone_lat = zone["center"]["lat"]
                zone_lon = zone["center"]["lon"]
            else:
                zone_lat = zone.get("lat")
                zone_lon = zone.get("lon")

            if zone_lat is None or zone_lon is None:
                continue

            # Use zone-specific radius if provided, else default
            radius = zone.get("radius_m", self.zone_radius_m)
            dist   = haversine_metres(lat, lon, zone_lat, zone_lon)

            if dist > radius:
                continue

            zone_type = zone.get("type", "")
            zone_name = zone.get("name") or zone_type

            payload = build_payload(
                device_id  = session_id,
                ntype      = NotificationType.AWARENESS_ZONE_ENTER,
                data       = {
                    "zone_type":  zone_type,
                    "zone_name":  zone_name,
                    "distance_m": round(dist, 1),
                    "zone_lat":   zone_lat,
                    "zone_lon":   zone_lon,
                },
                session_id = session_id,
                latitude   = lat,
                longitude  = lon,
            )

            result = await self.dispatcher.dispatch(payload, is_navigating=True)

            if result.sent:
                logger.info(
                    "awareness_zone_alert_fired",
                    session_id=session_id[:8],
                    zone_type=zone_type,
                    distance_m=round(dist, 1),
                )
            # Fire at most one zone notification per GPS tick
            return result.sent

        return False

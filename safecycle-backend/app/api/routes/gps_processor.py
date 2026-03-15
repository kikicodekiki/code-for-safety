from __future__ import annotations

import asyncio
import logging
from typing import Optional

from .hazard_service      import HazardService
from .models              import GPSFrame, NotificationEvent, NotificationType
from .notification_service import NotificationService
from .proximity_service   import ProximityService

log = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Ambient-light heuristic
# --------------------------------------------------------------------------
# When the phone reports speed ≥ 1 km/h but no light sensor data is
# available from the mobile app, we use a simple time-of-day proxy.
# The mobile client can override this by including an "is_dark" boolean
# in the GPS frame payload extension (handled via GPSFrame.model_extra).

LIGHTS_SPEED_THRESHOLD_KMH: float = 5.0    # ignore when stationary
LIGHTS_HOUR_START: int = 19                  # 19:00 – 07:00 → suggest lights
LIGHTS_HOUR_END:   int = 7


def _is_dark_by_hour(ts_hour: int) -> bool:
    return ts_hour >= LIGHTS_HOUR_START or ts_hour < LIGHTS_HOUR_END


# --------------------------------------------------------------------------
# GPS Processor
# --------------------------------------------------------------------------

class GPSProcessor:
    """
    Processes a single GPS frame and returns any notifications to send.
    Stateless between frames — all cooldown logic is inside the services.
    """

    def __init__(
        self,
        user_id:              str,
        fcm_token:            Optional[str],
        hazard_service:       HazardService,
        notification_service: NotificationService,
        proximity_service:    ProximityService,
    ) -> None:
        self._user_id              = user_id
        self._fcm_token            = fcm_token
        self._hazard_svc           = hazard_service
        self._notif_svc            = notification_service
        self._prox_svc             = proximity_service

    async def process(self, frame: GPSFrame) -> list[NotificationEvent]:
        """
        Main entry point.  Returns a list of NotificationEvents that the
        WebSocket handler should serialise and send back to the client.
        """

        events: list[NotificationEvent] = []
        lat, lon = frame.lat, frame.lon

        # Run the three independent checks concurrently
        crossroad_task = asyncio.create_task(
            self._check_crossroad(lat, lon)
        )
        zones_task = asyncio.create_task(
            self._check_zones(lat, lon)
        )
        hazards_task = asyncio.create_task(
            self._check_hazards(lat, lon)
        )

        crossroad_event, zone_events, hazard_events = await asyncio.gather(
            crossroad_task, zones_task, hazards_task
        )

        if crossroad_event:
            events.append(crossroad_event)
        events.extend(zone_events)
        events.extend(hazard_events)

        # Lights-on check (cheap, no I/O — no need for a task)
        lights_event = await self._check_lights(frame)
        if lights_event:
            events.append(lights_event)

        if events:
            log.debug(
                "user=%s lat=%.5f lon=%.5f → %d notification(s): %s",
                self._user_id, lat, lon, len(events),
                [e.notification_type.value for e in events],
            )

        return events

    # ------------------------------------------------------------------
    # Private checkers
    # ------------------------------------------------------------------

    async def _check_crossroad(
        self, lat: float, lon: float
    ) -> Optional[NotificationEvent]:
        hit = self._prox_svc.nearest_crossroad(lat, lon)
        if hit is None:
            return None

        if self._fcm_token:
            return await self._notif_svc.send_dismount_alert(
                user_id=self._user_id,
                fcm_token=self._fcm_token,
                node_id=hit.node_id,
                node_lat=hit.lat,
                node_lon=hit.lon,
                distance_m=hit.distance_m,
            )
        # No FCM token → build a WebSocket-only event (still useful)
        return NotificationEvent(
            notification_type=NotificationType.DISMOUNT,
            title="⚠️ Пресичане наближава",
            body=f"Слезте от колелото след ~{int(hit.distance_m)} м",
            payload={
                "node_id":    hit.node_id,
                "node_lat":   hit.lat,
                "node_lon":   hit.lon,
                "distance_m": hit.distance_m,
            },
        )

    async def _check_zones(
        self, lat: float, lon: float
    ) -> list[NotificationEvent]:
        zone_hits = self._prox_svc.zones_within_radius(lat, lon)
        events: list[NotificationEvent] = []

        for zone in zone_hits:
            if self._fcm_token:
                ev = await self._notif_svc.send_awareness_zone_alert(
                    user_id=self._user_id,
                    fcm_token=self._fcm_token,
                    zone_id=zone.zone_id,
                    zone_type=zone.zone_type.value,
                    zone_name=zone.name,
                    distance_m=zone.distance_m,
                )
            else:
                from .notification_service import COOLDOWN  # local import to avoid circular
                ev = NotificationEvent(
                    notification_type=NotificationType.AWARENESS_ZONE,
                    title=f"Внимание — {zone.name}",
                    body=f"Намалете скоростта — {int(zone.distance_m)} м напред",
                    payload={
                        "zone_id":    zone.zone_id,
                        "zone_type":  zone.zone_type.value,
                        "zone_name":  zone.name,
                        "distance_m": zone.distance_m,
                    },
                )
            if ev:
                events.append(ev)

        return events

    async def _check_hazards(
        self, lat: float, lon: float
    ) -> list[NotificationEvent]:
        # Fetch live hazards from Redis within 200 m (coarse)
        nearby_hazards = await self._hazard_svc.get_hazards_near(
            lat=lat, lon=lon, radius_km=0.2
        )
        # Fine filter: ≤ 50 m
        close_hazards = ProximityService.hazards_within_radius(
            lat, lon, nearby_hazards
        )

        events: list[NotificationEvent] = []
        for hazard in close_hazards:
            if self._fcm_token:
                ev = await self._notif_svc.send_hazard_nearby_alert(
                    user_id=self._user_id,
                    fcm_token=self._fcm_token,
                    hazard_id=hazard["hazard_id"],
                    hazard_type=hazard["hazard_type"],
                    distance_m=hazard["distance_m"],
                    description=hazard.get("description") or None,
                )
            else:
                ev = NotificationEvent(
                    notification_type=NotificationType.HAZARD_NEARBY,
                    title=f"🚧 {hazard['hazard_type']}",
                    body=f"Докладвана опасност на {int(hazard['distance_m'])} м",
                    payload=hazard,
                )
            if ev:
                events.append(ev)

        return events

    async def _check_lights(
        self, frame: GPSFrame
    ) -> Optional[NotificationEvent]:
        speed = frame.speed_kmh or 0.0
        if speed < LIGHTS_SPEED_THRESHOLD_KMH:
            return None   # stationary — skip

        ts_hour = frame.ts.hour if frame.ts else 12
        if not _is_dark_by_hour(ts_hour):
            return None

        if self._fcm_token:
            return await self._notif_svc.send_lights_on_alert(
                user_id=self._user_id,
                fcm_token=self._fcm_token,
            )
        return NotificationEvent(
            notification_type=NotificationType.LIGHTS_ON,
            title="💡 Включете светлините",
            body="Намалена видимост — пуснете фара и задната светлина",
            payload={},
        )
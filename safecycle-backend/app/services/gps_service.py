"""
SafeCycle Sofia — GPS WebSocket session manager and proximity dispatcher.

Manages all active cyclist WebSocket connections and processes GPS updates
in real time. Emits crossroad, awareness_zone, hazard_nearby, and lights_on events.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

import networkx as nx
import structlog
from fastapi import WebSocket

from app.config import Settings
from app.core.proximity.awareness import (
    awareness_debounce_ok,
    find_nearest_awareness_zone,
)
from app.core.proximity.crossroad import crossroad_debounce_ok, is_near_crossroad
from app.models.schemas.common import AwarenessZoneSchema, Coordinate
from app.models.schemas.gps import GPSUpdate
from app.models.schemas.route import RouteResponse
from app.notifications.sunset_service import SunsetService
from app.notifications.types import VOICE_TEXT, NotificationType
from app.services.hazard_service import HazardService
from app.utils.geo import haversine_metres
from app.utils.time import utc_now

logger = structlog.get_logger(__name__)


class GPSSession:
    """
    Represents one connected cyclist's WebSocket session.
    Holds current position state and the active route being navigated.
    """

    def __init__(self, websocket: WebSocket, session_id: str) -> None:
        self.websocket = websocket
        self.session_id = session_id
        self.current_position: Coordinate | None = None
        self.current_heading: float = 0.0
        self.current_speed_kmh: float = 0.0
        self.route: RouteResponse | None = None
        # Debounce timestamps — prevent alert spam near persistent hazards
        self.last_crossroad_alert: datetime | None = None
        self.last_zone_alert: datetime | None = None
        self.last_hazard_alert: datetime | None = None
        self.last_lights_alert: datetime | None = None
        self.connected_at: datetime = utc_now()


class GPSConnectionManager:
    """
    Manages all active WebSocket connections.
    Thread-safe for asyncio — single event loop, no locks needed.
    """

    def __init__(self) -> None:
        self.active_sessions: dict[str, GPSSession] = {}

    async def connect(
        self, websocket: WebSocket, session_id: str
    ) -> GPSSession:
        await websocket.accept()
        session = GPSSession(websocket, session_id)
        self.active_sessions[session_id] = session
        logger.info(
            "ws_connected",
            session_id=session_id,
            total_connections=len(self.active_sessions),
        )
        return session

    async def disconnect(self, session_id: str) -> None:
        session = self.active_sessions.pop(session_id, None)
        if session:
            logger.info(
                "ws_disconnected",
                session_id=session_id,
                total_connections=len(self.active_sessions),
            )

    async def disconnect_all(self) -> None:
        """Graceful shutdown — close all open WebSocket connections."""
        for session in list(self.active_sessions.values()):
            try:
                await session.websocket.close(code=1001)  # Going Away
            except Exception:
                pass
        self.active_sessions.clear()
        logger.info("ws_all_disconnected")

    async def broadcast_hazard_nearby(
        self,
        hazard,  # HazardResponse
        radius_m: float = 200.0,
    ) -> None:
        """
        Push a hazard_nearby event to all sessions within radius_m of the hazard.
        Called immediately after a new hazard is submitted.
        """
        for session in self.active_sessions.values():
            if session.current_position is None:
                continue
            dist = haversine_metres(
                session.current_position.lat,
                session.current_position.lon,
                hazard.lat,
                hazard.lon,
            )
            if dist <= radius_m:
                try:
                    await session.websocket.send_json({
                        "event": "hazard_nearby",
                        "payload": {
                            "hazard": hazard.model_dump(mode="json"),
                            "distance_m": round(dist, 1),
                        },
                    })
                except Exception as exc:
                    logger.warning(
                        "ws_send_failed",
                        session_id=session.session_id,
                        error=str(exc),
                    )


def _make_event(
    ntype: NotificationType,
    title: str,
    body: str,
    payload: dict,
    voice_text: str | None = None,
) -> dict:
    """
    Build a NotificationEvent dict — the wire format sent over WebSocket.
    Matches the NotificationEvent TypeScript interface in useVoiceNotifications.
    """
    return {
        "event_id":          str(uuid4()),
        "notification_type": ntype.value,
        "title":             title,
        "body":              body,
        "voice_text":        voice_text or VOICE_TEXT.get(ntype, body),
        "payload":           payload,
        "ts":                utc_now().isoformat(),
    }


def _lights_debounce_ok(last: datetime | None, now: datetime) -> bool:
    """10-minute debounce for lights reminders."""
    return last is None or (now - last) >= timedelta(minutes=10)


async def process_gps_update(
    update: GPSUpdate,
    session: GPSSession,
    graph: nx.MultiDiGraph,
    hazard_service: HazardService,
    awareness_zones: list[AwarenessZoneSchema],
    settings: Settings,
    redis,
    sunset_service: SunsetService | None = None,
) -> list[dict]:
    """
    Core GPS processing logic — called on every GPS update from a client.

    Checks (in order):
      1. Crossroad proximity → "crossroad_dismount" event (debounced 30 s)
      2. Awareness zone proximity → "awareness_zone_enter" event (debounced 30 s)
      3. Active hazard proximity → "hazard_nearby" event (debounced 30 s)
      4. Sunset / darkness check → "lights_on" event (debounced 10 min)

    Returns a (possibly empty) list of NotificationEvent dicts.
    """
    events: list[dict] = []
    now = utc_now()

    lat = update.lat
    lon = update.lon

    # ── 1. Crossroad proximity check ─────────────────────────────────────────
    if session.route and crossroad_debounce_ok(session.last_crossroad_alert, now):
        nearest_crossroad = is_near_crossroad(
            lat=lat,
            lon=lon,
            crossroad_nodes=session.route.crossroad_nodes,
            radius_m=settings.CROSSROAD_ALERT_RADIUS_M,
        )
        if nearest_crossroad:
            dist = haversine_metres(
                lat, lon, nearest_crossroad.lat, nearest_crossroad.lon
            )
            events.append(_make_event(
                ntype=NotificationType.CROSSROAD_DISMOUNT,
                title="Intersection ahead",
                body=f"Consider dismounting — intersection {int(dist)}m ahead",
                payload={
                    "distance_m": round(dist, 1),
                    "node": {
                        "lat": nearest_crossroad.lat,
                        "lon": nearest_crossroad.lon,
                    },
                },
            ))
            session.last_crossroad_alert = now
            logger.info(
                "crossroad_alert_fired",
                session_id=session.session_id,
                distance_m=round(dist, 1),
            )

    # ── 2. Awareness zone proximity check ────────────────────────────────────
    if awareness_debounce_ok(session.last_zone_alert, now):
        zone_result = find_nearest_awareness_zone(
            lat=lat,
            lon=lon,
            awareness_zones=awareness_zones,
            search_radius_m=settings.AWARENESS_ZONE_RADIUS_M,
        )
        if zone_result:
            zone, zone_dist = zone_result
            events.append(_make_event(
                ntype=NotificationType.AWARENESS_ZONE_ENTER,
                title="Awareness zone",
                body=f"Children may be present — {(zone.name or zone.type).replace('_', ' ')}",
                payload={
                    "zone_id":   zone.id,
                    "zone_type": zone.type,
                    "zone_name": zone.name,
                    "distance_m": round(zone_dist, 1),
                },
            ))
            session.last_zone_alert = now
            logger.info(
                "awareness_zone_alert_fired",
                session_id=session.session_id,
                zone_type=zone.type,
                zone_id=zone.id,
                distance_m=round(zone_dist, 1),
            )

    # ── 3. Active hazard proximity check ─────────────────────────────────────
    if awareness_debounce_ok(session.last_hazard_alert, now):
        active_hazards = await hazard_service.get_all_active(
            redis=redis,
            lat=lat,
            lon=lon,
            radius_m=settings.HAZARD_ALERT_RADIUS_M,
        )
        if active_hazards:
            nearest_hazard = active_hazards[0]  # already sorted by proximity
            h_dist = haversine_metres(lat, lon, nearest_hazard.lat, nearest_hazard.lon)
            htype  = getattr(nearest_hazard, "hazard_type", "hazard")
            events.append(_make_event(
                ntype=NotificationType.HAZARD_NEARBY,
                title="Hazard ahead",
                body=f"{str(htype).replace('_', ' ').title()} — {int(h_dist)}m ahead",
                payload={
                    "hazard":     nearest_hazard.model_dump(mode="json"),
                    "distance_m": round(h_dist, 1),
                },
            ))
            session.last_hazard_alert = now

    # ── 4. Sunset / lights check ──────────────────────────────────────────────
    if sunset_service and _lights_debounce_ok(session.last_lights_alert, now):
        try:
            if await sunset_service.is_dark(lat=lat, lon=lon):
                voice_text = await sunset_service.sunset_voice_text(lat=lat, lon=lon)
                sunset_dt  = await sunset_service.get_sunset(lat=lat, lon=lon)
                sunset_time = (
                    sunset_dt.strftime("%H:%M") if sunset_dt else ""
                )
                events.append(_make_event(
                    ntype=NotificationType.LIGHTS_ON,
                    title="Turn on your lights",
                    body=(
                        f"Sunset at {sunset_time} — turn on your front and rear lights"
                        if sunset_time else
                        "Visibility is reduced — turn on your lights"
                    ),
                    payload={"sunset_time": sunset_time},
                    voice_text=voice_text,
                ))
                session.last_lights_alert = now
                logger.info("lights_on_alert_fired", session_id=session.session_id)
        except Exception as exc:
            logger.warning("lights_check_failed", error=str(exc))

    return events

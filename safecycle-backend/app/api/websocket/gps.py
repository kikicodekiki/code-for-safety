"""
SafeCycle Sofia — WebSocket GPS endpoint.
WS /ws/gps — real-time GPS stream for active cycling navigation.

Clients send GPSUpdate JSON messages; the server responds with
proximity events (crossroad, awareness_zone, hazard_nearby).
"""
from __future__ import annotations

from uuid import uuid4

import structlog
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from redis.asyncio import Redis

from app.config import Settings
from app.dependencies import (
    get_awareness_zones,
    get_connection_manager,
    get_graph,
    get_redis,
    get_settings,
    get_sunset_service,
)
from app.notifications.sunset_service import SunsetService
from app.models.schemas.common import AwarenessZoneSchema
from app.models.schemas.gps import GPSUpdate
from app.services.gps_service import GPSConnectionManager, process_gps_update
from app.services.hazard_service import HazardService

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.websocket("/ws/gps")
async def gps_websocket(
    websocket: WebSocket,
    manager: GPSConnectionManager = Depends(get_connection_manager),
    graph=Depends(get_graph),
    awareness_zones: list[AwarenessZoneSchema] = Depends(get_awareness_zones),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
    sunset_service: SunsetService = Depends(get_sunset_service),
) -> None:
    """
    Real-time GPS WebSocket for active cycling navigation.

    ## Protocol

    **Client → Server** (send periodically while navigating):
    ```json
    {
      "lat": 42.6977,
      "lon": 23.3219,
      "heading": 270.0,
      "speed_kmh": 15.3,
      "accuracy_m": 5.0
    }
    ```

    **Server → Client** (pushed when proximity thresholds are crossed):
    ```json
    { "event": "crossroad",      "payload": { "distance_m": 12.4, "node": {...} } }
    { "event": "awareness_zone", "payload": { "zone_type": "playground", ... } }
    { "event": "hazard_nearby",  "payload": { "hazard": {...}, "distance_m": 18.0 } }
    ```

    All alerts include a 30-second debounce to prevent notification fatigue.
    """
    session_id = str(uuid4())
    session = await manager.connect(websocket, session_id)
    hazard_service = HazardService()

    # Send initial connection acknowledgement (matches useVoiceNotifications check)
    await websocket.send_json({
        "status":     "connected",
        "session_id": session_id,
        "message":    "SafeCycle GPS session established. Stay safe!",
    })

    try:
        while True:
            raw = await websocket.receive_json()

            # Validate and parse the GPS update
            try:
                update = GPSUpdate.model_validate(raw)
            except Exception as exc:
                await websocket.send_json({
                    "status": "error",
                    "detail": f"Invalid GPS update: {exc}",
                })
                continue

            # Process and compute proximity events
            events = await process_gps_update(
                update=update,
                session=session,
                graph=graph,
                hazard_service=hazard_service,
                awareness_zones=awareness_zones,
                settings=settings,
                redis=redis,
                sunset_service=sunset_service,
            )

            # Send all triggered events back to the client
            for event in events:
                await websocket.send_json(event)

    except WebSocketDisconnect:
        logger.info("ws_client_disconnected", session_id=session_id)
    except Exception as exc:
        logger.error("ws_error", session_id=session_id, error=str(exc))
    finally:
        await manager.disconnect(session_id)

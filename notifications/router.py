from __future__ import annotations

import json
import logging
from typing import Annotated, Optional, TypeAlias

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from pydantic import ValidationError

from .gps_processor        import GPSProcessor
from .hazard_service       import HazardService
from .models               import (
    GPSFrame,
    HazardReportIn,
    HazardReportOut,
    NotificationEvent,
)
from .notification_service import NotificationService
from .proximity_service    import ProximityService

log      = logging.getLogger(__name__)
router   = APIRouter(prefix="/notifications", tags=["notifications"])


# --------------------------------------------------------------------------
# Dependency helpers
# --------------------------------------------------------------------------

def get_hazard_service(request: Request) -> HazardService:
    return request.app.state.hazard_service


def get_notification_service(request: Request) -> NotificationService:
    return request.app.state.notification_service


def get_proximity_service(request: Request) -> ProximityService:
    return request.app.state.proximity_service


HazardSvc:  TypeAlias = Annotated[HazardService,       Depends(get_hazard_service)]
NotifSvc:   TypeAlias = Annotated[NotificationService,  Depends(get_notification_service)]
ProxSvc:    TypeAlias = Annotated[ProximityService,     Depends(get_proximity_service)]


# --------------------------------------------------------------------------
# REST — Hazard reports
# --------------------------------------------------------------------------

@router.post(
    "/hazard",
    response_model=HazardReportOut,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a user hazard report",
    description=(
        "Stores a geo-tagged hazard (rough road, dog, traffic, construction, "
        "closed road) in Redis with a 10-hour TTL.  The report is immediately "
        "injected into the edge-cost graph for subsequent route calculations."
    ),
)
async def post_hazard(
    report:      HazardReportIn,
    hazard_svc:  HazardSvc,
    notif_svc:   NotifSvc,
) -> HazardReportOut:
    stored = await hazard_svc.store_report(report)

    # Optionally ACK the reporter via FCM
    if report.fcm_token:
        try:
            from firebase_admin import messaging
            from firebase_admin.messaging import Message, Notification
            import asyncio

            ack_msg = Message(
                token=report.fcm_token,
                notification=Notification(
                    title="✅ Докладът е приет",
                    body="Благодарим! Докладът ви ще помогне на другите колоездачи.",
                ),
                data={"hazard_id": stored.hazard_id},
            )
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, messaging.send, ack_msg)
        except Exception as exc:
            log.warning("Reporter ACK FCM failed (non-fatal): %s", exc)

    return stored


@router.get(
    "/hazard/nearby",
    summary="Fetch active hazard reports near a coordinate",
)
async def get_hazards_nearby(
    hazard_svc: HazardSvc,
    lat:        float = Query(..., ge=-90,  le=90),
    lon:        float = Query(..., ge=-180, le=180),
    radius_km:  float = Query(2.0, ge=0.1, le=50.0),
) -> list[dict]:
    return await hazard_svc.get_hazards_near(lat, lon, radius_km)


@router.get(
    "/hazard/{hazard_id}",
    summary="Retrieve a single hazard report",
)
async def get_hazard(
    hazard_id:  str,
    hazard_svc: HazardSvc,
) -> dict:
    report = await hazard_svc.get_report(hazard_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Hazard '{hazard_id}' not found or has expired.",
        )
    return report


@router.delete(
    "/hazard/{hazard_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Retract a hazard report",
)
async def delete_hazard(
    hazard_id:  str,
    hazard_svc: HazardSvc,
) -> None:
    deleted = await hazard_svc.delete_report(hazard_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Hazard '{hazard_id}' not found or already expired.",
        )


# --------------------------------------------------------------------------
# WebSocket — GPS stream
# --------------------------------------------------------------------------

@router.websocket("/ws/gps/{user_id}")
async def websocket_gps(
    websocket:  WebSocket,
    user_id:    str,
    request:    Request,
) -> None:
    """
    Persistent WebSocket endpoint for real-time GPS tracking.

    Protocol (JSON messages)
    ------------------------
    Client → Server (every ~2 s):
        {
            "lat": 42.6977,
            "lon": 23.3219,
            "accuracy_m": 8.5,
            "bearing_deg": 135,
            "speed_kmh": 18.2,
            "route_id": "abc-123",
            "fcm_token": "<device FCM token>"
        }

    Server → Client:
        {
            "event_id": "<uuid>",
            "notification_type": "dismount" | "awareness_zone" | "hazard_nearby" | "lights_on",
            "title": "...",
            "body": "...",
            "payload": { ... },
            "ts": "<ISO-8601>"
        }

    Connection lifecycle
    --------------------
    • On connect: log and send a "connected" ack.
    • On each frame: run GPSProcessor.process() and push any events.
    • On disconnect / error: log and clean up.
    """

    await websocket.accept()
    log.info("WS connected: user=%s", user_id)

    hazard_svc  = request.app.state.hazard_service
    notif_svc   = request.app.state.notification_service
    prox_svc    = request.app.state.proximity_service

    # FCM token is sent in the *first* frame and cached for the session.
    fcm_token: Optional[str] = None
    processor: Optional[GPSProcessor] = None

    # Send connection acknowledgement
    await websocket.send_json({"status": "connected", "user_id": user_id})

    try:
        while True:
            raw = await websocket.receive_text()

            # --- Parse frame --------------------------------------------------
            try:
                data  = json.loads(raw)
                frame = GPSFrame(**data)
            except (json.JSONDecodeError, ValidationError) as exc:
                await websocket.send_json({
                    "status": "error",
                    "detail": f"Invalid GPS frame: {exc}",
                })
                continue

            # --- Initialise processor on first valid frame --------------------
            if processor is None or (data.get("fcm_token") and data["fcm_token"] != fcm_token):
                fcm_token = data.get("fcm_token") or fcm_token
                processor = GPSProcessor(
                    user_id=user_id,
                    fcm_token=fcm_token,
                    hazard_service=hazard_svc,
                    notification_service=notif_svc,
                    proximity_service=prox_svc,
                )

            # --- Process frame → get notification events ----------------------
            events: list[NotificationEvent] = await processor.process(frame)

            # --- Push events back to client -----------------------------------
            for event in events:
                await websocket.send_text(event.model_dump_json())

    except WebSocketDisconnect:
        log.info("WS disconnected: user=%s", user_id)
    except Exception as exc:
        log.exception("WS error for user=%s: %s", user_id, exc)
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except Exception:
            pass
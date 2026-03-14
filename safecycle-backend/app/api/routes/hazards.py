"""
SafeCycle Sofia — Hazard report endpoints.
POST /hazard   — submit a new crowd-sourced hazard report
GET  /hazards  — list active hazards (optionally filtered by proximity)
"""
from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Query
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.dependencies import (
    get_db,
    get_hazard_service,
    get_notification_service,
    get_redis,
    get_settings,
    get_connection_manager,
)
from app.models.schemas.hazard import (
    HazardReportCreate,
    HazardReportResponse,
    HazardResponse,
)
from app.services.gps_service import GPSConnectionManager
from app.services.hazard_service import HazardService
from app.services.notification_service import NotificationService
from app.utils.geo import is_within_bbox

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["hazards"])


@router.post(
    "/hazard",
    response_model=HazardReportResponse,
    status_code=201,
    summary="Report a cycling hazard",
    description="""
Submit a crowd-sourced hazard report at your current location.

The report is:
- **Persisted to PostgreSQL** for permanent record-keeping
- **Cached in Redis** with a 10-hour TTL — the routing engine reads from Redis
- **Broadcast via WebSocket** to nearby connected cyclists
- **Pushed via FCM** to devices within 200 m

Active reports (< 10 h old) add a dynamic penalty to nearby road edges,
causing the router to avoid those streets.
""",
)
async def report_hazard(
    report: HazardReportCreate,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    hazard_service: HazardService = Depends(get_hazard_service),
    notification_service: NotificationService = Depends(get_notification_service),
    manager: GPSConnectionManager = Depends(get_connection_manager),
    settings: Settings = Depends(get_settings),
) -> HazardReportResponse:
    # Coordinates are already validated by Pydantic Field constraints (Sofia bbox)

    response = await hazard_service.submit_report(
        report=report,
        db=db,
        redis=redis,
    )

    # Build a HazardResponse for broadcasting
    from app.models.schemas.hazard import HazardResponse
    from app.utils.time import utc_now
    hazard_broadcast = HazardResponse(
        id=response.id,
        lat=report.lat,
        lon=report.lon,
        type=report.type,
        description=report.description,
        timestamp=response.timestamp,
        age_hours=0.0,
        is_recent=True,
        is_active=True,
    )

    # Broadcast via WebSocket to nearby cyclists
    await manager.broadcast_hazard_nearby(
        hazard=hazard_broadcast,
        radius_m=200.0,
    )

    return response


@router.get(
    "/hazards",
    response_model=list[HazardResponse],
    summary="List active hazard reports",
    description="""
Returns active crowd-sourced hazard reports from Redis.

- Reports expire automatically after 10 hours.
- If `lat`/`lon` are provided, only reports within `radius_m` are returned.
- Set `active_only=false` to include recently expired reports (for analytics).
- Results are sorted freshest-first.
""",
)
async def list_hazards(
    lat: float | None = Query(
        None, ge=-90, le=90, description="Filter by proximity — your latitude"
    ),
    lon: float | None = Query(
        None, ge=-180, le=180, description="Filter by proximity — your longitude"
    ),
    radius_m: float = Query(
        500.0, gt=0, le=5000.0, description="Proximity filter radius in metres"
    ),
    active_only: bool = Query(
        True, description="If true, only return reports younger than 10 hours"
    ),
    redis: Redis = Depends(get_redis),
    hazard_service: HazardService = Depends(get_hazard_service),
) -> list[HazardResponse]:
    return await hazard_service.get_all_active(
        redis=redis,
        lat=lat,
        lon=lon,
        radius_m=radius_m,
        active_only=active_only,
    )

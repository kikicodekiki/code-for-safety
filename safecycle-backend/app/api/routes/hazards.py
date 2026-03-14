"""
Hazard API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from redis.asyncio import Redis

from app.core.hazard.validators import HazardValidationError
from app.models.enums import HazardType
from app.models.schemas.hazard_create import HazardReportCreate
from app.models.schemas.hazard_response import (
    AggregatedHazardResponse,
    HazardReportResponse,
    HazardStatsResponse,
)
from app.models.schemas.hazard_update import HazardConfirmationCreate
from app.dependencies import get_redis
from app.services.hazard_service import HazardService

router = APIRouter(tags=["hazards"])


def get_hazard_service() -> HazardService:
    return HazardService()


# ---------------------------------------------------------------------------
# POST /hazard — Submit a new report
# ---------------------------------------------------------------------------
@router.post("/hazard", response_model=HazardReportResponse, status_code=status.HTTP_201_CREATED)
async def report_hazard(
    payload: HazardReportCreate,
    redis: Redis = Depends(get_redis),
    service: HazardService = Depends(get_hazard_service),
) -> HazardReportResponse:
    try:
        return await service.submit_report(payload, redis)
    except HazardValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=[{"loc": ["body", exc.field_name], "msg": exc.message}],
        )


# ---------------------------------------------------------------------------
# GET /hazards — List active aggregated hazards
# ---------------------------------------------------------------------------
@router.get("/hazards", response_model=list[AggregatedHazardResponse])
async def list_hazards(
    lat: float | None = Query(None),
    lon: float | None = Query(None),
    radius_m: float = Query(500.0, gt=0, le=10_000),
    type: HazardType | None = Query(None),
    min_severity: int = Query(1, ge=1, le=10),
    aggregated: bool = Query(True),
    active_only: bool = Query(True),
    redis: Redis = Depends(get_redis),
    service: HazardService = Depends(get_hazard_service),
) -> list[AggregatedHazardResponse]:
    return await service.get_aggregated_hazards(
        redis=redis,
        lat=lat,
        lon=lon,
        radius_m=radius_m,
        hazard_type=type,
        min_severity=min_severity,
        active_only=active_only,
    )


# ---------------------------------------------------------------------------
# POST /hazard/{id}/confirm — Community validation
# ---------------------------------------------------------------------------
@router.post("/hazard/{report_id}/confirm", status_code=status.HTTP_204_NO_CONTENT)
async def confirm_or_dismiss_hazard(
    report_id: str,
    payload: HazardConfirmationCreate,
    redis: Redis = Depends(get_redis),
    service: HazardService = Depends(get_hazard_service),
) -> None:
    try:
        await service.confirm_hazard(report_id, payload, redis)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ---------------------------------------------------------------------------
# DELETE /hazard/{id} — Admin/system removal
# ---------------------------------------------------------------------------
@router.delete("/hazard/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_hazard(
    report_id: str,
    reason: str = Query(..., max_length=200),
    redis: Redis = Depends(get_redis),
) -> None:
    key = f"hazard:{report_id}"
    deleted = await redis.delete(key)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Hazard {report_id} not found.",
        )
    import logging
    logging.getLogger(__name__).info("Hazard %s removed. Reason: %s", report_id, reason)


# ---------------------------------------------------------------------------
# GET /hazards/stats — Demo dashboard stats
# ---------------------------------------------------------------------------
@router.get("/hazards/stats", response_model=HazardStatsResponse)
async def hazard_statistics(
    redis: Redis = Depends(get_redis),
    service: HazardService = Depends(get_hazard_service),
) -> HazardStatsResponse:
    return await service.get_statistics(redis)

"""
SafeCycle Sofia — Route endpoint.
GET /route — compute the safety-optimal cycling route between two points.
"""
from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from redis.asyncio import Redis

from app.config import Settings
from app.core.exceptions import (
    DestinationOutsideBBoxError,
    NodeNotReachableError,
    RouteNotFoundError,
)
from app.dependencies import get_redis, get_routing_service, get_settings
from app.models.schemas.route import RouteResponse
from app.services.routing_service import RoutingService
from app.utils.geo import is_within_bbox

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["routing"])


@router.get(
    "/route",
    response_model=RouteResponse,
    summary="Compute safety-optimal cycling route",
    description="""
Finds the safest cycling route between two points in Sofia using a
multi-factor safety cost function applied to the city's street graph.

The route is enriched with:
- **Sofia Open Data bike alleys** (486 verified bike paths from urbandata.sofia.bg)
- **Crossroad nodes** where the cyclist should be extra vigilant
- **Awareness zones** (kindergartens, playgrounds, bus stops) on the path
- **Safety score** (0.0–1.0) and human-readable label (Safe / Moderate / Risky)
- **Transparency flags** when default assumptions were applied due to missing OSM data
""",
)
async def get_safe_route(
    origin_lat: float = Query(..., ge=-90, le=90, description="Origin latitude"),
    origin_lon: float = Query(..., ge=-180, le=180, description="Origin longitude"),
    dest_lat: float = Query(..., ge=-90, le=90, description="Destination latitude"),
    dest_lon: float = Query(..., ge=-180, le=180, description="Destination longitude"),
    routing_service: RoutingService = Depends(get_routing_service),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> RouteResponse:
    # ── Validate coordinates within Sofia bounding box ───────────────────────
    for name, lat, lon in [
        ("Origin", origin_lat, origin_lon),
        ("Destination", dest_lat, dest_lon),
    ]:
        if not is_within_bbox(
            lat, lon,
            north=settings.SOFIA_BBOX_NORTH,
            south=settings.SOFIA_BBOX_SOUTH,
            east=settings.SOFIA_BBOX_EAST,
            west=settings.SOFIA_BBOX_WEST,
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"{name} coordinates ({lat}, {lon}) are outside the Sofia "
                    f"bounding box. SafeCycle only supports routing within Sofia, Bulgaria."
                ),
            )

    # ── Compute route ─────────────────────────────────────────────────────────
    try:
        result = await routing_service.find_route(
            origin_lat=origin_lat,
            origin_lon=origin_lon,
            dest_lat=dest_lat,
            dest_lon=dest_lon,
            redis=redis,
        )
    except NodeNotReachableError as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "location_not_on_graph",
                "detail": (
                    "Origin or destination is not reachable on the cycling graph. "
                    f"Detail: {exc}"
                ),
            },
        )
    except RouteNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "route_not_found",
                "detail": str(exc),
            },
        )

    return result

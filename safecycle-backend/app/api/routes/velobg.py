"""
SafeCycle Sofia — VeloBG API endpoints.

GET  /velobg/paths          List all usable cycling paths (from Redis cache or DB)
GET  /velobg/status         Cache and last-fetch metadata
POST /velobg/refresh        Trigger an immediate KML re-fetch (force=True bypasses cooldown)
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.config import settings

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/velobg", tags=["velobg"])


# ── Response schemas ──────────────────────────────────────────────────────────

class VeloBGPathResponse(BaseModel):
    id:                     str
    name:                   str | None
    description:            str | None
    path_type:              str
    layer_name:             str | None
    colour_hex:             str | None
    length_m:               float
    is_bidirectional:       bool
    edge_weight_multiplier: float
    geojson:                dict | None = None   # GeoJSON geometry for map display


class VeloBGPathsResponse(BaseModel):
    paths:       list[VeloBGPathResponse]
    total:       int
    source:      str       # "cache" | "database" | "memory"
    fetched_at:  datetime | None


class VeloBGStatusResponse(BaseModel):
    cache_ttl_s:  int
    total_paths:  int | None
    usable_paths: int | None
    fetched_at:   datetime | None
    scheduler_running: bool


class VeloBGRefreshResponse(BaseModel):
    success:      bool
    message:      str
    fetched_at:   datetime | None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_cache(request: Request):
    return getattr(request.app.state, "velobg_cache", None)


def _get_scheduler(request: Request):
    return getattr(request.app.state, "velobg_scheduler", None)


def _get_map_data(request: Request):
    return getattr(request.app.state, "velobg_map_data", None)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/paths", response_model=VeloBGPathsResponse)
async def get_velobg_paths(request: Request) -> VeloBGPathsResponse:
    """
    Returns all usable VeloBG cycling paths.

    Data source priority:
    1. Redis cache (fastest — pre-serialised at fetch time)
    2. In-memory map_data on app.state (set during startup)
    3. 503 if neither is available
    """
    cache = _get_cache(request)

    # 1. Try Redis cache
    if cache is not None:
        map_data = await cache.get()
        if map_data is not None:
            return VeloBGPathsResponse(
                paths=_map_data_to_responses(map_data.usable_paths),
                total=len(map_data.usable_paths),
                source="cache",
                fetched_at=map_data.fetched_at,
            )

    # 2. Try in-memory state
    map_data = _get_map_data(request)
    if map_data is not None:
        return VeloBGPathsResponse(
            paths=_map_data_to_responses(map_data.usable_paths),
            total=len(map_data.usable_paths),
            source="memory",
            fetched_at=map_data.fetched_at,
        )

    raise HTTPException(
        status_code=503,
        detail="VeloBG data not yet available. The initial fetch may still be in progress.",
    )


@router.get("/status", response_model=VeloBGStatusResponse)
async def get_velobg_status(request: Request) -> VeloBGStatusResponse:
    """Returns cache freshness and scheduler status."""
    cache     = _get_cache(request)
    scheduler = _get_scheduler(request)
    map_data  = _get_map_data(request)

    cache_ttl      = -2
    total_paths    = None
    usable_paths   = None
    fetched_at     = None

    if cache is not None:
        cache_ttl = await cache.ttl()
        cached    = await cache.get()
        if cached is not None:
            total_paths  = cached.total_paths
            usable_paths = len(cached.usable_paths)
            fetched_at   = cached.fetched_at
    elif map_data is not None:
        total_paths  = map_data.total_paths
        usable_paths = len(map_data.usable_paths)
        fetched_at   = map_data.fetched_at

    scheduler_running = (
        scheduler is not None
        and scheduler._task is not None
        and not scheduler._task.done()
    )

    return VeloBGStatusResponse(
        cache_ttl_s=cache_ttl,
        total_paths=total_paths,
        usable_paths=usable_paths,
        fetched_at=fetched_at,
        scheduler_running=scheduler_running,
    )


@router.post("/refresh", response_model=VeloBGRefreshResponse)
async def trigger_refresh(request: Request) -> VeloBGRefreshResponse:
    """
    Triggers an immediate KML re-fetch and graph re-enrichment.
    Bypasses the 1-hour rate-limit cooldown (force=True).
    """
    scheduler = _get_scheduler(request)
    if scheduler is None:
        raise HTTPException(
            status_code=503,
            detail="VeloBG scheduler is not running.",
        )

    success = await scheduler.refresh_now(force=True)

    if success:
        map_data = _get_map_data(request)
        return VeloBGRefreshResponse(
            success=True,
            message="VeloBG data refreshed successfully.",
            fetched_at=map_data.fetched_at if map_data else datetime.now(timezone.utc),
        )
    else:
        return VeloBGRefreshResponse(
            success=False,
            message="Refresh failed. Check server logs for details.",
            fetched_at=None,
        )


# ── Internal helpers ──────────────────────────────────────────────────────────

def _map_data_to_responses(paths) -> list[VeloBGPathResponse]:
    return [
        VeloBGPathResponse(
            id=p.id,
            name=p.name,
            description=p.description,
            path_type=p.path_type.value,
            layer_name=p.layer_name,
            colour_hex=p.colour_hex,
            length_m=p.length_m,
            is_bidirectional=p.is_bidirectional,
            edge_weight_multiplier=p.edge_weight_multiplier,
            geojson={
                "type": "LineString",
                "coordinates": [[c.lon, c.lat] for c in p.coordinates],
            },
        )
        for p in paths
    ]

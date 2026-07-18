"""
SafeCycle Sofia — Main API router.
Mounts all sub-routers with their prefixes.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.routes import device, hazards, health, route, velobg
from app.api.websocket import gps
from app.core.security import require_api_key

api_router = APIRouter()

# Health probes stay open: infra health checks (e.g. Railway) can't present an
# API key, and these endpoints expose no secrets.
api_router.include_router(health.router)

# Every data endpoint requires a valid API key when one is configured.
_auth = Depends(require_api_key)
api_router.include_router(route.router, dependencies=[_auth])
api_router.include_router(hazards.router, dependencies=[_auth])
api_router.include_router(device.router, dependencies=[_auth])
api_router.include_router(velobg.router, dependencies=[_auth])

# WebSocket authenticates itself in the handler (see gps_websocket).
api_router.include_router(gps.router)

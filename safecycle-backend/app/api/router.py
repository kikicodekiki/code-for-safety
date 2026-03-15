"""
SafeCycle Sofia — Main API router.
Mounts all sub-routers with their prefixes.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import air_quality, device, hazards, health, route, velobg
from app.api.websocket import gps

api_router = APIRouter()

# REST endpoints
api_router.include_router(health.router)
api_router.include_router(route.router)
api_router.include_router(hazards.router)
api_router.include_router(device.router)
api_router.include_router(velobg.router)
api_router.include_router(air_quality.router)

# WebSocket
api_router.include_router(gps.router)

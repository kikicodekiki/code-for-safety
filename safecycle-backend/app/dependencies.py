"""
SafeCycle Sofia — FastAPI dependency injectors.
All route handlers and WebSocket endpoints consume these.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated

import networkx as nx
import structlog
from fastapi import Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import HTTPConnection

from app.config import Settings, settings
from app.core.exceptions import GraphNotLoadedError
from app.data.air_quality.repository import AirQualityRepository
from app.db.session import get_async_session
from app.models.schemas.common import AwarenessZoneSchema
from app.notifications.sunset_service import SunsetService
from app.services.density_service import DensityService
from app.services.gps_service import GPSConnectionManager
from app.services.hazard_service import HazardService
from app.services.notification_service import NotificationService
from app.services.routing_service import RoutingService

logger = structlog.get_logger(__name__)

# ── Singletons (set during app lifespan) ─────────────────────────────────────
_connection_manager: GPSConnectionManager | None = None
_notification_service: NotificationService | None = None


def get_settings() -> Settings:
    return settings


async def get_db(
    session: AsyncSession = Depends(get_async_session),
) -> AsyncGenerator[AsyncSession, None]:
    yield session


async def get_redis(connection: HTTPConnection) -> Redis:
    return connection.app.state.redis


def get_graph(connection: HTTPConnection) -> nx.MultiDiGraph:
    graph = getattr(connection.app.state, "graph", None)
    if graph is None:
        raise GraphNotLoadedError(
            "The Sofia street graph is not loaded. "
            "Check server startup logs for errors."
        )
    return graph


def get_danger_nodes(connection: HTTPConnection) -> frozenset[int]:
    return getattr(connection.app.state, "danger_nodes", frozenset())


def get_awareness_zones(connection: HTTPConnection) -> list[AwarenessZoneSchema]:
    return getattr(connection.app.state, "awareness_zones", [])


def get_hazard_service() -> HazardService:
    return HazardService()


def get_notification_service() -> NotificationService:
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service


def get_connection_manager(connection: HTTPConnection) -> GPSConnectionManager:
    manager = getattr(connection.app.state, "connection_manager", None)
    if manager is None:
        raise RuntimeError("GPSConnectionManager not initialised on app state")
    return manager


def get_air_quality_repository(request: Request) -> AirQualityRepository | None:
    return getattr(request.app.state, "air_quality_repository", None)


async def get_routing_service(
    request: Request,
    graph: nx.MultiDiGraph = Depends(get_graph),
    danger_nodes: frozenset[int] = Depends(get_danger_nodes),
    awareness_zones: list[AwarenessZoneSchema] = Depends(get_awareness_zones),
    air_quality_repo: AirQualityRepository | None = Depends(get_air_quality_repository),
) -> RoutingService:
    return RoutingService(
        graph=graph,
        hazard_service=HazardService(),
        density_service=DensityService(settings),
        danger_nodes=danger_nodes,
        awareness_zones=awareness_zones,
        settings=settings,
        air_quality_repo=air_quality_repo,
    )


async def check_redis(redis: Redis) -> bool:
    try:
        return await redis.ping()
    except Exception:
        return False


async def check_database(db: AsyncSession) -> bool:
    try:
        await db.execute(__import__("sqlalchemy").text("SELECT 1"))
        return True
    except Exception:
        return False

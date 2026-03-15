"""
SafeCycle Sofia — FastAPI application factory.

Lifespan manages:
  - structlog configuration
  - Sofia OSMnx graph download/load
  - GeoJSON bike alley enrichment (urbandata.sofia.bg data)
  - Danger node set pre-computation
  - Awareness zone geometry pre-loading
  - Redis connection pool
  - Firebase Admin SDK initialisation
  - GPSConnectionManager
"""
from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from uuid import uuid4

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from redis.asyncio import Redis, from_url

from app.api.router import api_router
from app.config import settings
from app.core.exceptions import (
    DestinationOutsideBBoxError,
    GeoJSONEnrichmentError,
    GraphNotLoadedError,
    HazardValidationError,
    NodeNotReachableError,
    RouteNotFoundError,
)
from app.core.graph.enrichment import GeoJSONEnricher
from app.core.graph.loader import GraphLoader
from app.core.graph.zones import build_awareness_zone_list, build_danger_node_set
from app.data.air_quality.fetcher import AirQualityFetcher
from app.data.air_quality.repository import AirQualityRepository
from app.data.air_quality.scheduler import AirQualityScheduler
from app.data.velobg.cache import VeloBGCache
from app.data.velobg.enricher import VeloBGEnricher
from app.data.velobg.fetcher import VeloBGFetcher
from app.data.velobg.parser import VeloBGParser
from app.data.velobg.scheduler import VeloBGScheduler
from app.notifications.sunset_service import SunsetService
from app.services.gps_service import GPSConnectionManager
from app.services.notification_service import NotificationService


def _configure_logging() -> None:
    """
    Configure structlog with Python's stdlib logging as the backend.

    Using stdlib integration means:
      - structlog.stdlib.add_logger_name works correctly (logger has .name)
      - Log level filtering is handled by the stdlib root logger
      - JSON output in production; coloured console in development
    """
    import logging

    log_level = logging.DEBUG if settings.DEBUG else logging.INFO

    # Configure the stdlib root logger that structlog will write to
    logging.basicConfig(
        format="%(message)s",
        level=log_level,
    )

    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.ENVIRONMENT == "production":
        # JSON lines — one log event per line, machine-readable
        renderer = structlog.processors.JSONRenderer()
    else:
        # Human-friendly coloured output for local development
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Attach the renderer to the stdlib handler so output is formatted correctly
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    # Remove any handlers added by basicConfig, replace with our formatted one
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)


async def _load_awareness_zones_from_db(app: FastAPI) -> list[dict]:
    """
    Load awareness zones from PostgreSQL at startup.
    Returns raw dicts that are converted to AwarenessZoneSchema objects.
    Falls back to empty list if DB is unavailable (graph routing still works).
    """
    logger = structlog.get_logger(__name__)
    try:
        from sqlalchemy import text
        from app.db.session import async_session_factory

        async with async_session_factory() as session:
            result = await session.execute(
                text("SELECT id, name, type, lat, lon, radius_m, source FROM awareness_zones")
            )
            rows = result.fetchall()
            zones = [
                {
                    "id": str(row[0]),
                    "name": row[1],
                    "type": row[2],
                    "lat": row[3],
                    "lon": row[4],
                    "radius_m": row[5],
                    "source": row[6],
                }
                for row in rows
            ]
            logger.info("awareness_zones_loaded", count=len(zones))
            return zones
    except Exception as exc:
        logger.warning(
            "awareness_zones_load_failed",
            error=str(exc),
            note="Awareness zone alerts will be unavailable",
        )
        return []


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan context manager.
    Everything before `yield` runs on startup; after `yield` on shutdown.
    """
    logger = structlog.get_logger("safecycle.startup")
    _configure_logging()
    logger.info("app_startup", version=settings.APP_VERSION, env=settings.ENVIRONMENT)

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis: Redis = from_url(settings.REDIS_URL, decode_responses=True)
    app.state.redis = redis
    try:
        await redis.ping()
        logger.info("redis_connected", url=settings.REDIS_URL)
    except Exception as exc:
        logger.error("redis_connection_failed", error=str(exc))

    # ── Sunset Service ────────────────────────────────────────────────────────
    app.state.sunset_service = SunsetService(redis)
    logger.info("sunset_service_initialized")

    # ── OSMnx Graph ───────────────────────────────────────────────────────────
    t0 = time.perf_counter()
    graph = await GraphLoader.load(settings)
    load_ms = (time.perf_counter() - t0) * 1000
    logger.info("graph_loaded", nodes=graph.number_of_nodes(), edges=graph.number_of_edges(), load_ms=round(load_ms))

    # ── GeoJSON Bike Alley Enrichment ─────────────────────────────────────────
    # Enriches edges with Sofia Open Data bike alleys from urbandata.sofia.bg
    try:
        t1 = time.perf_counter()
        graph = GeoJSONEnricher.enrich(graph, settings.GEOJSON_BIKE_ALLEYS_PATH, settings)
        enrich_ms = (time.perf_counter() - t1) * 1000
        logger.info("graph_enriched", source="sofia_open_data", enrich_ms=round(enrich_ms))
    except GeoJSONEnrichmentError as exc:
        logger.warning("graph_enrichment_failed", error=str(exc), note="Routing continues without bike alley data")

    app.state.graph = graph

    # ── Awareness Zones ───────────────────────────────────────────────────────
    raw_zones = await _load_awareness_zones_from_db(app)
    from app.core.graph.zones import build_awareness_zone_list
    awareness_zones = build_awareness_zone_list(raw_zones)
    app.state.awareness_zones = awareness_zones

    # ── Danger Node Set ───────────────────────────────────────────────────────
    # Only accident_hotspot zones cause node exclusion — Rule 5
    hotspot_zones = [z for z in awareness_zones if z.type == "accident_hotspot"]
    danger_nodes = build_danger_node_set(graph, hotspot_zones)
    app.state.danger_nodes = danger_nodes
    logger.info("danger_nodes_computed", count=len(danger_nodes))

    # ── VeloBG KML Pipeline ───────────────────────────────────────────────────
    # Initial fetch + graph enrichment. Falls back to disk cache gracefully.
    velobg_fetcher   = VeloBGFetcher(settings)
    velobg_parser    = VeloBGParser()
    velobg_cache     = VeloBGCache(redis, settings)
    velobg_scheduler = VeloBGScheduler(settings, redis)

    app.state.velobg_cache     = velobg_cache
    app.state.velobg_scheduler = velobg_scheduler

    try:
        from datetime import datetime, timezone as tz
        t2 = time.perf_counter()
        kml_content, fallback_used = await velobg_fetcher.fetch(force=True)
        velobg_map_data = velobg_parser.parse(
            kml_content,
            fetched_at=datetime.now(tz.utc),
            fetch_duration=time.perf_counter() - t2,
        )
        graph = VeloBGEnricher().enrich(graph, velobg_map_data, settings)
        await velobg_cache.set(velobg_map_data)
        app.state.velobg_map_data = velobg_map_data
        velobg_ms = (time.perf_counter() - t2) * 1000
        logger.info(
            "velobg_enrichment_applied",
            total_paths=velobg_map_data.total_paths,
            usable_paths=len(velobg_map_data.usable_paths),
            fallback_used=fallback_used,
            elapsed_ms=round(velobg_ms),
        )
    except Exception as exc:
        logger.warning(
            "velobg_startup_fetch_failed",
            error=str(exc),
            note="Routing continues without VeloBG data. Scheduler will retry.",
        )
        app.state.velobg_map_data = None

    # Start the background refresh scheduler
    velobg_scheduler.start(app.state.graph)

    # ── Air Quality (sensor.community) ────────────────────────────────────────
    # Fetch initial PM2.5/PM10 data for Sofia, save to data/sofia_air_quality.json,
    # and build the in-memory spatial index used by the routing algorithm.
    aq_fetcher    = AirQualityFetcher(settings)
    aq_repository = AirQualityRepository()
    aq_scheduler  = AirQualityScheduler(settings, aq_fetcher, aq_repository)

    try:
        aq_payload = await aq_fetcher.fetch()
        aq_repository.update(aq_payload)
        logger.info(
            "air_quality_loaded",
            sensor_count=aq_repository.sensor_count,
            fetched_at=aq_repository.fetched_at,
        )
    except Exception as exc:
        logger.warning(
            "air_quality_startup_failed",
            error=str(exc),
            note="Routing continues without air quality data. Scheduler will retry.",
        )

    app.state.air_quality_repository = aq_repository
    app.state.air_quality_scheduler  = aq_scheduler
    aq_scheduler.start()

    # ── GPS Connection Manager ────────────────────────────────────────────────
    app.state.connection_manager = GPSConnectionManager()

    # ── Firebase ──────────────────────────────────────────────────────────────
    app.state.notification_service = NotificationService()

    logger.info("app_ready", version=settings.APP_VERSION)

    yield

    # ── Shutdown ──────────────────────────────────────────────────────────────
    logger.info("app_shutdown_started")
    await velobg_scheduler.stop()
    await aq_scheduler.stop()
    await app.state.connection_manager.disconnect_all()
    await redis.aclose()
    logger.info("app_shutdown_complete")


def create_app() -> FastAPI:
    """Application factory — creates and configures the FastAPI instance."""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="""
**SafeCycle Sofia** — cycling safety navigation API for Sofia, Bulgaria.

Built for the *Code for Security* hackathon theme.

## Key Features
- 🗺 **Safe routing** using Sofia Open Data bike alleys (486 verified paths)
- ⚖️ **Multi-factor safety cost** — speed, surface, road type, bike infrastructure
- 🚨 **Crowd-sourced hazards** — Waze-style reporting with Redis TTL
- 📡 **Real-time GPS** — WebSocket proximity alerts for crossroads and danger zones
- 🔔 **Push notifications** via Firebase FCM

## Data Sources
- **Graph**: OpenStreetMap via OSMnx (Sofia bbox)
- **Bike alleys**: [Sofia Open Data](https://urbandata.sofia.bg/tl/api/3) (GeoJSON, 486 features)
""",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ── Middleware (order matters — outermost first) ───────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    @app.middleware("http")
    async def request_timing_middleware(request: Request, call_next) -> Response:
        """Adds X-Process-Time header to every HTTP response."""
        t_start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - t_start) * 1000
        response.headers["X-Process-Time"] = f"{elapsed_ms:.2f}ms"
        return response

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next) -> Response:
        """Generates a UUID per request and binds it to structlog context."""
        request_id = str(uuid4())
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    # ── Exception handlers ────────────────────────────────────────────────────
    @app.exception_handler(RouteNotFoundError)
    async def route_not_found_handler(request: Request, exc: RouteNotFoundError):
        return JSONResponse(
            status_code=404,
            content={"error": "route_not_found", "detail": str(exc)},
        )

    @app.exception_handler(NodeNotReachableError)
    async def node_not_reachable_handler(request: Request, exc: NodeNotReachableError):
        return JSONResponse(
            status_code=404,
            content={"error": "location_not_on_graph", "detail": str(exc)},
        )

    @app.exception_handler(DestinationOutsideBBoxError)
    async def outside_bbox_handler(request: Request, exc: DestinationOutsideBBoxError):
        return JSONResponse(
            status_code=400,
            content={"error": "outside_service_area", "detail": str(exc)},
        )

    @app.exception_handler(GraphNotLoadedError)
    async def graph_not_loaded_handler(request: Request, exc: GraphNotLoadedError):
        return JSONResponse(
            status_code=503,
            content={"error": "graph_not_loaded", "detail": str(exc)},
        )

    @app.exception_handler(HazardValidationError)
    async def hazard_validation_handler(request: Request, exc: HazardValidationError):
        return JSONResponse(
            status_code=422,
            content={"error": "hazard_validation_failed", "detail": str(exc)},
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        """Catch-all — never expose raw Python tracebacks to clients."""
        structlog.get_logger("safecycle.error").error(
            "unhandled_exception",
            path=str(request.url.path),
            method=request.method,
            error=str(exc),
            exc_type=type(exc).__name__,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_server_error",
                "detail": "An unexpected error occurred. Please try again.",
            },
        )

    # ── Routes ────────────────────────────────────────────────────────────────
    app.include_router(api_router)

    return app


# WSGI/ASGI entry point
app = create_app()

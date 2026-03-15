from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import osmnx as ox
import redis.asyncio as aioredis
from fastapi import FastAPI

from notifications import (
    HazardService,
    NotificationService,
    ProximityService,
    init_firebase,
    router as notifications_router,
)

log = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Configuration  (use env vars / pydantic-settings in production)
# --------------------------------------------------------------------------

REDIS_URL               = os.getenv("REDIS_URL",              "redis://localhost:6379/0")
FIREBASE_SA_PATH        = os.getenv("FIREBASE_SA_PATH",       "firebase_service_account.json")
SOFIA_BBOX              = (42.62, 23.22, 42.76, 23.42)        # (south, west, north, east)
POSTGRES_DSN            = os.getenv("DATABASE_URL",           "postgresql+asyncpg://user:pass@localhost/safecycle")

# --------------------------------------------------------------------------
# Lifespan — startup / shutdown
# --------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Startup
    -------
    1. Connect Redis.
    2. Initialise Firebase Admin SDK.
    3. Download / load OSMnx graph for Sofia.
    4. Build crossroad spatial index.
    5. Load awareness zones from PostgreSQL.
    6. Build zone spatial index.

    Shutdown
    --------
    7. Close Redis connection.
    """

    # --- 1. Redis -----------------------------------------------------------
    redis_client: aioredis.Redis = await aioredis.from_url(
        REDIS_URL, decode_responses=False, max_connections=20
    )
    app.state.redis = redis_client
    log.info("Redis connected: %s", REDIS_URL)

    # --- 2. Firebase --------------------------------------------------------
    init_firebase(FIREBASE_SA_PATH)

    # --- 3. Services --------------------------------------------------------
    app.state.hazard_service       = HazardService(redis_client)
    app.state.notification_service = NotificationService(redis_client)
    app.state.proximity_service    = ProximityService()

    # --- 4. OSMnx graph + crossroad index -----------------------------------
    log.info("Loading OSMnx graph for Sofia …")
    G = ox.graph_from_bbox(
        *SOFIA_BBOX,
        network_type="bike",
        retain_all=False,
    )
    app.state.graph = G

    intersection_nodes = [
        {"node_id": n, "lat": data["y"], "lon": data["x"]}
        for n, data in G.nodes(data=True)
        if G.degree(n) >= 3
    ]
    app.state.proximity_service.build_crossroad_index(intersection_nodes)
    log.info("Crossroad index ready: %d nodes", len(intersection_nodes))

    # --- 5 & 6. Awareness zones from PostgreSQL -----------------------------
    zones = await _load_zones_from_db()
    app.state.proximity_service.build_zone_index(zones)
    log.info("Zone index ready: %d zones", len(zones))

    yield  # ← application runs here

    # --- Shutdown -----------------------------------------------------------
    await redis_client.aclose()
    log.info("Redis connection closed")


async def _load_zones_from_db() -> list[dict]:
    """
    Load school / playground / bus-stop zones from PostgreSQL.
    In a real deployment use asyncpg or SQLAlchemy async.
    Returns a flat list of dicts matching ProximityService.build_zone_index().

    Example query (PostGIS):
        SELECT zone_id, zone_type, name,
               ST_Y(geom) AS lat, ST_X(geom) AS lon, radius_m
        FROM awareness_zones
        WHERE active = TRUE;
    """

    # --- Stub: hardcoded sample zones for Sofia (replace with real DB call) ---
    return [
        {
            "zone_id":   "school-001",
            "zone_type": "school",
            "name":      "134 СУ Димчо Дебелянов",
            "lat":       42.6875,
            "lon":       23.3560,
            "radius_m":  100.0,
        },
        {
            "zone_id":   "school-002",
            "zone_type": "school",
            "name":      "ОУ Христо Смирненски",
            "lat":       42.7020,
            "lon":       23.3100,
            "radius_m":  100.0,
        },
        {
            "zone_id":   "playground-001",
            "zone_type": "playground",
            "name":      "Детска площадка, Борисова градина",
            "lat":       42.6864,
            "lon":       23.3364,
            "radius_m":   60.0,
        },
        {
            "zone_id":   "stop-001",
            "zone_type": "bus_stop",
            "name":      "Спирка НДК",
            "lat":       42.6850,
            "lon":       23.3190,
            "radius_m":   40.0,
        },
    ]


# --------------------------------------------------------------------------
# App factory
# --------------------------------------------------------------------------

def create_app() -> FastAPI:
    app = FastAPI(
        title="SafeCycle Sofia — API",
        version="0.1.0",
        description="Safe cycling route planner for Sofia",
        lifespan=lifespan,
    )

    app.include_router(notifications_router)

    # Register other routers (routing engine, etc.) here:
    # app.include_router(routing_router)

    return app


app = create_app()
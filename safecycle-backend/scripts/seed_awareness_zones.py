"""
SafeCycle Sofia — Seed awareness zones from OSM into PostgreSQL.

Queries OSMnx for kindergartens, playgrounds, and bus stops within the
Sofia bounding box, then inserts them into the awareness_zones table.

Usage:
    python scripts/seed_awareness_zones.py

Safe to run multiple times — uses INSERT ... ON CONFLICT DO NOTHING.
"""
from __future__ import annotations

import asyncio
import logging
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import osmnx as ox
import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.config import settings

logging.basicConfig(format="%(message)s", level=logging.INFO)
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(colors=False),
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger("seed_awareness_zones")

ZONE_QUERIES: list[tuple[str, dict]] = [
    ("kindergarten", {"amenity": "kindergarten"}),
    ("playground",   {"leisure": "playground"}),
    ("bus_stop",     {"highway": "bus_stop"}),
    ("bus_stop",     {"public_transport": "stop_position"}),
]


async def seed(session: AsyncSession) -> None:
    total_inserted = 0

    for zone_type, tags in ZONE_QUERIES:
        logger.info("querying_osm", zone_type=zone_type, tags=tags)
        try:
            gdf = ox.features_from_bbox(
                bbox=(
                    settings.SOFIA_BBOX_NORTH,
                    settings.SOFIA_BBOX_SOUTH,
                    settings.SOFIA_BBOX_EAST,
                    settings.SOFIA_BBOX_WEST,
                ),
                tags=tags,
            )
        except Exception as exc:
            logger.warning("osm_query_failed", zone_type=zone_type, error=str(exc))
            continue

        if gdf.empty:
            logger.info("no_features_found", zone_type=zone_type)
            continue

        inserted = 0
        for _, row in gdf.iterrows():
            geom = row.geometry
            if geom is None:
                continue

            centroid = geom.centroid if hasattr(geom, "centroid") else geom
            lat = centroid.y
            lon = centroid.x

            if not (settings.SOFIA_BBOX_SOUTH <= lat <= settings.SOFIA_BBOX_NORTH
                    and settings.SOFIA_BBOX_WEST <= lon <= settings.SOFIA_BBOX_EAST):
                continue

            name = row.get("name") or row.get("name:bg") or row.get("name:en")
            zone_id = str(uuid.uuid4())

            await session.execute(
                text("""
                    INSERT INTO awareness_zones (id, name, type, lat, lon, radius_m, source)
                    VALUES (:id, :name, :type, :lat, :lon, :radius_m, :source)
                    ON CONFLICT DO NOTHING
                """),
                {
                    "id": zone_id,
                    "name": name,
                    "type": zone_type,
                    "lat": lat,
                    "lon": lon,
                    "radius_m": 30.0,
                    "source": "osm",
                },
            )
            inserted += 1

        await session.commit()
        logger.info("zone_type_seeded", zone_type=zone_type, inserted=inserted)
        total_inserted += inserted

    await session.execute(
        text("""
            UPDATE awareness_zones
            SET buffer_geom = ST_Buffer(
                ST_SetSRID(ST_MakePoint(lon, lat), 4326)::geography,
                radius_m
            )::geometry
            WHERE buffer_geom IS NULL
        """)
    )
    await session.commit()
    logger.info("seed_complete", total_inserted=total_inserted)


async def main() -> None:
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await seed(session)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())

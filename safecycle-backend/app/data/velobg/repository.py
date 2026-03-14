"""
VeloBGRepository — persists parsed VeloBG paths to PostgreSQL.

Replaces all existing records on each refresh (truncate + insert pattern)
so the table always reflects the latest fetched state.
Geometry is stored as PostGIS LineString(4326) via raw SQL.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schemas.velobg import VeloBGMapData, VeloBGPath

logger = structlog.get_logger(__name__)


class VeloBGRepository:

    async def replace_all(
        self,
        session:  AsyncSession,
        map_data: VeloBGMapData,
    ) -> int:
        """
        Truncates the velobg_paths table and inserts all paths from map_data.

        Returns the number of rows inserted.
        """
        await session.execute(text("TRUNCATE TABLE velobg_paths"))

        inserted = 0
        for path in map_data.all_paths:
            await self._insert_path(session, path, map_data.fetched_at)
            inserted += 1

        await session.commit()

        logger.info(
            "velobg_paths_persisted",
            inserted=inserted,
            fetched_at=map_data.fetched_at.isoformat(),
        )
        return inserted

    async def _insert_path(
        self,
        session:    AsyncSession,
        path:       VeloBGPath,
        fetched_at: datetime,
    ) -> None:
        """Inserts a single VeloBGPath row, building the PostGIS geometry inline."""
        wkt = self._coordinates_to_wkt(path)

        await session.execute(
            text("""
                INSERT INTO velobg_paths (
                    id, name, description, path_type, layer_name,
                    style_id, colour_hex, length_m, is_bidirectional, is_usable,
                    edge_weight_multiplier, source_placemark_id, geom, fetched_at
                ) VALUES (
                    :id, :name, :description, :path_type, :layer_name,
                    :style_id, :colour_hex, :length_m, :is_bidirectional, :is_usable,
                    :edge_weight_multiplier, :source_placemark_id,
                    ST_GeomFromText(:wkt, 4326),
                    :fetched_at
                )
            """),
            {
                "id":                     path.id,
                "name":                   path.name,
                "description":            path.description,
                "path_type":              path.path_type.value,
                "layer_name":             path.layer_name,
                "style_id":               path.style_id,
                "colour_hex":             path.colour_hex,
                "length_m":               path.length_m,
                "is_bidirectional":       path.is_bidirectional,
                "is_usable":              path.is_usable,
                "edge_weight_multiplier": path.edge_weight_multiplier,
                "source_placemark_id":    path.source_placemark_id,
                "wkt":                    wkt,
                "fetched_at":             fetched_at,
            },
        )

    @staticmethod
    def _coordinates_to_wkt(path: VeloBGPath) -> str:
        """
        Builds a WKT LINESTRING from path coordinates.
        KML coordinates are lon,lat — PostGIS LINESTRING is also lon,lat (X,Y).
        """
        points = ", ".join(
            f"{c.lon} {c.lat}" for c in path.coordinates
        )
        return f"LINESTRING({points})"

    async def get_all_usable(self, session: AsyncSession) -> list[dict]:
        """Returns all usable (non-proposed) paths as raw dicts for the API."""
        result = await session.execute(
            text("""
                SELECT id, name, description, path_type, layer_name,
                       colour_hex, length_m, is_bidirectional,
                       edge_weight_multiplier,
                       ST_AsGeoJSON(geom)::text AS geojson,
                       fetched_at
                FROM velobg_paths
                WHERE is_usable = TRUE
                ORDER BY length_m DESC
            """)
        )
        rows = result.mappings().all()
        return [dict(r) for r in rows]

    async def count(self, session: AsyncSession) -> int:
        result = await session.execute(text("SELECT COUNT(*) FROM velobg_paths"))
        return result.scalar_one()

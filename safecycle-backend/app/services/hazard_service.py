"""
SafeCycle Sofia — Hazard service.

Manages hazard report lifecycle:
  - Submit: persist to PostgreSQL (permanent) + Redis (fast TTL path)
  - Query: read from Redis for routing; PostgreSQL for analytics
  - Penalty: compute dynamic edge penalties from active reports

Redis key format: "hazard:{uuid}"
Redis TTL: HAZARD_TTL_SECONDS (36 000 s = 10 hours)
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import networkx as nx
import structlog
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import insert

from app.config import settings
from app.models.db.hazard import HazardReport
from app.models.schemas.hazard import (
    HazardReportCreate,
    HazardReportResponse,
    HazardResponse,
)
from app.utils.geo import haversine_metres
from app.utils.time import age_hours, utc_now

logger = structlog.get_logger(__name__)

# Maximum distance (metres) between a hazard and a graph edge for the
# hazard to affect that edge's weight.
HAZARD_EDGE_SNAP_RADIUS_M: float = 50.0


class HazardService:

    # ── Submission ────────────────────────────────────────────────────────────

    async def submit_report(
        self,
        report: HazardReportCreate,
        db: AsyncSession,
        redis: Redis,
    ) -> HazardReportResponse:
        """
        Persist a hazard to PostgreSQL (permanent record) and Redis (fast path).

        Redis key: "hazard:{id}"
        Redis TTL: HAZARD_TTL_SECONDS (10 hours) — aligns with HAZARD_ACTIVE_THRESHOLD_HOURS
        """
        report_id = str(uuid.uuid4())
        now = utc_now()

        # Persist to PostgreSQL
        stmt = insert(HazardReport).values(
            id=report_id,
            lat=report.lat,
            lon=report.lon,
            type=report.type.value,
            description=report.description,
            created_at=now,
        )
        await db.execute(stmt)
        await db.commit()

        # Cache in Redis with TTL
        payload = json.dumps({
            "id": report_id,
            "lat": report.lat,
            "lon": report.lon,
            "type": report.type.value,
            "description": report.description,
            "timestamp": now.isoformat(),
        })
        await redis.setex(
            f"hazard:{report_id}",
            settings.HAZARD_TTL_SECONDS,
            payload,
        )

        logger.info(
            "hazard_reported",
            id=report_id,
            type=report.type.value,
            lat=report.lat,
            lon=report.lon,
        )
        return HazardReportResponse(id=report_id, timestamp=now)

    # ── Query ─────────────────────────────────────────────────────────────────

    async def get_all_active(
        self,
        redis: Redis,
        lat: float | None = None,
        lon: float | None = None,
        radius_m: float = 500.0,
        active_only: bool = True,
    ) -> list[HazardResponse]:
        """
        Fetch all hazard reports from Redis.

        Redis is the single source of truth for the active window.
        Reports expire automatically when the TTL fires.
        """
        keys = await redis.keys("hazard:*")
        if not keys:
            return []

        reports: list[HazardResponse] = []
        for key in keys:
            raw = await redis.get(key)
            if raw is None:
                continue  # expired between KEYS and GET — race condition safe

            try:
                data = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                logger.warning("hazard_redis_parse_error", key=key)
                continue

            timestamp = datetime.fromisoformat(data["timestamp"])
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)

            hours_old = age_hours(timestamp)

            if active_only and hours_old >= settings.HAZARD_ACTIVE_THRESHOLD_HOURS:
                continue

            # Radius filter
            if lat is not None and lon is not None:
                dist = haversine_metres(lat, lon, data["lat"], data["lon"])
                if dist > radius_m:
                    continue

            from app.models.schemas.hazard import HazardType
            reports.append(
                HazardResponse(
                    id=data["id"],
                    lat=data["lat"],
                    lon=data["lon"],
                    type=HazardType(data["type"]),
                    description=data.get("description"),
                    timestamp=timestamp,
                    age_hours=round(hours_old, 2),
                    is_recent=hours_old < settings.HAZARD_RECENT_THRESHOLD_HOURS,
                    is_active=hours_old < settings.HAZARD_ACTIVE_THRESHOLD_HOURS,
                )
            )

        # Sort freshest first
        reports.sort(key=lambda r: r.age_hours)
        return reports

    # ── Routing integration ───────────────────────────────────────────────────

    async def get_active_hazard_penalties(
        self,
        graph: nx.MultiDiGraph,
        redis: Redis,
    ) -> dict[int, float]:
        """
        Compute dynamic edge penalties from active hazard reports.

        Penalty formula (Rule 6):
            penalty = max(0.0, 2.0 - age_hours × 0.2)

        This means:
          0 h old  → +2.0 penalty (maximum, freshly reported)
          5 h old  → +1.0 penalty
          10 h old → +0.0 penalty (expired, no effect)

        The nearest graph edge to each hazard (within HAZARD_EDGE_SNAP_RADIUS_M)
        receives this penalty. The penalty is additive to the edge weight.

        Returns
        -------
        dict[int, float] — maps graph edge osmid → penalty float
        """
        active_reports = await self.get_all_active(redis)
        if not active_reports:
            return {}

        penalties: dict[int, float] = {}

        for report in active_reports:
            penalty = max(0.0, 2.0 - report.age_hours * 0.2)
            if penalty <= 0.0:
                continue

            # Find the nearest graph edge to this hazard
            nearest_osmid = _find_nearest_edge_osmid(graph, report.lat, report.lon)
            if nearest_osmid is not None:
                # Take the maximum penalty if multiple hazards affect the same edge
                existing = penalties.get(nearest_osmid, 0.0)
                penalties[nearest_osmid] = max(existing, penalty)

        return penalties


def _find_nearest_edge_osmid(
    G: nx.MultiDiGraph,
    lat: float,
    lon: float,
) -> int | None:
    """
    Find the osmid of the graph edge nearest to (lat, lon).

    Uses a simple O(E) scan — acceptable for Sofia's graph size.
    Returns None if no edge is within HAZARD_EDGE_SNAP_RADIUS_M.
    """
    best_osmid: int | None = None
    best_dist = HAZARD_EDGE_SNAP_RADIUS_M

    for u, v, data in G.edges(data=True):
        u_data = G.nodes[u]
        v_data = G.nodes[v]

        # Use edge midpoint as proximity proxy
        mid_lat = (u_data["y"] + v_data["y"]) / 2
        mid_lon = (u_data["x"] + v_data["x"]) / 2
        dist = haversine_metres(lat, lon, mid_lat, mid_lon)

        if dist < best_dist:
            osmid = data.get("osmid")
            if osmid is not None:
                if isinstance(osmid, list):
                    osmid = osmid[0]
                best_dist = dist
                best_osmid = osmid

    return best_osmid

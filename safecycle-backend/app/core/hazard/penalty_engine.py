"""
HazardPenaltyEngine — computes effective routing penalties per graph edge.
Called once per route computation by the routing service.
"""
from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timezone

from redis.asyncio import Redis

from app.core.hazard.aggregation import AggregatedHazard, HazardReport, aggregate_nearby_reports
from app.core.hazard.decay import decay_factor
from app.core.hazard.severity import SEVERITY_PENALTY_MAP, apply_severity_penalty
from app.models.enums import HazardType

logger = logging.getLogger(__name__)

REDIS_HAZARD_KEY_PREFIX = "hazard:"
CLUSTER_RADIUS_M = 25.0
EDGE_SNAP_RADIUS_M = 50.0


def _utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6_371_000.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class HazardPenaltyEngine:
    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    async def compute_edge_penalties(
        self,
        graph,  # nx.MultiDiGraph
    ) -> dict[int, float]:
        """
        Returns osmid → effective_penalty. inf means edge is impassable.
        """
        raw_reports = await self._fetch_active_reports()
        if not raw_reports:
            return {}

        aggregated = aggregate_nearby_reports(raw_reports, cluster_radius_m=CLUSTER_RADIUS_M)

        edge_penalties: dict[int, float] = {}
        now = _utc_now()

        for cluster in aggregated:
            osmid = self._find_nearest_edge(graph, cluster.lat, cluster.lon)
            if osmid is None:
                continue

            age_hours = (now - cluster.most_recent_report).total_seconds() / 3600.0
            factor = decay_factor(age_hours, cluster.hazard_type)
            if factor == 0.0:
                continue

            penalty_spec = SEVERITY_PENALTY_MAP.get(
                (cluster.hazard_type, cluster.effective_severity)
            )
            if penalty_spec is None:
                continue

            if penalty_spec.exclude:
                edge_penalties[osmid] = float("inf")
            else:
                # Get base weight from graph (default 1.0 if not set)
                base_weight = self._get_base_weight(graph, osmid)
                raw_penalty = penalty_spec.additive + base_weight * (penalty_spec.multiplier - 1.0)
                edge_penalties[osmid] = raw_penalty * factor * cluster.confidence

        return edge_penalties

    async def _fetch_active_reports(self) -> list[HazardReport]:
        """Scan Redis for all hazard:* keys and deserialise."""
        reports: list[HazardReport] = []
        try:
            keys = []
            async for key in self.redis.scan_iter(f"{REDIS_HAZARD_KEY_PREFIX}*"):
                keys.append(key)

            if not keys:
                return reports

            raw_values = await self.redis.mget(*keys)
            for raw in raw_values:
                if raw is None:
                    continue
                try:
                    data = json.loads(raw)
                    reports.append(
                        HazardReport(
                            id=data["id"],
                            lat=data["lat"],
                            lon=data["lon"],
                            hazard_type=HazardType(data["type"]),
                            severity=int(data["severity"]),
                            description=data.get("description"),
                            reported_at=datetime.fromisoformat(data["timestamp"]),
                        )
                    )
                except (KeyError, ValueError) as exc:
                    logger.warning("Skipping malformed Redis hazard entry: %s", exc)
        except Exception as exc:
            logger.error("Redis fetch failed in HazardPenaltyEngine: %s", exc)

        return reports

    def _find_nearest_edge(self, graph, lat: float, lon: float) -> int | None:
        """Returns the osmid of the nearest graph edge within EDGE_SNAP_RADIUS_M."""
        try:
            import osmnx as ox
            nearest = ox.nearest_edges(graph, X=lon, Y=lat)
            # nearest is (u, v, key) — get osmid from edge data
            u, v, k = nearest
            edge_data = graph[u][v][k]
            osmid = edge_data.get("osmid")
            if osmid is None:
                return None
            # osmid may be a list; take the first
            return int(osmid[0]) if isinstance(osmid, list) else int(osmid)
        except Exception:
            return None

    def _get_base_weight(self, graph, osmid: int) -> float:
        """Retrieve the pre-computed safe_weight for an edge, defaulting to 1.0."""
        try:
            for u, v, data in graph.edges(data=True):
                edge_osmid = data.get("osmid")
                if edge_osmid is None:
                    continue
                eid = int(edge_osmid[0]) if isinstance(edge_osmid, list) else int(edge_osmid)
                if eid == osmid:
                    return float(data.get("safe_weight", 1.0))
        except Exception:
            pass
        return 1.0

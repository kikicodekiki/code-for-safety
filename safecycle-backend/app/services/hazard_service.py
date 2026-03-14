"""
HazardService — full pipeline from report submission to routing penalty application.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone

import networkx as nx
import osmnx as ox
from redis.asyncio import Redis

from app.core.hazard.aggregation import (
    AggregatedHazard,
    HazardReport,
    aggregate_nearby_reports,
)
from app.core.hazard.decay import DECAY_HORIZON, decay_factor
from app.core.hazard.severity import SEVERITY_PENALTY_MAP, apply_severity_penalty
from app.core.hazard.validators import HazardValidationError, validate_hazard_report
from app.models.enums import HazardType
from app.models.schemas.hazard_create import HazardReportCreate
from app.models.schemas.hazard_response import (
    AggregatedHazardResponse,
    HazardReportResponse,
    HazardStatsResponse,
    RoutingImpact,
)
from app.models.schemas.hazard_update import HazardConfirmationCreate

logger = logging.getLogger(__name__)

REDIS_HAZARD_PREFIX = "hazard:"
REDIS_CLUSTER_PREFIX = "cluster:"

TYPE_DISPLAY = {
    HazardType.POTHOLE: "Pothole",
    HazardType.OBSTACLE: "Obstacle",
    HazardType.DANGEROUS_TRAFFIC: "Dangerous traffic",
    HazardType.ROAD_CLOSED: "Road closed",
    HazardType.WET_SURFACE: "Wet surface",
    HazardType.OTHER: "Other",
}
TYPE_ICON = {
    HazardType.POTHOLE: "🕳",
    HazardType.OBSTACLE: "🚧",
    HazardType.DANGEROUS_TRAFFIC: "🚗",
    HazardType.ROAD_CLOSED: "🚫",
    HazardType.WET_SURFACE: "💧",
    HazardType.OTHER: "❓",
}
SEVERITY_LABELS = {
    1: "Negligible", 2: "Minor", 3: "Low", 4: "Moderate", 5: "Noticeable",
    6: "Serious", 7: "Severe", 8: "Dangerous", 9: "Critical", 10: "Emergency",
}


def _utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _confidence_label(confidence: float) -> str:
    if confidence < 0.25:
        return "Low"
    if confidence < 0.5:
        return "Medium"
    if confidence < 1.0:
        return "High"
    return "Verified"


class HazardService:

    async def submit_report(
        self,
        report: HazardReportCreate,
        redis: Redis,
    ) -> HazardReportResponse:
        # 1. Type-specific validation
        validation = validate_hazard_report(report.type, report.severity, report.description)

        now = _utc_now()
        report_id = str(uuid.uuid4())
        horizon_hours = DECAY_HORIZON[report.type]
        expires_at = now + timedelta(hours=horizon_hours)

        # 2. Persist to Redis
        payload = {
            "id": report_id,
            "lat": report.lat,
            "lon": report.lon,
            "type": report.type.value,
            "severity": report.severity,
            "description": report.description,
            "timestamp": now.isoformat(),
        }
        ttl_seconds = int(horizon_hours * 3600)
        await redis.set(
            f"{REDIS_HAZARD_PREFIX}{report_id}",
            json.dumps(payload),
            ex=ttl_seconds,
        )

        # 3. Determine routing impact
        penalty_spec = SEVERITY_PENALTY_MAP.get((report.type, report.severity))
        edge_excluded = bool(penalty_spec and penalty_spec.exclude)
        penalty_added = (
            apply_severity_penalty(1.0, penalty_spec) if penalty_spec and not edge_excluded else None
        )

        if edge_excluded:
            routing_desc = "Road segment temporarily excluded from routing"
        elif penalty_spec and penalty_spec.additive > 0:
            routing_desc = f"Routing penalty of {penalty_added:.1f} applied to this segment"
        else:
            routing_desc = "No immediate routing impact"

        routing_impact = RoutingImpact(
            affects_routing=validation.affects_routing_immediately or edge_excluded,
            edge_excluded=edge_excluded,
            penalty_added=penalty_added,
            description=routing_desc,
        )

        return HazardReportResponse(
            id=report_id,
            status="reported",
            cluster_id=None,
            severity=report.severity,
            type=report.type,
            timestamp=now,
            expires_at=expires_at,
            routing_impact=routing_impact,
            message=f"{TYPE_ICON[report.type]} {TYPE_DISPLAY[report.type]} reported — thank you!",
        )

    async def get_active_hazard_penalties(
        self,
        G: nx.MultiDiGraph,
        redis: Redis,
    ) -> dict[int, float]:
        """
        Calculates additive segment penalties based on active crowd-sourced hazards.
        Returns a map of osmid -> penalty.
        """
        raw_reports = await self._fetch_reports_from_redis(redis)
        if not raw_reports:
            return {}

        aggregated = aggregate_nearby_reports(raw_reports)
        now = _utc_now()
        penalties: dict[int, float] = {}

        for cluster in aggregated:
            age_hours = (now - cluster.most_recent_report).total_seconds() / 3600.0
            factor = decay_factor(age_hours, cluster.hazard_type)

            if factor <= 0.0:
                continue

            # Find nearest edge in the graph
            # Note: ox.nearest_edges expects (X, Y) order
            try:
                u, v, k = ox.nearest_edges(G, X=cluster.lon, Y=cluster.lat)
                edge_data = G[u][v][k]
                osmid = edge_data.get("osmid")

                if osmid is None:
                    continue

                penalty_spec = SEVERITY_PENALTY_MAP.get(
                    (cluster.hazard_type, cluster.effective_severity)
                )
                if not penalty_spec:
                    continue

                if penalty_spec.exclude:
                    # Map excluded edges to a very high penalty if we can't remove them dynamically
                    penalty = 1_000_000.0
                else:
                    # Penalty = (base_penalty + multiplier_effect) * decay * confidence
                    # We assume a base length of 1.0 for the multiplier comparison
                    raw_p = penalty_spec.additive + 1.0 * (penalty_spec.multiplier - 1.0)
                    penalty = raw_p * factor * cluster.confidence

                # If osmid is a list (OSMnx simplification), apply to all
                osmids = osmid if isinstance(osmid, list) else [osmid]
                for oid in osmids:
                    penalties[oid] = penalties.get(oid, 0.0) + penalty

            except Exception as exc:
                logger.warning("Could not map hazard %s to edge: %s", cluster.canonical_id, exc)

        return penalties

    async def get_aggregated_hazards(
        self,
        redis: Redis,
        lat: float | None = None,
        lon: float | None = None,
        radius_m: float = 500.0,
        hazard_type: HazardType | None = None,
        min_severity: int = 1,
        active_only: bool = True,
    ) -> list[AggregatedHazardResponse]:
        raw_reports = await self._fetch_reports_from_redis(redis)
        if hazard_type:
            raw_reports = [r for r in raw_reports if r.hazard_type == hazard_type]

        aggregated = aggregate_nearby_reports(raw_reports)
        now = _utc_now()
        results: list[AggregatedHazardResponse] = []

        for cluster in aggregated:
            age_hours = (now - cluster.most_recent_report).total_seconds() / 3600.0
            factor = decay_factor(age_hours, cluster.hazard_type)

            if active_only and factor == 0.0:
                continue
            if cluster.effective_severity < min_severity:
                continue
            if lat is not None and lon is not None:
                import math
                dlat = math.radians(cluster.lat - lat)
                dlon = math.radians(cluster.lon - lon)
                a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat)) * math.cos(
                    math.radians(cluster.lat)
                ) * math.sin(dlon / 2) ** 2
                dist = 6_371_000 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
                if dist > radius_m:
                    continue

            penalty_spec = SEVERITY_PENALTY_MAP.get(
                (cluster.hazard_type, cluster.effective_severity)
            )
            routing_excluded = bool(penalty_spec and penalty_spec.exclude)
            effective_penalty: float | None = None
            if penalty_spec and not routing_excluded:
                raw_p = penalty_spec.additive + 1.0 * (penalty_spec.multiplier - 1.0)
                effective_penalty = raw_p * factor * cluster.confidence

            results.append(
                AggregatedHazardResponse(
                    id=cluster.canonical_id,
                    lat=cluster.lat,
                    lon=cluster.lon,
                    hazard_type=cluster.hazard_type,
                    type_display_name=TYPE_DISPLAY[cluster.hazard_type],
                    type_icon=TYPE_ICON[cluster.hazard_type],
                    report_count=cluster.report_count,
                    consensus_severity=cluster.consensus_severity,
                    effective_severity=cluster.effective_severity,
                    severity_label=SEVERITY_LABELS.get(cluster.effective_severity, "Unknown"),
                    confidence=round(cluster.confidence, 3),
                    confidence_label=_confidence_label(cluster.confidence),
                    age_hours=round(age_hours, 3),
                    is_recent=age_hours < 1.0,
                    is_fresh=age_hours < 0.25,
                    description=cluster.description,
                    routing_excluded=routing_excluded,
                    decay_factor=round(factor, 3),
                    effective_penalty=round(effective_penalty, 3) if effective_penalty else None,
                )
            )

        results.sort(key=lambda h: h.effective_severity, reverse=True)
        return results

    async def confirm_hazard(
        self,
        report_id: str,
        payload: HazardConfirmationCreate,
        redis: Redis,
    ) -> None:
        key = f"{REDIS_HAZARD_PREFIX}{report_id}"
        raw = await redis.get(key)
        if not raw:
            raise ValueError(f"Hazard {report_id} not found or already expired.")

        data = json.loads(raw)
        hazard_lat, hazard_lon = data["lat"], data["lon"]

        # Proximity check (confirmer must be within 200m)
        import math
        dlat = math.radians(payload.lat - hazard_lat)
        dlon = math.radians(payload.lon - hazard_lon)
        a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(hazard_lat)) * math.cos(
            math.radians(payload.lat)
        ) * math.sin(dlon / 2) ** 2
        dist = 6_371_000 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        if dist > 200:
            raise ValueError(
                f"Confirmer is {dist:.0f}m from hazard. Must be within 200m."
            )

        confirmed = data.get("confirmed_count", 0)
        dismissed = data.get("dismissed_count", 0)

        if payload.action == "confirm":
            data["confirmed_count"] = confirmed + 1
            # Reset decay: update timestamp to now
            data["timestamp"] = _utc_now().isoformat()
        else:
            data["dismissed_count"] = dismissed + 1
            # If majority dismiss, remove from Redis
            if data["dismissed_count"] > data.get("confirmed_count", 0) * 2:
                await redis.delete(key)
                return

        ttl = await redis.ttl(key)
        await redis.set(key, json.dumps(data), ex=max(ttl, 1))

    async def get_statistics(self, redis: Redis) -> HazardStatsResponse:
        reports = await self._fetch_reports_from_redis(redis)
        now = _utc_now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        by_type: dict[str, int] = {}
        by_severity: dict[int, int] = {}
        excluded_count = 0

        for r in reports:
            by_type[r.hazard_type.value] = by_type.get(r.hazard_type.value, 0) + 1
            by_severity[r.severity] = by_severity.get(r.severity, 0) + 1
            spec = SEVERITY_PENALTY_MAP.get((r.hazard_type, r.severity))
            if spec and spec.exclude:
                excluded_count += 1

        reports_today = sum(
            1 for r in reports if r.reported_at >= today_start
        )
        avg_confidence = (
            sum(min(1.0, 1 / 5) for _ in reports) / len(reports) if reports else 0.0
        )

        return HazardStatsResponse(
            total_active_clusters=len(aggregate_nearby_reports(reports)),
            total_reports_today=reports_today,
            by_type=by_type,
            by_severity=by_severity,
            edges_currently_excluded=excluded_count,
            avg_confidence=round(avg_confidence, 3),
            coverage_radius_km=1.0,
        )

    async def _fetch_reports_from_redis(self, redis: Redis) -> list[HazardReport]:
        reports: list[HazardReport] = []
        try:
            keys = [k async for k in redis.scan_iter(f"{REDIS_HAZARD_PREFIX}*")]
            if not keys:
                return reports
            for raw in await redis.mget(*keys):
                if raw is None:
                    continue
                try:
                    d = json.loads(raw)
                    reports.append(
                        HazardReport(
                            id=d["id"],
                            lat=d["lat"],
                            lon=d["lon"],
                            hazard_type=HazardType(d["type"]),
                            severity=int(d["severity"]),
                            description=d.get("description"),
                            reported_at=datetime.fromisoformat(d["timestamp"]),
                        )
                    )
                except (KeyError, ValueError) as exc:
                    logger.warning("Skipping malformed Redis entry: %s", exc)
        except Exception as exc:
            logger.error("Redis read error: %s", exc)
        return reports

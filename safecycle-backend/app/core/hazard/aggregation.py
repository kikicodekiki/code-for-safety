"""
Cluster nearby same-type hazard reports into aggregated signals.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

from app.core.hazard.decay import decay_factor
from app.models.enums import HazardType


@dataclass
class HazardReport:
    id: str
    lat: float
    lon: float
    hazard_type: HazardType
    severity: int          # 1–10
    description: str | None
    reported_at: datetime


@dataclass
class AggregatedHazard:
    canonical_id: str
    lat: float
    lon: float
    hazard_type: HazardType
    report_count: int
    consensus_severity: float   # weighted average
    effective_severity: int     # rounded consensus, clamped 1–10
    confidence: float           # 0.0–1.0
    most_recent_report: datetime
    oldest_report: datetime
    description: str | None     # from the highest-severity report


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


def _now_utc() -> datetime:
    from datetime import timezone
    return datetime.now(tz=timezone.utc)


def aggregate_nearby_reports(
    reports: list[HazardReport],
    cluster_radius_m: float = 25.0,
) -> list[AggregatedHazard]:
    """
    Groups individual hazard reports into location clusters.

    Rules:
    1. Cluster by type first — different types never merge.
    2. Greedy spatial clustering: first report of each type is the cluster
       centre; subsequent reports within cluster_radius_m join it.
    3. consensus_severity = weighted avg where weight = decay_factor(age, type).
    4. confidence = min(1.0, report_count / 5).
    5. effective_severity = round(consensus_severity), clamped [1, 10].
    """
    now = _now_utc()

    # Group by type first
    by_type: dict[HazardType, list[HazardReport]] = {}
    for r in reports:
        by_type.setdefault(r.hazard_type, []).append(r)

    clusters: list[AggregatedHazard] = []

    for hazard_type, type_reports in by_type.items():
        # Greedy clustering within this type
        assigned: list[list[HazardReport]] = []

        for report in type_reports:
            placed = False
            for cluster_members in assigned:
                centre = cluster_members[0]
                dist = _haversine_m(centre.lat, centre.lon, report.lat, report.lon)
                if dist <= cluster_radius_m:
                    cluster_members.append(report)
                    placed = True
                    break
            if not placed:
                assigned.append([report])

        for members in assigned:
            age_hours_list = [
                (now - r.reported_at).total_seconds() / 3600.0 for r in members
            ]
            weights = [decay_factor(age, hazard_type) for age in age_hours_list]
            total_weight = sum(weights) or 1.0

            consensus = sum(r.severity * w for r, w in zip(members, weights)) / total_weight
            effective = max(1, min(10, round(consensus)))

            # Description: from the highest-severity member
            desc_source = max(members, key=lambda r: r.severity)
            description = desc_source.description if desc_source.description else None

            clusters.append(
                AggregatedHazard(
                    canonical_id=members[0].id,
                    lat=members[0].lat,
                    lon=members[0].lon,
                    hazard_type=hazard_type,
                    report_count=len(members),
                    consensus_severity=round(consensus, 2),
                    effective_severity=effective,
                    confidence=min(1.0, len(members) / 5),
                    most_recent_report=max(r.reported_at for r in members),
                    oldest_report=min(r.reported_at for r in members),
                    description=description,
                )
            )

    return clusters

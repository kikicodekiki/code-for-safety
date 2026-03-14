from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.models.enums import HazardType


class RoutingImpact(BaseModel):
    affects_routing: bool
    edge_excluded: bool
    penalty_added: float | None = None
    description: str


class HazardReportResponse(BaseModel):
    id: str
    status: Literal["reported", "merged_into_cluster"]
    cluster_id: str | None = None
    severity: int
    type: HazardType
    timestamp: datetime
    expires_at: datetime
    routing_impact: RoutingImpact
    message: str


class AggregatedHazardResponse(BaseModel):
    id: str
    lat: float
    lon: float
    hazard_type: HazardType
    type_display_name: str
    type_icon: str
    report_count: int
    consensus_severity: float
    effective_severity: int
    severity_label: str
    confidence: float
    confidence_label: str
    age_hours: float
    is_recent: bool      # age < 1h
    is_fresh: bool       # age < 15 min
    description: str | None = None
    routing_excluded: bool
    decay_factor: float
    effective_penalty: float | None = None


class HazardStatsResponse(BaseModel):
    total_active_clusters: int
    total_reports_today: int
    by_type: dict[str, int]
    by_severity: dict[int, int]
    most_reported_area: str | None = None
    edges_currently_excluded: int
    avg_confidence: float
    coverage_radius_km: float

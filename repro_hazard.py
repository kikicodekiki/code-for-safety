from pydantic import BaseModel
from typing import Any, TypeVar
import time
from uuid import uuid4

class HazardReportCreate(BaseModel):
    lat: float
    lon: float
    type: str
    severity: int
    description: str | None = None

class RoutingImpact(BaseModel):
    affects_routing: bool
    edge_excluded: bool
    penalty_added: float | None
    description: str

class HazardReportResponse(BaseModel):
    id: str
    status: str
    cluster_id: str | None
    severity: int
    type: str
    timestamp: str
    expires_at: str
    routing_impact: RoutingImpact
    message: str

def get_hazard_icon(h_type: str) -> str:
    icons = {
        "pothole": "🕳️",
        "obstacle": "🚧",
        "dangerous_traffic": "🚗",
        "road_closed": "🚫",
        "wet_surface": "💦",
        "other": "⚠️",
    }
    return icons.get(h_type, "⚠️")

report = HazardReportCreate(lat=42.6977, lon=23.3219, type="pothole", severity=8, description="Big hole here")
hazard_id = str(uuid4())
now = time.strftime("%Y-%m-%dT%H:%M:%SZ")

resp_dict = {
    "id": hazard_id,
    "status": "reported",
    "cluster_id": None,
    "severity": report.severity,
    "type": report.type,
    "timestamp": now,
    "expires_at": now,
    "routing_impact": {
        "affects_routing": False,
        "edge_excluded": False,
        "penalty_added": None,
        "description": "Hazard added to map",
    },
    "message": "Hazard reported successfully",
}

# This simulates what FastAPI does with response_model
validated = HazardReportResponse(**resp_dict)
print("Validated successfully!")
print(validated.model_dump_json())

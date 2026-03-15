"""
SafeCycle Sofia — Lightweight FastAPI entry point.

Uses OSRM (free, no API key) for cycling route computation.
Does NOT require OSMnx, Redis, PostgreSQL, or Firebase.

Run:
    cd safecycle-backend
    python -m uvicorn app.main_lite:app --reload --port 8000 --host 0.0.0.0
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from uuid import uuid4
from typing import Any, TypeVar

import structlog
from dotenv import load_dotenv
from fastapi import FastAPI, Query, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.services.osrm_service import OSRMService, RoutingServiceError

load_dotenv()

# ── Logging ───────────────────────────────────────────────────────────────────
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(colors=True),
    ],
    wrapper_class=structlog.BoundLogger,
    cache_logger_on_first_use=True,
)
logger = structlog.get_logger("safecycle.lite")

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="SafeCycle Sofia API",
    version="1.0.0",
    description="Cycling safety API for Sofia — hackathon build (OSRM routing).",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS — allow all origins for hackathon ────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# ── OSRM routing service (free, no key) ──────────────────────────────────────
osrm = OSRMService()


# ── Timing middleware ─────────────────────────────────────────────────────────
@app.middleware("http")
async def timing_middleware(request: Request, call_next) -> Response:
    t0 = time.perf_counter()
    response = await call_next(request)
    ms = (time.perf_counter() - t0) * 1000
    response.headers["X-Process-Time"] = f"{ms:.2f}ms"
    response.headers["X-Request-ID"] = str(uuid4())
    return response


# ═══════════════════════════════════════════════════════════════════════════════
#  HEALTH
# ═══════════════════════════════════════════════════════════════════════════════
@app.get("/health", tags=["health"], summary="Liveness probe")
async def health():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/health/ready", tags=["health"], summary="Readiness probe")
async def readiness():
    return JSONResponse(
        status_code=200,
        content={
            "status": "ready",
            "checks": {
            },
        },
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  VELOBG (Bike Paths)
# ═══════════════════════════════════════════════════════════════════════════════
@app.get("/velobg/paths", tags=["velobg"], summary="List Sofia bike alleys")
async def get_velobg_paths():
    """Returns the bike alleys from the local GeoJSON file."""
    geojson_path = Path(__file__).parent.parent / "data" / "sofia_bike_alleys.geojson"
    if not geojson_path.exists():
        logger.error("velobg_data_missing", path=str(geojson_path))
        return {"paths": [], "total": 0, "source": "fallback", "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")}
    
    try:
        data = json.loads(geojson_path.read_text(encoding="utf-8"))
        paths = []
        for i, feature in enumerate(data.get("features", [])):
            paths.append({
                "id": str(feature.get("properties", {}).get("id") or f"path_{i}"),
                "name": feature.get("properties", {}).get("text_") or "Bike Alley",
                "description": None,
                "path_type": "DEDICATED_LANE",
                "layer_name": "Bike Alleys",
                "colour_hex": "#2ecc71", # Nice Emerald Green
                "length_m": 0,
                "is_bidirectional": True,
                "geojson": feature.get("geometry"),
                "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")
            })
            
        return {
            "paths": paths,
            "total": len(paths),
            "source": "cache",
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")
        }
    except Exception as exc:
        logger.error("velobg_load_error", error=str(exc))
        raise HTTPException(status_code=500, detail="Failed to load bike path data")


# ═══════════════════════════════════════════════════════════════════════════════
#  ROUTE  — matches the frontend's existing GET /route contract
# ═══════════════════════════════════════════════════════════════════════════════
@app.get("/route", tags=["routing"], summary="Compute cycling route")
async def get_route(
    origin_lat: float = Query(..., ge=-90, le=90),
    origin_lon: float = Query(..., ge=-180, le=180),
    dest_lat:   float = Query(..., ge=-90, le=90),
    dest_lon:   float = Query(..., ge=-180, le=180),
):
    """
    Compute a cycling route between two points using OSRM.

    Returns the **exact RouteResponse shape** the frontend expects:
    path, distance_m, duration_min, safety_score, crossroad_nodes,
    awareness_zones, etc.
    """
    logger.info(
        "route_requested",
        origin=f"{origin_lat},{origin_lon}",
        dest=f"{dest_lat},{dest_lon}",
    )

    try:
        result = await osrm.calculate_route(
            origin_lat, origin_lon,
            dest_lat, dest_lon,
            alternatives=2,
        )
    except RoutingServiceError as exc:
        logger.error("route_failed", error=str(exc))
        raise HTTPException(status_code=502, detail=str(exc))

    coords = result["path"]["coordinates"]
    distance_m = result["distance_m"]

    # Simple safety heuristic (shorter + fewer points = safer)
    safety_score = min(1.0, max(0.3, 1.0 - (distance_m / 20_000)))
    safety_score = round(safety_score, 2)

    response = {
        # ── Fields the frontend reads directly ────────────────────────
        "path":                  result["path"],          # GeoJSON LineString
        "crossroad_nodes":       [],                      # list[Coordinate]
        "distance_m":            distance_m,
        "duration_min":          result["duration_min"],
        "safety_score":          safety_score,
        "safety_label":          "Safe" if safety_score >= 0.7 else (
                                 "Moderate" if safety_score >= 0.5 else "Risky"),
        "surface_defaulted":     False,
        "speed_limit_defaulted": False,
        "awareness_zones":       [],                      # list[AwarenessZone]
        "edge_count":            len(coords),
        "excluded_edges_count":  0,
        # ── Extra data ────────────────────────────────────────────────
        "alternatives":          result.get("alternatives", []),
    }

    logger.info(
        "route_computed",
        distance_m=distance_m,
        duration_min=result["duration_min"],
        safety=safety_score,
        points=len(coords),
    )
    return response


# ── Hazard Models ─────────────────────────────────────────────────────────────
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


# In-memory storage for the demo
HAZARDS_DB: list[dict[str, Any]] = []


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


# ═══════════════════════════════════════════════════════════════════════════════
#  HAZARD ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════
@app.get("/hazards", tags=["hazards"], summary="List active hazards")
async def list_hazards():
    """Returns the list of hazards stored in memory."""
    return HAZARDS_DB


@app.post("/hazard", tags=["hazards"], status_code=201, response_model=HazardReportResponse)
async def report_hazard(report: HazardReportCreate):
    """
    Accepts a hazard report and stores it in memory.
    Returns a response matching the frontend's HazardReportResponse.
    """
    try:
        hazard_id = str(uuid4())
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        # Store in the "aggregated" format the frontend GET expects
        aggregated_hazard = {
            "id": hazard_id,
            "lat": report.lat,
            "lon": report.lon,
            "hazard_type": report.type,
            "type_display_name": report.type.replace("_", " ").title(),
            "type_icon": get_hazard_icon(report.type),
            "report_count": 1,
            "consensus_severity": report.severity,
            "effective_severity": report.severity,
            "severity_label": f"Level {report.severity}",
            "confidence": 0.5,
            "confidence_label": "Reported",
            "age_hours": 0,
            "is_recent": True,
            "is_fresh": True,
            "description": report.description,
            "routing_excluded": False,
            "decay_factor": 1.0,
            "effective_penalty": None,
        }
        
        HAZARDS_DB.append(aggregated_hazard)
        
        logger.info("hazard_reported", id=hazard_id, type=report.type)
        
        return {
            "id": hazard_id,
            "status": "reported",
            "cluster_id": None,
            "severity": report.severity,
            "type": report.type,
            "timestamp": now,
            "expires_at": now,  # In a real app this would be in the future
            "routing_impact": {
                "affects_routing": False,
                "edge_excluded": False,
                "penalty_added": None,
                "description": "Hazard added to map",
            },
            "message": "Hazard reported successfully",
        }
    except Exception as exc:
        logger.error("hazard_report_error", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/hazard/{report_id}/confirm", tags=["hazards"], status_code=204)
async def confirm_hazard(report_id: str):
    """Stub for confirmation."""
    return Response(status_code=204)


@app.delete("/hazard/{report_id}", tags=["hazards"], status_code=204)
async def delete_hazard(report_id: str):
    """Removes a hazard from memory."""
    global HAZARDS_DB
    HAZARDS_DB = [h for h in HAZARDS_DB if h["id"] != report_id]
    return Response(status_code=204)


@app.get("/hazards/stats", tags=["hazards"])
async def hazard_stats():
    """Returns hazard statistics based on in-memory data."""
    return {
        "total_active_clusters": len(HAZARDS_DB),
        "total_reports_today": len(HAZARDS_DB),
        "by_type": {},
        "by_severity": {},
        "most_reported_area": "Sofia",
        "edges_currently_excluded": 0,
        "avg_confidence": 0.5,
        "coverage_radius_km": 10,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  DEVICE TOKEN STUB
# ═══════════════════════════════════════════════════════════════════════════════
@app.post("/device-token", tags=["devices"], status_code=204)
async def register_device_token():
    return Response(status_code=204)

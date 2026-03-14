"""
SafeCycle Sofia — Edge safety cost function.

This is the product's computational core. Every road edge in the Sofia
street graph receives a safety-weighted cost w(e) that the A* router
minimises. Lower weight = safer and more preferable for cyclists.

Weight formula:
    w = (length_m × traffic_factor × surface_factor × speed_factor
         × bike_factor × air_quality_factor × density_factor)
        + hazard_penalty

w = inf means the edge is completely excluded from routing.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import structlog

from app.config import Settings

logger = structlog.get_logger(__name__)

# ── Hard-excluded highway types ──────────────────────────────────────────────
# These road classes are always unsafe for cyclists regardless of speed tags.
EXCLUDED_HIGHWAY_TYPES: frozenset[str] = frozenset({
    "motorway",
    "motorway_link",
    "trunk",
    "trunk_link",
    "raceway",
    "proposed",
    "construction",
})

# ── Speed-limit factor map ────────────────────────────────────────────────────
# Maps resolved speed (km/h) → multiplicative cost factor.
# Higher speed = more dangerous = higher factor = avoided by router.
SPEED_FACTOR_MAP: dict[int, float] = {
    10: 0.5,   # walking speed (pedestrian zones)
    20: 0.6,
    30: 0.8,   # 30-zone — cyclist-friendly, small bonus
    40: 1.0,   # 40 km/h — neutral baseline
    50: 1.4,   # 50 km/h — standard Sofia urban (DEFAULT applies here)
    60: 2.0,   # significant penalty — major arterials
    70: float("inf"),  # hard exclude — cyclists should not be here
}

# ── Surface factor map ────────────────────────────────────────────────────────
# Maps OSM surface tag → multiplicative cost factor.
# Rougher/more dangerous surfaces receive higher factors.
SURFACE_FACTOR_MAP: dict[str, float] = {
    "asphalt": 1.0,
    "paved": 1.0,
    "concrete": 1.05,
    "paving_stones": 1.3,
    "sett": 1.5,
    "cobblestone": 1.8,
    "unhewn_cobblestone": 2.0,
    "gravel": 2.0,
    "fine_gravel": 1.6,
    "dirt": 2.2,
    "sand": 2.5,
    "unpaved": 2.3,
    "grass": 2.8,
    "ground": 2.2,
    "mud": 3.0,
}

# ── Traffic proxy (road type) factor map ─────────────────────────────────────
# Approximates traffic volume and cyclist danger from the highway tag.
# Primary and secondary roads carry fast, heavy traffic → higher factor.
TRAFFIC_FACTOR_MAP: dict[str, float] = {
    "cycleway": 0.4,
    "path": 0.5,
    "footway": 0.55,
    "pedestrian": 0.6,
    "living_street": 0.7,
    "residential": 0.9,
    "service": 0.85,
    "unclassified": 1.0,
    "tertiary_link": 1.05,
    "tertiary": 1.1,
    "secondary_link": 1.2,
    "secondary": 1.3,
    "primary_link": 1.4,
    "primary": 1.5,
}

# ── Bike infrastructure bonus factors ────────────────────────────────────────
# The primary mechanism for routing onto dedicated cycling infrastructure.
# Lower factor = strongly preferred by the router.

# VeloBG / Sofia Open Data — dedicated, separated bike alley (highest quality)
BIKE_ALLEY_FACTOR: float = 0.25    # Sofia bike alleys from urbandata.sofia.bg

# Recreational routes (рекреационни маршрути) from the open data
RECREATIONAL_ROUTE_FACTOR: float = 0.3

# Connecting routes on main street network (свързващи маршрути)
CONNECTING_ROUTE_FACTOR: float = 0.55

# OSM cycleway tag — marked bike lane but less verified
CYCLEWAY_FACTOR: float = 0.6

# OSM cycleway:both / cycleway:left — painted lane, less separation
BIKE_LANE_FACTOR: float = 0.75

# ── Air quality (PM2.5) factor ────────────────────────────────────────────────
# PM2.5 ranges from 0 to 500 µg/m³. We normalise to a multiplicative factor:
#   0 µg/m³   → 1.0  (clean air, no penalty)
#   250 µg/m³ → 2.0  (very unhealthy)
#   500 µg/m³ → 3.0  (hazardous, strongly avoided)
# Formula: factor = 1.0 + (pm25 / PM25_MAX) * PM25_FACTOR_RANGE
PM25_MAX: float = 500.0
PM25_FACTOR_RANGE: float = 2.0  # max additional penalty multiplier

# ── People density factor ─────────────────────────────────────────────────────
# People density (pedestrians per 100m of road segment).
#   0   → 1.0  (empty street, no penalty)
#   50  → 1.5  (moderate crowd)
#   100 → 2.0  (very crowded, collision risk)
# Formula: factor = 1.0 + (density / DENSITY_MAX) * DENSITY_FACTOR_RANGE
DENSITY_MAX: float = 100.0
DENSITY_FACTOR_RANGE: float = 1.0  # max additional penalty multiplier


def compute_air_quality_factor(pm25: float) -> float:
    """
    Convert PM2.5 µg/m³ → multiplicative cost factor.

    Uses linear scaling:
        0   → 1.0 (clean)
        250 → 2.0 (very unhealthy)
        500 → 3.0 (hazardous)

    Values are clamped to [0, PM25_MAX].
    """
    clamped = max(0.0, min(pm25, PM25_MAX))
    return 1.0 + (clamped / PM25_MAX) * PM25_FACTOR_RANGE


def compute_density_factor(density: float) -> float:
    """
    Convert people density (per 100m) → multiplicative cost factor.

    Uses linear scaling:
        0   → 1.0 (empty)
        50  → 1.5 (moderate)
        100 → 2.0 (crowded)

    Values are clamped to [0, DENSITY_MAX].
    """
    clamped = max(0.0, min(density, DENSITY_MAX))
    return 1.0 + (clamped / DENSITY_MAX) * DENSITY_FACTOR_RANGE


@dataclass
class EdgeWeightResult:
    """
    Full output of compute_edge_weight().

    All metadata fields are returned so the route response can disclose
    exactly what assumptions were made — a key SafeCycle transparency feature.
    """
    weight: float
    speed_limit: int
    speed_limit_defaulted: bool
    surface: str
    surface_defaulted: bool
    bike_path: bool
    bike_path_type: str | None  # "alley" | "recreational" | "connecting" | None
    pm25_value: float           # PM2.5 µg/m³ used for this edge
    pm25_factor: float          # normalised air quality factor [1.0–3.0]
    density_value: float        # people density per 100m used for this edge
    density_factor: float       # normalised density factor [1.0–2.0]
    excluded: bool
    exclusion_reason: str | None  # "speed_limit" | "highway_type" | None


def parse_maxspeed(raw: str | int | list | None, default: int = 50) -> int:
    """
    Parse the OSM maxspeed tag into an integer km/h value.

    Handles all known OSM maxspeed formats:
      "50"             → 50
      "50 mph"         → 80  (converted to km/h)
      "BG:urban"       → 50  (Bulgarian national urban default)
      "RO:urban"       → 50  (Romanian — conservative fallback)
      "urban"          → 50
      "walk" / "foot"  → 10
      "none"           → 130 (autobahn-style — will be excluded by speed check)
      [50, 70]         → 50  (list → take minimum)
      None             → default (50)
    """
    if raw is None:
        return default

    # Handle list — OSMnx sometimes returns a list for complex ways
    if isinstance(raw, list):
        parsed = [parse_maxspeed(v, default) for v in raw]
        return min(parsed)

    if isinstance(raw, int):
        return raw

    raw_str = str(raw).strip().lower()

    # Numeric string
    if raw_str.isdigit():
        return int(raw_str)

    # Speed with unit
    if "mph" in raw_str:
        try:
            mph = float(raw_str.replace("mph", "").strip())
            return int(mph * 1.60934)
        except ValueError:
            return default

    if "km/h" in raw_str:
        try:
            return int(float(raw_str.replace("km/h", "").strip()))
        except ValueError:
            return default

    # Named speed limits — Bulgarian / regional
    urban_tags = {
        "bg:urban", "ro:urban", "ua:urban", "ru:urban",
        "pl:urban", "de:urban", "urban", "city",
    }
    if raw_str in urban_tags:
        return 50

    rural_tags = {"bg:rural", "ro:rural", "rural"}
    if raw_str in rural_tags:
        return 90  # will be excluded

    motorway_tags = {"bg:motorway", "motorway", "none"}
    if raw_str in motorway_tags:
        return 130  # will be excluded

    walk_tags = {"walk", "foot", "walking", "5", "10"}
    if raw_str in walk_tags:
        return 10

    # Try to extract leading digits (e.g. "50;" or "50|70")
    import re
    m = re.match(r"^(\d+)", raw_str)
    if m:
        return int(m.group(1))

    logger.warning("maxspeed_parse_failed", raw=raw, using_default=default)
    return default


def compute_edge_weight(
    edge_data: dict,
    hazard_penalties: dict[int, float],
    settings: Settings,
    pm25_value: float = 0.0,
    people_density: float = 0.0,
) -> EdgeWeightResult:
    """
    Compute the safety-weighted cost of traversing a road edge.

    Weight formula:
        w = (length_m × traffic_factor × surface_factor × speed_factor
             × bike_factor × air_quality_factor × density_factor)
            + hazard_penalty

    Lower weight = safer and more preferable.
    w = inf means the edge is completely excluded from routing.

    Parameters
    ----------
    edge_data : dict
        Raw OSMnx edge attribute dict. Many fields may be absent —
        all missing values are handled with explicit defaults.
    hazard_penalties : dict
        Maps edge osmid → additional float penalty from active user reports.
        Penalties are additive (not multiplicative) so they cannot turn a
        finite weight into inf.
    settings : Settings
        All thresholds come from here — never from magic numbers.
    pm25_value : float
        PM2.5 air quality reading in µg/m³ (0–500). Defaults to 0 (clean).
    people_density : float
        Pedestrian density per 100m of road (0–100). Defaults to 0 (empty).

    Returns
    -------
    EdgeWeightResult
        Structured result with the weight and all transparency metadata.
    """
    # ── Step 1: Highway type hard exclusion ──────────────────────────────────
    highway = edge_data.get("highway", "unclassified")
    if isinstance(highway, list):
        highway = highway[0]  # take primary classification
    highway = str(highway).lower()

    if highway in EXCLUDED_HIGHWAY_TYPES:
        return EdgeWeightResult(
            weight=float("inf"),
            speed_limit=0,
            speed_limit_defaulted=False,
            surface="unknown",
            surface_defaulted=False,
            bike_path=False,
            bike_path_type=None,
            pm25_value=pm25_value,
            pm25_factor=1.0,
            density_value=people_density,
            density_factor=1.0,
            excluded=True,
            exclusion_reason="highway_type",
        )

    # ── Step 2: Speed limit resolution ──────────────────────────────────────
    raw_speed = edge_data.get("maxspeed")
    speed_defaulted = raw_speed is None

    speed_limit = parse_maxspeed(raw_speed, default=settings.DEFAULT_SPEED_LIMIT_KMH)

    if speed_limit > settings.MAX_ALLOWED_SPEED_KMH:
        return EdgeWeightResult(
            weight=float("inf"),
            speed_limit=speed_limit,
            speed_limit_defaulted=speed_defaulted,
            surface="unknown",
            surface_defaulted=False,
            bike_path=False,
            bike_path_type=None,
            pm25_value=pm25_value,
            pm25_factor=1.0,
            density_value=people_density,
            density_factor=1.0,
            excluded=True,
            exclusion_reason="speed_limit",
        )

    # Find the closest speed bracket (e.g. 45 → use 50 factor)
    speed_factor = SPEED_FACTOR_MAP.get(speed_limit)
    if speed_factor is None:
        # Round up to nearest bracket
        brackets = sorted(SPEED_FACTOR_MAP.keys())
        for bracket in brackets:
            if speed_limit <= bracket:
                speed_factor = SPEED_FACTOR_MAP[bracket]
                break
        else:
            speed_factor = float("inf")  # above all brackets → exclude

    if speed_factor == float("inf"):
        return EdgeWeightResult(
            weight=float("inf"),
            speed_limit=speed_limit,
            speed_limit_defaulted=speed_defaulted,
            surface="unknown",
            surface_defaulted=False,
            bike_path=False,
            bike_path_type=None,
            pm25_value=pm25_value,
            pm25_factor=1.0,
            density_value=people_density,
            density_factor=1.0,
            excluded=True,
            exclusion_reason="speed_limit",
        )

    # ── Step 3: Surface resolution ───────────────────────────────────────────
    raw_surface = edge_data.get("surface")
    surface_defaulted = raw_surface is None
    surface = str(raw_surface).lower() if raw_surface else settings.DEFAULT_SURFACE
    surface_factor = SURFACE_FACTOR_MAP.get(surface, 1.0)

    # ── Step 4: Bike infrastructure bonus ────────────────────────────────────
    # Priority: Sofia open-data alley > recreational > connecting > OSM cycleway > none
    bike_path = edge_data.get("bike_path", False)
    bike_path_type = edge_data.get("bike_path_type")  # set by GeoJSONEnricher

    if bike_path and bike_path_type == "alley":
        bike_factor = BIKE_ALLEY_FACTOR
    elif bike_path and bike_path_type == "recreational":
        bike_factor = RECREATIONAL_ROUTE_FACTOR
    elif bike_path and bike_path_type == "connecting":
        bike_factor = CONNECTING_ROUTE_FACTOR
    elif bike_path:
        bike_factor = RECREATIONAL_ROUTE_FACTOR  # default bike path bonus
    else:
        # Fall back to OSM cycleway tags
        cycleway = edge_data.get("cycleway")
        bike_lanes = (
            edge_data.get("cycleway:both")
            or edge_data.get("cycleway:left")
            or edge_data.get("cycleway:right")
        )
        if cycleway and str(cycleway).lower() not in ("no", "none", "separate"):
            bike_factor = CYCLEWAY_FACTOR
        elif bike_lanes:
            bike_factor = BIKE_LANE_FACTOR
        else:
            bike_factor = 1.0

    # ── Step 5: Traffic proxy from road type ─────────────────────────────────
    traffic_factor = TRAFFIC_FACTOR_MAP.get(highway, 1.0)

    # ── Step 6: Hazard penalty (dynamic, additive) ───────────────────────────
    osmid = edge_data.get("osmid")
    hazard_penalty = 0.0
    if osmid is not None:
        # osmid can be int or list of ints
        if isinstance(osmid, list):
            hazard_penalty = max(hazard_penalties.get(oid, 0.0) for oid in osmid)
        else:
            hazard_penalty = hazard_penalties.get(osmid, 0.0)

    # ── Step 7: Air quality factor (PM2.5) ────────────────────────────────────
    air_factor = compute_air_quality_factor(pm25_value)

    # ── Step 8: People density factor ────────────────────────────────────────
    dens_factor = compute_density_factor(people_density)

    # ── Step 9: Final composition ─────────────────────────────────────────────
    base_length = edge_data.get("length", 10.0)
    weight = (
        base_length
        * traffic_factor
        * surface_factor
        * speed_factor
        * bike_factor
        * air_factor
        * dens_factor
    ) + hazard_penalty

    return EdgeWeightResult(
        weight=weight,
        speed_limit=speed_limit,
        speed_limit_defaulted=speed_defaulted,
        surface=surface,
        surface_defaulted=surface_defaulted,
        bike_path=bike_path,
        bike_path_type=bike_path_type,
        pm25_value=pm25_value,
        pm25_factor=round(air_factor, 4),
        density_value=people_density,
        density_factor=round(dens_factor, 4),
        excluded=False,
        exclusion_reason=None,
    )

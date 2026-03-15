"""
SafeCycle Sofia — A* routing algorithm with safety-weighted edges.

Algorithm overview:
  1. Pre-weight all edges using compute_edge_weight() — O(E)
  2. Remove hard-danger nodes (accident hotspot exclusion zones)
  3. Run nx.astar_path() with haversine heuristic and 'safe_weight'
  4. Extract crossroad nodes, awareness zones, safety score
  5. Return structured SafeRouteResult

The combination of A* speed and Dijkstra-style non-negative edge costs
gives an admissible, consistent heuristic that finds the true
safety-optimal path efficiently.
"""
from __future__ import annotations

from datetime import datetime, timezone

import networkx as nx
import structlog
from shapely.geometry import LineString, Point
from pydantic import BaseModel

from app.config import Settings
from app.core.exceptions import RouteNotFoundError
from app.core.graph.weighting import EdgeWeightResult, compute_edge_weight
from app.core.routing.heuristic import haversine_heuristic
from app.data.air_quality.repository import AirQualityRepository
from app.models.schemas.common import AwarenessZoneSchema, Coordinate, GeoJSONLineString
from app.models.schemas.route import RouteResponse
from app.utils.geo import haversine_metres, metres_to_degrees
from app.utils.time import utc_now

logger = structlog.get_logger(__name__)


def find_safe_route(
    G: nx.MultiDiGraph,
    origin_node: int,
    dest_node: int,
    hazard_penalties: dict[int, float],
    danger_nodes: frozenset[int],
    awareness_zones: list[AwarenessZoneSchema],
    settings: Settings,
    air_quality_repo: AirQualityRepository | None = None,
) -> RouteResponse:
    """
    Find the safety-optimal cycling route using A* with safety-weighted edges.

    Parameters
    ----------
    G : nx.MultiDiGraph — full Sofia street graph
    origin_node : int  — OSMnx node ID for the origin
    dest_node : int    — OSMnx node ID for the destination
    hazard_penalties : dict — osmid → additive penalty from user reports
    danger_nodes : frozenset — node IDs to remove (accident hotspots only)
    awareness_zones : list  — zones flagged in response but NOT removed from graph
    settings : Settings
    air_quality_repo : AirQualityRepository | None
        When provided, each edge gets the PM2.5 reading of the nearest sensor
        (up to 3 km away) factored into its safety cost.  Edges in areas with
        high PM2.5 receive a multiplicative penalty so the router prefers
        cleaner air corridors (e.g. parks, bike alleys away from traffic).

    Returns
    -------
    RouteResponse — the full route response ready to serialise

    Raises
    ------
    RouteNotFoundError — if no safe path exists
    """
    # ── Step 1: Apply safety weights to a working copy ───────────────────────
    H = G.copy()
    weight_results: dict[tuple[int, int, int], EdgeWeightResult] = {}
    surface_defaulted_any = False
    speed_defaulted_any = False
    excluded_count = 0

    for u, v, k, data in H.edges(data=True, keys=True):
        # Look up PM2.5 at the edge midpoint from the nearest sensor
        pm25 = 0.0
        if air_quality_repo is not None:
            lat_u = H.nodes[u].get("y", 0.0)
            lon_u = H.nodes[u].get("x", 0.0)
            lat_v = H.nodes[v].get("y", 0.0)
            lon_v = H.nodes[v].get("x", 0.0)
            pm25 = air_quality_repo.get_pm25(
                (lat_u + lat_v) / 2.0, (lon_u + lon_v) / 2.0
            )

        result = compute_edge_weight(data, hazard_penalties, settings, pm25_value=pm25)
        data["safe_weight"] = result.weight
        weight_results[(u, v, k)] = result

        if result.surface_defaulted:
            surface_defaulted_any = True
        if result.speed_limit_defaulted:
            speed_defaulted_any = True
        if result.excluded:
            excluded_count += 1

    # ── Step 2: Remove danger nodes (accident hotspots ONLY) ─────────────────
    # Rule 5: awareness zone nodes (schools, bus stops) are NOT removed.
    nodes_to_remove = danger_nodes & set(H.nodes())
    H.remove_nodes_from(nodes_to_remove)

    # ── Step 3: Verify reachability ──────────────────────────────────────────
    if origin_node not in H:
        raise RouteNotFoundError(
            "Origin coordinate falls within an excluded danger zone."
        )
    if dest_node not in H:
        raise RouteNotFoundError(
            "Destination coordinate falls within an excluded danger zone."
        )
    if not nx.has_path(H, origin_node, dest_node):
        raise RouteNotFoundError(
            "No cycling path exists between origin and destination "
            "on the safe street graph."
        )

    # ── Step 4: A* search ────────────────────────────────────────────────────
    try:
        path_nodes: list[int] = nx.astar_path(
            H,
            origin_node,
            dest_node,
            heuristic=lambda u, v: haversine_heuristic(u, v, H),
            weight="safe_weight",
        )
    except nx.NetworkXNoPath as exc:
        raise RouteNotFoundError(
            "A* could not find a path on the safe graph."
        ) from exc

    # ── Step 5: Extract coordinates (lat, lon) ───────────────────────────────
    coordinates: list[tuple[float, float]] = [
        (H.nodes[n]["y"], H.nodes[n]["x"])  # (lat, lon)
        for n in path_nodes
    ]

    # ── Step 6: Compute route statistics ─────────────────────────────────────
    total_distance_m = 0.0
    total_weighted_cost = 0.0

    for i in range(len(path_nodes) - 1):
        u, v = path_nodes[i], path_nodes[i + 1]
        if H.has_edge(u, v):
            # Get the minimum-cost key for this edge pair
            edge_data_list = [H[u][v][k] for k in H[u][v]]
            best = min(edge_data_list, key=lambda d: d.get("safe_weight", float("inf")))
            total_distance_m += best.get("length", 0.0)
            total_weighted_cost += best.get("safe_weight", 0.0)

    # Safety score: normalise average weight-per-metre to [0, 1]
    # avg ≤ 0.3 → dedicated bike path → score 1.0
    # avg = 1.5 → typical road mix → score ~0.56
    # avg ≥ 3.0 → dangerous → score 0.0
    safety_score = _compute_safety_score(total_weighted_cost, total_distance_m)

    # Average cycling speed on Sofia terrain: 14 km/h (accounts for stops/signals)
    duration_min = (total_distance_m / 1000.0) / 14.0 * 60.0

    # ── Step 7: Extract crossroad nodes ──────────────────────────────────────
    crossroad_coords = _extract_crossroad_nodes(path_nodes, G)

    # ── Step 8: Find awareness zones the path passes through ─────────────────
    zones_on_path = _find_awareness_zones_on_path(
        coordinates, awareness_zones, settings
    )

    # ── Assemble GeoJSON LineString ───────────────────────────────────────────
    # GeoJSON uses [lon, lat] order
    geojson_coords = [[lon, lat] for lat, lon in coordinates]

    return RouteResponse(
        path=GeoJSONLineString(coordinates=geojson_coords),
        crossroad_nodes=crossroad_coords,
        distance_m=round(total_distance_m, 1),
        duration_min=round(duration_min, 1),
        safety_score=round(safety_score, 3),
        surface_defaulted=surface_defaulted_any,
        speed_limit_defaulted=speed_defaulted_any,
        awareness_zones=zones_on_path,
        edge_count=len(path_nodes) - 1,
        excluded_edges_count=excluded_count,
        computed_at=utc_now(),
    )


def _compute_safety_score(
    total_weighted_cost: float, total_distance_m: float
) -> float:
    """
    Normalise total path weight into a 0.0–1.0 safety score.

    Formula:
        avg = total_weighted_cost / max(total_distance_m, 1)
        score = 1.0 - clamp((avg - 0.3) / 2.7, 0.0, 1.0)

    Calibration:
        avg ≤ 0.3  → score 1.0  (fully on dedicated bike alleys)
        avg = 1.5  → score ~0.56 (mixed infrastructure)
        avg ≥ 3.0  → score 0.0  (predominantly dangerous roads)
    """
    if total_distance_m <= 0:
        return 0.5  # degenerate case

    avg_weight_per_metre = total_weighted_cost / total_distance_m
    raw = (avg_weight_per_metre - 0.3) / 2.7
    clamped = max(0.0, min(1.0, raw))
    return 1.0 - clamped


def _extract_crossroad_nodes(
    path_nodes: list[int],
    G: nx.MultiDiGraph,
) -> list[Coordinate]:
    """
    Return nodes on the path where degree >= 3 in the full graph.
    These are true intersections where cyclists should be alert.

    Filters out motorway on/off ramps (highway=motorway_link) which
    appear as degree-3 nodes but are not relevant to cyclists.
    """
    crossroads: list[Coordinate] = []
    for node in path_nodes:
        if node not in G.nodes:
            continue
        if G.degree(node) >= 3:
            node_data = G.nodes[node]
            # Skip motorway junction nodes — not relevant for cyclists
            highway_type = node_data.get("highway", "")
            if isinstance(highway_type, str) and "motorway" in highway_type:
                continue
            crossroads.append(
                Coordinate(lat=node_data["y"], lon=node_data["x"])
            )
    return crossroads


def _find_awareness_zones_on_path(
    coordinates: list[tuple[float, float]],
    awareness_zones: list[AwarenessZoneSchema],
    settings: Settings,
) -> list[AwarenessZoneSchema]:
    """
    Return awareness zones whose buffered geometry intersects the route path.

    Uses shapely LineString + Point.buffer() for efficient intersection tests.
    Degrees approximation is acceptable here — we are looking for zones
    within ~30 m of the path, and 1° ≈ 111 320 m at Sofia's latitude.
    """
    if not coordinates or not awareness_zones:
        return []

    # Build the path as a shapely LineString (lon, lat order for shapely)
    path_line = LineString([(lon, lat) for lat, lon in coordinates])
    # Small buffer around the path line itself (path width approximation)
    path_buffer = path_line.buffer(metres_to_degrees(5.0))

    matched: list[AwarenessZoneSchema] = []
    for zone in awareness_zones:
        zone_point = Point(zone.center.lon, zone.center.lat)
        zone_circle = zone_point.buffer(metres_to_degrees(zone.radius_m))
        if path_buffer.intersects(zone_circle):
            matched.append(zone)

    return matched

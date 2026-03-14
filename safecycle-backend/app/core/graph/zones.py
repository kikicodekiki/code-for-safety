"""
SafeCycle Sofia — Danger zone node exclusion and awareness zone detection.

CRITICAL DISTINCTION (Rule 5):
  - accident_hotspot nodes → HARD REMOVED from the routing graph (weight = inf)
  - kindergarten / playground / bus_stop → KEPT in graph, flagged in response

The mobile client shows dismount/awareness alerts for flagged zones.
Only documented accident hotspots cause nodes to be physically removed.
"""
from __future__ import annotations

import structlog
from shapely.geometry import Point
from shapely.prepared import PreparedGeometry, prep

import networkx as nx

from app.models.schemas.common import AwarenessZoneSchema, Coordinate

logger = structlog.get_logger(__name__)


def build_danger_node_set(
    G: nx.MultiDiGraph,
    accident_hotspots: list[AwarenessZoneSchema],
) -> frozenset[int]:
    """
    Build the set of graph nodes that fall within any accident hotspot zone.
    These nodes are REMOVED from the routing graph before A* runs.

    Parameters
    ----------
    G : nx.MultiDiGraph
        The full Sofia street graph.
    accident_hotspots : list[AwarenessZoneSchema]
        Zones of type 'accident_hotspot' — sourced from the DB seed data.

    Returns
    -------
    frozenset[int]
        Node IDs that must be removed before routing.
    """
    if not accident_hotspots:
        return frozenset()

    # Build shapely points with buffers for each hotspot
    hotspot_geoms: list[PreparedGeometry] = []
    for zone in accident_hotspots:
        radius_deg = zone.radius_m / 111_320.0  # approx degrees at Sofia's latitude
        circle = Point(zone.center.lon, zone.center.lat).buffer(radius_deg)
        hotspot_geoms.append(prep(circle))

    danger_nodes: set[int] = set()
    for node, data in G.nodes(data=True):
        node_point = Point(data["x"], data["y"])  # (lon, lat)
        for geom in hotspot_geoms:
            if geom.contains(node_point):
                danger_nodes.add(node)
                break

    logger.info(
        "danger_nodes_computed",
        hotspot_zones=len(accident_hotspots),
        excluded_nodes=len(danger_nodes),
    )
    return frozenset(danger_nodes)


def build_awareness_zone_list(
    raw_zones: list[dict],
) -> list[AwarenessZoneSchema]:
    """
    Convert raw DB rows into AwarenessZoneSchema objects.

    Parameters
    ----------
    raw_zones : list[dict]
        Rows from the awareness_zones table (id, name, type, lat, lon, radius_m, source).

    Returns
    -------
    list[AwarenessZoneSchema]
    """
    result: list[AwarenessZoneSchema] = []
    for row in raw_zones:
        result.append(
            AwarenessZoneSchema(
                id=str(row["id"]),
                name=row.get("name"),
                type=row["type"],
                center=Coordinate(lat=row["lat"], lon=row["lon"]),
                radius_m=float(row.get("radius_m", 30.0)),
                source=row.get("source", "osm"),
            )
        )
    return result


def find_zones_near_coordinate(
    lat: float,
    lon: float,
    awareness_zones: list[AwarenessZoneSchema],
    radius_m: float,
) -> list[AwarenessZoneSchema]:
    """
    Return awareness zones whose buffered geometry contains the given coordinate.
    Used by the GPS proximity service on every location update.

    Parameters
    ----------
    lat, lon : float — cyclist's current position
    awareness_zones : list[AwarenessZoneSchema] — pre-loaded zone list
    radius_m : float — search radius (normally AWARENESS_ZONE_RADIUS_M)
    """
    from app.utils.geo import haversine_metres

    return [
        zone
        for zone in awareness_zones
        if haversine_metres(lat, lon, zone.center.lat, zone.center.lon)
        <= (zone.radius_m + radius_m)
    ]

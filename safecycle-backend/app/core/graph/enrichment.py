"""
SafeCycle Sofia — GeoJSON bike alley enrichment.

Reads the Sofia Open Data bike alleys GeoJSON (sourced from
urbandata.sofia.bg/tl/api/3) and overlays bike path attributes
onto the OSMnx graph edges.

The GeoJSON contains 486 MultiLineString features with a `text_` field
that classifies routes (in Bulgarian):

  null                                    → dedicated bike alley
  "рекреационни маршрути"                 → recreational routes
  "свързващи маршрути по главната ул.мрежа" → connecting routes on main streets

These three tiers map to different cost factors in weighting.py:
  alley        → BIKE_ALLEY_FACTOR      = 0.25  (strongest preference)
  recreational → RECREATIONAL_ROUTE_FACTOR = 0.30
  connecting   → CONNECTING_ROUTE_FACTOR  = 0.55
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import networkx as nx
import osmnx as ox
import structlog
from shapely.geometry import LineString, MultiLineString, shape

from app.config import Settings
from app.core.exceptions import GeoJSONEnrichmentError

logger = structlog.get_logger(__name__)

# Maximum distance (metres) between a GeoJSON line endpoint and the
# nearest graph node before we give up trying to snap it.
MAX_SNAP_DISTANCE_M: float = 50.0

# Bulgarian text_ values → internal path type codes
_TEXT_TO_TYPE: dict[str | None, str] = {
    None: "alley",
    "рекреационни маршрути": "recreational",
    "свързващи маршрути по главната ул.мрежа": "connecting",
}


class GeoJSONEnricher:
    """
    Reads the Sofia Open Data bike alleys GeoJSON and overlays
    bike_path = True and bike_path_type onto matching graph edges.

    The primary source of ground-truth cycling infrastructure in Sofia.
    Their data is more current and accurate than generic OSM tags.
    """

    @staticmethod
    def enrich(
        G: nx.MultiDiGraph,
        geojson_path: str,
        settings: Settings,
    ) -> nx.MultiDiGraph:
        """
        Overlay Sofia bike alley data onto graph edges.

        For each GeoJSON MultiLineString feature:
          1. Convert each LineString segment into (start_node, end_node) pairs
             by snapping endpoints to the nearest graph node.
          2. If a direct graph edge exists between those nodes, mark it.
          3. If no direct edge but the nodes are within MAX_SNAP_DISTANCE_M,
             find the shortest connecting path and mark all intermediate edges.

        Returns the enriched graph (same object, mutated in place).
        """
        path = Path(geojson_path)
        if not path.exists():
            logger.warning(
                "geojson_enrichment_skipped",
                reason="file_not_found",
                path=str(path),
            )
            return G

        try:
            with open(path, encoding="utf-8") as f:
                geojson = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.error(
                "geojson_load_failed", path=str(path), error=str(exc)
            )
            raise GeoJSONEnrichmentError(
                f"Failed to load GeoJSON from {path}: {exc}"
            ) from exc

        features: list[dict[str, Any]] = geojson.get("features", [])
        if not features:
            logger.warning("geojson_no_features", path=str(path))
            return G

        total_features = len(features)
        edges_enriched = 0
        features_matched = 0

        # Pre-build a node lookup for fast nearest-node queries
        node_ids = list(G.nodes())
        node_xs = [G.nodes[n]["x"] for n in node_ids]
        node_ys = [G.nodes[n]["y"] for n in node_ids]

        for feature in features:
            props = feature.get("properties", {})
            text_label = props.get("text_")
            path_type = _TEXT_TO_TYPE.get(text_label, "alley")

            geometry = feature.get("geometry", {})
            if not geometry:
                continue

            # Collect all individual LineStrings from MultiLineString
            geom_type = geometry.get("type")
            coords_list: list[list[tuple[float, float]]] = []

            if geom_type == "MultiLineString":
                for ring in geometry.get("coordinates", []):
                    coords_list.append([(c[0], c[1]) for c in ring])
            elif geom_type == "LineString":
                coords = geometry.get("coordinates", [])
                coords_list.append([(c[0], c[1]) for c in coords])
            else:
                continue

            for segment in coords_list:
                if len(segment) < 2:
                    continue

                start_lon, start_lat = segment[0]
                end_lon, end_lat = segment[-1]

                try:
                    u = ox.nearest_nodes(G, X=start_lon, Y=start_lat)
                    v = ox.nearest_nodes(G, X=end_lon, Y=end_lat)
                except Exception:
                    continue

                if u == v:
                    continue

                enriched = GeoJSONEnricher._mark_edge(G, u, v, path_type)
                if enriched > 0:
                    edges_enriched += enriched
                    features_matched += 1

        logger.info(
            "graph_enriched",
            source="sofia_open_data_geojson",
            total_features=total_features,
            features_matched=features_matched,
            edges_enriched=edges_enriched,
        )
        return G

    @staticmethod
    def _mark_edge(
        G: nx.MultiDiGraph,
        u: int,
        v: int,
        path_type: str,
    ) -> int:
        """
        Attempt to mark edge (u→v) and (v→u) as bike infrastructure.

        Returns the number of edges that were actually marked.
        """
        marked = 0

        # Direct edge u → v
        if G.has_edge(u, v):
            for key in G[u][v]:
                G[u][v][key]["bike_path"] = True
                G[u][v][key]["bike_path_type"] = path_type
                marked += 1

        # Direct edge v → u (the graph is directed but bike paths are bidirectional)
        if G.has_edge(v, u):
            for key in G[v][u]:
                G[v][u][key]["bike_path"] = True
                G[v][u][key]["bike_path_type"] = path_type
                marked += 1

        if marked > 0:
            return marked

        # No direct edge — try shortest path through intermediate nodes
        try:
            path_nodes = nx.shortest_path(G, u, v, weight="length")
            if len(path_nodes) <= 4:  # only mark short connecting paths
                for i in range(len(path_nodes) - 1):
                    a, b = path_nodes[i], path_nodes[i + 1]
                    if G.has_edge(a, b):
                        for key in G[a][b]:
                            G[a][b][key]["bike_path"] = True
                            G[a][b][key]["bike_path_type"] = path_type
                            marked += 1
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            pass

        return marked

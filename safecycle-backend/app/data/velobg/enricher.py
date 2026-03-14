"""
VeloBGEnricher — overlays VeloBG path data onto the OSMnx graph.

Accepts VeloBGMapData (from the KML pipeline) instead of a static file.
The graph edge attributes it sets are compatible with weighting.py:

    bike_path (bool)                  True for any VeloBG-confirmed infrastructure
    bike_path_type (str)              "alley" | "recreational" | "connecting" (weighting.py keys)
    velobg_path_type (str)            Full VeloBGPathType value (for display/API)
    velobg_path_id (str)              ID of the matching VeloBGPath
    velobg_weight_multiplier (float)  Pre-computed weight multiplier

Matching strategy:
    For each VeloBGPath coordinate sequence:
    1. Snap start/end (and sampled intermediate) coordinates to nearest graph nodes
    2. If nodes are within MAX_SNAP_DISTANCE_M, find direct or shortest-path edges
    3. Mark all matched edges with bike infrastructure attributes
"""
from __future__ import annotations

import math
from typing import Optional

import networkx as nx
import osmnx as ox
import structlog

from app.config import Settings
from app.models.schemas.velobg import VeloBGMapData, VeloBGPath, VeloBGPathType

logger = structlog.get_logger(__name__)

MAX_SNAP_DISTANCE_M = 50.0
INTERMEDIATE_SAMPLE_INTERVAL = 5  # Sample every Nth coordinate for long paths

# Maps VeloBGPathType to the bike_path_type values weighting.py understands
_VELOBG_TO_BIKE_PATH_TYPE: dict[VeloBGPathType, Optional[str]] = {
    VeloBGPathType.DEDICATED_LANE: "alley",
    VeloBGPathType.GREENWAY:       "recreational",
    VeloBGPathType.PAINTED_LANE:   "connecting",
    VeloBGPathType.SHARED_PATH:    "connecting",
    VeloBGPathType.OFF_ROAD:       None,    # generic bike_path bonus
    VeloBGPathType.UNKNOWN:        None,    # generic bike_path bonus
    VeloBGPathType.PROPOSED:       None,    # should never reach here (filtered out)
}


class VeloBGEnricher:

    def enrich(
        self,
        G:        nx.MultiDiGraph,
        map_data: VeloBGMapData,
        settings: Settings,
    ) -> nx.MultiDiGraph:
        """
        Enriches the graph G with VeloBG path data from map_data.
        Modifies G in-place and returns it.

        Only usable paths (not PROPOSED) are applied to the graph.
        """
        enriched_edges = 0
        skipped_paths  = 0

        usable_paths = map_data.usable_paths

        logger.info(
            "velobg_enrichment_starting",
            total_paths=map_data.total_paths,
            usable_paths=len(usable_paths),
            proposed_skipped=map_data.total_paths - len(usable_paths),
        )

        for path in usable_paths:
            edges_matched = self._snap_path_to_graph(G, path)

            if edges_matched == 0:
                skipped_paths += 1
                logger.debug(
                    "velobg_path_no_edges_matched",
                    path_name=path.name,
                    path_type=path.path_type.value,
                    coordinates=len(path.coordinates),
                )
            else:
                enriched_edges += edges_matched

        logger.info(
            "velobg_enrichment_complete",
            enriched_edges=enriched_edges,
            skipped_paths=skipped_paths,
        )

        return G

    def _snap_path_to_graph(
        self,
        G:    nx.MultiDiGraph,
        path: VeloBGPath,
    ) -> int:
        """
        Snaps a VeloBGPath to graph edges and sets bike infrastructure attributes.
        Returns the number of edges successfully matched.
        """
        coords = path.coordinates
        if len(coords) < 2:
            return 0

        edges_matched = 0

        if len(coords) <= 4:
            sample_coords = [coords[0], coords[-1]]
        else:
            indices = (
                [0]
                + list(range(INTERMEDIATE_SAMPLE_INTERVAL, len(coords) - 1, INTERMEDIATE_SAMPLE_INTERVAL))
                + [len(coords) - 1]
            )
            sample_coords = [coords[i] for i in indices]

        for i in range(len(sample_coords) - 1):
            c_start = sample_coords[i]
            c_end   = sample_coords[i + 1]

            try:
                u = ox.nearest_nodes(G, c_start.lon, c_start.lat)
                v = ox.nearest_nodes(G, c_end.lon,   c_end.lat)
            except Exception:
                continue

            dist_u = self._node_distance_m(G, u, c_start.lat, c_start.lon)
            dist_v = self._node_distance_m(G, v, c_end.lat,   c_end.lon)

            if dist_u > MAX_SNAP_DISTANCE_M or dist_v > MAX_SNAP_DISTANCE_M:
                continue

            if G.has_edge(u, v):
                self._apply_path_attributes(G[u][v][0], path)
                edges_matched += 1
            elif G.has_edge(v, u):
                self._apply_path_attributes(G[v][u][0], path)
                edges_matched += 1
            else:
                try:
                    path_nodes = nx.shortest_path(G, u, v, weight="length")
                    for j in range(len(path_nodes) - 1):
                        n1, n2 = path_nodes[j], path_nodes[j + 1]
                        if G.has_edge(n1, n2):
                            self._apply_path_attributes(G[n1][n2][0], path)
                            edges_matched += 1
                except nx.NetworkXNoPath:
                    pass

        return edges_matched

    def _apply_path_attributes(
        self,
        edge_data: dict,
        path:      VeloBGPath,
    ) -> None:
        """
        Sets bike infrastructure attributes on a graph edge dict.
        Only upgrades — never downgrades an edge to worse infrastructure.
        Sets both bike_path_type (for weighting.py) and velobg_path_type (for display).
        """
        current_multiplier = edge_data.get("velobg_weight_multiplier", 1.0)
        new_multiplier     = path.edge_weight_multiplier

        if new_multiplier < current_multiplier:
            edge_data["bike_path"]                = True
            # bike_path_type must use the vocabulary weighting.py understands
            edge_data["bike_path_type"]           = _VELOBG_TO_BIKE_PATH_TYPE.get(path.path_type)
            # velobg-specific fields for display and API
            edge_data["velobg_path_type"]         = path.path_type.value
            edge_data["velobg_path_id"]           = path.id
            edge_data["velobg_weight_multiplier"] = new_multiplier
            edge_data["velobg_path_name"]         = path.name or ""
            edge_data["velobg_colour"]            = path.colour_hex or ""

    @staticmethod
    def _node_distance_m(
        G:    nx.MultiDiGraph,
        node: int,
        lat:  float,
        lon:  float,
    ) -> float:
        n_lat = G.nodes[node].get("y", 0.0)
        n_lon = G.nodes[node].get("x", 0.0)
        R     = 6_371_000
        dphi  = math.radians(lat - n_lat)
        dlam  = math.radians(lon - n_lon)
        phi1  = math.radians(n_lat)
        phi2  = math.radians(lat)
        a     = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
        return 2 * R * math.asin(math.sqrt(a))

"""
SafeCycle Sofia — OSMnx graph loader.
Downloads, caches, filters, and prepares the Sofia street graph for routing.
"""
from __future__ import annotations

import os
from pathlib import Path

import networkx as nx
import osmnx as ox
import structlog

from app.config import Settings
from app.core.exceptions import GraphNotLoadedError, NodeNotReachableError

logger = structlog.get_logger(__name__)

# Maximum distance (metres) between a requested coordinate and the
# nearest graph node before we consider the destination unreachable.
MAX_SNAP_DISTANCE_M: float = 500.0


class GraphLoader:
    """
    Manages the Sofia OSMnx street graph lifecycle.

    Strategy:
      1. If GRAPH_CACHE_PATH exists on disk → load from GraphML (fast, ~2 s)
      2. Otherwise → download from OSMnx, enrich with speed/travel-time
         metadata, save to GraphML cache for next startup.

    The graph is stored in app.state.graph and injected via dependency.
    """

    @staticmethod
    async def load(settings: Settings) -> nx.MultiDiGraph:
        """
        Load or download the Sofia cycling street graph.

        After loading, calls ox.add_edge_speeds() and ox.add_edge_travel_times()
        to populate 'speed_kph' and 'travel_time' edge attributes from OSM
        maxspeed tags (missing values get the network-type default speed).
        """
        cache_path = Path(settings.GRAPH_CACHE_PATH)
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        if cache_path.exists():
            logger.info("graph_cache_hit", path=str(cache_path))
            G = ox.load_graphml(str(cache_path))
        else:
            logger.info(
                "graph_downloading",
                bbox={
                    "north": settings.SOFIA_BBOX_NORTH,
                    "south": settings.SOFIA_BBOX_SOUTH,
                    "east": settings.SOFIA_BBOX_EAST,
                    "west": settings.SOFIA_BBOX_WEST,
                },
                network_type=settings.GRAPH_NETWORK_TYPE,
            )
            G = ox.graph_from_bbox(
                bbox=(
                    settings.SOFIA_BBOX_NORTH,
                    settings.SOFIA_BBOX_SOUTH,
                    settings.SOFIA_BBOX_EAST,
                    settings.SOFIA_BBOX_WEST,
                ),
                network_type=settings.GRAPH_NETWORK_TYPE,
                simplify=True,
                retain_all=False,
            )
            # Populate speed and travel time from OSM maxspeed tags
            G = ox.add_edge_speeds(G)
            G = ox.add_edge_travel_times(G)

            ox.save_graphml(G, str(cache_path))
            logger.info("graph_cache_saved", path=str(cache_path))

        # Defensive bbox filter — removes stray nodes from neighbouring areas
        G = GraphLoader.filter_to_bbox(
            G,
            north=settings.SOFIA_BBOX_NORTH,
            south=settings.SOFIA_BBOX_SOUTH,
            east=settings.SOFIA_BBOX_EAST,
            west=settings.SOFIA_BBOX_WEST,
        )

        logger.info(
            "graph_loaded",
            nodes=G.number_of_nodes(),
            edges=G.number_of_edges(),
        )
        return G

    @staticmethod
    def filter_to_bbox(
        G: nx.MultiDiGraph,
        north: float,
        south: float,
        east: float,
        west: float,
    ) -> nx.MultiDiGraph:
        """
        Remove any nodes outside the Sofia bounding box.
        OSMnx may include nodes just beyond the bbox boundary when
        edges cross the border — this removes those strays.
        """
        nodes_to_remove = [
            node
            for node, data in G.nodes(data=True)
            if not (south <= data["y"] <= north and west <= data["x"] <= east)
        ]
        G.remove_nodes_from(nodes_to_remove)
        if nodes_to_remove:
            logger.debug(
                "graph_bbox_filtered", removed_nodes=len(nodes_to_remove)
            )
        return G

    @staticmethod
    def get_node_for_coordinate(
        G: nx.MultiDiGraph, lat: float, lon: float
    ) -> int:
        """
        Return the nearest graph node to a coordinate.

        OSMnx uses (lon, lat) order — this wrapper handles the reversal
        so callers always pass (lat, lon) as expected.

        Raises
        ------
        NodeNotReachableError
            If the nearest node is more than MAX_SNAP_DISTANCE_M away,
            indicating the coordinate is outside the mapped cycling network.
        """
        # ox.nearest_nodes expects (X=lon, Y=lat)
        node = ox.nearest_nodes(G, X=lon, Y=lat)
        node_data = G.nodes[node]
        node_lat = node_data["y"]
        node_lon = node_data["x"]

        # Haversine snap-distance check
        from app.utils.geo import haversine_metres
        dist = haversine_metres(lat, lon, node_lat, node_lon)
        if dist > MAX_SNAP_DISTANCE_M:
            raise NodeNotReachableError(
                f"Nearest graph node is {dist:.0f} m away "
                f"(max allowed: {MAX_SNAP_DISTANCE_M} m). "
                "The coordinate may be outside the cycling network."
            )
        return node

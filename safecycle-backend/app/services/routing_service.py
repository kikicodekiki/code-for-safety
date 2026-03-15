"""
SafeCycle Sofia — Routing service.
Orchestrates graph → weighting → A* → response pipeline.
"""
from __future__ import annotations

import time

import networkx as nx
import structlog

from app.config import Settings
from app.core.graph.loader import GraphLoader
from app.core.routing.algorithm import find_safe_route
from app.models.schemas.common import AwarenessZoneSchema
from app.models.schemas.route import RouteResponse
from app.services.density_service import DensityService
from app.services.hazard_service import HazardService
from redis.asyncio import Redis

logger = structlog.get_logger(__name__)


class RoutingService:
    """
    Orchestrates the full safe-route computation pipeline.
    Injected as a FastAPI dependency.
    """

    def __init__(
        self,
        graph: nx.MultiDiGraph,
        hazard_service: HazardService,
        density_service: DensityService,
        danger_nodes: frozenset[int],
        awareness_zones: list[AwarenessZoneSchema],
        settings: Settings,
    ) -> None:
        self.graph = graph
        self.hazard_service = hazard_service
        self.density_service = density_service
        self.danger_nodes = danger_nodes
        self.awareness_zones = awareness_zones
        self.settings = settings

    async def find_route(
        self,
        origin_lat: float,
        origin_lon: float,
        dest_lat: float,
        dest_lon: float,
        redis: Redis,
    ) -> RouteResponse:
        """
        Compute the safety-optimal cycling route.

        Steps:
          1. Snap coordinates to nearest graph nodes
          2. Fetch active hazard penalties from Redis
          3. Run A* routing algorithm
          4. Return RouteResponse

        Parameters
        ----------
        origin_lat, origin_lon : float — start point
        dest_lat, dest_lon : float — end point
        redis : Redis — for fetching active hazard penalties

        Returns
        -------
        RouteResponse — fully computed route

        Raises
        ------
        NodeNotReachableError — if origin/dest are outside the graph coverage
        RouteNotFoundError — if no safe path exists
        """
        t_start = time.perf_counter()

        # Snap coordinates to graph nodes
        origin_node = GraphLoader.get_node_for_coordinate(
            self.graph, origin_lat, origin_lon
        )
        dest_node = GraphLoader.get_node_for_coordinate(
            self.graph, dest_lat, dest_lon
        )

        # Fetch hazard penalties (additive to edge weights)
        hazard_penalties = await self.hazard_service.get_active_hazard_penalties(
            self.graph, redis
        )

        # Fetch real-time crowd density at route midpoint
        mid_lat = (origin_lat + dest_lat) / 2.0
        mid_lon = (origin_lon + dest_lon) / 2.0
        density_result = await self.density_service.estimate_density(
            lat=mid_lat, lon=mid_lon
        )

        # Run the routing algorithm
        result = find_safe_route(
            G=self.graph,
            origin_node=origin_node,
            dest_node=dest_node,
            hazard_penalties=hazard_penalties,
            danger_nodes=self.danger_nodes,
            awareness_zones=self.awareness_zones,
            settings=self.settings,
            people_density=density_result.people_density,
        )

        elapsed_ms = (time.perf_counter() - t_start) * 1000

        logger.info(
            "route_computed",
            origin_lat=origin_lat,
            origin_lon=origin_lon,
            dest_lat=dest_lat,
            dest_lon=dest_lon,
            safety_score=result.safety_score,
            safety_label=result.safety_label,
            distance_m=result.distance_m,
            duration_min=result.duration_min,
            surface_defaulted=result.surface_defaulted,
            speed_limit_defaulted=result.speed_limit_defaulted,
            edge_count=result.edge_count,
            excluded_edges_count=result.excluded_edges_count,
            active_hazards=len(hazard_penalties),
            awareness_zones_on_path=len(result.awareness_zones),
            density_score=density_result.density_score,
            density_real_time=density_result.is_real_time,
            computation_ms=round(elapsed_ms, 1),
        )

        return result

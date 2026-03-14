"""
SafeCycle Sofia — Haversine A* heuristic.

The heuristic function must be:
  - Admissible: h(n) <= true cost from n to goal (straight line <= any road path)
  - Consistent: h(n) <= cost(n, n') + h(n') for all successors n'

Both properties hold for the haversine distance when edge weights represent
metres, which guarantees A* finds the globally optimal (safest) path.
"""
from __future__ import annotations

import networkx as nx

from app.utils.geo import haversine_metres


def haversine_heuristic(u: int, v: int, G: nx.MultiDiGraph) -> float:
    """
    Admissible A* heuristic: straight-line great-circle distance in metres.

    This returns the physical distance, not the safety-weighted cost.
    Since safety weights are always >= physical length (no negative weights
    and no weight < 1.0 × length except for bike paths which are ≥ 0.25×),
    the heuristic remains admissible.

    Parameters
    ----------
    u : int — source node ID
    v : int — target node ID
    G : nx.MultiDiGraph — the graph (needed to look up node coordinates)

    Returns
    -------
    float — straight-line distance in metres (lower bound on actual path cost)
    """
    u_data = G.nodes[u]
    v_data = G.nodes[v]
    return haversine_metres(
        lat1=u_data["y"],
        lon1=u_data["x"],
        lat2=v_data["y"],
        lon2=v_data["x"],
    )

import sys
import os

# Add app to path
sys.path.append(os.getcwd())

from app.core.graph.weighting import compute_edge_weight, BIKE_ALLEY_FACTOR
from app.config import settings
from app.core.routing.algorithm import find_safe_route
import networkx as nx

def test_weighting():
    print("Testing Weighting Logic...")
    
    # Base edge data
    edge_data = {
        "osmid": 123,
        "length": 100.0,
        "highway": "residential",
        "maxspeed": "50",
        "surface": "asphalt"
    }
    
    # 1. Check bike alley factor
    alley_data = edge_data.copy()
    alley_data["bike_path"] = True
    alley_data["bike_path_type"] = "alley"
    
    normal_res = compute_edge_weight(edge_data, {}, settings)
    alley_res = compute_edge_weight(alley_data, {}, settings)
    
    print(f"Normal weight: {normal_res.weight}")
    print(f"Alley weight: {alley_res.weight}")
    print(f"Alley factor: {alley_res.weight / normal_res.weight:.2f} (Expected 0.15)")

    # 2. Check speed limits
    for speed in [70, 80, 90]:
        s_data = edge_data.copy()
        s_data["maxspeed"] = str(speed)
        res = compute_edge_weight(s_data, {}, settings)
        print(f"Speed {speed} result: excluded={res.excluded}, weight={res.weight}")

def test_danger_nodes():
    print("\nTesting Danger Node Penalization...")
    # Mock graph
    G = nx.MultiDiGraph()
    G.add_node(1, x=23.32, y=42.69)
    G.add_node(2, x=23.33, y=42.70)
    G.add_edge(1, 2, osmid=999, length=100.0, highway="residential", maxspeed="50")
    
    # Node 1 is a danger node
    danger_nodes = frozenset([1])
    
    # Compute route
    from app.models.schemas.common import AwarenessZoneSchema
    try:
        res = find_safe_route(
            G, 1, 2, 
            hazard_penalties={}, 
            danger_nodes=danger_nodes, 
            awareness_zones=[], 
            settings=settings
        )
        print(f"Route found through danger node 1. Distance: {res.distance_m}")
        # We can't easily check the internal weight used in nx.astar_path from here without mocking more,
        # but the fact it didn't raise RouteNotFoundError (if it was the only path) shows Step 2 removal worked.
    except Exception as e:
        print(f"Error in find_safe_route: {e}")

if __name__ == "__main__":
    test_weighting()
    test_danger_nodes()

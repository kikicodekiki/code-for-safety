"""
SafeCycle Sofia — pytest fixtures.
Shared test infrastructure for all test modules.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import networkx as nx
import pytest

from app.config import Settings


# ── Settings fixture ──────────────────────────────────────────────────────────

@pytest.fixture
def test_settings() -> Settings:
    """Settings instance with test-safe defaults."""
    return Settings(
        DEBUG=True,
        ENVIRONMENT="test",
        DATABASE_URL="postgresql+asyncpg://test:test@localhost/test",
        REDIS_URL="redis://localhost:6379/1",
        GOOGLE_MAPS_API_KEY="test_key",
        FIREBASE_ENABLED=False,
        GRAPH_CACHE_PATH="/tmp/test_sofia_graph.graphml",
        GEOJSON_BIKE_ALLEYS_PATH=str(
            Path(__file__).parent.parent / "data" / "sofia_bike_alleys.geojson"
        ),
    )


# ── Minimal Sofia-area graph ──────────────────────────────────────────────────

@pytest.fixture
def minimal_graph() -> nx.MultiDiGraph:
    """
    A small synthetic graph representing 4 nodes and 5 edges in Sofia.
    Coordinates are real Sofia locations for realistic distance calculations.
    """
    G = nx.MultiDiGraph()

    # Nodes: (node_id, {x: lon, y: lat})
    nodes = [
        (1, {"x": 23.3219, "y": 42.6977}),  # NDK (National Palace of Culture)
        (2, {"x": 23.3250, "y": 42.6980}),  # nearby intersection
        (3, {"x": 23.3280, "y": 42.6975}),  # further east
        (4, {"x": 23.3240, "y": 42.6955}),  # south
    ]
    G.add_nodes_from(nodes)

    # Edges with OSM-style attributes
    edges = [
        (1, 2, 0, {
            "osmid": 1001,
            "length": 150.0,
            "highway": "residential",
            "maxspeed": "50",
            "surface": "asphalt",
        }),
        (2, 1, 0, {
            "osmid": 1002,
            "length": 150.0,
            "highway": "residential",
            "maxspeed": "50",
            "surface": "asphalt",
        }),
        (2, 3, 0, {
            "osmid": 1003,
            "length": 200.0,
            "highway": "secondary",
            "maxspeed": "50",
            "surface": "asphalt",
        }),
        (3, 2, 0, {
            "osmid": 1004,
            "length": 200.0,
            "highway": "secondary",
            "maxspeed": "50",
            "surface": "asphalt",
        }),
        (2, 4, 0, {
            "osmid": 1005,
            "length": 250.0,
            "highway": "tertiary",
        }),
        (4, 2, 0, {
            "osmid": 1006,
            "length": 250.0,
            "highway": "tertiary",
        }),
        (1, 4, 0, {
            "osmid": 1007,
            "length": 300.0,
            "highway": "residential",
            "bike_path": True,
            "bike_path_type": "alley",
        }),
        (4, 1, 0, {
            "osmid": 1008,
            "length": 300.0,
            "highway": "residential",
            "bike_path": True,
            "bike_path_type": "alley",
        }),
    ]
    G.add_edges_from(edges)
    return G


# ── Redis mock ────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_redis() -> AsyncMock:
    """Mock Redis client."""
    redis = AsyncMock()
    redis.ping.return_value = True
    redis.keys.return_value = []
    redis.get.return_value = None
    redis.setex.return_value = True
    return redis


# ── DB session mock ───────────────────────────────────────────────────────────

@pytest.fixture
def mock_db() -> AsyncMock:
    """Mock async SQLAlchemy session."""
    session = AsyncMock()
    session.execute.return_value = MagicMock(fetchall=lambda: [])
    session.commit.return_value = None
    return session

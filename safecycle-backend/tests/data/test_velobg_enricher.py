"""Tests for VeloBGEnricher."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import networkx as nx
import pytest

from app.data.velobg.enricher import VeloBGEnricher, _VELOBG_TO_BIKE_PATH_TYPE
from app.models.schemas.velobg import (
    VeloBGCoordinate, VeloBGLayer, VeloBGMapData, VeloBGPath, VeloBGPathType,
)


NOW = datetime.now(timezone.utc)


def _make_path(
    path_type: VeloBGPathType = VeloBGPathType.DEDICATED_LANE,
    coords: list[tuple[float, float]] | None = None,
) -> VeloBGPath:
    if coords is None:
        coords = [(42.697, 23.321), (42.698, 23.322)]
    return VeloBGPath(
        id="test-id",
        name="Test Path",
        description=None,
        path_type=path_type,
        coordinates=[VeloBGCoordinate(lat=lat, lon=lon) for lat, lon in coords],
        layer_name="велоалея",
        style_id="#style1",
        colour_hex="#00FF00",
        length_m=150.0,
        is_bidirectional=True,
    )


def _make_map_data(paths: list[VeloBGPath]) -> VeloBGMapData:
    layer = VeloBGLayer(id="l1", name="test", paths=paths, points=[])
    return VeloBGMapData(
        map_id="test",
        fetched_at=NOW,
        layers=[layer],
        total_paths=len(paths),
        total_points=0,
        kml_size_bytes=100,
        fetch_duration_s=0.1,
    )


def _make_graph_with_edge() -> nx.MultiDiGraph:
    """Minimal graph: node 1 → node 2 with a direct edge."""
    G = nx.MultiDiGraph()
    G.add_node(1, x=23.321, y=42.697)
    G.add_node(2, x=23.322, y=42.698)
    G.add_edge(1, 2, 0, length=150.0)
    return G


class TestVeloBGEnricherApplyAttributes:

    def test_sets_bike_path_true(self):
        enricher  = VeloBGEnricher()
        edge_data = {}
        path      = _make_path(VeloBGPathType.DEDICATED_LANE)
        enricher._apply_path_attributes(edge_data, path)
        assert edge_data["bike_path"] is True

    def test_sets_velobg_path_type(self):
        enricher  = VeloBGEnricher()
        edge_data = {}
        path      = _make_path(VeloBGPathType.DEDICATED_LANE)
        enricher._apply_path_attributes(edge_data, path)
        assert edge_data["velobg_path_type"] == "dedicated_lane"

    def test_sets_bike_path_type_compatible_with_weighting(self):
        enricher = VeloBGEnricher()
        for velobg_type, expected_bpt in _VELOBG_TO_BIKE_PATH_TYPE.items():
            if velobg_type == VeloBGPathType.PROPOSED:
                continue
            edge_data = {}
            path = _make_path(velobg_type)
            enricher._apply_path_attributes(edge_data, path)
            assert edge_data.get("bike_path_type") == expected_bpt, (
                f"Expected bike_path_type={expected_bpt!r} for {velobg_type}"
            )

    def test_no_downgrade(self):
        """Better infrastructure already on edge should not be overwritten."""
        enricher  = VeloBGEnricher()
        edge_data = {
            "velobg_weight_multiplier": 0.25,   # already DEDICATED_LANE quality
            "bike_path": True,
            "velobg_path_type": "dedicated_lane",
        }
        path = _make_path(VeloBGPathType.PAINTED_LANE)   # multiplier=0.6 (worse)
        enricher._apply_path_attributes(edge_data, path)
        # Should not downgrade
        assert edge_data["velobg_weight_multiplier"] == 0.25
        assert edge_data["velobg_path_type"] == "dedicated_lane"

    def test_upgrade_replaces_worse_infrastructure(self):
        """Better new infrastructure should replace worse existing."""
        enricher  = VeloBGEnricher()
        edge_data = {"velobg_weight_multiplier": 0.75}
        path = _make_path(VeloBGPathType.DEDICATED_LANE)   # multiplier=0.3
        enricher._apply_path_attributes(edge_data, path)
        assert edge_data["velobg_weight_multiplier"] == pytest.approx(0.3)


class TestVeloBGEnricherProposedExclusion:

    def test_proposed_paths_not_enriched(self):
        """PROPOSED paths must not modify the graph."""
        G   = _make_graph_with_edge()
        enricher  = VeloBGEnricher()
        settings  = MagicMock()
        map_data  = _make_map_data([_make_path(VeloBGPathType.PROPOSED)])

        enricher.enrich(G, map_data, settings)

        # No edge should have bike_path set
        for _, _, data in G.edges(data=True):
            assert data.get("bike_path") is not True


class TestVeloBGEnricherNodeDistance:

    def test_zero_distance_for_exact_match(self):
        G = nx.MultiDiGraph()
        G.add_node(1, x=23.321, y=42.697)
        dist = VeloBGEnricher._node_distance_m(G, 1, 42.697, 23.321)
        assert dist == pytest.approx(0.0, abs=0.1)

    def test_non_zero_distance_for_offset(self):
        G = nx.MultiDiGraph()
        G.add_node(1, x=23.321, y=42.697)
        dist = VeloBGEnricher._node_distance_m(G, 1, 42.700, 23.321)
        assert dist > 0


class TestVeloBGEnricherGraphEnrichment:

    def test_direct_edge_gets_marked(self):
        G        = _make_graph_with_edge()
        enricher = VeloBGEnricher()
        settings = MagicMock()
        path     = _make_path(VeloBGPathType.DEDICATED_LANE)
        map_data = _make_map_data([path])

        with patch("app.data.velobg.enricher.ox.nearest_nodes") as mock_nn:
            mock_nn.side_effect = [1, 2]
            enricher.enrich(G, map_data, settings)

        assert G[1][2][0].get("bike_path") is True
        assert G[1][2][0].get("bike_path_type") == "alley"

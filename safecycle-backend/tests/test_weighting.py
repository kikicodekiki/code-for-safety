"""
SafeCycle Sofia — Edge weighting unit tests.
Tests every domain rule in compute_edge_weight() and parse_maxspeed().
"""
from __future__ import annotations

import pytest

from app.config import Settings
from app.core.graph.weighting import (
    EdgeWeightResult,
    compute_edge_weight,
    parse_maxspeed,
)


@pytest.fixture
def settings() -> Settings:
    return Settings(
        DATABASE_URL="postgresql+asyncpg://test:test@localhost/test",
        REDIS_URL="redis://localhost:6379/1",
        GOOGLE_MAPS_API_KEY="test",
        FIREBASE_ENABLED=False,
        DEFAULT_SPEED_LIMIT_KMH=50,
        DEFAULT_SURFACE="asphalt",
        MAX_ALLOWED_SPEED_KMH=50,
    )


def base_edge(overrides: dict | None = None) -> dict:
    """Return a minimal valid OSM edge attribute dict."""
    base = {
        "osmid": 999,
        "length": 100.0,
        "highway": "residential",
        "maxspeed": "50",
        "surface": "asphalt",
    }
    if overrides:
        base.update(overrides)
    return base


# ── parse_maxspeed ────────────────────────────────────────────────────────────

class TestParseMaxspeed:

    def test_numeric_string(self):
        assert parse_maxspeed("50") == 50

    def test_plain_int(self):
        assert parse_maxspeed(30) == 30

    def test_mph_conversion(self):
        # 50 mph → 80 km/h
        result = parse_maxspeed("50 mph")
        assert result == 80

    def test_bg_urban(self):
        assert parse_maxspeed("BG:urban") == 50

    def test_bg_urban_lowercase(self):
        assert parse_maxspeed("bg:urban") == 50

    def test_urban_generic(self):
        assert parse_maxspeed("urban") == 50

    def test_walk(self):
        assert parse_maxspeed("walk") == 10

    def test_foot(self):
        assert parse_maxspeed("foot") == 10

    def test_none_returns_default(self, settings):
        assert parse_maxspeed(None, default=settings.DEFAULT_SPEED_LIMIT_KMH) == 50

    def test_none_string_returns_130(self):
        # "none" = no speed limit (autobahn-style) → will be excluded
        result = parse_maxspeed("none")
        assert result == 130

    def test_list_takes_minimum(self):
        assert parse_maxspeed([50, 70, 30]) == 30

    def test_leading_digit_extraction(self):
        # "50;30" OSM format
        assert parse_maxspeed("50;30") == 50


# ── compute_edge_weight — Speed limit rules ───────────────────────────────────

class TestSpeedLimitRules:

    def test_no_maxspeed_defaults_to_50(self, settings):
        """Rule 1: Missing maxspeed → defaults to 50 km/h, flagged."""
        edge = base_edge({"maxspeed": None})
        del edge["maxspeed"]
        result = compute_edge_weight(edge, {}, settings)
        assert result.speed_limit == 50
        assert result.speed_limit_defaulted is True
        assert result.excluded is False

    def test_maxspeed_70_excluded(self, settings):
        """Rule 2: maxspeed > MAX_ALLOWED_SPEED_KMH → weight=inf."""
        edge = base_edge({"maxspeed": "70"})
        result = compute_edge_weight(edge, {}, settings)
        assert result.weight == float("inf")
        assert result.excluded is True
        assert result.exclusion_reason == "speed_limit"

    def test_maxspeed_exactly_50_not_excluded(self, settings):
        """maxspeed=50 is exactly at the limit → included."""
        edge = base_edge({"maxspeed": "50"})
        result = compute_edge_weight(edge, {}, settings)
        assert result.excluded is False
        assert result.weight < float("inf")


# ── compute_edge_weight — Highway type rules ──────────────────────────────────

class TestHighwayTypeRules:

    def test_motorway_excluded(self, settings):
        """Rule 2 (highway): motorway always excluded."""
        edge = base_edge({"highway": "motorway"})
        result = compute_edge_weight(edge, {}, settings)
        assert result.weight == float("inf")
        assert result.excluded is True
        assert result.exclusion_reason == "highway_type"

    def test_motorway_link_excluded(self, settings):
        edge = base_edge({"highway": "motorway_link"})
        result = compute_edge_weight(edge, {}, settings)
        assert result.excluded is True

    def test_trunk_excluded(self, settings):
        edge = base_edge({"highway": "trunk"})
        result = compute_edge_weight(edge, {}, settings)
        assert result.excluded is True

    def test_residential_not_excluded(self, settings):
        edge = base_edge({"highway": "residential"})
        result = compute_edge_weight(edge, {}, settings)
        assert result.excluded is False


# ── compute_edge_weight — Surface rules ───────────────────────────────────────

class TestSurfaceRules:

    def test_no_surface_defaults_to_asphalt(self, settings):
        """Rule 3: Missing surface → default asphalt, surface_defaulted=True."""
        edge = base_edge()
        del edge["surface"]
        result = compute_edge_weight(edge, {}, settings)
        assert result.surface == "asphalt"
        assert result.surface_defaulted is True

    def test_asphalt_neutral_multiplier(self, settings):
        """Asphalt gives a factor of 1.0 — no penalty."""
        asphalt = compute_edge_weight(base_edge({"surface": "asphalt"}), {}, settings)
        missing  = compute_edge_weight(base_edge(), {}, settings)
        del_edge = base_edge()
        del del_edge["surface"]
        defaulted = compute_edge_weight(del_edge, {}, settings)
        # All three should give the same weight (1.0 factor)
        assert abs(asphalt.weight - defaulted.weight) < 0.001

    def test_cobblestone_penalty(self, settings):
        """Cobblestone factor = 1.8 vs asphalt 1.0."""
        asphalt     = compute_edge_weight(base_edge({"surface": "asphalt"}), {}, settings)
        cobblestone = compute_edge_weight(base_edge({"surface": "cobblestone"}), {}, settings)
        ratio = cobblestone.weight / asphalt.weight
        assert abs(ratio - 1.8) < 0.01

    def test_mud_highest_surface_penalty(self, settings):
        asphalt = compute_edge_weight(base_edge({"surface": "asphalt"}), {}, settings)
        mud     = compute_edge_weight(base_edge({"surface": "mud"}), {}, settings)
        assert mud.weight > asphalt.weight * 2.5


# ── compute_edge_weight — Bike infrastructure bonus ──────────────────────────

class TestBikeInfrastructureBonus:

    def test_bike_alley_factor(self, settings):
        """Rule 4: Sofia bike alley → factor 0.25 (strongest preference)."""
        normal = compute_edge_weight(base_edge(), {}, settings)
        alley  = compute_edge_weight(
            base_edge({"bike_path": True, "bike_path_type": "alley"}), {}, settings
        )
        # alley weight should be ~0.25x the normal weight
        ratio = alley.weight / normal.weight
        assert abs(ratio - 0.25) < 0.05

    def test_recreational_route_factor(self, settings):
        normal       = compute_edge_weight(base_edge(), {}, settings)
        recreational = compute_edge_weight(
            base_edge({"bike_path": True, "bike_path_type": "recreational"}), {}, settings
        )
        ratio = recreational.weight / normal.weight
        assert abs(ratio - 0.30) < 0.05

    def test_connecting_route_factor(self, settings):
        normal     = compute_edge_weight(base_edge(), {}, settings)
        connecting = compute_edge_weight(
            base_edge({"bike_path": True, "bike_path_type": "connecting"}), {}, settings
        )
        ratio = connecting.weight / normal.weight
        assert abs(ratio - 0.55) < 0.05

    def test_bike_path_flag_set(self, settings):
        result = compute_edge_weight(
            base_edge({"bike_path": True, "bike_path_type": "alley"}), {}, settings
        )
        assert result.bike_path is True

    def test_no_bike_path_factor_is_one(self, settings):
        """Without any bike infrastructure, bike_factor = 1.0."""
        result = compute_edge_weight(base_edge(), {}, settings)
        assert result.bike_path is False


# ── compute_edge_weight — Hazard penalty ─────────────────────────────────────

class TestHazardPenalty:

    def test_fresh_hazard_adds_2(self, settings):
        """A brand-new hazard (0 h old) adds +2.0 penalty."""
        no_hazard   = compute_edge_weight(base_edge(), {}, settings)
        with_hazard = compute_edge_weight(base_edge(), {999: 2.0}, settings)
        assert abs((with_hazard.weight - no_hazard.weight) - 2.0) < 0.001

    def test_5h_hazard_adds_1(self, settings):
        """5-hour-old hazard: penalty = 2.0 - 5*0.2 = 1.0."""
        penalty_5h = max(0.0, 2.0 - 5 * 0.2)
        no_hazard   = compute_edge_weight(base_edge(), {}, settings)
        with_hazard = compute_edge_weight(base_edge(), {999: penalty_5h}, settings)
        assert abs((with_hazard.weight - no_hazard.weight) - 1.0) < 0.001

    def test_10h_hazard_adds_0(self, settings):
        """10-hour-old hazard: penalty = 0.0, no effect."""
        penalty_10h = max(0.0, 2.0 - 10 * 0.2)
        no_hazard   = compute_edge_weight(base_edge(), {}, settings)
        with_hazard = compute_edge_weight(base_edge(), {999: penalty_10h}, settings)
        assert abs(with_hazard.weight - no_hazard.weight) < 0.001

    def test_hazard_on_different_edge_no_effect(self, settings):
        """Hazard on edge 888 does not affect edge 999."""
        no_hazard   = compute_edge_weight(base_edge(), {}, settings)
        with_hazard = compute_edge_weight(base_edge(), {888: 2.0}, settings)
        assert abs(with_hazard.weight - no_hazard.weight) < 0.001

    def test_hazard_does_not_exclude_edge(self, settings):
        """Hazard penalty is additive — cannot make a finite edge infinite."""
        result = compute_edge_weight(base_edge(), {999: 100.0}, settings)
        assert result.weight < float("inf")
        assert result.excluded is False

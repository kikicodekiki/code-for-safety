"""Tests for VeloBGClassifier."""
from __future__ import annotations

import pytest

from app.data.velobg.classifier import VeloBGClassifier, COLOUR_MAP
from app.models.schemas.velobg import VeloBGPathType


@pytest.fixture()
def clf():
    return VeloBGClassifier()


class TestColourClassification:

    def test_exact_green_is_dedicated_lane(self, clf):
        result = clf.classify(None, None, None, "#0F9D58", None)
        assert result == VeloBGPathType.DEDICATED_LANE

    def test_exact_orange_is_proposed(self, clf):
        result = clf.classify(None, None, None, "#FF9800", None)
        assert result == VeloBGPathType.PROPOSED

    def test_approximate_colour_match(self, clf):
        # Slightly off-green — should still match DEDICATED_LANE
        result = clf.classify(None, None, None, "#10A060", None)
        assert result == VeloBGPathType.DEDICATED_LANE

    def test_no_colour_match_falls_through(self, clf):
        # Colour very far from any known colour → no colour match
        result = clf.classify(None, None, None, "#808080", None)
        # Should fall through to UNKNOWN (no layer/name either)
        assert result == VeloBGPathType.UNKNOWN

    def test_colour_takes_priority_over_layer(self, clf):
        # Green colour (dedicated) but layer says proposed
        result = clf.classify(None, None, "планирана", "#0F9D58", None)
        assert result == VeloBGPathType.DEDICATED_LANE


class TestLayerClassification:

    def test_bulgarian_dedicated_lane_layer(self, clf):
        result = clf.classify(None, None, "велоалея", None, None)
        assert result == VeloBGPathType.DEDICATED_LANE

    def test_bulgarian_proposed_layer(self, clf):
        result = clf.classify(None, None, "планирана магистрала", None, None)
        assert result == VeloBGPathType.PROPOSED

    def test_english_greenway_layer(self, clf):
        result = clf.classify(None, None, "City Greenway Network", None, None)
        assert result == VeloBGPathType.GREENWAY

    def test_case_insensitive_layer_match(self, clf):
        result = clf.classify(None, None, "ВЕЛОЛЕНТА", None, None)
        assert result == VeloBGPathType.PAINTED_LANE


class TestNameKeywordClassification:

    def test_name_with_велоалея(self, clf):
        result = clf.classify("велоалея борисова градина", None, None, None, None)
        assert result == VeloBGPathType.DEDICATED_LANE

    def test_name_with_proposed_keyword(self, clf):
        result = clf.classify("proposed bike path section", None, None, None, None)
        assert result == VeloBGPathType.PROPOSED

    def test_description_fallback(self, clf):
        result = clf.classify(None, "shared path along river", None, None, None)
        assert result == VeloBGPathType.SHARED_PATH


class TestUnknownFallback:

    def test_no_signals_returns_unknown(self, clf):
        result = clf.classify(None, None, None, None, None)
        assert result == VeloBGPathType.UNKNOWN

    def test_unrecognised_text_returns_unknown(self, clf):
        result = clf.classify("random segment 42", "nothing useful here", "misc", None, None)
        assert result == VeloBGPathType.UNKNOWN


class TestColourHelpers:

    def test_hex_to_rgb(self):
        assert VeloBGClassifier._hex_to_rgb("#FF0000") == (255, 0, 0)
        assert VeloBGClassifier._hex_to_rgb("#00FF00") == (0, 255, 0)
        assert VeloBGClassifier._hex_to_rgb("#0000FF") == (0, 0, 255)

    def test_hex_to_rgb_invalid_raises(self):
        with pytest.raises(ValueError):
            VeloBGClassifier._hex_to_rgb("#FFF")


class TestColourMapUpdate:

    def test_update_colour_map(self, clf):
        custom_colour = "#ABCDEF"
        clf.update_colour_map(custom_colour, VeloBGPathType.GREENWAY)
        assert COLOUR_MAP[custom_colour.upper()] == VeloBGPathType.GREENWAY
        # Verify it's used in classification
        result = clf.classify(None, None, None, custom_colour, None)
        assert result == VeloBGPathType.GREENWAY

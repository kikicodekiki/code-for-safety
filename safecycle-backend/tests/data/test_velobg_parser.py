"""Tests for VeloBGParser."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.core.exceptions import VeloBGParseError
from app.data.velobg.parser import VeloBGParser
from app.models.schemas.velobg import VeloBGPath, VeloBGPoint, VeloBGPathType


NOW = datetime.now(timezone.utc)

# Minimal valid KML with one LineString and one Point
SAMPLE_KML = """\
<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Style id="s_green">
      <LineStyle>
        <color>ff00FF00</color>
        <width>4</width>
      </LineStyle>
    </Style>
    <StyleMap id="sm_green">
      <Pair>
        <key>normal</key>
        <styleUrl>#s_green</styleUrl>
      </Pair>
    </StyleMap>
    <Folder>
      <name>велоалея</name>
      <Placemark>
        <name>Test Bike Lane</name>
        <styleUrl>#sm_green</styleUrl>
        <LineString>
          <coordinates>
            23.3219,42.6977,0 23.3230,42.6985,0 23.3245,42.6990,0
          </coordinates>
        </LineString>
      </Placemark>
      <Placemark>
        <name>Bike Repair Station</name>
        <styleUrl>#sm_green</styleUrl>
        <Point>
          <coordinates>23.3219,42.6977,0</coordinates>
        </Point>
      </Placemark>
    </Folder>
  </Document>
</kml>"""


# KML without namespace prefix
NO_NS_KML = """\
<?xml version="1.0" encoding="UTF-8"?>
<kml>
  <Document>
    <Folder>
      <name>test</name>
      <Placemark>
        <LineString>
          <coordinates>23.31,42.69,0 23.32,42.70,0</coordinates>
        </LineString>
      </Placemark>
    </Folder>
  </Document>
</kml>"""


@pytest.fixture()
def parser():
    return VeloBGParser()


class TestVeloBGParserBasic:

    def test_parse_returns_map_data(self, parser):
        result = parser.parse(SAMPLE_KML, fetched_at=NOW)
        assert result.map_id == "1iQ1EYaAvinM_vnupk6w0twyeYOEN9o4"
        assert result.fetched_at == NOW

    def test_parse_finds_one_layer(self, parser):
        result = parser.parse(SAMPLE_KML, fetched_at=NOW)
        assert len(result.layers) == 1
        assert result.layers[0].name == "велоалея"

    def test_parse_finds_line_and_point(self, parser):
        result = parser.parse(SAMPLE_KML, fetched_at=NOW)
        layer = result.layers[0]
        assert len(layer.paths)  == 1
        assert len(layer.points) == 1

    def test_path_has_correct_name(self, parser):
        result = parser.parse(SAMPLE_KML, fetched_at=NOW)
        path = result.layers[0].paths[0]
        assert path.name == "Test Bike Lane"

    def test_path_coordinates_are_lat_lon_order(self, parser):
        result = parser.parse(SAMPLE_KML, fetched_at=NOW)
        coord = result.layers[0].paths[0].coordinates[0]
        # KML lon,lat → our lat,lon
        assert coord.lat == pytest.approx(42.6977, abs=1e-4)
        assert coord.lon == pytest.approx(23.3219, abs=1e-4)

    def test_path_length_is_positive(self, parser):
        result = parser.parse(SAMPLE_KML, fetched_at=NOW)
        assert result.layers[0].paths[0].length_m > 0

    def test_point_type_classified_as_repair(self, parser):
        result = parser.parse(SAMPLE_KML, fetched_at=NOW)
        assert result.layers[0].points[0].point_type == "repair"

    def test_total_counts(self, parser):
        result = parser.parse(SAMPLE_KML, fetched_at=NOW)
        assert result.total_paths  == 1
        assert result.total_points == 1


class TestVeloBGParserColourExtraction:

    def test_colour_extracted_from_style(self, parser):
        result = parser.parse(SAMPLE_KML, fetched_at=NOW)
        # KML "ff00FF00" → AABBGGRR → #00FF00 (green)
        path = result.layers[0].paths[0]
        assert path.colour_hex == "#00FF00"

    def test_kml_colour_conversion(self, parser):
        # "ff0000ff" → BB=00, GG=00, RR=ff → #FF0000 (red)
        assert VeloBGParser._kml_colour_to_hex("ff0000ff") == "#FF0000"
        # "ff14F000" → BB=14, GG=F0, RR=00 → #00F014 (green-ish)
        assert VeloBGParser._kml_colour_to_hex("ff14F000") == "#00F014"


class TestVeloBGParserNoNamespace:

    def test_parses_kml_without_ns_prefix(self, parser):
        result = parser.parse(NO_NS_KML, fetched_at=NOW)
        assert result.total_paths == 1


class TestVeloBGParserCoordinateFilter:

    def test_coordinates_outside_sofia_are_rejected(self, parser):
        out_of_bounds_kml = """\
<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Folder><name>test</name>
      <Placemark>
        <LineString>
          <coordinates>
            10.0,50.0,0 10.1,50.1,0
          </coordinates>
        </LineString>
      </Placemark>
    </Folder>
  </Document>
</kml>"""
        result = parser.parse(out_of_bounds_kml, fetched_at=NOW)
        # All coordinates are outside Sofia bbox → path rejected (< 2 coords)
        assert result.total_paths == 0

    def test_mixed_valid_invalid_coords(self, parser):
        kml = """\
<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Folder><name>test</name>
      <Placemark>
        <LineString>
          <coordinates>
            23.31,42.69,0  10.0,50.0,0  23.32,42.70,0
          </coordinates>
        </LineString>
      </Placemark>
    </Folder>
  </Document>
</kml>"""
        result = parser.parse(kml, fetched_at=NOW)
        # Two valid coords survive → path is kept
        assert result.total_paths == 1
        assert len(result.layers[0].paths[0].coordinates) == 2


class TestVeloBGParserErrors:

    def test_malformed_xml_raises_parse_error(self, parser):
        with pytest.raises(VeloBGParseError, match="malformed"):
            parser.parse("<kml><broken", fetched_at=NOW)


class TestVeloBGParserUsablePaths:

    def test_all_paths_property(self, parser):
        result = parser.parse(SAMPLE_KML, fetched_at=NOW)
        assert len(result.all_paths) == result.total_paths

    def test_usable_paths_excludes_proposed(self, parser):
        proposed_kml = SAMPLE_KML.replace("велоалея", "планирана")
        result = parser.parse(proposed_kml, fetched_at=NOW)
        # Layer name "планирана" → PROPOSED → not usable
        usable = result.usable_paths
        for p in usable:
            assert p.path_type != VeloBGPathType.PROPOSED

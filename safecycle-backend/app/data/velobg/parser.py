"""
VeloBGParser — parses raw KML XML into structured VeloBGMapData.

KML Structure from Google My Maps:
    <kml>
      <Document>
        <name>VeloBG Map Name</name>
        <Folder>                          ← One per layer in My Maps
          <name>Layer name</name>
          <Placemark>                     ← One per feature
            <name>Feature name</name>
            <description>...</description>
            <styleUrl>#style_id</styleUrl>
            <LineString>
              <coordinates>
                lon,lat,alt lon,lat,alt ...
              </coordinates>
            </LineString>
          </Placemark>
        </Folder>
        <Style id="style_id">
          <LineStyle>
            <color>aabbggrr</color>       ← KML colour in AABBGGRR format
            <width>3</width>
          </LineStyle>
        </Style>
      </Document>
    </kml>

Coordinate order in KML is ALWAYS lon,lat,alt (not lat,lon).
This parser converts to lat,lon for all output objects.

Colour format in KML is AABBGGRR (alpha, blue, green, red in hex).
This parser converts to standard #RRGGBB for human readability.
"""
from __future__ import annotations

import hashlib
import math
import time
import uuid
from datetime import datetime
from typing import Optional
from xml.etree import ElementTree as ET

import structlog

from app.data.velobg.classifier import VeloBGClassifier
from app.data.velobg.fetcher import VELOBG_MAP_ID
from app.models.schemas.velobg import (
    VeloBGCoordinate, VeloBGLayer, VeloBGMapData,
    VeloBGPath, VeloBGPathType, VeloBGPoint,
)

logger = structlog.get_logger(__name__)

KML_NS = "http://www.opengis.net/kml/2.2"
GX_NS  = "http://www.google.com/kml/ext/2.2"


class VeloBGParser:

    def __init__(self) -> None:
        self.classifier = VeloBGClassifier()

    def parse(
        self,
        kml_content:    str,
        fetched_at:     datetime,
        fetch_duration: float = 0.0,
    ) -> VeloBGMapData:
        """
        Parses a complete KML string into a VeloBGMapData object.

        Raises
        ------
        VeloBGParseError
            If the XML is malformed or doesn't match expected KML structure.
        """
        start = time.monotonic()

        try:
            root = ET.fromstring(kml_content)
        except ET.ParseError as e:
            from app.core.exceptions import VeloBGParseError
            raise VeloBGParseError(f"KML XML is malformed: {e}") from e

        ns = self._detect_namespace(root)
        styles = self._extract_styles(root, ns)

        layers: list[VeloBGLayer] = []
        document = root.find(f"{ns}Document") or root

        folders = document.findall(f"{ns}Folder")
        if not folders:
            folders_synthetic = True
            folders = [document]
            logger.warning("velobg_no_folders_found_using_document_root")
        else:
            folders_synthetic = False

        for folder in folders:
            layer = self._parse_folder(folder, ns, styles, folders_synthetic)
            if layer.paths or layer.points:
                layers.append(layer)

        # Also parse top-level placemarks not inside any Folder
        if not folders_synthetic:
            top_level = self._parse_top_level_placemarks(document, ns, styles)
            if top_level.paths or top_level.points:
                layers.append(top_level)

        total_paths  = sum(len(l.paths)  for l in layers)
        total_points = sum(len(l.points) for l in layers)
        elapsed      = time.monotonic() - start

        logger.info(
            "velobg_kml_parsed",
            layers=len(layers),
            total_paths=total_paths,
            total_points=total_points,
            kml_size_bytes=len(kml_content),
            parse_time_s=round(elapsed, 3),
        )

        return VeloBGMapData(
            map_id=VELOBG_MAP_ID,
            fetched_at=fetched_at,
            layers=layers,
            total_paths=total_paths,
            total_points=total_points,
            kml_size_bytes=len(kml_content),
            fetch_duration_s=fetch_duration,
        )

    def _detect_namespace(self, root: ET.Element) -> str:
        tag = root.tag
        if tag.startswith("{"):
            return tag.split("}")[0] + "}"
        return ""

    def _extract_styles(self, root: ET.Element, ns: str) -> dict[str, dict]:
        """
        Extracts all <Style> and <StyleMap> elements into a lookup dict.

        Returns
        -------
        dict[str, dict]
            Maps style_id → { "line_colour": "#RRGGBB", "line_width": float,
                               "icon_href": str | None }
        """
        styles: dict[str, dict] = {}
        document = root.find(f"{ns}Document") or root

        for style_elem in document.findall(f"{ns}Style"):
            style_id = style_elem.get("id", "")
            if not style_id:
                continue

            style_data: dict = {"line_colour": None, "line_width": 2.0, "icon_href": None}

            line_style = style_elem.find(f"{ns}LineStyle")
            if line_style is not None:
                colour_elem = line_style.find(f"{ns}color")
                width_elem  = line_style.find(f"{ns}width")
                if colour_elem is not None and colour_elem.text:
                    style_data["line_colour"] = self._kml_colour_to_hex(colour_elem.text)
                if width_elem is not None and width_elem.text:
                    try:
                        style_data["line_width"] = float(width_elem.text)
                    except ValueError:
                        pass

            icon_style = style_elem.find(f"{ns}IconStyle")
            if icon_style is not None:
                icon = icon_style.find(f"{ns}Icon")
                if icon is not None:
                    href = icon.find(f"{ns}href")
                    if href is not None:
                        style_data["icon_href"] = href.text

            styles[f"#{style_id}"] = style_data

        # Resolve StyleMap → Normal style
        for stylemap_elem in document.findall(f"{ns}StyleMap"):
            map_id = stylemap_elem.get("id", "")
            for pair in stylemap_elem.findall(f"{ns}Pair"):
                key_elem       = pair.find(f"{ns}key")
                style_url_elem = pair.find(f"{ns}styleUrl")
                if (key_elem is not None and key_elem.text == "normal"
                        and style_url_elem is not None):
                    resolved = styles.get(style_url_elem.text, {})
                    styles[f"#{map_id}"] = resolved
                    break

        return styles

    def _parse_folder(
        self,
        folder:      ET.Element,
        ns:          str,
        styles:      dict[str, dict],
        is_document: bool = False,
    ) -> VeloBGLayer:
        name_elem  = folder.find(f"{ns}name")
        layer_name = (
            name_elem.text.strip()
            if name_elem is not None and name_elem.text
            else "Unknown Layer"
        )
        layer_id = hashlib.md5(layer_name.encode()).hexdigest()[:8]

        paths:  list[VeloBGPath]  = []
        points: list[VeloBGPoint] = []

        for placemark in folder.findall(f"{ns}Placemark"):
            result = self._parse_placemark(placemark, ns, styles, layer_name)
            if isinstance(result, VeloBGPath):
                paths.append(result)
            elif isinstance(result, VeloBGPoint):
                points.append(result)

        return VeloBGLayer(id=layer_id, name=layer_name, paths=paths, points=points)

    def _parse_top_level_placemarks(
        self,
        document: ET.Element,
        ns:       str,
        styles:   dict[str, dict],
    ) -> VeloBGLayer:
        paths:  list[VeloBGPath]  = []
        points: list[VeloBGPoint] = []

        for placemark in document.findall(f"{ns}Placemark"):
            result = self._parse_placemark(placemark, ns, styles, "Top Level")
            if isinstance(result, VeloBGPath):
                paths.append(result)
            elif isinstance(result, VeloBGPoint):
                points.append(result)

        return VeloBGLayer(id="top_level", name="Top Level", paths=paths, points=points)

    def _parse_placemark(
        self,
        placemark:  ET.Element,
        ns:         str,
        styles:     dict[str, dict],
        layer_name: str,
    ) -> Optional[VeloBGPath | VeloBGPoint]:
        name_elem = placemark.find(f"{ns}name")
        desc_elem = placemark.find(f"{ns}description")
        name      = name_elem.text.strip() if name_elem is not None and name_elem.text else None
        desc      = desc_elem.text.strip() if desc_elem is not None and desc_elem.text else None

        style_url_elem = placemark.find(f"{ns}styleUrl")
        style_id  = style_url_elem.text if style_url_elem is not None else None
        style     = styles.get(style_id, {}) if style_id else {}
        colour    = style.get("line_colour")

        placemark_id = (
            placemark.get("id")
            or hashlib.md5(f"{name}{layer_name}".encode()).hexdigest()[:12]
        )

        # ── LineString → cycling path ──────────────────────────────────────
        line_string = (
            placemark.find(f"{ns}LineString")
            or placemark.find(f"{ns}MultiGeometry/{ns}LineString")
        )
        if line_string is not None:
            coords_elem = line_string.find(f"{ns}coordinates")
            if coords_elem is None or not coords_elem.text:
                return None

            coordinates = self._parse_coordinates(coords_elem.text)
            if len(coordinates) < 2:
                return None

            path_type = self.classifier.classify(
                name=name,
                description=desc,
                layer_name=layer_name,
                colour_hex=colour,
                style_id=style_id,
            )
            length_m = self._compute_length(coordinates)

            return VeloBGPath(
                id=str(uuid.uuid4()),
                name=name,
                description=desc,
                path_type=path_type,
                coordinates=coordinates,
                layer_name=layer_name,
                style_id=style_id,
                colour_hex=colour,
                length_m=length_m,
                is_bidirectional=True,
                source_placemark_id=placemark_id,
            )

        # ── Point → POI ───────────────────────────────────────────────────
        point_elem = placemark.find(f"{ns}Point")
        if point_elem is not None:
            coords_elem = point_elem.find(f"{ns}coordinates")
            if coords_elem is None or not coords_elem.text:
                return None

            coords = self._parse_coordinates(coords_elem.text)
            if not coords:
                return None

            point_type = self._classify_point(name, desc, style.get("icon_href"))

            return VeloBGPoint(
                id=str(uuid.uuid4()),
                name=name,
                description=desc,
                lat=coords[0].lat,
                lon=coords[0].lon,
                layer_name=layer_name,
                point_type=point_type,
            )

        return None

    def _parse_coordinates(self, raw: str) -> list[VeloBGCoordinate]:
        """
        Parses KML coordinate string into VeloBGCoordinate list.

        KML format: "lon,lat,alt lon,lat,alt ..." (space-separated tuples)
        Converts from KML lon,lat order to internal lat,lon order.
        Rejects coordinates outside the Sofia bounding box.
        """
        coordinates: list[VeloBGCoordinate] = []

        for token in raw.strip().split():
            token = token.strip()
            if not token:
                continue
            parts = token.split(",")
            if len(parts) < 2:
                continue
            try:
                lon = float(parts[0])
                lat = float(parts[1])
                alt = float(parts[2]) if len(parts) > 2 else 0.0

                # Sanity check: Sofia is roughly 42.5–43.0°N, 23.0–23.6°E
                if not (42.0 < lat < 43.5 and 22.5 < lon < 24.0):
                    logger.debug(
                        "velobg_coordinate_outside_sofia_bbox",
                        lat=lat, lon=lon,
                    )
                    continue

                coordinates.append(VeloBGCoordinate(lat=lat, lon=lon, alt=alt))
            except (ValueError, IndexError):
                logger.debug("velobg_coordinate_parse_failure", token=token)
                continue

        return coordinates

    def _compute_length(self, coords: list[VeloBGCoordinate]) -> float:
        """Computes path length in metres using the Haversine formula."""
        total = 0.0
        for i in range(len(coords) - 1):
            total += self._haversine_m(
                coords[i].lat, coords[i].lon,
                coords[i + 1].lat, coords[i + 1].lon,
            )
        return total

    @staticmethod
    def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        R    = 6_371_000
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlam = math.radians(lon2 - lon1)
        a    = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
        return 2 * R * math.asin(math.sqrt(a))

    @staticmethod
    def _kml_colour_to_hex(kml_colour: str) -> str:
        """
        Converts KML AABBGGRR colour to standard #RRGGBB.

        KML byte order: AA=alpha, BB=blue, GG=green, RR=red.
        Example: "ff0000ff" → "#FF0000" (red)
        """
        c = kml_colour.strip().lstrip("#")
        if len(c) != 8:
            return "#888888"
        bb = c[2:4]
        gg = c[4:6]
        rr = c[6:8]
        return f"#{rr.upper()}{gg.upper()}{bb.upper()}"

    @staticmethod
    def _classify_point(
        name:      Optional[str],
        desc:      Optional[str],
        icon_href: Optional[str],
    ) -> str:
        text = f"{(name or '')} {(desc or '')}".lower()
        if any(kw in text for kw in ["repair", "поправк", "инструмент"]):
            return "repair"
        if any(kw in text for kw in ["rental", "rent", "наем", "велосипеди под наем"]):
            return "rental"
        if any(kw in text for kw in ["parking", "паркинг", "bike rack"]):
            return "parking"
        return "landmark"

"""
VeloBGClassifier — infers VeloBGPathType from available KML metadata.

Classification is attempted in priority order:
    1. Colour-based classification (most reliable — VeloBG uses consistent colours)
    2. Layer name classification (second most reliable)
    3. Placemark name classification (text matching)
    4. Description text classification
    5. Default: UNKNOWN

Run scripts/inspect_velobg_kml.py to discover the actual colours used
and update COLOUR_MAP accordingly.
"""
from __future__ import annotations

from typing import Optional

import structlog

from app.models.schemas.velobg import VeloBGPathType

logger = structlog.get_logger(__name__)


# Observed VeloBG colour scheme — update after running inspect_velobg_kml.py
# Keys are uppercase #RRGGBB hex strings
COLOUR_MAP: dict[str, VeloBGPathType] = {
    # Green shades → dedicated lanes (safest)
    "#00FF00": VeloBGPathType.DEDICATED_LANE,
    "#00E400": VeloBGPathType.DEDICATED_LANE,
    "#0F9D58": VeloBGPathType.DEDICATED_LANE,
    "#1E8449": VeloBGPathType.DEDICATED_LANE,
    "#27AE60": VeloBGPathType.DEDICATED_LANE,

    # Blue shades → painted lanes / shared paths
    "#4285F4": VeloBGPathType.PAINTED_LANE,
    "#1A73E8": VeloBGPathType.PAINTED_LANE,
    "#2196F3": VeloBGPathType.PAINTED_LANE,
    "#039BE5": VeloBGPathType.SHARED_PATH,

    # Teal / cyan → greenways
    "#00BCD4": VeloBGPathType.GREENWAY,
    "#009688": VeloBGPathType.GREENWAY,
    "#26C6DA": VeloBGPathType.GREENWAY,

    # Orange / yellow → proposed or shared
    "#FF9800": VeloBGPathType.PROPOSED,
    "#FFC107": VeloBGPathType.PROPOSED,
    "#FFEB3B": VeloBGPathType.PROPOSED,
    "#F4B400": VeloBGPathType.PROPOSED,

    # Red → off-road / caution
    "#F44336": VeloBGPathType.OFF_ROAD,
    "#E53935": VeloBGPathType.OFF_ROAD,
    "#DB4437": VeloBGPathType.OFF_ROAD,

    # Brown / earth tones → off-road trails
    "#795548": VeloBGPathType.OFF_ROAD,
    "#8D6E63": VeloBGPathType.OFF_ROAD,
}

# Colour distance threshold — allow approximate matches for similar shades
COLOUR_MATCH_THRESHOLD = 40    # Euclidean RGB distance


# Layer name → path type (Bulgarian and English)
LAYER_NAME_MAP: dict[str, VeloBGPathType] = {
    # Bulgarian
    "велоалея":              VeloBGPathType.DEDICATED_LANE,
    "велосипедна алея":      VeloBGPathType.DEDICATED_LANE,
    "обособена велолента":   VeloBGPathType.DEDICATED_LANE,
    "велолента":             VeloBGPathType.PAINTED_LANE,
    "споделена пътека":      VeloBGPathType.SHARED_PATH,
    "зелен коридор":         VeloBGPathType.GREENWAY,
    "паркова алея":          VeloBGPathType.GREENWAY,
    "планирана":             VeloBGPathType.PROPOSED,
    "проектирана":           VeloBGPathType.PROPOSED,
    "предстоящо":            VeloBGPathType.PROPOSED,
    "предстои":              VeloBGPathType.PROPOSED,
    "предвидена":            VeloBGPathType.PROPOSED,
    "черен път":             VeloBGPathType.OFF_ROAD,
    # English equivalents
    "dedicated lane":        VeloBGPathType.DEDICATED_LANE,
    "bike lane":             VeloBGPathType.PAINTED_LANE,
    "shared path":           VeloBGPathType.SHARED_PATH,
    "greenway":              VeloBGPathType.GREENWAY,
    "proposed":              VeloBGPathType.PROPOSED,
    "planned":               VeloBGPathType.PROPOSED,
    "off-road":              VeloBGPathType.OFF_ROAD,
    "trail":                 VeloBGPathType.OFF_ROAD,
}

# Placemark name keywords → path type
NAME_KEYWORD_MAP: list[tuple[list[str], VeloBGPathType]] = [
    (["велоалея", "bike path", "cycle path", "dedicated"],          VeloBGPathType.DEDICATED_LANE),
    (["велолента", "bike lane", "cycle lane", "painted"],           VeloBGPathType.PAINTED_LANE),
    (["споделена", "shared", "пешеходна"],                          VeloBGPathType.SHARED_PATH),
    (["паркова", "парк", "greenway", "park", "borisova",
      "борисова", "river"],                                          VeloBGPathType.GREENWAY),
    (["планирана", "проект", "предстои", "proposed",
      "planned", "future"],                                          VeloBGPathType.PROPOSED),
    (["черен", "off-road", "trail", "dirt", "горски"],              VeloBGPathType.OFF_ROAD),
]


class VeloBGClassifier:

    def classify(
        self,
        name:        Optional[str],
        description: Optional[str],
        layer_name:  Optional[str],
        colour_hex:  Optional[str],
        style_id:    Optional[str],
    ) -> VeloBGPathType:
        """
        Classifies a path into a VeloBGPathType using all available signals.
        Returns the highest-confidence classification found, or UNKNOWN.
        """
        # 1. Colour-based (highest confidence)
        if colour_hex:
            colour_match = self._match_colour(colour_hex)
            if colour_match:
                logger.debug(
                    "velobg_classified_by_colour",
                    colour=colour_hex,
                    result=colour_match.value,
                )
                return colour_match

        # 2. Layer name
        if layer_name:
            layer_match = self._match_layer_name(layer_name)
            if layer_match:
                logger.debug(
                    "velobg_classified_by_layer",
                    layer=layer_name,
                    result=layer_match.value,
                )
                return layer_match

        # 3. Placemark name keywords
        if name:
            name_match = self._match_keywords(name)
            if name_match:
                return name_match

        # 4. Description keywords
        if description:
            desc_match = self._match_keywords(description)
            if desc_match:
                return desc_match

        logger.debug(
            "velobg_classification_unknown",
            name=name,
            layer=layer_name,
            colour=colour_hex,
        )
        return VeloBGPathType.UNKNOWN

    def _match_colour(self, colour_hex: str) -> Optional[VeloBGPathType]:
        normalised = "#" + colour_hex.upper().lstrip("#")

        # Exact match
        if normalised in COLOUR_MAP:
            return COLOUR_MAP[normalised]

        # Approximate match via Euclidean RGB distance
        try:
            r1, g1, b1 = self._hex_to_rgb(normalised)
        except ValueError:
            return None

        best_type:     Optional[VeloBGPathType] = None
        best_distance: float                    = float("inf")

        for mapped_colour, path_type in COLOUR_MAP.items():
            try:
                r2, g2, b2 = self._hex_to_rgb(mapped_colour)
                distance   = ((r1-r2)**2 + (g1-g2)**2 + (b1-b2)**2) ** 0.5
                if distance < best_distance:
                    best_distance = distance
                    best_type     = path_type
            except ValueError:
                continue

        if best_distance <= COLOUR_MATCH_THRESHOLD:
            return best_type

        return None

    def _match_layer_name(self, layer_name: str) -> Optional[VeloBGPathType]:
        lower = layer_name.lower().strip()
        for keyword, path_type in LAYER_NAME_MAP.items():
            if keyword in lower:
                return path_type
        return None

    def _match_keywords(self, text: str) -> Optional[VeloBGPathType]:
        lower = text.lower()
        for keywords, path_type in NAME_KEYWORD_MAP:
            if any(kw in lower for kw in keywords):
                return path_type
        return None

    @staticmethod
    def _hex_to_rgb(hex_colour: str) -> tuple[int, int, int]:
        h = hex_colour.lstrip("#")
        if len(h) != 6:
            raise ValueError(f"Invalid hex colour: {hex_colour}")
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    def update_colour_map(self, colour: str, path_type: VeloBGPathType) -> None:
        """Allows runtime updates to the colour map from the admin API."""
        COLOUR_MAP["#" + colour.upper().lstrip("#")] = path_type
        logger.info(
            "velobg_colour_map_updated",
            colour=colour,
            path_type=path_type.value,
        )

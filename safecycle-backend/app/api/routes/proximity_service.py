from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from .models import CrossroadHit, ZoneHit, ZoneType

log = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

CROSSROAD_RADIUS_M:   float = 15.0   # GPS drift buffer
AWARENESS_RADIUS_M:   float = 80.0   # user gets ~4 s warning at 20 km/h
HAZARD_ALERT_RADIUS_M: float = 50.0  # show hazard alert when within 50 m

EARTH_RADIUS_M: float = 6_371_000.0


# --------------------------------------------------------------------------
# Haversine helper
# --------------------------------------------------------------------------

def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance in metres between two WGS-84 points."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi  = math.radians(lat2 - lat1)
    dlam  = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


# --------------------------------------------------------------------------
# In-memory spatial index structures
# --------------------------------------------------------------------------

@dataclass
class CrossroadNode:
    node_id: int
    lat:     float
    lon:     float


@dataclass
class ZoneRecord:
    zone_id:  str
    zone_type: ZoneType
    name:     str
    lat:      float
    lon:      float
    radius_m: float          # alert radius for this specific zone


# --------------------------------------------------------------------------
# Proximity service
# --------------------------------------------------------------------------

class ProximityService:
    """
    Stateful service that holds the in-memory spatial indexes and exposes
    three proximity check methods consumed by the WebSocket GPS processor.

    Call `build_indexes()` once after the OSMnx graph is ready and zone
    data has been loaded from PostgreSQL.
    """

    def __init__(self) -> None:
        self._crossroad_nodes: list[CrossroadNode] = []
        self._zones:           list[ZoneRecord]    = []
        self._indexed:         bool                = False
        # Numpy arrays for vectorised distance computation
        self._cr_lats: np.ndarray = np.empty(0)
        self._cr_lons: np.ndarray = np.empty(0)
        self._zo_lats: np.ndarray = np.empty(0)
        self._zo_lons: np.ndarray = np.empty(0)

    # ------------------------------------------------------------------
    # Index construction
    # ------------------------------------------------------------------

    def build_crossroad_index(self, nodes: list[dict]) -> None:
        """
        Load intersection nodes from the OSMnx graph.

        Expected dict format:
            {"node_id": int, "lat": float, "lon": float}
        Typically called once at startup with the result of:
            [(n, d["y"], d["x"]) for n, d in G.nodes(data=True)
             if G.degree(n) >= 3]
        """

        self._crossroad_nodes = [
            CrossroadNode(node_id=n["node_id"], lat=n["lat"], lon=n["lon"])
            for n in nodes
        ]
        self._cr_lats = np.array([n.lat for n in self._crossroad_nodes])
        self._cr_lons = np.array([n.lon for n in self._crossroad_nodes])
        log.info("Crossroad index built: %d intersection nodes", len(self._crossroad_nodes))

    def build_zone_index(self, zones: list[dict]) -> None:
        """
        Load awareness zones (schools, playgrounds, bus stops).

        Expected dict format:
            {
                "zone_id":  str,
                "zone_type": str,   # "school" | "playground" | "bus_stop" | "high_traffic"
                "name":     str,
                "lat":      float,
                "lon":      float,
                "radius_m": float,  # optional, defaults based on type
            }
        """

        default_radii = {
            ZoneType.SCHOOL:       100.0,
            ZoneType.PLAYGROUND:    60.0,
            ZoneType.BUS_STOP:      40.0,
            ZoneType.HIGH_TRAFFIC:  80.0,
        }

        self._zones = []
        for z in zones:
            zone_type = ZoneType(z["zone_type"])
            self._zones.append(ZoneRecord(
                zone_id=z["zone_id"],
                zone_type=zone_type,
                name=z["name"],
                lat=float(z["lat"]),
                lon=float(z["lon"]),
                radius_m=float(z.get("radius_m") or default_radii[zone_type]),
            ))

        self._zo_lats = np.array([z.lat for z in self._zones])
        self._zo_lons = np.array([z.lon for z in self._zones])
        log.info("Zone index built: %d awareness zones", len(self._zones))
        self._indexed = True

    # ------------------------------------------------------------------
    # 1. Crossroad detection
    # ------------------------------------------------------------------

    def nearest_crossroad(
        self,
        lat: float,
        lon: float,
        radius_m: float = CROSSROAD_RADIUS_M,
    ) -> Optional[CrossroadHit]:
        """
        Return the nearest intersection node within `radius_m`, or None.
        Uses a vectorised haversine approximation:
            Δlat in metres  ≈ (lat2-lat1) * EARTH_RADIUS_M * π/180
            Δlon in metres  ≈ (lon2-lon1) * cos(lat) * EARTH_RADIUS_M * π/180
        This is precise enough at ≤ 500 m distances.
        """

        if len(self._crossroad_nodes) == 0:
            return None

        cos_lat = math.cos(math.radians(lat))
        dlat_m  = (self._cr_lats - lat)  * (EARTH_RADIUS_M * math.pi / 180)
        dlon_m  = (self._cr_lons - lon)  * (EARTH_RADIUS_M * math.pi / 180 * cos_lat)
        dists   = np.sqrt(dlat_m ** 2 + dlon_m ** 2)

        idx     = int(np.argmin(dists))
        min_d   = float(dists[idx])

        if min_d > radius_m:
            return None

        node = self._crossroad_nodes[idx]
        return CrossroadHit(
            node_id=node.node_id,
            lat=node.lat,
            lon=node.lon,
            distance_m=round(min_d, 2),
        )

    # ------------------------------------------------------------------
    # 2. Awareness zone detection
    # ------------------------------------------------------------------

    def zones_within_radius(
        self,
        lat: float,
        lon: float,
        global_radius_m: float = AWARENESS_RADIUS_M,
    ) -> list[ZoneHit]:
        """
        Return all awareness zones whose *own* alert radius (or the global
        cap, whichever is smaller) includes (lat, lon).

        Returns list sorted by distance ascending.
        """

        if len(self._zones) == 0:
            return []

        cos_lat = math.cos(math.radians(lat))
        dlat_m  = (self._zo_lats - lat)  * (EARTH_RADIUS_M * math.pi / 180)
        dlon_m  = (self._zo_lons - lon)  * (EARTH_RADIUS_M * math.pi / 180 * cos_lat)
        dists   = np.sqrt(dlat_m ** 2 + dlon_m ** 2)

        hits: list[ZoneHit] = []
        for i, zone in enumerate(self._zones):
            effective_radius = min(zone.radius_m, global_radius_m)
            if dists[i] <= effective_radius:
                hits.append(ZoneHit(
                    zone_id=zone.zone_id,
                    zone_type=zone.zone_type,
                    name=zone.name,
                    lat=zone.lat,
                    lon=zone.lon,
                    distance_m=round(float(dists[i]), 2),
                    radius_m=zone.radius_m,
                ))

        hits.sort(key=lambda h: h.distance_m)
        return hits

    # ------------------------------------------------------------------
    # 3. Hazard proximity  (against live Redis reports)
    # ------------------------------------------------------------------

    @staticmethod
    def hazards_within_radius(
        lat: float,
        lon: float,
        hazards: list[dict],
        radius_m: float = HAZARD_ALERT_RADIUS_M,
    ) -> list[dict]:
        """
        Filter a list of hazard dicts (as returned by HazardService.get_hazards_near)
        to only those within `radius_m`.  Returns list sorted by distance asc.

        The list is already pre-filtered by Redis GEOSEARCH, so this is a
        cheap final pass to apply the tighter per-alert radius.
        """

        result = []
        for h in hazards:
            h_lat, h_lon = float(h["lat"]), float(h["lon"])
            d = haversine_m(lat, lon, h_lat, h_lon)
            if d <= radius_m:
                result.append({**h, "distance_m": round(d, 2)})

        result.sort(key=lambda h: h["distance_m"])
        return result
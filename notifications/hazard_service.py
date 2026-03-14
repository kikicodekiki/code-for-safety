from __future__ import annotations

import json
import uuid
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import redis.asyncio as aioredis

from .models import HazardReportIn, HazardReportOut, HazardType

log = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

HAZARD_TTL_SECONDS: int = 10 * 60 * 60          # 10 hours
GEO_INDEX_KEY:      str = "hazard:geo"
HASH_KEY_PREFIX:    str = "hazard:"
RECENT_REPORTS_KEY: str = "hazard:recent"        # sorted set (score = epoch)
MAX_RADIUS_KM:      float = 50.0                 # safety cap on geo queries


# --------------------------------------------------------------------------
# Service class
# --------------------------------------------------------------------------

class HazardService:
    """
    All hazard read/write operations against Redis.
    Injected as a FastAPI dependency (app.state.hazard_service).
    """

    def __init__(self, redis: aioredis.Redis) -> None:
        self._r = redis

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def store_report(self, report: HazardReportIn) -> HazardReportOut:
        """
        Persist a user hazard report.

        Steps
        -----
        1. Generate deterministic key.
        2. Store all fields in a Redis Hash with HSET.
        3. Set EXPIRE on the hash (10 h TTL).
        4. Register coordinates in the geo index (GEOADD).
        5. Add to the recency sorted set for quick "latest N" queries.
        6. Return structured response.
        """

        hazard_id  = str(uuid.uuid4())
        hash_key   = f"{HASH_KEY_PREFIX}{hazard_id}"
        created_at = datetime.now(tz=timezone.utc)
        expires_at = created_at + timedelta(seconds=HAZARD_TTL_SECONDS)

        # --- 1. Store hash ---------------------------------------------------
        mapping: dict[str, str] = {
            "hazard_id":   hazard_id,
            "hazard_type": report.hazard_type.value,
            "lat":         str(report.lat),
            "lon":         str(report.lon),
            "description": report.description or "",
            "created_at":  created_at.isoformat(),
            "expires_at":  expires_at.isoformat(),
        }

        pipe = self._r.pipeline(transaction=True)
        pipe.hset(hash_key, mapping=mapping)
        pipe.expire(hash_key, HAZARD_TTL_SECONDS)

        # --- 2. Geo index (lon first — Redis convention) ---------------------
        #   GEOADD hazard:geo  lon lat  member
        pipe.geoadd(GEO_INDEX_KEY, [report.lon, report.lat, hazard_id])

        # --- 3. Recency set  (score = unix epoch) ----------------------------
        pipe.zadd(
            RECENT_REPORTS_KEY,
            {hazard_id: created_at.timestamp()},
        )
        # Trim to last 10 000 entries to avoid unbounded growth
        pipe.zremrangebyrank(RECENT_REPORTS_KEY, 0, -10_001)

        await pipe.execute()

        log.info("Stored hazard %s type=%s lat=%.5f lon=%.5f",
                 hazard_id, report.hazard_type.value, report.lat, report.lon)

        return HazardReportOut(
            hazard_id=hazard_id,
            hazard_type=report.hazard_type,
            lat=report.lat,
            lon=report.lon,
            description=report.description,
            created_at=created_at,
            expires_at=expires_at,
            redis_key=hash_key,
        )

    # ------------------------------------------------------------------
    # Read — radius query (used by routing engine + WebSocket checker)
    # ------------------------------------------------------------------

    async def get_hazards_near(
        self,
        lat: float,
        lon: float,
        radius_km: float = 5.0,
    ) -> list[dict]:
        """
        Return all *live* hazard reports within `radius_km` of (lat, lon).

        Uses GEORADIUS (or the newer GEOSEARCH) for O(N+log M) lookup.
        Dead entries whose hash has expired are silently skipped.
        """

        radius_km = min(radius_km, MAX_RADIUS_KM)

        # GEOSEARCH returns list of (member, distance, coords)
        results = await self._r.geosearch(
            GEO_INDEX_KEY,
            longitude=lon,
            latitude=lat,
            radius=radius_km,
            unit="km",
            withcoord=True,
            withdist=True,
            sort="ASC",
            count=200,               # hard cap — routing only needs ~200 nearby
        )

        hazards: list[dict] = []
        dead_members: list[str] = []

        for member, distance_km, (geo_lon, geo_lat) in results:
            hazard_id = member if isinstance(member, str) else member.decode()
            hash_key  = f"{HASH_KEY_PREFIX}{hazard_id}"

            data = await self._r.hgetall(hash_key)
            if not data:
                # Hash expired but geo entry still alive → clean up lazily
                dead_members.append(hazard_id)
                continue

            # Decode bytes → str if needed
            decoded = {
                (k.decode() if isinstance(k, bytes) else k):
                (v.decode() if isinstance(v, bytes) else v)
                for k, v in data.items()
            }
            decoded["distance_km"] = round(distance_km, 4)
            hazards.append(decoded)

        # Async cleanup of stale geo entries
        if dead_members:
            await self._r.zrem(GEO_INDEX_KEY, *dead_members)
            log.debug("Pruned %d expired geo entries", len(dead_members))

        return hazards

    # ------------------------------------------------------------------
    # Read — single report
    # ------------------------------------------------------------------

    async def get_report(self, hazard_id: str) -> Optional[dict]:
        data = await self._r.hgetall(f"{HASH_KEY_PREFIX}{hazard_id}")
        if not data:
            return None
        return {
            (k.decode() if isinstance(k, bytes) else k):
            (v.decode() if isinstance(v, bytes) else v)
            for k, v in data.items()
        }

    # ------------------------------------------------------------------
    # Delete (moderation / user retraction)
    # ------------------------------------------------------------------

    async def delete_report(self, hazard_id: str) -> bool:
        pipe = self._r.pipeline(transaction=True)
        pipe.delete(f"{HASH_KEY_PREFIX}{hazard_id}")
        pipe.zrem(GEO_INDEX_KEY, hazard_id)
        pipe.zrem(RECENT_REPORTS_KEY, hazard_id)
        results = await pipe.execute()
        deleted = bool(results[0])
        if deleted:
            log.info("Deleted hazard %s", hazard_id)
        return deleted

    # ------------------------------------------------------------------
    # Convenience — inject into edge weights (called by routing engine)
    # ------------------------------------------------------------------

    async def get_edge_penalties(
        self,
        lat: float,
        lon: float,
        radius_km: float = 2.0,
    ) -> list[dict]:
        """
        Returns a slim payload the routing engine uses to add +0.5 cost
        to edges near each hazard.  Only lat/lon/hazard_type returned.
        """

        raw = await self.get_hazards_near(lat, lon, radius_km)
        return [
            {
                "lat":  float(h["lat"]),
                "lon":  float(h["lon"]),
                "type": h["hazard_type"],
            }
            for h in raw
        ]
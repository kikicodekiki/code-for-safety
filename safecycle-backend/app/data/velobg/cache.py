"""
VeloBGCache — Redis cache for parsed VeloBGMapData.

Stores the full serialised map data so the scheduler can check freshness
and the API can serve paths without hitting the database on every request.

Cache key: velobg:map_data
TTL:       25 hours (VELOBG_REDIS_TTL_S in config — slightly longer than the
           24-hour refresh interval so there's no gap window)

Serialisation: Pydantic model → JSON string (model_dump_json)
Deserialisation: JSON string → VeloBGMapData.model_validate_json
"""
from __future__ import annotations

from typing import Optional

import structlog
from redis.asyncio import Redis

from app.config import Settings
from app.models.schemas.velobg import VeloBGMapData

logger = structlog.get_logger(__name__)


class VeloBGCache:

    def __init__(self, redis: Redis, settings: Settings) -> None:
        self._redis    = redis
        self._settings = settings

    async def set(self, map_data: VeloBGMapData) -> None:
        """Serialises and stores VeloBGMapData in Redis with configured TTL."""
        payload = map_data.model_dump_json()
        await self._redis.setex(
            self._settings.VELOBG_REDIS_KEY,
            self._settings.VELOBG_REDIS_TTL_S,
            payload,
        )
        logger.info(
            "velobg_cache_set",
            key=self._settings.VELOBG_REDIS_KEY,
            ttl_s=self._settings.VELOBG_REDIS_TTL_S,
            paths=map_data.total_paths,
        )

    async def get(self) -> Optional[VeloBGMapData]:
        """
        Retrieves VeloBGMapData from Redis.
        Returns None if the key is missing or the data is unreadable.
        """
        raw = await self._redis.get(self._settings.VELOBG_REDIS_KEY)
        if raw is None:
            return None
        try:
            return VeloBGMapData.model_validate_json(raw)
        except Exception as exc:
            logger.warning("velobg_cache_deserialise_failed", error=str(exc))
            return None

    async def delete(self) -> None:
        """Invalidates the cache — forces a fresh fetch on next request."""
        await self._redis.delete(self._settings.VELOBG_REDIS_KEY)
        logger.info("velobg_cache_invalidated", key=self._settings.VELOBG_REDIS_KEY)

    async def ttl(self) -> int:
        """Returns seconds until cache expiry, or -2 if key does not exist."""
        return await self._redis.ttl(self._settings.VELOBG_REDIS_KEY)

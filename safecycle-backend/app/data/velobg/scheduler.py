"""
VeloBGScheduler — background asyncio task that refreshes VeloBG data on a schedule.

Runs as a long-lived asyncio.Task started during app lifespan.
Default refresh interval: every 24 hours (VELOBG_REFRESH_INTERVAL_S).

On each refresh cycle:
    1. Fetch KML from Google My Maps (VeloBGFetcher)
    2. Parse KML into VeloBGMapData (VeloBGParser)
    3. Update Redis cache (VeloBGCache)
    4. Re-enrich the OSMnx graph in-place (VeloBGEnricher)
    5. Persist to PostgreSQL (VeloBGRepository)

On failure: logs the error, retains the current cache, and retries after
the normal interval (no exponential back-off — the fetch already has its
own fallback to disk cache).
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import structlog
import networkx as nx

from app.config import Settings
from app.data.velobg.cache import VeloBGCache
from app.data.velobg.enricher import VeloBGEnricher
from app.data.velobg.fetcher import VeloBGFetcher
from app.data.velobg.parser import VeloBGParser
from app.data.velobg.repository import VeloBGRepository

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = structlog.get_logger(__name__)


class VeloBGScheduler:
    """
    Wraps a background asyncio task that refreshes VeloBG data periodically.

    Usage (in app lifespan):
        scheduler = VeloBGScheduler(settings, redis)
        scheduler.start(graph)          # starts background task
        ...
        await scheduler.stop()          # graceful shutdown
    """

    def __init__(self, settings: Settings, redis: "Redis") -> None:
        self._settings   = settings
        self._redis      = redis
        self._task:      asyncio.Task | None = None
        self._fetcher    = VeloBGFetcher(settings)
        self._parser     = VeloBGParser()
        self._cache      = VeloBGCache(redis, settings)
        self._enricher   = VeloBGEnricher()
        self._repository = VeloBGRepository()

    def start(self, graph: nx.MultiDiGraph) -> None:
        """Starts the background refresh loop."""
        self._graph = graph
        self._task  = asyncio.create_task(
            self._refresh_loop(),
            name="velobg_refresh_scheduler",
        )
        logger.info(
            "velobg_scheduler_started",
            interval_s=self._settings.VELOBG_REFRESH_INTERVAL_S,
        )

    async def stop(self) -> None:
        """Cancels the background task and waits for it to finish."""
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("velobg_scheduler_stopped")

    async def refresh_now(self, force: bool = True) -> bool:
        """
        Triggers an immediate refresh outside the normal schedule.
        Called by POST /velobg/refresh.
        Returns True on success.
        """
        return await self._do_refresh(force=force)

    async def _refresh_loop(self) -> None:
        """
        Runs forever, refreshing at the configured interval.
        First iteration sleeps before refreshing so startup fetch takes
        priority (startup already calls refresh_now).
        """
        while True:
            await asyncio.sleep(self._settings.VELOBG_REFRESH_INTERVAL_S)
            await self._do_refresh(force=False)

    async def _do_refresh(self, force: bool = False) -> bool:
        logger.info("velobg_refresh_starting", force=force)
        try:
            kml_content, fallback_used = await self._fetcher.fetch(force=force)
            fetched_at = datetime.now(timezone.utc)

            map_data = self._parser.parse(
                kml_content,
                fetched_at=fetched_at,
            )

            # Update Redis cache
            await self._cache.set(map_data)

            # Re-enrich graph in-place
            if hasattr(self, "_graph") and self._graph is not None:
                self._enricher.enrich(self._graph, map_data, self._settings)

            # Persist to PostgreSQL
            try:
                from app.db.session import async_session_factory
                async with async_session_factory() as session:
                    await self._repository.replace_all(session, map_data)
            except Exception as db_exc:
                logger.warning(
                    "velobg_db_persist_failed",
                    error=str(db_exc),
                    note="Cache and graph are still updated",
                )

            logger.info(
                "velobg_refresh_complete",
                fallback_used=fallback_used,
                total_paths=map_data.total_paths,
                usable_paths=len(map_data.usable_paths),
            )
            return True

        except Exception as exc:
            logger.error("velobg_refresh_failed", error=str(exc))
            return False

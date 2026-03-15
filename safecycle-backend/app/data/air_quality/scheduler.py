"""
AirQualityScheduler — refreshes sensor.community data in the background.

Runs an asyncio task that fetches fresh air quality readings every
AIR_QUALITY_REFRESH_INTERVAL_S seconds (default 1800 = 30 min).
Updates the AirQualityRepository in-place so the routing algorithm
always uses current data without a restart.
"""
from __future__ import annotations

import asyncio

import structlog

from app.config import Settings
from app.data.air_quality.fetcher import AirQualityFetcher
from app.data.air_quality.repository import AirQualityRepository

logger = structlog.get_logger(__name__)


class AirQualityScheduler:

    def __init__(
        self,
        settings: Settings,
        fetcher: AirQualityFetcher,
        repository: AirQualityRepository,
    ) -> None:
        self._settings = settings
        self._fetcher = fetcher
        self._repository = repository
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._loop(), name="air_quality_refresh")
        logger.info(
            "air_quality_scheduler_started",
            interval_s=getattr(
                self._settings, "AIR_QUALITY_REFRESH_INTERVAL_S", 1800
            ),
        )

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("air_quality_scheduler_stopped")

    async def _loop(self) -> None:
        interval = getattr(self._settings, "AIR_QUALITY_REFRESH_INTERVAL_S", 1800)
        while True:
            await asyncio.sleep(interval)
            try:
                payload = await self._fetcher.fetch()
                self._repository.update(payload)
            except Exception as exc:
                logger.warning("air_quality_scheduled_refresh_failed", error=str(exc))

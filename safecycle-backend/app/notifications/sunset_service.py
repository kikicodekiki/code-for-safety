"""
notifications/sunset_service.py
Fetches the real sunset time for Sofia (or any lat/lon) via the
Open-Meteo free API and caches the result in Redis until midnight.

Usage
-----
    svc = SunsetService(redis_client)
    sunset_dt = await svc.get_sunset()          # returns datetime (UTC-aware)
    is_dark   = await svc.is_after_sunset()     # simple bool
"""

from __future__ import annotations

import logging
from datetime import datetime, date, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx

import redis.asyncio as aioredis

log = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------

SOFIA_LAT: float = 42.6977
SOFIA_LON: float = 23.3219
SOFIA_TZ:  ZoneInfo = ZoneInfo("Europe/Sofia")

OPEN_METEO_URL = (
    "https://api.open-meteo.com/v1/forecast"
    "?latitude={lat}&longitude={lon}"
    "&daily=sunset,sunrise"
    "&timezone={tz}"
    "&forecast_days=1"
)

REDIS_KEY_PREFIX = "sunset:"
# How many seconds BEFORE sunset we start alerting (5-minute grace)
SUNSET_ALERT_LEAD_SECONDS: int = 5 * 60


# --------------------------------------------------------------------------
# Service
# --------------------------------------------------------------------------

class SunsetService:
    """
    Async service that provides today's sunset time for Sofia.
    Injected into GPSProcessor via app.state.sunset_service.
    """

    def __init__(self, redis: aioredis.Redis) -> None:
        self._r = redis
        # In-process fallback cache so we survive transient Redis failures
        self._memory_cache: dict[str, datetime] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_sunset(
        self,
        lat: float = SOFIA_LAT,
        lon: float = SOFIA_LON,
    ) -> datetime | None:
        """
        Return today's sunset as a timezone-aware datetime (UTC).
        Returns None if the API is unreachable and there is no cached value.
        """
        today = date.today().isoformat()
        cache_key = f"{REDIS_KEY_PREFIX}{today}"

        # 1. Try Redis cache
        cached = await self._try_redis_get(cache_key)
        if cached:
            return cached

        # 2. Try in-process memory fallback (survives short Redis blip)
        if today in self._memory_cache:
            return self._memory_cache[today]

        # 3. Fetch from Open-Meteo
        sunset_dt = await self._fetch_from_api(lat, lon)
        if sunset_dt is None:
            log.warning("SunsetService: API fetch failed, no cached value available")
            return None

        # 4. Store in Redis with TTL = seconds until midnight + 60 s
        await self._cache_to_redis(cache_key, sunset_dt)
        self._memory_cache[today] = sunset_dt

        return sunset_dt

    async def get_sunrise(
        self,
        lat: float = SOFIA_LAT,
        lon: float = SOFIA_LON,
    ) -> datetime | None:
        """Return today's sunrise as a timezone-aware datetime (UTC)."""
        today = date.today().isoformat()
        cache_key = f"{REDIS_KEY_PREFIX}sunrise:{today}"

        cached = await self._try_redis_get(cache_key)
        if cached:
            return cached

        sunrise_dt = await self._fetch_from_api(lat, lon, field="sunrise")
        if sunrise_dt:
            await self._cache_to_redis(cache_key, sunrise_dt)
        return sunrise_dt

    async def is_after_sunset(
        self,
        lat: float = SOFIA_LAT,
        lon: float = SOFIA_LON,
        lead_seconds: int = SUNSET_ALERT_LEAD_SECONDS,
    ) -> bool:
        """
        Returns True if the current UTC time is within `lead_seconds` before
        sunset OR after sunset (and before midnight).

        This is the main predicate used by GPSProcessor._check_lights().
        """
        sunset = await self.get_sunset(lat, lon)
        if sunset is None:
            # Fallback to time-of-day heuristic when API is unavailable
            sofia_hour = datetime.now(tz=SOFIA_TZ).hour
            return sofia_hour >= 19 or sofia_hour < 7

        now_utc = datetime.now(tz=timezone.utc)
        # Alert window: from (sunset - lead) until midnight Sofia time
        alert_start = sunset - timedelta(seconds=lead_seconds)
        midnight_sofia = (
            datetime.now(tz=SOFIA_TZ)
            .replace(hour=23, minute=59, second=59, microsecond=0)
            .astimezone(timezone.utc)
        )

        return alert_start <= now_utc <= midnight_sofia

    async def is_before_sunrise(
        self,
        lat: float = SOFIA_LAT,
        lon: float = SOFIA_LON,
    ) -> bool:
        """Returns True if current time is before today's sunrise."""
        sunrise = await self.get_sunrise(lat, lon)
        if sunrise is None:
            sofia_hour = datetime.now(tz=SOFIA_TZ).hour
            return sofia_hour < 7

        now_utc = datetime.now(tz=timezone.utc)
        return now_utc < sunrise

    async def is_dark(
        self,
        lat: float = SOFIA_LAT,
        lon: float = SOFIA_LON,
    ) -> bool:
        """True when it's dark outside (after sunset OR before sunrise)."""
        return (
            await self.is_after_sunset(lat, lon)
            or await self.is_before_sunrise(lat, lon)
        )

    async def sunset_voice_text(
        self,
        lat: float = SOFIA_LAT,
        lon: float = SOFIA_LON,
    ) -> str:
        """
        Returns a human-readable Bulgarian TTS string describing why
        lights should be turned on. Used by NotificationService.
        """
        sunset = await self.get_sunset(lat, lon)
        if sunset is None:
            return "Включете светлините. Видимостта е намалена."

        sunset_sofia = sunset.astimezone(SOFIA_TZ)
        hour   = sunset_sofia.hour
        minute = sunset_sofia.minute
        return (
            f"Залезът в София е в {hour} часа и {minute} минути. "
            f"Включете предната и задната светлина на колелото."
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _fetch_from_api(
        self,
        lat: float,
        lon: float,
        field: str = "sunset",
    ) -> datetime | None:
        url = OPEN_METEO_URL.format(
            lat=lat,
            lon=lon,
            tz="Europe/Sofia",
        )
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()

            value_str = data["daily"][field][0]          # e.g. "2025-06-15T21:04"
            # Open-Meteo returns local time — attach Sofia tz then convert to UTC
            local_dt = datetime.fromisoformat(value_str).replace(tzinfo=SOFIA_TZ)
            utc_dt   = local_dt.astimezone(timezone.utc)
            log.info("SunsetService: %s=%s (UTC: %s)", field, value_str, utc_dt)
            return utc_dt

        except httpx.HTTPError as exc:
            log.error("SunsetService: HTTP error fetching %s: %s", field, exc)
        except (KeyError, IndexError, ValueError) as exc:
            log.error("SunsetService: parse error for %s: %s", field, exc)
        return None

    async def _try_redis_get(self, key: str) -> datetime | None:
        try:
            val = await self._r.get(key)
            if val:
                raw = val.decode() if isinstance(val, bytes) else val
                return datetime.fromisoformat(raw)
        except Exception as exc:
            log.warning("SunsetService: Redis GET failed (%s)", exc)
        return None

    async def _cache_to_redis(self, key: str, dt: datetime) -> None:
        try:
            # TTL = seconds until midnight Sofia time + 60 s buffer
            now_sofia      = datetime.now(tz=SOFIA_TZ)
            midnight_sofia = now_sofia.replace(
                hour=23, minute=59, second=59, microsecond=0
            )
            ttl = max(int((midnight_sofia - now_sofia).total_seconds()) + 60, 60)
            await self._r.set(key, dt.isoformat(), ex=ttl)
            log.debug("SunsetService: cached %s (TTL=%ds)", key, ttl)
        except Exception as exc:
            log.warning("SunsetService: Redis SET failed (%s)", exc)
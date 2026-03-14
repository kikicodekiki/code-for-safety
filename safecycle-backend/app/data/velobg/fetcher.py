"""
VeloBGFetcher — downloads the KML export of the VeloBG Google My Map.

The primary URL is:
    https://www.google.com/maps/d/kml?mid=1iQ1EYaAvinM_vnupk6w0twyeYOEN9o4&forcekml=1

Fallback chain on failure:
    1. Primary KML URL
    2. Cached KML file on disk (data/velobg_cache.kml)
    3. Raise VeloBGFetchError (caller decides whether to block startup)

The fetcher saves a local copy of every successful fetch to disk as
data/velobg_cache.kml so the fallback is always fresh.

Rate limiting: Do not fetch more than once per hour. The scheduler
enforces this but the fetcher also checks an internal cooldown.
"""
from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Optional

import httpx
import structlog

from app.config import Settings
from app.core.exceptions import VeloBGFetchError

logger = structlog.get_logger(__name__)

VELOBG_MAP_ID       = "1iQ1EYaAvinM_vnupk6w0twyeYOEN9o4"
KML_PRIMARY_URL     = f"https://www.google.com/maps/d/kml?mid={VELOBG_MAP_ID}&forcekml=1"
KML_CACHE_PATH      = Path("data/velobg_cache.kml")
FETCH_TIMEOUT_S     = 30
MIN_FETCH_INTERVAL_S = 3600    # Never fetch more than once per hour

# Browser-like User-Agent to avoid 403 from Google
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

_last_fetch_time: float = 0.0


class VeloBGFetcher:

    def __init__(self, settings: Settings):
        self.settings = settings

    async def fetch(self, force: bool = False) -> tuple[str, bool]:
        """
        Fetches the KML content for the VeloBG My Map.

        Returns
        -------
        tuple[str, bool]
            (kml_content, fallback_used)
            fallback_used is True when the cached file was served
            instead of a fresh download.

        Parameters
        ----------
        force : bool
            If True, bypasses the rate-limit cooldown.
            Use for manual refresh via POST /velobg/refresh.
        """
        global _last_fetch_time

        elapsed = time.monotonic() - _last_fetch_time
        if not force and elapsed < MIN_FETCH_INTERVAL_S:
            logger.info(
                "velobg_fetch_skipped_cooldown",
                seconds_until_eligible=int(MIN_FETCH_INTERVAL_S - elapsed),
            )
            cached = self._load_from_disk_cache()
            if cached:
                return cached, True
            raise VeloBGFetchError(
                "Rate limit cooldown active and no disk cache available."
            )

        try:
            kml_content = await self._fetch_from_google()
            _last_fetch_time = time.monotonic()
            self._save_to_disk_cache(kml_content)
            return kml_content, False

        except Exception as primary_error:
            logger.warning(
                "velobg_primary_fetch_failed",
                error=str(primary_error),
                falling_back_to_disk_cache=True,
            )
            cached = self._load_from_disk_cache()
            if cached:
                logger.info(
                    "velobg_fallback_cache_used",
                    cache_path=str(KML_CACHE_PATH),
                    cache_size_bytes=len(cached),
                )
                return cached, True

            raise VeloBGFetchError(
                f"Primary fetch failed and no disk cache available. "
                f"Primary error: {primary_error}"
            ) from primary_error

    async def _fetch_from_google(self) -> str:
        """
        Performs the actual HTTP GET to Google's KML export endpoint.

        Handles:
        - 200 OK with KML content → success
        - 302 redirect → follow (httpx follows redirects by default)
        - 403 Forbidden → raise with UA hint
        - 429 Too Many Requests → raise with retry-after
        - Non-KML content-type → raise (Google sometimes returns HTML error pages)
        """
        start = time.monotonic()

        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=FETCH_TIMEOUT_S,
        ) as client:
            response = await client.get(
                KML_PRIMARY_URL,
                headers={
                    "User-Agent":      USER_AGENT,
                    "Accept":          "application/vnd.google-earth.kml+xml, application/xml, */*",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Referer":         "https://www.google.com/maps/d/",
                },
            )

        elapsed = time.monotonic() - start

        if response.status_code == 403:
            raise VeloBGFetchError(
                "Google returned 403 Forbidden. "
                "The map may have been made private or the User-Agent was rejected."
            )

        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After", "unknown")
            raise VeloBGFetchError(
                f"Google rate-limited the KML fetch. Retry-After: {retry_after}"
            )

        if response.status_code != 200:
            raise VeloBGFetchError(
                f"Unexpected HTTP {response.status_code} from Google KML endpoint."
            )

        content = response.text

        # Validate it's actually KML and not an HTML error page
        if not content.strip().startswith("<?xml") and "<kml" not in content[:500]:
            raise VeloBGFetchError(
                f"Response does not appear to be valid KML. "
                f"First 200 chars: {content[:200]!r}"
            )

        logger.info(
            "velobg_kml_fetched",
            url=KML_PRIMARY_URL,
            size_bytes=len(content),
            elapsed_s=round(elapsed, 2),
            status_code=response.status_code,
        )

        return content

    def _load_from_disk_cache(self) -> Optional[str]:
        path = Path(self.settings.VELOBG_KML_CACHE_PATH)
        if path.exists():
            return path.read_text(encoding="utf-8")
        # Also try the default path
        if KML_CACHE_PATH.exists():
            return KML_CACHE_PATH.read_text(encoding="utf-8")
        return None

    def _save_to_disk_cache(self, kml_content: str) -> None:
        path = Path(self.settings.VELOBG_KML_CACHE_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(kml_content, encoding="utf-8")
        logger.debug(
            "velobg_kml_cached_to_disk",
            path=str(path),
            size_bytes=len(kml_content),
        )

    async def fetch_layer_ids(self) -> list[dict]:
        """
        Discovers all layer IDs from the My Map embed page.
        Parses the embed URL HTML to extract layer metadata.
        Returns list of {id, name} dicts.
        """
        embed_url = (
            f"https://www.google.com/maps/d/u/0/embed"
            f"?mid={VELOBG_MAP_ID}&ehbc=2E312F"
        )

        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=15.0,
        ) as client:
            response = await client.get(
                embed_url,
                headers={"User-Agent": USER_AGENT},
            )

        layer_pattern = re.compile(r'"lid":"([^"]+)".*?"name":"([^"]+)"')
        layers = [
            {"id": m.group(1), "name": m.group(2)}
            for m in layer_pattern.finditer(response.text)
        ]

        logger.info("velobg_layers_discovered", count=len(layers), layers=layers)
        return layers

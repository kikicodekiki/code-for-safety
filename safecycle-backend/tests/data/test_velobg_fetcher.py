"""Tests for VeloBGFetcher."""
from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import VeloBGFetchError
from app.data.velobg import fetcher as fetcher_module
from app.data.velobg.fetcher import VeloBGFetcher


VALID_KML = """\
<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document><name>Test</name></Document>
</kml>"""


@pytest.fixture()
def settings(tmp_path):
    s = MagicMock()
    s.VELOBG_KML_CACHE_PATH = str(tmp_path / "velobg_cache.kml")
    s.VELOBG_FETCH_TIMEOUT_S = 10
    return s


@pytest.fixture(autouse=True)
def reset_cooldown():
    """Reset the module-level last_fetch_time between tests."""
    fetcher_module._last_fetch_time = 0.0
    yield
    fetcher_module._last_fetch_time = 0.0


class TestVeloBGFetcherSuccess:

    @pytest.mark.asyncio
    async def test_fetch_returns_kml_and_false_fallback(self, settings):
        """Successful fetch returns (kml_content, False)."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = VALID_KML

        with patch("app.data.velobg.fetcher.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            content, fallback = await VeloBGFetcher(settings).fetch(force=True)

        assert content == VALID_KML
        assert fallback is False

    @pytest.mark.asyncio
    async def test_fetch_saves_disk_cache(self, settings, tmp_path):
        """Successful fetch writes kml to disk cache."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = VALID_KML

        with patch("app.data.velobg.fetcher.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            await VeloBGFetcher(settings).fetch(force=True)

        assert Path(settings.VELOBG_KML_CACHE_PATH).read_text() == VALID_KML


class TestVeloBGFetcherFallback:

    @pytest.mark.asyncio
    async def test_falls_back_to_disk_cache_on_network_error(self, settings):
        """On network error, returns disk cache with fallback=True."""
        Path(settings.VELOBG_KML_CACHE_PATH).parent.mkdir(parents=True, exist_ok=True)
        Path(settings.VELOBG_KML_CACHE_PATH).write_text(VALID_KML)

        with patch("app.data.velobg.fetcher.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=Exception("connection refused")
            )
            content, fallback = await VeloBGFetcher(settings).fetch(force=True)

        assert content == VALID_KML
        assert fallback is True

    @pytest.mark.asyncio
    async def test_raises_when_no_cache_and_network_fails(self, settings):
        """Raises VeloBGFetchError when both network and cache fail."""
        with patch("app.data.velobg.fetcher.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=Exception("network down")
            )
            with pytest.raises(VeloBGFetchError, match="Primary fetch failed"):
                await VeloBGFetcher(settings).fetch(force=True)


class TestVeloBGFetcherRateLimit:

    @pytest.mark.asyncio
    async def test_cooldown_uses_cache_without_fetching(self, settings):
        """When cooldown is active and cache exists, returns cache without HTTP call."""
        Path(settings.VELOBG_KML_CACHE_PATH).parent.mkdir(parents=True, exist_ok=True)
        Path(settings.VELOBG_KML_CACHE_PATH).write_text(VALID_KML)

        # Simulate a recent fetch
        fetcher_module._last_fetch_time = time.monotonic()

        with patch("app.data.velobg.fetcher.httpx.AsyncClient") as mock_client:
            content, fallback = await VeloBGFetcher(settings).fetch(force=False)
            mock_client.assert_not_called()

        assert content == VALID_KML
        assert fallback is True

    @pytest.mark.asyncio
    async def test_force_bypasses_cooldown(self, settings):
        """force=True fetches even within the cooldown window."""
        fetcher_module._last_fetch_time = time.monotonic()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = VALID_KML

        with patch("app.data.velobg.fetcher.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            content, fallback = await VeloBGFetcher(settings).fetch(force=True)

        assert fallback is False


class TestVeloBGFetcherHTTPErrors:

    @pytest.mark.asyncio
    async def test_403_raises_fetch_error(self, settings):
        mock_response = MagicMock()
        mock_response.status_code = 403

        with patch("app.data.velobg.fetcher.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            with pytest.raises(VeloBGFetchError, match="403"):
                await VeloBGFetcher(settings)._fetch_from_google()

    @pytest.mark.asyncio
    async def test_html_response_raises_fetch_error(self, settings):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>Error</body></html>"

        with patch("app.data.velobg.fetcher.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            with pytest.raises(VeloBGFetchError, match="valid KML"):
                await VeloBGFetcher(settings)._fetch_from_google()

"""
SafeCycle Sofia — Hazard service unit tests.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import Settings
from app.models.schemas.hazard import HazardReportCreate, HazardType
from app.services.hazard_service import HazardService


@pytest.fixture
def settings() -> Settings:
    return Settings(
        DATABASE_URL="postgresql+asyncpg://test:test@localhost/test",
        REDIS_URL="redis://localhost:6379/1",
        GOOGLE_MAPS_API_KEY="test",
        FIREBASE_ENABLED=False,
        HAZARD_TTL_SECONDS=36000,
        HAZARD_RECENT_THRESHOLD_HOURS=1,
        HAZARD_ACTIVE_THRESHOLD_HOURS=10,
    )


def _make_redis_hazard(age_hours: float, hazard_id: str = "abc-123") -> str:
    """Create a JSON-serialised hazard at a given age."""
    ts = datetime.now(tz=timezone.utc) - timedelta(hours=age_hours)
    return json.dumps({
        "id": hazard_id,
        "lat": 42.6977,
        "lon": 23.3219,
        "type": "pothole",
        "description": "Test hazard",
        "timestamp": ts.isoformat(),
    })


class TestHazardPenaltyDecay:
    """Verify the penalty formula: max(0, 2.0 - age_hours * 0.2)"""

    def _penalty(self, age_hours: float) -> float:
        return max(0.0, 2.0 - age_hours * 0.2)

    def test_fresh_report_max_penalty(self):
        assert self._penalty(0.0) == 2.0

    def test_5h_penalty_is_1(self):
        assert abs(self._penalty(5.0) - 1.0) < 0.001

    def test_10h_penalty_is_zero(self):
        assert self._penalty(10.0) == 0.0

    def test_beyond_10h_is_still_zero(self):
        assert self._penalty(15.0) == 0.0


class TestHazardService:

    @pytest.mark.asyncio
    async def test_get_all_active_empty_redis(self, settings):
        service = HazardService()
        redis = AsyncMock()
        redis.keys.return_value = []

        with patch("app.services.hazard_service.settings", settings):
            result = await service.get_all_active(redis)

        assert result == []

    @pytest.mark.asyncio
    async def test_active_hazard_returned(self, settings):
        """A 2-hour-old hazard (< 10h) should be in the result."""
        service = HazardService()
        redis = AsyncMock()
        redis.keys.return_value = ["hazard:abc-123"]
        redis.get.return_value = _make_redis_hazard(2.0, "abc-123")

        with patch("app.services.hazard_service.settings", settings):
            result = await service.get_all_active(redis)

        assert len(result) == 1
        assert result[0].id == "abc-123"
        assert result[0].is_active is True

    @pytest.mark.asyncio
    async def test_expired_hazard_excluded_when_active_only(self, settings):
        """A 10+ hour hazard is excluded when active_only=True."""
        service = HazardService()
        redis = AsyncMock()
        redis.keys.return_value = ["hazard:old-123"]
        redis.get.return_value = _make_redis_hazard(11.0, "old-123")

        with patch("app.services.hazard_service.settings", settings):
            result = await service.get_all_active(redis, active_only=True)

        assert result == []

    @pytest.mark.asyncio
    async def test_expired_hazard_included_when_not_active_only(self, settings):
        """Expired hazard appears when active_only=False."""
        service = HazardService()
        redis = AsyncMock()
        redis.keys.return_value = ["hazard:old-123"]
        redis.get.return_value = _make_redis_hazard(11.0, "old-123")

        with patch("app.services.hazard_service.settings", settings):
            result = await service.get_all_active(redis, active_only=False)

        assert len(result) == 1
        assert result[0].is_active is False

    @pytest.mark.asyncio
    async def test_is_recent_flag_set_correctly(self, settings):
        service = HazardService()
        redis_recent = AsyncMock()
        redis_recent.keys.return_value = ["hazard:recent"]
        redis_recent.get.return_value = _make_redis_hazard(0.5, "recent")

        redis_old = AsyncMock()
        redis_old.keys.return_value = ["hazard:old"]
        redis_old.get.return_value = _make_redis_hazard(2.0, "old")

        with patch("app.services.hazard_service.settings", settings):
            result_recent = await service.get_all_active(redis_recent)
            result_old = await service.get_all_active(redis_old)

        assert result_recent[0].is_recent is True
        assert result_old[0].is_recent is False

    @pytest.mark.asyncio
    async def test_radius_filter(self, settings):
        """Only hazards within radius_m are returned when lat/lon provided."""
        service = HazardService()
        redis = AsyncMock()
        redis.keys.return_value = ["hazard:near", "hazard:far"]

        # Near hazard: at NDK (42.6977, 23.3219)
        near_hazard = json.dumps({
            "id": "near",
            "lat": 42.6977,
            "lon": 23.3219,
            "type": "pothole",
            "description": None,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        })
        # Far hazard: in Lozenets (~3 km away)
        far_hazard = json.dumps({
            "id": "far",
            "lat": 42.6800,
            "lon": 23.3350,
            "type": "pothole",
            "description": None,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        })

        async def mock_get(key):
            return near_hazard if "near" in key else far_hazard

        redis.get = mock_get

        with patch("app.services.hazard_service.settings", settings):
            result = await service.get_all_active(
                redis,
                lat=42.6977,
                lon=23.3219,
                radius_m=200.0,  # only 200 m
            )

        ids = [r.id for r in result]
        assert "near" in ids
        assert "far" not in ids

    @pytest.mark.asyncio
    async def test_results_sorted_freshest_first(self, settings):
        service = HazardService()
        redis = AsyncMock()
        redis.keys.return_value = ["hazard:old", "hazard:new"]

        async def mock_get(key):
            if "old" in key:
                return _make_redis_hazard(8.0, "old")
            return _make_redis_hazard(1.0, "new")

        redis.get = mock_get

        with patch("app.services.hazard_service.settings", settings):
            result = await service.get_all_active(redis)

        assert result[0].id == "new"
        assert result[1].id == "old"


class TestHazardValidation:
    """Validate the coordinate constraints on HazardReportCreate."""

    def test_valid_sofia_coords(self):
        report = HazardReportCreate(lat=42.6977, lon=23.3219, type=HazardType.POTHOLE)
        assert report.lat == 42.6977

    def test_outside_sofia_north_rejected(self):
        with pytest.raises(Exception):
            HazardReportCreate(lat=42.80, lon=23.32, type=HazardType.POTHOLE)

    def test_outside_sofia_west_rejected(self):
        with pytest.raises(Exception):
            HazardReportCreate(lat=42.69, lon=23.10, type=HazardType.POTHOLE)

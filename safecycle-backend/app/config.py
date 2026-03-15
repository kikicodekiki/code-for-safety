"""
SafeCycle Sofia — Application Configuration
All settings read from environment variables / .env file.
Never read os.environ directly outside this module.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── App ──────────────────────────────────────────────────────────────────
    APP_NAME: str = "SafeCycle Sofia API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"

    # ── Server ───────────────────────────────────────────────────────────────
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    ALLOWED_ORIGINS: list[str] = ["*"]

    # ── Database ─────────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://safecycle:safecycle@localhost/safecycle"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # ── Redis ─────────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    HAZARD_TTL_SECONDS: int = 36000          # 10 hours
    HAZARD_RECENT_THRESHOLD_HOURS: int = 1
    HAZARD_ACTIVE_THRESHOLD_HOURS: int = 10

    # ── Google APIs ───────────────────────────────────────────────────────────
    GOOGLE_MAPS_API_KEY: str = ""
    GOOGLE_ROADS_API_ENABLED: bool = True

    # ── Firebase ──────────────────────────────────────────────────────────────
    FIREBASE_CREDENTIALS_PATH: str = "firebase-credentials.json"
    FIREBASE_ENABLED: bool = True

    # ── Graph / routing ──────────────────────────────────────────────────────
    SOFIA_BBOX_NORTH: float = 42.73
    SOFIA_BBOX_SOUTH: float = 42.62
    SOFIA_BBOX_EAST: float = 23.42
    SOFIA_BBOX_WEST: float = 23.23
    GRAPH_CACHE_PATH: str = "data/sofia_graph.graphml"
    # Real bike alley GeoJSON from urbandata.sofia.bg
    GEOJSON_BIKE_ALLEYS_PATH: str = "data/sofia_bike_alleys.geojson"
    GRAPH_NETWORK_TYPE: str = "bike"

    # ── Safety thresholds ────────────────────────────────────────────────────
    # These are the product's CORE safety parameters.
    # They must never appear as magic numbers anywhere else in the codebase.

    # Applied when OSM maxspeed tag is missing — conservative assumption
    DEFAULT_SPEED_LIMIT_KMH: int = 50
    # Applied when OSM surface tag is missing — neutral assumption
    DEFAULT_SURFACE: str = "asphalt"
    # Roads above this speed are completely excluded from routing (weight=inf)
    MAX_ALLOWED_SPEED_KMH: int = 50
    # GPS proximity radius to trigger dismount/slow-down alert at intersection
    CROSSROAD_ALERT_RADIUS_M: float = 15.0
    # Radius around schools / playgrounds / bus stops for awareness events
    AWARENESS_ZONE_RADIUS_M: float = 30.0
    # Radius for proximity alert from user-reported hazard
    HAZARD_ALERT_RADIUS_M: float = 20.0

    # ── VeloBG KML Pipeline ───────────────────────────────────────────────────
    VELOBG_REFRESH_INTERVAL_S: int = 86400   # 24 hours between scheduled refreshes
    VELOBG_FETCH_TIMEOUT_S: int = 30
    VELOBG_KML_CACHE_PATH: str = "data/velobg_cache.kml"
    VELOBG_REDIS_KEY: str = "velobg:map_data"
    VELOBG_REDIS_TTL_S: int = 90000          # 25 hours — slightly longer than refresh interval

    # ── Air Quality (sensor.community) ───────────────────────────────────────
    # Path to the local JSON cache written after each successful fetch
    AIR_QUALITY_JSON_PATH: str = "data/sofia_air_quality.json"
    # How often the background scheduler re-fetches sensor data (seconds)
    AIR_QUALITY_REFRESH_INTERVAL_S: int = 1800   # 30 minutes

    # ── GPS WebSocket ─────────────────────────────────────────────────────────
    GPS_POLL_INTERVAL_S: int = 10
    WS_PING_INTERVAL_S: int = 30
    WS_MAX_CONNECTIONS: int = 500

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


# Singleton — import this everywhere
settings = Settings()

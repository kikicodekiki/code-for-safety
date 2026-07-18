"""
SafeCycle Sofia — Application Configuration
All settings read from environment variables / .env file.
Never read os.environ directly outside this module.
"""
from __future__ import annotations

from pydantic import field_validator
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
    # CORS allow-list. Empty = no cross-origin browser access (safe default for
    # a private/dev deploy; native mobile clients are unaffected by CORS).
    # Set to your web app's origin(s) as JSON, e.g. ["https://app.example.com"].
    # "*" is honoured but forces credentials off (browsers forbid the combo).
    ALLOWED_ORIGINS: list[str] = []

    # ── Security ──────────────────────────────────────────────────────────────
    # Shared secret required in the `X-API-Key` header on every protected route
    # (and as the `token` query param on the GPS WebSocket). Empty disables the
    # gate — set it as a platform secret to keep the deploy private. Never
    # commit a real value; .env is git-ignored.
    API_KEY: str = ""
    # Serve interactive docs (/docs, /redoc, /openapi.json). Off in production
    # by default so the API schema is not exposed publicly; auto-on outside
    # production. Flip to true to expose docs on a shared deploy if desired.
    ENABLE_DOCS: bool = False
    # Simple in-process per-client rate limit (requests/minute). Blunts abuse
    # and accidental hammering; /health is always exempt.
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 120

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
    # FIREBASE_CREDENTIALS_JSON takes priority when set — the full service
    # account JSON as a string, for platforms with no durable filesystem to
    # drop a credentials file on (Railway, Cloud Run, ECS/Fargate). Falls
    # back to FIREBASE_CREDENTIALS_PATH (a file on disk) when unset, which
    # is what local dev / docker-compose still uses.
    FIREBASE_CREDENTIALS_JSON: str = ""
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

    # ── GPS WebSocket ─────────────────────────────────────────────────────────
    GPS_POLL_INTERVAL_S: int = 10
    WS_PING_INTERVAL_S: int = 30
    WS_MAX_CONNECTIONS: int = 500

    @field_validator("DATABASE_URL")
    @classmethod
    def _normalise_database_url(cls, v: str) -> str:
        """
        Make managed-Postgres URLs work with the async (asyncpg) engine.

        Platforms like Railway/Heroku hand out `postgres://` or `postgresql://`
        URLs (the sync psycopg form). SQLAlchemy's async engine needs the
        `postgresql+asyncpg://` driver prefix, and asyncpg does not accept the
        libpq `sslmode` query param — so we rewrite the scheme and drop it.
        This lets you paste Railway's DATABASE_URL reference variable verbatim.
        """
        if v.startswith("postgres://"):
            v = "postgresql+asyncpg://" + v[len("postgres://"):]
        elif v.startswith("postgresql://"):
            v = "postgresql+asyncpg://" + v[len("postgresql://"):]

        # Strip a trailing ?sslmode=... (asyncpg configures TLS differently).
        if "sslmode=" in v:
            base, _, query = v.partition("?")
            kept = [p for p in query.split("&") if not p.startswith("sslmode=")]
            v = base + (("?" + "&".join(kept)) if kept else "")
        return v

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


# Singleton — import this everywhere
settings = Settings()

-- ============================================================
-- SafeCycle Sofia — Initial database schema
-- Requires PostgreSQL 15 + PostGIS 3.3
-- ============================================================

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ────────────────────────────────────────────────────────────
-- Hazard reports
-- PostgreSQL is the permanent record; Redis is the TTL cache.
-- ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS hazard_reports (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    lat         DOUBLE PRECISION NOT NULL,
    lon         DOUBLE PRECISION NOT NULL,
    geom        GEOMETRY(Point, 4326) GENERATED ALWAYS AS
                    (ST_SetSRID(ST_MakePoint(lon, lat), 4326)) STORED,
    type        VARCHAR(50) NOT NULL,
    description TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at  TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '10 hours'
);

CREATE INDEX IF NOT EXISTS idx_hazard_reports_geom
    ON hazard_reports USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_hazard_reports_expires
    ON hazard_reports(expires_at);
CREATE INDEX IF NOT EXISTS idx_hazard_reports_created
    ON hazard_reports(created_at DESC);

-- ────────────────────────────────────────────────────────────
-- Awareness zones
-- Seeded from OSM for kindergartens, playgrounds, bus stops.
-- NOT removed from routing graph — flagged in route response.
-- ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS awareness_zones (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        VARCHAR(255),
    type        VARCHAR(50) NOT NULL,
    -- type values: kindergarten | playground | bus_stop | accident_hotspot
    lat         DOUBLE PRECISION NOT NULL,
    lon         DOUBLE PRECISION NOT NULL,
    radius_m    DOUBLE PRECISION NOT NULL DEFAULT 30.0,
    geom        GEOMETRY(Point, 4326) GENERATED ALWAYS AS
                    (ST_SetSRID(ST_MakePoint(lon, lat), 4326)) STORED,
    buffer_geom GEOMETRY(Polygon, 4326), -- pre-computed buffer for fast lookup
    source      VARCHAR(100) DEFAULT 'osm',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_awareness_zones_geom
    ON awareness_zones USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_awareness_zones_buffer
    ON awareness_zones USING GIST(buffer_geom);
CREATE INDEX IF NOT EXISTS idx_awareness_zones_type
    ON awareness_zones(type);

-- ────────────────────────────────────────────────────────────
-- Device tokens for FCM push notifications
-- ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS device_tokens (
    token       VARCHAR(512) PRIMARY KEY,
    platform    VARCHAR(10) NOT NULL,  -- ios | android
    user_id     VARCHAR(255),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ────────────────────────────────────────────────────────────
-- Spatial helper function: awareness zones near a point
-- Used by the GPS proximity service for efficient zone lookup.
-- ────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION zones_near_point(
    p_lat      DOUBLE PRECISION,
    p_lon      DOUBLE PRECISION,
    p_radius_m DOUBLE PRECISION DEFAULT 30.0
)
RETURNS TABLE(
    id         UUID,
    name       VARCHAR,
    type       VARCHAR,
    lat        DOUBLE PRECISION,
    lon        DOUBLE PRECISION,
    radius_m   DOUBLE PRECISION,
    distance_m DOUBLE PRECISION
)
LANGUAGE SQL STABLE AS $$
    SELECT
        id,
        name,
        type,
        lat,
        lon,
        radius_m,
        ST_Distance(
            ST_SetSRID(ST_MakePoint(p_lon, p_lat), 4326)::geography,
            geom::geography
        ) AS distance_m
    FROM awareness_zones
    WHERE ST_DWithin(
        geom::geography,
        ST_SetSRID(ST_MakePoint(p_lon, p_lat), 4326)::geography,
        p_radius_m
    )
    ORDER BY distance_m;
$$;

-- ────────────────────────────────────────────────────────────
-- Seed: Known accident hotspots in Sofia (manually curated)
-- These are hard danger zones — nodes within radius are
-- excluded from the routing graph entirely.
-- ────────────────────────────────────────────────────────────
INSERT INTO awareness_zones (name, type, lat, lon, radius_m, source)
VALUES
    ('Орлов мост кръстовище',       'accident_hotspot', 42.6945, 23.3411, 40.0, 'manual'),
    ('бул. Черни връх / ул. Резово', 'accident_hotspot', 42.6698, 23.3187, 35.0, 'manual'),
    ('бул. България / ул. Тодорини кукли', 'accident_hotspot', 42.6815, 23.2981, 35.0, 'manual')
ON CONFLICT DO NOTHING;

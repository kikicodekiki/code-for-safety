-- Migration 006: VeloBG paths table
-- Stores cycling infrastructure paths extracted from the VeloBG Google My Maps KML.
-- Refreshed on a 24-hour schedule — truncate + re-insert pattern.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS velobg_paths (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name                    TEXT,
    description             TEXT,
    path_type               VARCHAR(50)      NOT NULL,
    layer_name              TEXT,
    style_id                TEXT,
    colour_hex              CHAR(7),
    length_m                DOUBLE PRECISION NOT NULL DEFAULT 0,
    is_bidirectional        BOOLEAN          NOT NULL DEFAULT TRUE,
    is_usable               BOOLEAN          NOT NULL DEFAULT TRUE,
    edge_weight_multiplier  DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    source_placemark_id     TEXT,
    geom                    GEOMETRY(LineString, 4326) NOT NULL,
    fetched_at              TIMESTAMPTZ      NOT NULL DEFAULT NOW(),
    created_at              TIMESTAMPTZ      NOT NULL DEFAULT NOW()
);

-- Spatial index for map display queries
CREATE INDEX IF NOT EXISTS idx_velobg_paths_geom
    ON velobg_paths USING GIST (geom);

-- Index for routing queries (filter by usable + path_type)
CREATE INDEX IF NOT EXISTS idx_velobg_paths_usable_type
    ON velobg_paths (is_usable, path_type);

-- Index for chronological queries
CREATE INDEX IF NOT EXISTS idx_velobg_paths_fetched_at
    ON velobg_paths (fetched_at DESC);

COMMENT ON TABLE velobg_paths IS
    'Cycling infrastructure paths extracted from the VeloBG Google My Maps KML. '
    'Truncated and re-populated on each 24-hour refresh cycle.';

COMMENT ON COLUMN velobg_paths.path_type IS
    'VeloBGPathType: dedicated_lane, painted_lane, shared_path, greenway, off_road, proposed, unknown';

COMMENT ON COLUMN velobg_paths.edge_weight_multiplier IS
    'Routing weight multiplier (0.3–1.0). Lower = safer / more preferred.';

COMMENT ON COLUMN velobg_paths.geom IS
    'PostGIS LineString in WGS-84 (SRID 4326). Coordinates in lon,lat order.';

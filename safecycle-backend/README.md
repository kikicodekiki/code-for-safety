# SafeCycle Sofia — Backend API

**Cycling safety navigation for Sofia, Bulgaria**
*Built for the "Code for Security" hackathon*

---

## Overview

SafeCycle Sofia is the server-side implementation of a cycling safety navigation app. It downloads and preprocesses the Sofia street graph, applies a multi-factor safety cost function to every road edge, runs a hybrid Dijkstra/A* routing algorithm, manages real-time GPS streams from cyclists, and handles a Waze-style crowd-sourced hazard reporting system.

## Data Sources

| Source | Description |
|--------|-------------|
| [OpenStreetMap via OSMnx](https://osmnx.readthedocs.io) | Sofia street graph with speed limits, surface types, highway classifications |
| [Sofia Open Data — urbandata.sofia.bg](https://urbandata.sofia.bg/tl/api/3) | 486 verified bike alleys in GeoJSON format (`data/sofia_bike_alleys.geojson`) |
| Crowd-sourced reports | Real-time hazard reports from cyclists via POST /hazard |

## Quick Start

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env — set GOOGLE_MAPS_API_KEY at minimum

# 2. Start all services
docker-compose up --build

# 3. The API is available at http://localhost:8000
# 4. Interactive docs: http://localhost:8000/docs
```

The first startup downloads the Sofia OSMnx graph (~60–120 s). Subsequent starts load from the GraphML cache in ~2 s.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   FastAPI App                        │
│  GET /route  POST /hazard  GET /hazards  WS /ws/gps │
└──────────────┬──────────────────────────────────────┘
               │
       ┌───────▼────────┐
       │  RoutingService │
       │  (orchestrator) │
       └───────┬────────┘
               │
    ┌──────────▼──────────────┐
    │      Core Pipeline       │
    │  1. GraphLoader.load()   │  ← OSMnx download / GraphML cache
    │  2. GeoJSONEnricher      │  ← Sofia Open Data bike alleys
    │  3. compute_edge_weight  │  ← 7-factor safety cost function
    │  4. A* (safe_weight)     │  ← networkx.astar_path()
    │  5. SafeRouteResult      │  ← crossroads, zones, safety score
    └──────────────────────────┘
               │
    ┌──────────▼──────────────┐    ┌──────────────┐
    │   HazardService          │◄──►│ Redis (TTL)  │
    │   (dynamic penalties)    │    └──────────────┘
    └──────────────────────────┘
               │
    ┌──────────▼──────────────┐    ┌──────────────┐
    │   PostgreSQL + PostGIS   │    │  Firebase FCM │
    │   (permanent records)    │    │  (push alerts)│
    └──────────────────────────┘    └──────────────┘
```

## Safety Cost Function

Every road edge receives a weight `w(e)`:

```
w = length_m × traffic_factor × surface_factor × speed_factor × bike_factor
    + hazard_penalty
```

### Bike Infrastructure Tiers (from Sofia Open Data)

| Source | Tier | Factor |
|--------|------|--------|
| Sofia bike alley (dedicated) | `alley` | **0.25** |
| Recreational route | `recreational` | **0.30** |
| Connecting route on main streets | `connecting` | **0.55** |
| OSM cycleway tag | `cycleway` | 0.60 |
| OSM bike lane | `bike_lane` | 0.75 |
| No infrastructure | — | 1.00 |

### Speed Limit Rules

- **Missing maxspeed** → treated as 50 km/h (conservative default, flagged in response)
- **> 50 km/h** → `weight = inf` (excluded from routing entirely)
- **motorway / trunk / motorway_link / trunk_link** → always excluded

### Hazard Penalty Decay

```
penalty(age_hours) = max(0.0, 2.0 − age_hours × 0.2)
```
A fresh report adds +2.0 to nearby edge weight; after 10 hours it adds +0.0.

## API Reference

### `GET /route`

```
/route?origin_lat=42.6977&origin_lon=23.3219&dest_lat=42.7100&dest_lon=23.3350
```

Returns GeoJSON LineString with crossroad nodes, awareness zones, and safety score.

**Response flags:**
- `surface_defaulted: true` — some edges used the default asphalt assumption
- `speed_limit_defaulted: true` — some edges assumed 50 km/h due to missing OSM data
- `safety_label` — `"Safe"` (≥0.7) / `"Moderate"` (≥0.4) / `"Risky"` (<0.4)

### `POST /hazard`

```json
{
  "lat": 42.6977, "lon": 23.3219,
  "type": "pothole",
  "description": "Large pothole near the bus stop"
}
```

Reports persist for 10 hours and dynamically increase edge weights near the hazard.

### `GET /hazards`

```
/hazards?lat=42.6977&lon=23.3219&radius_m=500
```

### `WS /ws/gps`

**Send** (every `GPS_POLL_INTERVAL_S` seconds):
```json
{"lat": 42.6977, "lon": 23.3219, "heading": 90.0, "speed_kmh": 15.0}
```

**Receive** (when proximity thresholds are crossed):
```json
{"event": "crossroad",      "payload": {"distance_m": 12.4, "node": {...}}}
{"event": "awareness_zone", "payload": {"zone_type": "playground", ...}}
{"event": "hazard_nearby",  "payload": {"hazard": {...}, "distance_m": 18.0}}
```

## Project Structure

```
safecycle-backend/
├── app/
│   ├── main.py                     # FastAPI factory, lifespan, middleware
│   ├── config.py                   # Pydantic BaseSettings
│   ├── dependencies.py             # FastAPI DI injectors
│   ├── api/routes/                 # REST endpoints
│   ├── api/websocket/gps.py        # Real-time GPS WebSocket
│   ├── core/graph/                 # OSMnx loader, weighting, GeoJSON enricher
│   ├── core/routing/               # A* algorithm, heuristic, simplification
│   ├── core/proximity/             # Crossroad and awareness zone detection
│   ├── models/                     # Pydantic schemas + SQLAlchemy ORM models
│   ├── services/                   # Hazard, routing, GPS, notification services
│   └── db/                         # Async SQLAlchemy session + SQL migrations
├── data/
│   └── sofia_bike_alleys.geojson   # 486 bike paths from urbandata.sofia.bg
├── scripts/
│   ├── preload_graph.py            # Pre-download OSMnx graph (Docker build)
│   └── seed_awareness_zones.py     # Seed kindergartens/playgrounds from OSM
├── tests/                          # pytest unit tests
├── Dockerfile
└── docker-compose.yml
```

## Running Tests

```bash
pip install -r requirements.txt
pytest tests/ -v --tb=short
```

## Configuration

All safety thresholds are in `.env` and map to `Settings` constants. They are **never** magic numbers inline.

| Variable | Default | Description |
|----------|---------|-------------|
| `DEFAULT_SPEED_LIMIT_KMH` | 50 | Assumed speed when OSM maxspeed is missing |
| `MAX_ALLOWED_SPEED_KMH` | 50 | Roads above this are excluded (w=inf) |
| `DEFAULT_SURFACE` | asphalt | Assumed surface when OSM surface is missing |
| `CROSSROAD_ALERT_RADIUS_M` | 15.0 | GPS radius to trigger intersection alert |
| `AWARENESS_ZONE_RADIUS_M` | 30.0 | Radius around schools/bus stops for alerts |
| `HAZARD_ALERT_RADIUS_M` | 20.0 | GPS radius to trigger hazard alert |
| `HAZARD_TTL_SECONDS` | 36000 | How long hazard reports live in Redis (10 h) |

## Technology Stack

- **FastAPI** — async web framework
- **OSMnx + NetworkX** — graph download and A* routing
- **Shapely + GeoPandas** — geospatial operations
- **PostgreSQL 15 + PostGIS** — permanent hazard and zone storage
- **Redis 7** — TTL-expiring hazard cache (fast path for routing)
- **Firebase FCM** — push notifications
- **structlog** — structured JSON logging

---

*SafeCycle Sofia — "Code for Security" hackathon, 2025*

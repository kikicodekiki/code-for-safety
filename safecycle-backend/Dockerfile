FROM python:3.11-slim

# Runtime system libraries. The geospatial stack (shapely, pyproj, pyogrio,
# fiona) installs from manylinux wheels that bundle their own GEOS/PROJ/GDAL,
# so no -dev headers or source compile are needed here. curl is kept for the
# HEALTHCHECK; git for any VCS-based pip deps.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (layer cache optimisation).
# Every requirement ships a prebuilt wheel — no source compilation — so the
# build stays light enough for memory-constrained builders (e.g. Railway).
# The previous `pip install GDAL==$(gdal-config --version)` compiled the osgeo
# bindings from source, which nothing imports; it was removed.
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Create data directory for graph cache
RUN mkdir -p /app/data

# Pre-download Sofia graph at build time so first request is instant.
# The || true ensures a failed download (e.g. no network at build time)
# does not break the image — the app will download on first startup instead.
RUN python scripts/preload_graph.py || true

EXPOSE 8000

# Liveness probe — returns 200 as soon as the process serves HTTP, WITHOUT
# gating on Redis/Postgres (those may be unprovisioned on a fresh platform).
# Railway assigns a dynamic $PORT; probe that (falling back to 8000 locally).
# start-period is generous: cold start loads the graph and does GeoJSON +
# VeloBG enrichment before uvicorn accepts requests.
HEALTHCHECK \
    --interval=30s \
    --timeout=10s \
    --start-period=240s \
    --retries=3 \
    CMD curl -f "http://localhost:${PORT:-8000}/health" || exit 1

# uvloop + httptools for maximum async performance.
# Shell form so ${PORT} (injected by Railway) expands; falls back to 8000.
CMD uvicorn app.main:app \
     --host 0.0.0.0 \
     --port ${PORT:-8000} \
     --workers 1 \
     --loop uvloop \
     --http httptools \
     --log-level warning

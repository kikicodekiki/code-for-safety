FROM python:3.11-slim

# System dependencies for osmnx, shapely, geopandas, asyncpg
RUN apt-get update && apt-get install -y \
    gdal-bin \
    libgdal-dev \
    libgeos-dev \
    libproj-dev \
    libpq-dev \
    gcc \
    g++ \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Expose GDAL headers so Fiona can compile against the system GDAL
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal

WORKDIR /app

# Install Python dependencies first (layer cache optimisation)
# Install GDAL Python bindings matching the system version before the rest
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir "GDAL==$(gdal-config --version)" \
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

# Readiness probe — checks graph, Redis, and DB are all healthy
HEALTHCHECK \
    --interval=30s \
    --timeout=10s \
    --start-period=90s \
    --retries=3 \
    CMD curl -f http://localhost:8000/health/ready || exit 1

# uvloop + httptools for maximum async performance
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--loop", "uvloop", \
     "--http", "httptools", \
     "--log-level", "warning"]

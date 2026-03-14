"""
SafeCycle Sofia — Health check endpoints.
GET /health       — liveness (always 200 if process is alive)
GET /health/ready — readiness (200 only when all dependencies are healthy)
"""
from __future__ import annotations

import networkx as nx
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import check_database, check_redis, get_db, get_graph, get_redis

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness probe")
async def health_check() -> dict:
    """
    Liveness probe — returns 200 as long as the process is running.
    Used by Docker HEALTHCHECK and load balancers.
    """
    return {"status": "ok", "version": settings.APP_VERSION}


@router.get("/health/ready", summary="Readiness probe")
async def readiness_check(
    graph: nx.MultiDiGraph = Depends(get_graph),
    redis: Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """
    Readiness probe — returns 200 only when ALL critical dependencies are up:
      - Sofia street graph loaded in memory
      - Redis connection healthy
      - PostgreSQL connection healthy

    Returns 503 if any dependency is unavailable.
    """
    graph_ok = graph is not None
    redis_ok = await check_redis(redis)
    db_ok = await check_database(db)

    checks = {
        "graph_loaded": graph_ok,
        "graph_node_count": graph.number_of_nodes() if graph_ok else 0,
        "graph_edge_count": graph.number_of_edges() if graph_ok else 0,
        "redis": redis_ok,
        "database": db_ok,
    }
    all_ready = graph_ok and redis_ok and db_ok

    return JSONResponse(
        status_code=200 if all_ready else 503,
        content={
            "status": "ready" if all_ready else "not_ready",
            "checks": checks,
        },
    )

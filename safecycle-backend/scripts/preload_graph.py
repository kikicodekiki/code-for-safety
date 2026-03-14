"""
SafeCycle Sofia — Pre-download and cache the Sofia OSMnx graph.

Run at Docker build time so the first API request is instant.
Can also be run manually to refresh the cached graph:

    python scripts/preload_graph.py

The graph is saved to GRAPH_CACHE_PATH (default: data/sofia_graph.graphml).
Subsequent app startups load from the cache in ~2 seconds instead of
downloading from OSMnx (~60-120 seconds depending on network).
"""
from __future__ import annotations

import asyncio
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import structlog

from app.config import settings
from app.core.graph.loader import GraphLoader


def _configure_logging() -> None:
    logging.basicConfig(format="%(message)s", level=logging.INFO)
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(colors=False),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


async def main() -> None:
    _configure_logging()
    logger = structlog.get_logger("preload_graph")

    logger.info(
        "preload_start",
        cache_path=settings.GRAPH_CACHE_PATH,
        bbox={
            "north": settings.SOFIA_BBOX_NORTH,
            "south": settings.SOFIA_BBOX_SOUTH,
            "east": settings.SOFIA_BBOX_EAST,
            "west": settings.SOFIA_BBOX_WEST,
        },
    )

    t_start = time.perf_counter()
    try:
        graph = await GraphLoader.load(settings)
        elapsed = time.perf_counter() - t_start
        logger.info(
            "preload_complete",
            nodes=graph.number_of_nodes(),
            edges=graph.number_of_edges(),
            elapsed_s=round(elapsed, 1),
            cache_path=settings.GRAPH_CACHE_PATH,
        )
    except Exception as exc:
        logger.error("preload_failed", error=str(exc))
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

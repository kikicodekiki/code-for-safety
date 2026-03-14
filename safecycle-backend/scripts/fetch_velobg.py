#!/usr/bin/env python3
"""
Manual VeloBG fetch + ingest script.

Usage:
    python scripts/fetch_velobg.py [--force] [--no-db] [--output path/to/out.json]

Options:
    --force      Bypass the 1-hour rate-limit cooldown
    --no-db      Skip PostgreSQL persistence (useful for local testing)
    --output     Write parsed paths as JSON to a file for inspection

Example:
    # Fetch live, persist to DB, print summary
    python scripts/fetch_velobg.py --force

    # Fetch and dump to JSON without touching the DB
    python scripts/fetch_velobg.py --force --no-db --output /tmp/velobg.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is on the path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.data.velobg.fetcher import VeloBGFetcher
from app.data.velobg.parser import VeloBGParser


async def main(force: bool, no_db: bool, output: str | None) -> None:
    print(f"[fetch_velobg] Starting fetch  (force={force})")

    fetcher = VeloBGFetcher(settings)
    parser  = VeloBGParser()

    kml_content, fallback_used = await fetcher.fetch(force=force)
    print(f"[fetch_velobg] KML fetched — {len(kml_content):,} bytes  (fallback={fallback_used})")

    map_data = parser.parse(kml_content, fetched_at=datetime.now(timezone.utc))

    print(f"\n── Parse Summary ────────────────────────────────")
    print(f"  Layers:       {len(map_data.layers)}")
    print(f"  Total paths:  {map_data.total_paths}")
    print(f"  Usable paths: {len(map_data.usable_paths)}")
    print(f"  Total points: {map_data.total_points}")
    print()

    from collections import Counter
    type_counts = Counter(p.path_type.value for p in map_data.all_paths)
    print("  Path types:")
    for ptype, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"    {ptype:<25} {count}")

    print()
    print("  Layers:")
    for layer in map_data.layers:
        print(f"    [{layer.name}]  {len(layer.paths)} paths, {len(layer.points)} points")

    if output:
        out_data = map_data.model_dump(mode="json")
        Path(output).write_text(json.dumps(out_data, indent=2, ensure_ascii=False))
        print(f"\n[fetch_velobg] JSON written to {output}")

    if not no_db:
        try:
            from app.db.session import async_session_factory
            from app.data.velobg.repository import VeloBGRepository
            repo = VeloBGRepository()
            async with async_session_factory() as session:
                inserted = await repo.replace_all(session, map_data)
            print(f"\n[fetch_velobg] Persisted {inserted} rows to PostgreSQL.")
        except Exception as exc:
            print(f"\n[fetch_velobg] DB persist failed: {exc}", file=sys.stderr)
            print("[fetch_velobg] Use --no-db to skip persistence.", file=sys.stderr)
    else:
        print("\n[fetch_velobg] Skipped DB persistence (--no-db).")


if __name__ == "__main__":
    parser_cli = argparse.ArgumentParser(description="Fetch and ingest VeloBG KML data")
    parser_cli.add_argument("--force",  action="store_true", help="Bypass cooldown")
    parser_cli.add_argument("--no-db",  action="store_true", help="Skip DB persistence")
    parser_cli.add_argument("--output", default=None, help="Write JSON output to file")
    args = parser_cli.parse_args()

    asyncio.run(main(force=args.force, no_db=args.no_db, output=args.output))

#!/usr/bin/env python3
"""
Debug script — inspect the raw VeloBG KML structure.

Usage:
    # Fetch fresh KML and inspect
    python scripts/inspect_velobg_kml.py

    # Inspect from local cache file
    python scripts/inspect_velobg_kml.py --file data/velobg_cache.kml

    # Show all unique colours found (to update classifier.py COLOUR_MAP)
    python scripts/inspect_velobg_kml.py --colours

    # Show raw XML for a specific layer
    python scripts/inspect_velobg_kml.py --layer "велоалея"

Output helps calibrate:
  - COLOUR_MAP in app/data/velobg/classifier.py
  - LAYER_NAME_MAP if new layer names appear
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from xml.etree import ElementTree as ET
from collections import Counter, defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _detect_ns(root: ET.Element) -> str:
    tag = root.tag
    return tag.split("}")[0] + "}" if tag.startswith("{") else ""


def _kml_colour_to_hex(kml_colour: str) -> str:
    c = kml_colour.strip().lstrip("#")
    if len(c) != 8:
        return "#??????"
    bb, gg, rr = c[2:4], c[4:6], c[6:8]
    return f"#{rr.upper()}{gg.upper()}{bb.upper()}"


def inspect(kml_content: str, show_colours: bool, filter_layer: str | None) -> None:
    root = ET.fromstring(kml_content)
    ns   = _detect_ns(root)
    doc  = root.find(f"{ns}Document") or root

    # ── Styles ──────────────────────────────────────────────────────────────
    styles: dict[str, str] = {}   # style_id → #RRGGBB
    for style_elem in doc.findall(f"{ns}Style"):
        sid   = style_elem.get("id", "")
        ls    = style_elem.find(f"{ns}LineStyle")
        if ls is not None:
            ce = ls.find(f"{ns}color")
            if ce is not None and ce.text:
                styles[f"#{sid}"] = _kml_colour_to_hex(ce.text)

    # Resolve StyleMap
    for sm in doc.findall(f"{ns}StyleMap"):
        mid = sm.get("id", "")
        for pair in sm.findall(f"{ns}Pair"):
            k = pair.find(f"{ns}key")
            u = pair.find(f"{ns}styleUrl")
            if k is not None and k.text == "normal" and u is not None:
                styles[f"#{mid}"] = styles.get(u.text, "#??????")
                break

    folders = doc.findall(f"{ns}Folder")
    print(f"\n── KML Summary ──────────────────────────────────────────")
    print(f"  Folders (layers):  {len(folders)}")
    print(f"  Style definitions: {len(styles)}")
    print()

    colour_usage: Counter[str]          = Counter()
    layer_colour_map: dict[str, set]    = defaultdict(set)
    layer_counts: dict[str, dict]       = {}

    for folder in folders:
        name_elem  = folder.find(f"{ns}name")
        layer_name = name_elem.text.strip() if name_elem is not None and name_elem.text else "?"

        if filter_layer and filter_layer.lower() not in layer_name.lower():
            continue

        placemarks = folder.findall(f"{ns}Placemark")
        lines      = sum(1 for p in placemarks if p.find(f"{ns}LineString") is not None)
        points     = sum(1 for p in placemarks if p.find(f"{ns}Point")      is not None)

        layer_counts[layer_name] = {"total": len(placemarks), "lines": lines, "points": points}

        for placemark in placemarks:
            su = placemark.find(f"{ns}styleUrl")
            if su is not None and su.text:
                colour = styles.get(su.text, "#??????")
                colour_usage[colour] += 1
                layer_colour_map[layer_name].add(colour)

    # ── Print layer table ───────────────────────────────────────────────────
    print(f"  {'Layer':<40} {'Total':>6} {'Lines':>6} {'Points':>7}")
    print(f"  {'-'*40} {'-'*6} {'-'*6} {'-'*7}")
    for name, counts in sorted(layer_counts.items()):
        colours_str = ", ".join(sorted(layer_colour_map.get(name, set())))
        print(
            f"  {name:<40} {counts['total']:>6} {counts['lines']:>6} "
            f"{counts['points']:>7}   colours: {colours_str}"
        )

    if show_colours:
        print(f"\n── Unique colours found ─────────────────────────────────")
        print(f"  (Add these to COLOUR_MAP in app/data/velobg/classifier.py)")
        print()
        for colour, count in colour_usage.most_common():
            layers_using = [l for l, cs in layer_colour_map.items() if colour in cs]
            print(f"  \"{colour}\": VeloBGPathType.UNKNOWN,   # {count:>4}x  —  {', '.join(layers_using)}")


async def _fetch_kml() -> str:
    from app.config import settings
    from app.data.velobg.fetcher import VeloBGFetcher
    fetcher = VeloBGFetcher(settings)
    content, _ = await fetcher.fetch(force=False)
    return content


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description="Inspect VeloBG KML structure")
    cli.add_argument("--file",    default=None,            help="Local KML file path")
    cli.add_argument("--colours", action="store_true",     help="List unique colours")
    cli.add_argument("--layer",   default=None,            help="Filter to one layer name")
    args = cli.parse_args()

    if args.file:
        kml = Path(args.file).read_text(encoding="utf-8")
        print(f"[inspect] Loaded from {args.file}  ({len(kml):,} bytes)")
    else:
        print("[inspect] Fetching KML from Google My Maps...")
        kml = asyncio.run(_fetch_kml())
        print(f"[inspect] Fetched {len(kml):,} bytes")

    inspect(kml, show_colours=args.colours, filter_layer=args.layer)

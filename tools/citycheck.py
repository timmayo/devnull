#!/usr/bin/env python3
"""citycheck.py - is a city ready to ship? Lists what is still missing in a city file.

    python tools/citycheck.py                  every city in cities/ (a report; always exits 0)
    python tools/citycheck.py grand_rapids     one city
    python tools/citycheck.py --release        exit 1 if any city has a blocker (use this before a release)

A city is a major version of the game, so it is only ready when every real fact is researched and sourced,
the real-officials blocklist is filled, and the name pools and events are there. Each line below says what
to fix and where. "Blockers" must be zero to ship; "warnings" are worth a look.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from devnull import __version__  # noqa: E402

CITIES = ROOT / "cities"
STALE_DAYS = 180                  # a fact retrieved longer ago than this is worth re-checking
MIN_NAMES = 40                    # smallest name pool that gives enough variety
CITY_FIELDS = ("id", "display_name", "state", "content_version", "min_game_version")


def version_tuple(v: Any) -> tuple[int, ...] | None:
    try:
        return tuple(int(p) for p in str(v).split("."))
    except ValueError:
        return None


def as_date(v: Any) -> date | None:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v))
    except ValueError:
        return None


def walk(node: Any, path: str):
    """Every scalar in a nested structure, with its path."""
    if isinstance(node, dict):
        for k, v in node.items():
            yield from walk(v, f"{path}.{k}" if path else str(k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk(v, f"{path}[{i}]")
    else:
        yield path, node


def fact_entries(node: Any, path: str):
    """The facts in the `real` layer: a mapping that holds plain values (not just more mappings) is one fact."""
    if isinstance(node, dict):
        if any(not isinstance(v, dict) for v in node.values()):
            yield path, node
        else:
            for k, v in node.items():
                yield from fact_entries(v, f"{path}.{k}" if path else str(k))


def check_city(data: dict[str, Any], today: date) -> tuple[list[str], list[str], dict[str, int]]:
    """(blockers, warnings, counts)"""
    blockers: list[str] = []
    warnings: list[str] = []
    city = data.get("city") or {}

    for f in CITY_FIELDS:
        if not city.get(f):
            blockers.append(f"city.{f} is missing")
    need = version_tuple(city.get("min_game_version"))
    have = version_tuple(__version__)
    if city.get("min_game_version") and need is None:
        blockers.append(f"city.min_game_version {city['min_game_version']!r} is not a version like 1.0")
    elif need and have and need > have:
        blockers.append(f"city needs game {city['min_game_version']} or newer; this is {__version__}")

    # ---- the real layer
    unresearched = unconfirmed = 0
    real = data.get("real") or {}
    covered: set[str] = set()
    for path, e in fact_entries(real, "real"):
        gaps = [k for k, v in e.items() if v == "VERIFY"]
        flags = [str(v) for k, v in e.items() if isinstance(v, str) and v.startswith("VERIFY_")]
        covered.update(f"{path}.{k}" for k in e)
        if gaps:
            unresearched += 1
            blockers.append(f"{path}: not researched yet (fill in: {', '.join(gaps)})")
        for flag in flags:
            unconfirmed += 1
            blockers.append(f"{path}: researched but not confirmed ({flag})")
    for path, v in walk(real, "real"):                  # anything marked VERIFY outside a sourced fact
        if path not in covered and isinstance(v, str) and v.startswith("VERIFY"):
            unresearched += 1
            blockers.append(f"{path}: not researched yet ({v})")
    stale = 0
    for path, e in fact_entries(real, "real"):
        if not e.get("source"):
            blockers.append(f"{path}: has no source")
        r = as_date(e.get("retrieved"))
        if r and (today - r).days > STALE_DAYS:
            stale += 1
            warnings.append(f"{path}: retrieved {r}, over {STALE_DAYS} days ago (re-check)")
        elif e.get("retrieved") is None and e.get("source") not in (None, "VERIFY"):
            warnings.append(f"{path}: no `retrieved` date")

    # ---- fictional layer and display
    fic = data.get("fictional") or {}
    if not (fic.get("cast_templates") or {}):
        blockers.append("fictional.cast_templates is missing (no cast to generate)")
    if not (fic.get("plot_rules") or []):
        blockers.append("fictional.plot_rules is missing (the rules that keep real people out)")
    if not (data.get("display") or {}).get("disclaimer"):
        blockers.append("display.disclaimer is missing")

    # ---- real officials blocklist and name pools
    gen = fic.get("generation") or {}
    coll = gen.get("collision_check") or {}
    listed = 0
    bl = coll.get("blocklist")
    if coll.get("enabled") and bl:
        p = ROOT / bl
        if not p.exists():
            blockers.append(f"{bl}: blocklist file not found")
        else:
            listed = sum(1 for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.startswith("#"))
            if listed == 0:
                blockers.append(f"{bl}: empty. Fill it with the city's real office-holders (now and recent past) from published rosters")
    else:
        blockers.append("fictional.generation.collision_check is not set up (real-name blocklist)")
    for kind, rel in (gen.get("name_pools") or {}).items():
        p = ROOT / rel
        n = sum(1 for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.startswith("#")) if p.exists() else -1
        if n < 0:
            blockers.append(f"{rel}: {kind} name pool not found")
        elif n < MIN_NAMES:
            warnings.append(f"{rel}: only {n} {kind} names (aim for {MIN_NAMES}+)")

    # ---- dated events and news
    events = data.get("events") or []
    upcoming = past = 0
    for e in events:
        who = f"events[{e.get('id', '?')}]"
        for f in ("id", "title", "start", "source", "retrieved"):
            if not e.get(f):
                blockers.append(f"{who}: missing {f}")
        if not e.get("url"):
            warnings.append(f"{who}: no url (players cannot check it)")
        end = as_date(e.get("end") or e.get("start"))
        if end and end < today:
            past += 1
        else:
            upcoming += 1
    if not upcoming:
        warnings.append("no upcoming dated events: players will have nothing real to attend")
    news = data.get("news") or {}
    for e in news.get("real_events") or []:
        for f in ("source", "url", "retrieved"):
            if not e.get(f):
                warnings.append(f"news.real_events[{e.get('id', '?')}]: missing {f}")
    if not (news.get("fillers") or {}).get("all"):
        warnings.append("news.fillers.all is empty")

    counts = {"unresearched": unresearched, "unconfirmed": unconfirmed, "stale facts": stale,
              "blocklist names": listed, "events upcoming": upcoming, "events past": past}
    return blockers, warnings, counts


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("city", nargs="?", help="a city id (default: every city)")
    ap.add_argument("--release", action="store_true", help="exit 1 if any city has a blocker")
    ap.add_argument("--quiet", action="store_true", help="summary lines only")
    args = ap.parse_args()

    paths = sorted(CITIES.glob("*.yaml"))
    if args.city:
        paths = [p for p in paths if p.stem == args.city]
        if not paths:
            sys.exit(f"No city file cities/{args.city}.yaml")
    today = date.today()
    worst = 0
    for p in paths:
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
        blockers, warnings, counts = check_city(data, today)
        city = data.get("city") or {}
        ready = not blockers
        worst = max(worst, 0 if ready else 1)
        print(f"{city.get('display_name', p.stem)}, {city.get('state', '?')}  content {city.get('content_version', '?')}  "
              f"-  {'READY TO SHIP' if ready else 'NOT READY'}  ({len(blockers)} blocker(s), {len(warnings)} warning(s))")
        print("  " + ", ".join(f"{k}: {v}" for k, v in counts.items()))
        if not args.quiet:
            for b in blockers:
                print(f"  BLOCKER  {b}")
            for w in warnings:
                print(f"  warning  {w}")
        print()
    return worst if args.release else 0


if __name__ == "__main__":
    raise SystemExit(main())

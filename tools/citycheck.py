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
import re
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
RESOURCE_KINDS = ("facts", "events", "feed", "roster", "other")
REQUIRED_KINDS = ("facts", "events", "feed", "roster")      # a city needs at least one of each
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


def _rule_files() -> tuple[dict[str, Any], dict[str, Any]]:
    """(data/slice_rules.yaml, data/people.yaml): what a city's mechanics, setup and overrides must fit."""
    load = lambda n: yaml.safe_load((ROOT / "data" / n).read_text(encoding="utf-8"))  # noqa: E731
    return load("slice_rules.yaml"), load("people.yaml")


def _dotted(tree: Any, path: str) -> Any:
    for part in path.split("."):
        tree = tree.get(part) if isinstance(tree, dict) else None
    return tree


def check_mechanics(data: dict[str, Any]) -> tuple[list[str], list[str]]:
    """The `mechanics`, `setup`, `start` and `daily` blocks: present, sourced, and fitting the game's rules."""
    blockers: list[str] = []
    warnings: list[str] = []
    rules, people = _rule_files()
    state_vars = set(rules["start"])
    skills = set((people.get("skills") or {}).get("catalog") or {})
    mech = data.get("mechanics")
    setup = data.get("setup")

    for name, block in (("mechanics", mech), ("setup", setup)):
        if not isinstance(block, dict) or not block:
            blockers.append(f"{name}: is missing (see tools/city_template.yaml)")
            continue
        for path, v in walk(block, name):
            if isinstance(v, str) and v.startswith("VERIFY"):
                blockers.append(f"{path}: not filled in yet ({v})")

    def sourced(block: str, spec: Any) -> None:
        fact = spec.get("source_fact") if isinstance(spec, dict) else None
        if not fact:
            blockers.append(f"{block}: has no source_fact (the `real:` fact its numbers come from)")
        elif _dotted(data, str(fact)) is None:
            blockers.append(f"{block}: source_fact '{fact}' is not in this file")

    if isinstance(mech, dict):
        rec = mech.get("records")
        if not isinstance(rec, dict):
            blockers.append("mechanics.records: is missing (the public-records response times)")
        else:
            sourced("mechanics.records", rec)
            if not isinstance(rec.get("respond_business_days"), int) or rec["respond_business_days"] < 1:
                blockers.append("mechanics.records.respond_business_days: must be a whole number of 1 or more")
            for k in ("receive_lag_business_days", "extension_business_days"):
                if k in rec and not (isinstance(rec[k], int) and rec[k] >= 0):
                    blockers.append(f"mechanics.records.{k}: must be a whole number of 0 or more")
            if not 0 <= float(rec.get("extension_chance", 0) or 0) <= 1:
                blockers.append("mechanics.records.extension_chance: must be between 0 and 1")
        el = mech.get("elections")
        if not isinstance(el, dict) or not el.get("contests"):
            blockers.append("mechanics.elections.contests: is missing (the city's own races and when they fall)")
        else:
            sourced("mechanics.elections", el)
            for c in el["contests"]:
                who = f"mechanics.elections.contests[{c.get('id', '?')}]"
                for f in ("id", "label", "years", "effect"):
                    if not c.get(f):
                        blockers.append(f"{who}: missing {f}")
                if c.get("years") not in ("even", "presidential"):
                    blockers.append(f"{who}: years must be even or presidential (is {c.get('years')!r})")
                for var in ((c.get("effect") or {}).get("terms") or {}):
                    if var not in state_vars:
                        blockers.append(f"{who}: effect uses '{var}', which is not a game value")
        for name in ("zoning", "open_meetings"):
            if isinstance(mech.get(name), dict):
                sourced(f"mechanics.{name}", mech[name])
            else:
                warnings.append(f"mechanics.{name}: is missing (used by the zoning storyline, a later release)")

    for key in ("start", "daily"):
        block = data.get(key) or {}
        if not isinstance(block, dict):
            blockers.append(f"{key}: must be a mapping")
            continue
        for path in block:
            if key == "start" and path not in state_vars:
                blockers.append(f"start.{path}: not a game value (see start: in data/slice_rules.yaml)")
            if key == "daily" and not isinstance(_dotted(rules["daily"], path), (int, float)):
                blockers.append(f"daily.{path}: not a number in daily: of data/slice_rules.yaml")

    if isinstance(setup, dict):
        for g in ("neighborhood", "job"):
            if not (isinstance(setup.get(g), dict) and setup[g].get("options")):
                blockers.append(f"setup.{g}: is missing (a player chooses a home neighborhood and a day job)")
        if not (isinstance(setup.get("cushion"), dict) and setup["cushion"].get("options")):
            warnings.append("setup.cushion: is missing (the savings choice)")
        hood_text = str(_dotted(data, "real.geography.neighborhoods.value") or "")
        for g, spec in setup.items():
            if not isinstance(spec, dict) or not spec.get("options"):
                continue
            if g in ("neighborhood", "job"):
                sourced(f"setup.{g}", spec)
            seen: set[str] = set()
            defaults = [o for o in spec["options"] if o.get("default")]
            if len(defaults) > 1:
                blockers.append(f"setup.{g}: more than one default option")
            default = (defaults or spec["options"])[0]
            for o in spec["options"]:
                who = f"setup.{g}.{o.get('id', '?')}"
                for f in ("id", "name", "blurb"):
                    if not o.get(f):
                        blockers.append(f"{who}: missing {f}")
                if o.get("id") in seen:
                    blockers.append(f"{who}: id is used twice")
                seen.add(o.get("id"))
                if o is default and any(o.get(k) for k in ("daily", "state", "skills")):
                    blockers.append(f"{who}: the default option must have no effects (it is the baseline)")
                for path in o.get("daily") or {}:
                    if not isinstance(_dotted(rules["daily"], path), (int, float)):
                        blockers.append(f"{who}: daily.{path} is not a number in daily: of data/slice_rules.yaml")
                for var in o.get("state") or {}:
                    if var not in state_vars:
                        blockers.append(f"{who}: state.{var} is not a game value")
                for sk, lvl in (o.get("skills") or {}).items():
                    if sk not in skills:
                        blockers.append(f"{who}: skill '{sk}' is not in the skill catalog (data/people.yaml)")
                    elif lvl not in (1, 2, 3):
                        blockers.append(f"{who}: skill level for '{sk}' must be 1, 2 or 3")
                if g == "neighborhood" and o.get("name") and o["name"] not in hood_text:
                    blockers.append(f"{who}: '{o['name']}' is not in real.geography.neighborhoods (use a real neighborhood)")
    return blockers, warnings


def check_city(data: dict[str, Any], today: date) -> tuple[list[str], list[str], dict[str, int]]:
    """(blockers, warnings, counts)"""
    blockers: list[str] = []
    warnings: list[str] = []
    city = data.get("city") or {}

    for f in CITY_FIELDS:
        if not city.get(f):
            blockers.append(f"city.{f} is missing")
    if city.get("status", "released") not in ("draft", "released"):
        blockers.append(f"city.status must be draft or released (is {city.get('status')!r})")
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
        sink = warnings if e.get("use") == "reference" else blockers      # reference-only facts never block a release
        if gaps:
            unresearched += 1
            sink.append(f"{path}: not researched yet (fill in: {', '.join(gaps)})")
        for flag in flags:
            unconfirmed += 1
            sink.append(f"{path}: researched but not confirmed ({flag})")
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

    # ---- resources: every outside page the city's content comes from
    res = data.get("resources")
    r_total = r_needed = 0
    if not isinstance(res, list) or not res:
        blockers.append("resources: is missing (list every outside page this city's content comes from)")
    else:
        seen_ids: set[str] = set()
        kinds_present: set[str] = set()
        manifest_urls: set[str] = set()
        for i, r in enumerate(res, 1):
            if not isinstance(r, dict) or not r.get("id"):
                blockers.append(f"resources[#{i}]: has no id")
                continue
            r_total += 1
            who = f"resources.{r['id']}"
            if r["id"] in seen_ids:
                blockers.append(f"{who}: id is used twice")
            seen_ids.add(r["id"])
            if r.get("kind") not in RESOURCE_KINDS:
                blockers.append(f"{who}: kind must be one of {', '.join(RESOURCE_KINDS)} (is {r.get('kind')!r})")
            else:
                kinds_present.add(r["kind"])
            url = r.get("url")
            if url is None:
                r_needed += 1
                blockers.append(f"{who}: needs a URL ({r.get('note') or r.get('name') or 'no note'})")
            elif not (isinstance(url, str) and url.startswith(("http://", "https://"))):
                blockers.append(f"{who}: url must start with http:// or https://")
            else:
                manifest_urls.add(url.rstrip("/"))
            got = as_date(r.get("retrieved"))
            if got and (today - got).days > STALE_DAYS:
                warnings.append(f"{who}: retrieved {got}, over {STALE_DAYS} days ago (re-check)")
            for path_ in r.get("covers") or []:
                node: Any = data
                for part in str(path_).split("."):
                    node = node.get(part) if isinstance(node, dict) else None
                if node is None:
                    warnings.append(f"{who}: covers '{path_}', which is not in this file")
        for kind in REQUIRED_KINDS:
            if kind not in kinds_present:
                blockers.append(f"resources: no `{kind}` resource (a city needs at least one)")
        for path_, v in walk(real, "real"):
            for u in re.findall(r'https?://[^\s")\]]+', v) if isinstance(v, str) else []:
                if u.rstrip("/") not in manifest_urls:
                    warnings.append(f"{path_}: cites {u}, which is not in `resources`")

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

    mb, mw = check_mechanics(data)
    blockers += mb
    warnings += mw

    counts = {"resources": r_total, "needing URL": r_needed, "unresearched": unresearched, "unconfirmed": unconfirmed, "stale facts": stale,
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
        status = city.get("status", "released")
        print(f"{city.get('display_name', p.stem)}, {city.get('state', '?')}  content {city.get('content_version', '?')}  [{status}]  "
              f"-  {'READY TO SHIP' if ready else 'NOT READY'}  ({len(blockers)} blocker(s), {len(warnings)} warning(s))")
        if ready and status == "draft":
            print("  This city passes every check. Set `status: released` in its file to put it in the menu.")
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

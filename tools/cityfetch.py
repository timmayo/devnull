#!/usr/bin/env python3
"""cityfetch.py - do a city's resource links still work, and have the pages changed?

    python tools/cityfetch.py                    check every city's resources (a report)
    python tools/cityfetch.py grand_rapids       one city
    python tools/cityfetch.py --update           also save what the pages look like now (cities/<id>.links.json)
    python tools/cityfetch.py --strict           exit 1 if any link is dead (the weekly GitHub check uses this)

Each resource in a city file (resources: with a url) is fetched. The result is one of:
    ok        works, same content as the last saved check
    (feeds are only checked for reachability: their content changes daily)
    NEW       works, nothing saved yet to compare with (run with --update to save it)
    CHANGED   works, but the page text differs from the last saved check: re-read it, a fact may be out of date
    MOVED     works, but the address redirects somewhere else: update the url in the city file
    DEAD      cannot be fetched (error, 404, 5xx): fix or replace the link
    BLOCKED   the site answered 401, 403 or 429: it refuses automated visits. Open it in a browser to check it. (Not a failure.)
A resource with no url yet is listed as NEEDED. The saved check (cities/<id>.links.json) holds only a hash of the
visible page text, never the page itself. Needs internet access: run it on your PC or let GitHub run it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any, Callable

import yaml

ROOT = Path(__file__).resolve().parents[1]
CITIES = ROOT / "cities"
UA = "devnull-linkcheck/0.1 (+https://github.com/timmayo/devnull)"
MAX_BYTES = 3_000_000
BLOCKED_CODES = (401, 403, 429)

Fetcher = Callable[[str, float], dict[str, Any]]


# ---------------------------------------------------------------- fetching

def fetch(url: str, timeout: float = 20.0) -> dict[str, Any]:
    """{status, final_url, body (bytes), type} or {error}. Never raises."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
        with urllib.request.urlopen(req, timeout=timeout) as r:        # noqa: S310 (admin-supplied http(s) URLs)
            return {"status": r.status, "final_url": r.geturl(), "body": r.read(MAX_BYTES),
                    "type": r.headers.get("Content-Type", "")}
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}", "status": e.code}
    except Exception as e:                                                # network, DNS, TLS, timeout
        return {"error": f"{type(e).__name__}: {e}"[:160]}


def visible_hash(body: bytes, content_type: str) -> str:
    """A hash of what a reader would see: HTML tags, scripts and styles are dropped so ads and timestamps in the
    markup do not look like changes. Other types (PDF ...) are hashed as they are."""
    if "html" in content_type.lower() or body[:200].lstrip().lower().startswith((b"<!doctype html", b"<html")):
        text = body.decode("utf-8", "replace")
        text = re.sub(r"(?is)<(script|style|noscript)\b.*?</\1>", " ", text)
        text = re.sub(r"(?s)<!--.*?-->", " ", text)
        text = re.sub(r"(?s)<[^>]+>", " ", text)
        body = re.sub(r"\s+", " ", text).strip().lower().encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def concrete(url: str, city: dict[str, Any]) -> str:
    """Fill {city} and {state} in a feed address."""
    return url.format(city=urllib.parse.quote_plus(city.get("display_name", "")),
                      state=urllib.parse.quote_plus(city.get("state", "")))


# ---------------------------------------------------------------- one city

def same_address(a: str, b: str) -> bool:
    pa, pb = urllib.parse.urlsplit(a), urllib.parse.urlsplit(b)
    return (pa.netloc.lower().removeprefix("www."), pa.path.rstrip("/"), pa.query) == \
           (pb.netloc.lower().removeprefix("www."), pb.path.rstrip("/"), pb.query)


def check_resources(data: dict[str, Any], lock: dict[str, Any], getter: Fetcher = fetch,
                    timeout: float = 20.0) -> list[dict[str, Any]]:
    """One result per resource: {id, kind, url, state, detail, hash, final_url}."""
    city = data.get("city") or {}
    out: list[dict[str, Any]] = []
    for r in data.get("resources") or []:
        row = {"id": r.get("id", "?"), "kind": r.get("kind", "?"), "url": r.get("url"), "state": "", "detail": "",
               "hash": None, "final_url": None}
        out.append(row)
        if not r.get("url"):
            row["state"], row["detail"] = "NEEDED", r.get("note") or "no url yet"
            continue
        url = concrete(r["url"], city)
        got = getter(url, timeout)
        if "error" in got:
            if got.get("status") in BLOCKED_CODES:       # the site refuses automated visits; the page may be fine
                row["state"], row["detail"] = "BLOCKED", f"{got['error']}: the site refuses automated checks, open it in a browser"
            else:
                row["state"], row["detail"] = "DEAD", got["error"]
            continue
        row["hash"] = visible_hash(got["body"], got.get("type", ""))
        row["final_url"] = got["final_url"]
        prev = lock.get(row["id"]) or {}
        if not same_address(url, got["final_url"]):
            row["state"], row["detail"] = "MOVED", f"now {got['final_url']}"
        elif r.get("kind") == "feed":                    # headlines change every day; only reachability matters
            row["state"] = "ok"
        elif not prev.get("hash"):
            row["state"], row["detail"] = "NEW", "no saved check to compare with"
        elif prev["hash"] != row["hash"]:
            row["state"], row["detail"] = "CHANGED", f"page text differs from the check on {prev.get('checked', '?')}"
        else:
            row["state"] = "ok"
    return out


def lock_path(city_file: Path) -> Path:
    return city_file.with_suffix(".links.json")


def read_lock(city_file: Path) -> dict[str, Any]:
    try:
        return json.loads(lock_path(city_file).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def write_lock(city_file: Path, rows: list[dict[str, Any]], old: dict[str, Any]) -> None:
    today = date.today().isoformat()
    new = dict(old)
    for r in rows:
        if r["hash"]:                                   # only pages that could be read are saved
            new[r["id"]] = {"url": r["url"], "hash": r["hash"], "checked": today}
    lock_path(city_file).write_text(json.dumps(new, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("city", nargs="?", help="a city id (default: every city)")
    ap.add_argument("--update", action="store_true", help="save the current page hashes as the new baseline")
    ap.add_argument("--strict", action="store_true", help="exit 1 if any link is DEAD")
    ap.add_argument("--timeout", type=float, default=20.0)
    args = ap.parse_args()

    files = sorted(CITIES.glob("*.yaml"))
    if args.city:
        files = [p for p in files if p.stem == args.city]
        if not files:
            sys.exit(f"No city file cities/{args.city}.yaml")
    dead = 0
    for p in files:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        if not data.get("resources"):
            print(f"{p.stem}: no `resources:` list yet\n")
            continue
        lock = read_lock(p)
        rows = check_resources(data, lock, timeout=args.timeout)
        counts: dict[str, int] = {}
        for r in rows:
            counts[r["state"]] = counts.get(r["state"], 0) + 1
        print(f"{(data.get('city') or {}).get('display_name', p.stem)}: " + ", ".join(f"{n} {s}" for s, n in sorted(counts.items())))
        for r in rows:
            if r["state"] != "ok":
                print(f"  {r['state']:7} {r['id']:36} {r['detail']}")
        dead += counts.get("DEAD", 0)
        if args.update:
            write_lock(p, rows, lock)
            print(f"  saved {lock_path(p).name}")
        print()
    return 1 if (args.strict and dead) else 0


if __name__ == "__main__":
    raise SystemExit(main())

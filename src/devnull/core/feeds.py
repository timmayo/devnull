"""Live news headlines (RSS) for day 1 of a run. Standard library only.

Fails soft: any feed that cannot be fetched or parsed is skipped. Untested
against the live servers from the build sandbox: run `python -m devnull.core.feeds`
to check. Headline and link only.
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

import yaml

from devnull.core.sim import REPO_ROOT

UA = "devnull-game/0.0.1"
CACHE = Path.home() / ".devnull" / "news.json"
CACHE_SECONDS = 30 * 60


def parse_rss(text: str, outlet: str, max_age_hours: float, now: datetime | None = None) -> list[dict[str, Any]]:
    """RSS 2.0 items -> [{title, link, source, published}], newest first, recent only."""
    now = now or datetime.now(timezone.utc)
    root = ET.fromstring(text)
    items = []
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        src_el = it.find("source")
        source = (src_el.text or "").strip() if src_el is not None and src_el.text else outlet
        if src_el is not None and title.endswith(" - " + source):      # Google News appends the outlet
            title = title[: -len(source) - 3].strip()
        try:
            when = parsedate_to_datetime(it.findtext("pubDate") or "")
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            continue
        if not title or not link.startswith("http") or now - when > timedelta(hours=max_age_hours):
            continue
        items.append({"title": title, "link": link, "source": source, "published": when.isoformat()})
    return sorted(items, key=lambda i: i["published"], reverse=True)


def _fetch(feed: dict[str, str], city: str, state: str, max_age: float, timeout: float) -> list[dict[str, Any]]:
    url = feed["url"].format(city=urllib.parse.quote_plus(city), state=urllib.parse.quote_plus(state))
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:     # noqa: S310 (fixed https URLs)
            return parse_rss(r.read().decode("utf-8", "replace"), feed["name"], max_age)
    except Exception:
        return []


def fetch_feeds(city: str, state: str, timeout: float = 6.0, use_cache: bool = True) -> dict[str, list[dict[str, Any]]]:
    """{'local': [...], 'national': [...]} with at most `per_section` items each."""
    cfg = yaml.safe_load(open(REPO_ROOT / "data" / "feeds.yaml", encoding="utf-8"))
    key = f"{city}|{state}"
    if use_cache:
        try:
            c = json.loads(CACHE.read_text(encoding="utf-8"))
            if c["key"] == key and time.time() - c["saved"] < CACHE_SECONDS:
                return c["feed"]
        except (OSError, KeyError, ValueError):
            pass
    jobs = [("local", f) for f in cfg["local"]] + [("national", f) for f in cfg["national"]]
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda j: _fetch(j[1], city, state, cfg["max_age_hours"], timeout), jobs))
    out: dict[str, list[dict[str, Any]]] = {"local": [], "national": []}
    seen: set[str] = set()
    for (scope, _), items in zip(jobs, results):
        for it in items:
            if it["title"].lower() not in seen:
                seen.add(it["title"].lower())
                out[scope].append(it)
    for scope in out:
        out[scope] = sorted(out[scope], key=lambda i: i["published"], reverse=True)[: cfg["per_section"]]
    if out["local"] or out["national"]:
        try:
            CACHE.parent.mkdir(parents=True, exist_ok=True)
            CACHE.write_text(json.dumps({"key": key, "saved": time.time(), "feed": out}), encoding="utf-8")
        except OSError:
            pass
    return out


if __name__ == "__main__":
    import sys
    got = fetch_feeds(sys.argv[1] if len(sys.argv) > 1 else "Grand Rapids",
                      sys.argv[2] if len(sys.argv) > 2 else "Michigan", use_cache=False)
    for scope, items in got.items():
        print(scope.upper())
        for i in items:
            print(f"  {i['title']} ({i['source']}, {i['published'][:16]})\n    {i['link']}")
        if not items:
            print("  nothing fetched")

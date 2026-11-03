"""Delayed stock quotes for the market tape.

Tries Stooq (CSV, no key), then Yahoo's chart endpoint (JSON, unofficial). Both
are free, delayed and for personal use. A shipped game needs a licensed data
feed (see docs/design.md); swap `fetch_one` for it. Fails soft: any ticker that
cannot be fetched is simply left out. Standard library only.

Check it from a terminal:  python -m devnull.core.market
"""

from __future__ import annotations

import csv
import io
import json
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

UA = "devnull-game/0.0.1"
CACHE = Path.home() / ".devnull" / "quotes.json"
CACHE_SECONDS = 30 * 60


def _get(url: str, timeout: float) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:        # noqa: S310 (fixed https URLs)
        return r.read().decode("utf-8", "replace")


def parse_stooq(text: str) -> dict[str, Any] | None:
    """Stooq CSV: Symbol,Date,Time,Open,High,Low,Close,Volume. 'N/D' means no data."""
    rows = list(csv.DictReader(io.StringIO(text.strip())))
    if not rows:
        return None
    r = rows[0]
    try:
        close, opn = float(r["Close"]), float(r["Open"])
    except (KeyError, ValueError):
        return None
    return {"price": close, "change_pct": (close / opn - 1) * 100 if opn else 0.0,
            "basis": "vs open", "asof": f"{r.get('Date', '')} {r.get('Time', '')}".strip(),
            "source": "Stooq"}


def parse_yahoo(text: str) -> dict[str, Any] | None:
    try:
        meta = json.loads(text)["chart"]["result"][0]["meta"]
        price, prev = float(meta["regularMarketPrice"]), float(meta["chartPreviousClose"])
        ts = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(meta["regularMarketTime"]))
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError):
        return None
    return {"price": price, "change_pct": (price / prev - 1) * 100 if prev else 0.0,
            "basis": "vs prior close", "asof": ts, "source": "Yahoo Finance"}


def fetch_one(sym: str, timeout: float = 5.0) -> dict[str, Any] | None:
    attempts = [
        (f"https://stooq.com/q/l/?s={sym.lower()}.us&f=sd2t2ohlcv&h&e=csv", parse_stooq),
        (f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=5d", parse_yahoo),
    ]
    for url, parse in attempts:
        try:
            q = parse(_get(url, timeout))
        except Exception:                      # offline, blocked, timeout: try the next source
            continue
        if q:
            return q
    return None


def fetch_quotes(symbols: list[str], timeout: float = 5.0, use_cache: bool = True) -> dict[str, dict[str, Any]]:
    """Quotes for the symbols that could be fetched. Cached for 30 minutes."""
    if use_cache:
        try:
            cached = json.loads(CACHE.read_text(encoding="utf-8"))
            if time.time() - cached["saved"] < CACHE_SECONDS and set(symbols) <= set(cached["quotes"]):
                return {s: cached["quotes"][s] for s in symbols}
        except (OSError, KeyError, ValueError):
            pass
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda s: fetch_one(s, timeout), symbols))
    quotes = {s: q for s, q in zip(symbols, results) if q}
    if len(quotes) == len(symbols):
        try:
            CACHE.parent.mkdir(parents=True, exist_ok=True)
            CACHE.write_text(json.dumps({"saved": time.time(), "quotes": quotes}), encoding="utf-8")
        except OSError:
            pass
    return quotes


if __name__ == "__main__":
    import sys
    syms = sys.argv[1:] or ["MSFT", "AAPL", "META", "GOOGL", "AMZN", "NBIS", "CRWV", "IREN", "HUT", "APLD"]
    got = fetch_quotes(syms, use_cache=False)
    for s in syms:
        q = got.get(s)
        print(f"{s:<6}", f"{q['price']:>9.2f} {q['change_pct']:+6.2f}% ({q['basis']}) {q['source']} {q['asof']}" if q else "no data")

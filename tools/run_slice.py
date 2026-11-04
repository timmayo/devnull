"""Run the vertical slice headlessly across many seeds and summarize outcomes.

A run starts on the day the player first picks a city, so the start date
varies. By default each seed gets a different start date spread across a
4-year cycle; pass --start-date to fix one.

Usage (from the repo root):
    python tools/run_slice.py                 # 100 seeds, all policies
    python tools/run_slice.py --seeds 500
    python tools/run_slice.py --policy activist --trace 7   # one run, per-turn
    python tools/run_slice.py --start-date 2026-11-03
"""

from __future__ import annotations

import argparse
import statistics as st
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from devnull.core.policies import POLICIES  # noqa: E402
from devnull.core.sim import load_rules, play  # noqa: E402

KEYS = ["cash", "legibility", "heat", "ai", "opinion", "market", "case_file", "fbi", "nsa",
        "trust", "regulation", "laptop", "os", "evidence", "terms", "burnout"]
BASE_START = date(2026, 11, 3)


def start_for(seed: int, fixed: date | None) -> date:
    """Spread start dates over four years (16 steps of 13 weeks) unless one is fixed."""
    return fixed or BASE_START + timedelta(days=91 * (seed % 16))


def summarize(name: str, seeds: int, rules: dict, fixed: date | None) -> None:
    runs = [play(s, POLICIES[name], rules, start_date=start_for(s, fixed)) for s in range(seeds)]
    endings = Counter(r.ending for r in runs)
    print(f"\n== {name} ({seeds} seeds)")
    print("endings: " + ", ".join(f"{k} {v}" for k, v in sorted(endings.items())))
    print(f"mean turns survived: {st.mean(r.turn for r in runs):.1f}")
    print(f"{'var':<11}{'mean':>9}{'min':>9}{'max':>9}   (final values)")
    for k in KEYS:
        vals = [r.state[k] for r in runs]
        print(f"{k:<11}{st.mean(vals):>9.1f}{min(vals):>9.1f}{max(vals):>9.1f}")
    peak = [max(h["legibility"] for h in r.history) for r in runs]
    print(f"peak legibility: mean {st.mean(peak):.1f}, max {max(peak):.1f}")
    got = [next((i for i, h in enumerate(r.history) if h["laptop"] >= 1), None) for r in runs]
    days = [g for g in got if g is not None]
    if name != "idle":
        print(f"laptop fixed in {len(days)}/{len(runs)} runs"
              + (f", median day {st.median(days):.0f}" if days else ""))


def trace(name: str, seed: int, rules: dict, fixed: date | None) -> None:
    r = play(seed, POLICIES[name], rules, start_date=start_for(seed, fixed))
    print(f"start {r.start_date}  end {r.end_date}  turns {r.max_turns}")
    print("turn " + " ".join(f"{k[:7]:>8}" for k in KEYS))
    for t, h in enumerate(r.history):
        if t % 100 == 0 or t == len(r.history) - 1:
            print(f"{t:>4} " + " ".join(f"{h[k]:>8.1f}" for k in KEYS))
    print("ending:", r.ending)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=100)
    ap.add_argument("--policy", choices=list(POLICIES))
    ap.add_argument("--trace", type=int, metavar="SEED")
    ap.add_argument("--start-date", type=date.fromisoformat, default=None)
    args = ap.parse_args()
    rules = load_rules()
    if args.trace is not None:
        trace(args.policy or "activist", args.trace, rules, args.start_date)
        return 0
    for name in ([args.policy] if args.policy else POLICIES):
        summarize(name, args.seeds, rules, args.start_date)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

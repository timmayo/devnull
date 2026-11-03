"""Run the vertical slice headlessly across many seeds and summarize outcomes.

Usage (from the repo root):
    python tools/run_slice.py                 # 100 seeds, all policies
    python tools/run_slice.py --seeds 500
    python tools/run_slice.py --policy activist --trace 7   # one run, per-turn
"""

from __future__ import annotations

import argparse
import statistics as st
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from devnull.core.policies import POLICIES  # noqa: E402
from devnull.core.sim import load_rules, play  # noqa: E402

KEYS = ["cash", "legibility", "heat", "ai", "opinion", "market", "case_file", "fbi", "nsa", "trust"]


def summarize(name: str, seeds: int, rules: dict) -> None:
    runs = [play(s, POLICIES[name], rules) for s in range(seeds)]
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


def trace(name: str, seed: int, rules: dict) -> None:
    r = play(seed, POLICIES[name], rules)
    print(f"turn " + " ".join(f"{k[:7]:>8}" for k in KEYS))
    for t, h in enumerate(r.history):
        if t % 5 == 0 or t == len(r.history) - 1:
            print(f"{t:>4} " + " ".join(f"{h[k]:>8.1f}" for k in KEYS))
    print("ending:", r.ending)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=100)
    ap.add_argument("--policy", choices=list(POLICIES))
    ap.add_argument("--trace", type=int, metavar="SEED")
    args = ap.parse_args()
    rules = load_rules()
    if args.trace is not None:
        trace(args.policy or "activist", args.trace, rules)
        return 0
    for name in ([args.policy] if args.policy else POLICIES):
        summarize(name, args.seeds, rules)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

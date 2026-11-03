"""Stories the game generates from its own state (see data/news.yaml).

The news lags reality by three days. Uses the digest's own RNG, so reading the
news never changes the simulation.
"""

from __future__ import annotations

import random
from typing import Any

from devnull.core.sim import Sim

LAG_DAYS = 3


def story_p(spec: dict[str, Any], state: dict[str, float]) -> float:
    p = float(spec.get("bias", 0.0))
    for var, coef in (spec.get("terms") or {}).items():
        p += coef * state[var]
    return min(0.9, max(0.0, p))


def game_stories(sim: Sim, scope: str, rng: random.Random, limit: int = 2) -> list[str]:
    """Up to `limit` generated stories for 'local' or 'national'."""
    cfg = sim.rules.get("news", {}).get(scope, [])
    lag = sim.history[max(0, len(sim.history) - 1 - LAG_DAYS)]
    recent = {code for turn, code, _ in sim.log if turn >= sim.turn - LAG_DAYS}
    hits: list[tuple[float, str]] = []
    for item in cfg:
        if any(lag[v] < need for v, need in (item.get("when") or {}).items()):
            continue
        if item.get("after_event") and item["after_event"] not in recent:
            continue
        tr = item.get("trend")
        if tr:
            past = sim.history[max(0, len(sim.history) - 1 - tr["days"])][tr["var"]]
            change = sim.history[-1][tr["var"]] - past
            if ("min" in tr and change < tr["min"]) or ("max" in tr and change > tr["max"]):
                continue
        p = story_p(item["p"], lag)
        roll = rng.random()                         # always drawn, so a story's odds do not shift others
        text = rng.choice(item["text"])
        if roll < p:
            hits.append((p, text))
    hits.sort(key=lambda h: -h[0])
    return [t for _, t in hits[:limit]]

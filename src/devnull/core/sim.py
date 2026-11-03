"""Vertical slice simulation: applies data/slice_rules.yaml turn by turn.

Deterministic for a given seed. No UI code here.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RULES = REPO_ROOT / "data" / "slice_rules.yaml"


def load_rules(path: Path = DEFAULT_RULES) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def evaluate(spec: dict[str, Any], state: dict[str, float], rng: random.Random) -> float:
    """bias + sum(coef * source) + noise * N(0, 1)."""
    value = float(spec.get("bias", 0.0))
    for src, coef in (spec.get("terms") or {}).items():
        value += coef * state[src]
    noise = spec.get("noise", 0.0)
    if noise:
        value += noise * rng.gauss(0.0, 1.0)
    return value


@dataclass
class Sim:
    seed: int
    rules: dict[str, Any] = field(default_factory=load_rules)
    turn: int = 0
    state: dict[str, float] = field(default_factory=dict)
    history: list[dict[str, float]] = field(default_factory=list)
    ending: str | None = None

    def __post_init__(self) -> None:
        self.rng = random.Random(self.seed)
        self.state = {k: float(v) for k, v in self.rules["start"].items()}
        self.history.append(dict(self.state))

    # -- helpers ---------------------------------------------------------
    def _clamp(self, key: str) -> None:
        lo, hi = self.rules["ranges"][key]
        self.state[key] = min(hi, max(lo, self.state[key]))

    def can_do(self, action: str) -> bool:
        need = self.rules["actions"][action].get("requires") or {}
        return all(self.state[k] >= v for k, v in need.items())

    # -- one turn --------------------------------------------------------
    def step(self, chosen: list[str]) -> None:
        if self.ending:
            return
        r = self.rules
        # 1. player actions (limited per turn, skipped if requirements fail)
        for action in chosen[: r["actions_per_turn"]]:
            if not self.can_do(action):
                continue
            for var, spec in r["actions"][action]["effects"].items():
                self.state[var] += evaluate(spec, self.state, self.rng)
                self._clamp(var)

        # 2. world update, all rules read the same post-action snapshot
        snap = dict(self.state)
        for var, spec in r["world"].items():
            target = evaluate(spec, snap, self.rng)
            if spec["kind"] == "relax":
                self.state[var] = snap[var] + spec["rate"] * (target - snap[var])
            else:  # add
                self.state[var] = snap[var] + target
            self._clamp(var)

        # 3. upkeep
        self.state["cash"] -= r["upkeep"]
        self._clamp("cash")

        # 4. FBI ladder
        self._ladder()

        self.turn += 1
        self.history.append(dict(self.state))
        self._check_endings()

    def _ladder(self) -> None:
        lad = self.rules["ladder"]
        level = int(self.state[lad["var"]])
        src = self.state[lad["source"]]
        thr = lad["thresholds"]
        if level < len(thr) and src >= thr[level] and self.rng.random() < lad["p_up"]:
            level += 1
        elif level > 0 and src < thr[level - 1] - lad["drop_margin"] and self.rng.random() < lad["p_down"]:
            level -= 1
        self.state[lad["var"]] = float(level)

    def _check_endings(self) -> None:
        final = self.turn >= self.rules["turns"]
        for e in self.rules["endings"]:
            env = {k: self.state[k] for k in self.state}
            hit = bool(eval(e["when"], {"__builtins__": {}}, env))  # trusted repo data
            early = e["id"] in ("caught", "broke")
            if hit and (final or early):
                self.ending = e["id"]
                return


Policy = Callable[["Sim"], list[str]]


def play(seed: int, policy: Policy, rules: dict[str, Any] | None = None) -> Sim:
    sim = Sim(seed=seed, rules=rules or load_rules())
    while sim.ending is None:
        sim.step(policy(sim))
    return sim

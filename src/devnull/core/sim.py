"""Vertical slice simulation: applies data/slice_rules.yaml turn by turn.

Deterministic for a given seed and start date. No UI code here.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, timedelta
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


def add_years(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year + years)
    except ValueError:            # Feb 29 -> Feb 28
        return d.replace(year=d.year + years, day=28)


def election_days(start: date, end: date) -> list[date]:
    """US federal general elections: Tuesday after the first Monday of November, even years."""
    days = []
    for year in range(start.year, end.year + 1):
        if year % 2:
            continue
        nov1 = date(year, 11, 1)
        first_monday = nov1 + timedelta((0 - nov1.weekday()) % 7)
        day = first_monday + timedelta(1)
        if start <= day <= end:
            days.append(day)
    return days


@dataclass
class Sim:
    seed: int
    rules: dict[str, Any] = field(default_factory=load_rules)
    start_date: date | None = None          # the day the player first picked a city
    max_turns_override: int | None = None
    turn: int = 0
    state: dict[str, float] = field(default_factory=dict)
    history: list[dict[str, float]] = field(default_factory=list)
    ending: str | None = None

    def __post_init__(self) -> None:
        self.rng = random.Random(self.seed)
        cal = self.rules["calendar"]
        self.start_date = self.start_date or date.today()
        self.end_date = add_years(self.start_date, cal["years"])
        self.max_turns = self.max_turns_override or (self.end_date - self.start_date).days
        self.election_turns = {
            (d - self.start_date).days for d in election_days(self.start_date, self.end_date)
        }
        self.election_log: list[tuple[int, float]] = []
        self.state = {k: float(v) for k, v in self.rules["start"].items()}
        self.history.append(dict(self.state))
        self.hours_left = self.free_hours()

    # -- helpers ---------------------------------------------------------
    @property
    def date(self) -> date:
        return self.start_date + timedelta(self.turn)

    @property
    def is_workday(self) -> bool:
        return self.date.weekday() in self.rules["daily"]["job"]["days"]

    def free_hours(self) -> int:
        """Free hours today, after the job, commute, chores and burnout."""
        d = self.rules["daily"]
        hours = d["free_hours"]["workday" if self.is_workday else "offday"]
        for above, lost in d["burnout_hours_penalty"]:
            if self.state["burnout"] > above:
                hours -= lost
        return max(0, hours)

    def _clamp(self, key: str) -> None:
        lo, hi = self.rules["ranges"][key]
        self.state[key] = min(hi, max(lo, self.state[key]))

    def can_do(self, action: str) -> bool:
        spec = self.rules["actions"][action]
        if spec["hours"] > self.hours_left:
            return False
        s = self.state
        if any(s[k] < v for k, v in (spec.get("requires") or {}).items()):
            return False
        if any(s[k] > v for k, v in (spec.get("requires_max") or {}).items()):
            return False
        return True

    def _apply_effect(self, var: str, spec: dict[str, Any]) -> None:
        gate = spec.get("if") or {}
        if any(self.state[k] < v for k, v in gate.items()):
            return
        if "set" in spec:
            if self.rng.random() < spec.get("p", 1.0):
                self.state[var] = float(spec["set"])
        else:
            self.state[var] += evaluate(spec, self.state, self.rng)
        self._clamp(var)

    # -- one turn --------------------------------------------------------
    def step(self, chosen: list[str]) -> None:
        if self.ending:
            return
        r = self.rules
        d = r["daily"]

        # 1. the day job: pay and burnout on workdays, recovery on days off
        if self.is_workday:
            self.state["cash"] += d["job"]["pay"]
            self.state["burnout"] += d["job"]["burnout_gain"]
        else:
            self.state["burnout"] -= d["off_day_burnout_loss"]
        self._clamp("burnout")

        # 2. free hours, then the player's actions in the order chosen
        self.hours_left = self.free_hours()
        for action in chosen:
            if not self.can_do(action):
                continue
            spec = r["actions"][action]
            self.hours_left -= spec["hours"]
            for var, eff in spec["effects"].items():
                self._apply_effect(var, eff)
            if spec.get("online") and self.state["laptop"] < 1:
                for var, amount in r["tethered_extra"].items():
                    self.state[var] += amount
                    self._clamp(var)

        # 3. world update, all rules read the same post-action snapshot
        snap = dict(self.state)
        for var, spec in r["world"].items():
            target = evaluate(spec, snap, self.rng)
            if spec["kind"] == "relax":
                self.state[var] = snap[var] + spec["rate"] * (target - snap[var])
            elif spec["kind"] == "logistic":
                k = spec["rate"] * (1 + sum(c * snap[s] for s, c in spec["terms"].items()))
                x = snap[var]
                self.state[var] = x + max(0.0, k) * x * (1 - x / spec["cap"]) + (
                    spec.get("noise", 0.0) * self.rng.gauss(0.0, 1.0))
            else:  # add
                self.state[var] = snap[var] + target
            self._clamp(var)

        # 4. upkeep
        self.state["cash"] -= d["upkeep"]
        self._clamp("cash")

        # 5. FBI ladder
        self._ladder()

        # 6. ballots from yesterday's election are counted today
        delay = r["calendar"]["count_delay_days"]
        if (self.turn + 1 - delay) in self.election_turns:
            self.state["regulation"] += evaluate(r["election"]["regulation"], self.state, self.rng)
            self._clamp("regulation")
            self.election_log.append((self.turn + 1, self.state["regulation"]))

        self.turn += 1
        self.history.append(dict(self.state))
        self.hours_left = self.free_hours()
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
        final = self.turn >= self.max_turns
        for e in self.rules["endings"]:
            env = {k: self.state[k] for k in self.state}
            hit = bool(eval(e["when"], {"__builtins__": {}}, env))  # trusted repo data
            early = e["id"] in ("caught", "broke")
            if hit and (final or early):
                self.ending = e["id"]
                return


Policy = Callable[["Sim"], list[str]]


def play(seed: int, policy: Policy, rules: dict[str, Any] | None = None,
         max_turns: int | None = None, start_date: date | None = None) -> Sim:
    sim = Sim(seed=seed, rules=rules or load_rules(), start_date=start_date,
              max_turns_override=max_turns)
    while sim.ending is None:
        sim.step(policy(sim))
    return sim

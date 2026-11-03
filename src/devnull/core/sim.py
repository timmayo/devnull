"""Vertical slice simulation: applies data/slice_rules.yaml and data/contacts.yaml.

Deterministic for a given seed and start date. No UI code here.

A day has three parts, so a human can play it interactively:
    begin_day()  delayed results arrive, free hours are computed
    act(text)    one player action, applied immediately
    end_day()    the world moves, pay and upkeep, courts, elections, date advances
`step(actions)` runs all three for bots and tests.

Action strings:  "rest", "buy vpn", "attend", "attend 2", "meet 3 coffee".
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
DEFAULT_CONTACTS = REPO_ROOT / "data" / "contacts.yaml"
DEFAULT_MARKET = REPO_ROOT / "data" / "market.yaml"
DEFAULT_NEWS = REPO_ROOT / "data" / "news.yaml"


def load_rules(path: Path = DEFAULT_RULES, contacts_path: Path = DEFAULT_CONTACTS) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        rules = yaml.safe_load(f)
    if contacts_path.exists():
        with open(contacts_path, encoding="utf-8") as f:
            rules["contacts"] = yaml.safe_load(f)
    if DEFAULT_MARKET.exists():
        with open(DEFAULT_MARKET, encoding="utf-8") as f:
            rules["market_tape"] = yaml.safe_load(f)
    if DEFAULT_NEWS.exists():
        with open(DEFAULT_NEWS, encoding="utf-8") as f:
            rules["news"] = yaml.safe_load(f)
    return rules


def read_pool(rel: str) -> list[str]:
    path = REPO_ROOT / rel
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.startswith("#")]


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


def scheduled(when: dict[str, Any], d: date) -> bool:
    """Does a meeting schedule fall on this date?"""
    if "weekday" in when and d.weekday() != when["weekday"]:
        return False
    if "nth" in when and (d.day - 1) // 7 + 1 != when["nth"]:
        return False
    if when.get("every_other_week") and d.isocalendar()[1] % 2 != 0:
        return False
    return True


def place(m: dict[str, Any]) -> str:
    """'the City Commission meeting' for a recurring meeting; the bare title for a real event."""
    return m["label"] if m.get("real") else "the " + m["label"]


def a_or_an(label: str) -> str:
    return ("an " if label[0].lower() in "aeiou" else "a ") + label


@dataclass
class Contact:
    """A person you know. Fictional. Some fields are hidden from the player."""
    id: int
    name: str
    type: str
    met_turn: int
    last_turn: int
    traits: dict[str, float]
    trust: float = 10.0
    exposure: float = 0.0
    bond: float = 0.0
    owes: float = 0.0
    leverage: float = 0.0
    ally: bool = False
    hostile: bool = False
    plant: bool = False           # hidden: secretly reporting on you
    revealed: bool = False
    history: list[dict[str, Any]] = field(default_factory=list)


CONTACT_LIMITS = {"trust": (0, 100), "exposure": (0, 100), "bond": (0, 100),
                  "owes": (0, 9), "leverage": (0, 5)}


@dataclass
class Sim:
    seed: int
    rules: dict[str, Any] = field(default_factory=load_rules)
    start_date: date | None = None          # the day the player first picked a city
    max_turns_override: int | None = None
    events: list[dict[str, Any]] = field(default_factory=list)   # real dated events from the city file
    quotes: dict[str, dict[str, Any]] = field(default_factory=dict)  # real delayed quotes at run start
    feed: dict[str, list[dict[str, Any]]] = field(default_factory=dict)  # real headlines at run start (day 1)
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
        self.pending: list[tuple[int, str, dict[str, Any]]] = []   # delayed effects
        self.log: list[tuple[int, str, Any]] = []                  # (turn, code, data)
        self.contacts: list[Contact] = []
        self._next_cid = 1
        self.unlocked: set[str] = set()
        self.new_unlocks: list[str] = []
        self._began = False
        self.hours_left = 0
        cr = self.rules.get("contacts", {})
        self._surnames = read_pool(cr.get("names", {}).get("surnames", "")) or ["Smith"]
        self._given = read_pool(cr.get("names", {}).get("given", "")) or ["Alex"]
        self._blocked = {ln.lower() for ln in read_pool(cr.get("names", {}).get("blocklist", ""))}
        # market tape: real quotes on day 1, then a simulated path
        self.prices = {s: q["price"] for s, q in self.quotes.items()}
        self.price_change = {s: q["change_pct"] for s, q in self.quotes.items()}
        self.prices_real = bool(self.quotes)       # False once the path is simulated
        self._refresh_derived()
        self._refresh_unlocks(silent=True)
        self.history.append(dict(self.state))

    # -- helpers ---------------------------------------------------------
    @property
    def date(self) -> date:
        return self.start_date + timedelta(self.turn)

    @property
    def is_workday(self) -> bool:
        return self.date.weekday() in self.rules["daily"]["job"]["days"]

    def event(self, code: str, data: Any = None) -> None:
        self.log.append((self.turn, code, data))

    def free_hours(self) -> int:
        """Free hours today, after the job, commute, chores and burnout."""
        d = self.rules["daily"]
        hours = d["free_hours"]["workday" if self.is_workday else "offday"]
        for above, lost in d["burnout_hours_penalty"]:
            if self.state["burnout"] > above:
                hours -= lost
        return max(0, hours)

    def _clamp(self, key: str) -> None:
        if key in self.rules["ranges"]:
            lo, hi = self.rules["ranges"][key]
            self.state[key] = min(hi, max(lo, self.state[key]))

    def contact(self, cid: int) -> Contact | None:
        return next((c for c in self.contacts if c.id == cid), None)

    # -- derived state and unlocks --------------------------------------
    def _refresh_derived(self) -> None:
        live = [c for c in self.contacts if not c.hostile]
        trusts = sorted((c.trust for c in live), reverse=True)
        if len(trusts) >= 2:
            self.state["trust"] = (trusts[0] + trusts[1]) / 2
        else:
            self.state["trust"] = trusts[0] / 2 if trusts else 0.0
        self.state["press_trust"] = max([c.trust for c in live if c.type == "local_reporter"] or [0.0])
        self.state["techie_trust"] = max([c.trust for c in live if c.type == "techie"] or [0.0])
        self.state["contacts_n"] = float(len(self.contacts))

    def _refresh_unlocks(self, silent: bool = False) -> None:
        items = [(n, a.get("unlock")) for n, a in self.rules["actions"].items()]
        items += [(f"buy {n}", i.get("unlock")) for n, i in self.rules["shop"].items()]
        for name, cond in items:
            if name in self.unlocked:
                continue
            if all(self.state[k] >= v for k, v in (cond or {}).items()):
                self.unlocked.add(name)
                if not silent:
                    self.new_unlocks.append(name)

    def unlock_all(self) -> None:
        for n, a in self.rules["actions"].items():
            self.unlocked.add(n)
        for n in self.rules["shop"]:
            self.unlocked.add(f"buy {n}")

    def visible_actions(self) -> list[str]:
        return [n for n in self.rules["actions"] if n in self.unlocked]

    def visible_shop(self) -> list[str]:
        return [n for n in self.rules["shop"] if f"buy {n}" in self.unlocked]

    # -- meetings ----------------------------------------------------------
    def gatherings(self, d: date) -> list[tuple[str, dict[str, Any]]]:
        """Everything you can attend on a date: recurring meetings plus real dated events.

        Events borrow a meeting template (`kind`) for who attends; their `real`
        key holds the source details."""
        meetings = self.rules.get("contacts", {}).get("meetings", {})
        listed = {(ev["kind"], ev["start"].year) for ev in self.events}
        out = [(k, m) for k, m in meetings.items()
               if "when" in m and scheduled(m["when"], d)
               and not (m.get("approx_unless_listed") and (k, d.year) in listed)]
        if d == self.start_date:                       # day 1 always has somewhere to go
            out += [(k, m) for k, m in meetings.items() if m.get("day1")]
        for ev in self.events:
            if ev["start"] <= d <= ev.get("end", ev["start"]) and ev["kind"] in meetings:
                tmpl = meetings[ev["kind"]]
                out.append((ev["id"], {**tmpl, "label": ev["title"], "time": ev.get("time", "all day"),
                                       "hours": ev.get("hours", tmpl["hours"]), "real": ev}))
        return out

    def meetings_today(self) -> list[tuple[str, dict[str, Any]]]:
        return self.gatherings(self.date)

    def upcoming(self, days: int = 14) -> list[tuple[date, str, dict[str, Any]]]:
        """Next occurrence of each gathering in the coming days (not today)."""
        seen: set[str] = set()
        today_keys = {k for k, _ in self.gatherings(self.date)}
        out = []
        for i in range(1, days + 1):
            d = self.date + timedelta(i)
            for k, m in self.gatherings(d):
                if k in seen or k in today_keys:
                    continue                      # one line per gathering; ongoing ones are in TODAY
                seen.add(k)
                out.append((d, k, m))
        return out

    def _meeting_choice(self, arg: str | None) -> tuple[str, dict[str, Any]] | None:
        ms = self.meetings_today()
        if not ms:
            return None
        if arg is None:
            return ms[0]
        if arg.isdigit():
            i = int(arg) - 1
            return ms[i] if 0 <= i < len(ms) else None
        return next(((k, m) for k, m in ms if k.startswith(arg.lower())), None)

    # -- contacts ----------------------------------------------------------
    def _weighted(self, weights: dict[str, float]) -> str:
        total = sum(weights.values())
        r = self.rng.random() * total
        for key, w in weights.items():
            r -= w
            if r <= 0:
                return key
        return next(iter(weights))

    def new_contact(self, ctype: str, where: str | None = None) -> Contact:
        cr = self.rules["contacts"]
        spec = cr["types"][ctype]
        name = ""
        for _ in range(30):
            name = f"{self.rng.choice(self._given)} {self.rng.choice(self._surnames)}"
            used = {c.name for c in self.contacts}
            if name.lower() not in self._blocked and name not in used:
                break
        traits = {k: min(1.0, max(0.0, v + self.rng.uniform(-0.1, 0.1)))
                  for k, v in spec["traits"].items()}
        c = Contact(id=self._next_cid, name=name, type=ctype, met_turn=self.turn,
                    last_turn=self.turn, traits=traits, trust=self.rng.uniform(8, 14))
        c.plant = self.rng.random() < spec["traits"]["plant_p"]
        c.leverage = 1.0 if self.rng.random() < 0.4 * (1 - traits["honesty"]) else 0.0
        c.history.append({"turn": self.turn, "date": self.date.isoformat(), "action": "met",
                          "outcome": "met", "text": f"Met at {where}." if where else "Met."})
        self._next_cid += 1
        self.contacts.append(c)
        self.event("contact_met", c.id)
        self._refresh_derived()
        return c

    def _meet_people(self, key: str, m: dict[str, Any]) -> list[str]:
        msgs: list[str] = []
        if self.rng.random() >= m["meet_chance"]:
            return ["You listen and take notes, but you do not end up talking to anyone."]
        people = 1 + (self.rng.random() < m.get("people_extra", 0.2))
        types = self.rules["contacts"]["types"]
        for _ in range(people):
            ctype = self._weighted(m["attendees"])
            known = [c for c in self.contacts if c.type == ctype and not c.hostile]
            if known and self.rng.random() < 0.4:
                c = self.rng.choice(known)
                c.last_turn = self.turn
                c.trust = min(100, c.trust + 1)
                c.history.append({"turn": self.turn, "date": self.date.isoformat(), "action": "ran into",
                                  "outcome": "met", "text": f"Ran into them at {place(m)}."})
                msgs.append(f"You run into {c.name} again ({types[ctype]['label']}). [contact #{c.id}]")
            else:
                c = self.new_contact(ctype, where=place(m))
                msgs.append(f"You get talking with {c.name}, {a_or_an(types[ctype]['label'])}. [contact #{c.id}]")
        self._refresh_derived()
        return msgs

    def contact_action_reason(self, c: Contact, action: str) -> str | None:
        ca = self.rules["contacts"]["contact_actions"].get(action)
        if ca is None:
            return "Unknown contact action."
        if c.hostile:
            return f"{c.name} will not talk to you."
        if ca["hours"] > self.hours_left:
            return f"Not enough hours left today (needs {ca['hours']})."
        if self.state["cash"] < ca.get("cost", 0):
            return f"You cannot afford it (${ca['cost']})."
        for k, v in (ca.get("requires_contact") or {}).items():
            if getattr(c, k) < v:
                return f"Needs more {k} with {c.name} ({k} {v})." if k != "leverage" else \
                    f"You have nothing on {c.name} to use."
        return None

    def contact_menu(self, cid: int) -> list[tuple[str, dict[str, Any], str | None]]:
        c = self.contact(cid)
        if c is None:
            return []
        return [(a, spec, self.contact_action_reason(c, a))
                for a, spec in self.rules["contacts"]["contact_actions"].items()]

    def _contact_ctx(self, c: Contact) -> dict[str, float]:
        return {"trust": c.trust / 100, "bond": c.bond / 100, "owes": c.owes,
                "leverage": c.leverage, "honesty": c.traits["honesty"],
                "talkative": c.traits["talkative"], "corruptibility": c.traits["corruptibility"],
                "skills": self.state["skills"] / 100}

    def _do_contact_action(self, c: Contact, action: str) -> list[str]:
        cr = self.rules["contacts"]
        ca = cr["contact_actions"][action]
        ctx = self._contact_ctx(c)
        self.hours_left -= ca["hours"]
        self.state["cash"] -= ca.get("cost", 0)
        p = min(0.95, max(0.03, evaluate(ca["p"], ctx, self.rng)))
        if self.rng.random() < p:
            outcome = "success"
        elif "backfire" in ca and self.rng.random() < ca.get("backfire_share", 0):
            outcome = "backfire"
        else:
            outcome = "fail"
        res = ca[outcome]
        msgs = [res["text"].format(name=c.name)]
        for field_name, eff in (res.get("contact") or {}).items():
            if "set" in eff:
                setattr(c, field_name, bool(eff["set"]))
            else:
                lo, hi = CONTACT_LIMITS[field_name]
                setattr(c, field_name, min(hi, max(lo, getattr(c, field_name) + evaluate(eff, ctx, self.rng))))
        for var, eff in (res.get("player") or {}).items():
            self._apply_effect(var, eff)
        if res.get("uses_type_gives"):
            gives = cr["types"][c.type].get("ask_gives") or {}
            gained = []
            for var, delta in gives.items():
                self.state[var] += delta
                self._clamp(var)
                gained.append(f"{delta:+g} {var.replace('_', ' ')}")
            if gained:
                msgs.append("  (" + ", ".join(gained) + ")")
        hook = (cr.get("hooks") or {}).get("lead_npc")
        if (hook and action in hook["actions"] and outcome == "success" and c.type in hook["types"]
                and c.trust >= hook["min_trust"] and self.state["laptop"] < 1
                and self.state["lead_npc"] < 1 and self.rng.random() < hook["p"]):
            self.state["lead_npc"] = 1.0
            msgs.append(hook["msg"].format(name=c.name))
        if c.plant and ca.get("plant"):
            for var, eff in ca["plant"].items():
                self._apply_effect(var, eff)
            if not c.revealed and self.rng.random() < 0.15:
                c.revealed = True
                c.hostile = True
                msgs.append(f"You realize {c.name} has been reporting on you. They are done talking to you.")
                self.event("plant_revealed", c.id)
        c.last_turn = self.turn
        c.history.append({"turn": self.turn, "date": self.date.isoformat(), "action": action,
                          "outcome": outcome, "text": res["text"].format(name=c.name)})
        self.event("contact_action", (c.id, action, outcome))
        self._refresh_derived()
        return msgs

    # -- actions -----------------------------------------------------------
    def action_spec(self, text: str) -> dict[str, Any] | None:
        """The rules for a plain action, including 'buy <item>' built from the shop list."""
        tokens = text.replace(":", " ").split()
        if not tokens:
            return None
        name = tokens[0]
        if name == "buy":
            item = self.rules["shop"].get(tokens[1] if len(tokens) > 1 else "")
            if not item:
                return None
            return {
                "hours": 1,
                "help": f"Buy {tokens[1]} (${item['price']}). {item['note']}",
                "requires": {"cash": item["price"]},
                "requires_max": {item["flag"]: 0},
                "why": f"You need ${item['price']} and you must not already own it.",
                "effects": {
                    "cash": {"bias": -item["price"]},
                    item["flag"]: {"set": 1, "msg": f"Bought: {tokens[1]}."},
                    "legibility": {"bias": 0.5},
                },
            }
        return self.rules["actions"].get(name) if len(tokens) == 1 else None

    def why_not(self, text: str) -> str | None:
        """None if the action can be done right now, otherwise the reason."""
        tokens = text.replace(":", " ").split()
        if not tokens:
            return "Unknown action."
        if tokens[0] == "attend":
            choice = self._meeting_choice(tokens[1] if len(tokens) > 1 else None)
            if choice is None:
                return "There is no such meeting today." if self.meetings_today() else "There are no meetings today."
            if choice[1]["hours"] > self.hours_left:
                return f"Not enough hours left today (needs {choice[1]['hours']})."
            return None
        if tokens[0] == "meet":
            if len(tokens) < 3 or not tokens[1].isdigit():
                return "Usage: meet <contact#> <action>."
            c = self.contact(int(tokens[1]))
            if c is None:
                return "You do not know anyone with that number."
            return self.contact_action_reason(c, tokens[2])
        spec = self.action_spec(text)
        if spec is None:
            return "Unknown action."
        if spec["hours"] > self.hours_left:
            return f"Not enough hours left today (needs {spec['hours']})."
        s = self.state
        if any(s[k] < v for k, v in (spec.get("requires") or {}).items()) or \
           any(s[k] > v for k, v in (spec.get("requires_max") or {}).items()):
            return spec.get("why", "Requirements not met.")
        return None

    def can_do(self, text: str) -> bool:
        return self.why_not(text) is None

    def _apply_effect(self, var: str, spec: dict[str, Any], now: bool = False,
                      scale: float = 1.0) -> str | None:
        """Apply one effect. Returns a message if the effect has one and it fired."""
        if any(self.state[k] < v for k, v in (spec.get("if") or {}).items()):
            return None
        if spec.get("delay") and not now:
            due = self.turn + self.rng.randint(*spec["delay"])
            self.pending.append((due, var, spec))
            return None
        msg = None
        if "set" in spec:
            if self.rng.random() < spec.get("p", 1.0):
                self.state[var] = float(spec["set"])
                msg = spec.get("msg")
        else:
            self.state[var] += evaluate(spec, self.state, self.rng) * scale
        self._clamp(var)
        return msg

    def begin_day(self) -> list[str]:
        """Start the day: delayed results arrive, free hours are set."""
        if self._began or self.ending:
            return []
        self._began = True
        d = self.rules["daily"]
        due = [p for p in self.pending if p[0] <= self.turn]
        self.pending = [p for p in self.pending if p[0] > self.turn]
        for _, var, spec in due:
            self._apply_effect(var, spec, now=True)
            if var == "evidence":
                self.event("records_arrived")
        if self.is_workday:
            self.state["burnout"] += d["job"]["burnout_gain"]
        else:
            self.state["burnout"] -= d["off_day_burnout_loss"]
        self._clamp("burnout")
        self.hours_left = self.free_hours()
        self._refresh_unlocks()
        return []

    def act(self, text: str) -> tuple[bool, list[str]]:
        """Do one action now. Returns (done, messages)."""
        self.begin_day()
        reason = self.why_not(text)
        if reason:
            return False, [reason]
        tokens = text.replace(":", " ").split()
        msgs: list[str] = []
        if tokens[0] == "attend":
            key, m = self._meeting_choice(tokens[1] if len(tokens) > 1 else None)
            self.hours_left -= m["hours"]
            base = self.rules["actions"]["attend"]
            msgs.append(f"You go to {place(m)}.")
            for var, eff in base["effects"].items():
                self._apply_effect(var, eff, scale=m["mult"].get(var, 1.0))
            msgs += self._meet_people(key, m)
            self.event("attended", key)
        elif tokens[0] == "meet":
            msgs = self._do_contact_action(self.contact(int(tokens[1])), tokens[2])
        else:
            spec = self.action_spec(text)
            self.hours_left -= spec["hours"]
            if spec.get("done"):
                msgs.append(spec["done"])
            for var, eff in spec["effects"].items():
                m = self._apply_effect(var, eff)
                if m:
                    msgs.append(m)
                    self.event("discovery", m)
            if spec.get("online") and self.state["laptop"] < 1:
                for var, ex in self.rules["tethered_extra"].items():
                    self.state[var] += evaluate(ex, self.state, self.rng)
                    self._clamp(var)
        self._refresh_derived()
        self._refresh_unlocks()
        return True, msgs

    def end_day(self) -> None:
        """The world moves and the date advances."""
        if self.ending:
            return
        self.begin_day()
        r = self.rules
        d = r["daily"]

        # world update: all rules read the same post-action snapshot
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

        if self.is_workday:
            self.state["cash"] += d["job"]["pay"]       # paid for today's shift
        self.state["cash"] -= d["upkeep"]
        self._clamp("cash")

        self._move_prices(snap["market"])
        self._contacts_daily()
        self._ladder()
        self._lawsuit()

        # ballots from yesterday's election are counted today
        delay = r["calendar"]["count_delay_days"]
        if (self.turn + 1 - delay) in self.election_turns:
            before = self.state["regulation"]
            self.state["regulation"] += evaluate(r["election"]["regulation"], self.state, self.rng)
            self._clamp("regulation")
            self.election_log.append((self.turn + 1, self.state["regulation"]))
            self.event("election", self.state["regulation"] - before)

        self._refresh_derived()
        self.turn += 1
        self.history.append(dict(self.state))
        self._began = False
        self._check_endings()

    def step(self, chosen: list[str]) -> None:
        """A whole day for bots and tests: start, act in order, end."""
        if self.ending:
            return
        self.begin_day()
        for action in chosen:
            self.act(action)
        self.end_day()

    # -- slow systems ----------------------------------------------------
    def _move_prices(self, market_before: float) -> None:
        """Simulated tape. Own RNG stream, so it never changes the rest of the run."""
        tape = self.rules.get("market_tape")
        if not tape or not self.prices:
            return
        rng = random.Random(f"{self.seed}-px-{self.turn}")
        dm = self.state["market"] - market_before
        for g in tape["groups"].values():
            for sym in g["tickers"]:
                if sym not in self.prices:
                    continue
                r = tape["sim_drift_per_point"] * g["beta"] * dm + g["sigma"] * rng.gauss(0, 1)
                self.prices[sym] *= 2.718281828 ** r
                self.price_change[sym] = (2.718281828 ** r - 1) * 100
        self.prices_real = False

    def _contacts_daily(self) -> None:
        types = self.rules.get("contacts", {}).get("types", {})
        for c in self.contacts:
            if c.hostile:
                continue
            if self.turn - c.last_turn > 21:
                c.trust = max(0.0, c.trust - 0.15)        # people drift when you do not call
            if c.ally:
                for var, delta in (types[c.type].get("ally_daily") or {}).items():
                    self.state[var] += delta * (c.trust / 100)
                    self._clamp(var)

    def _ladder(self) -> None:
        lad = self.rules["ladder"]
        level = int(self.state[lad["var"]])
        src = self.state[lad["source"]]
        thr = lad["thresholds"]
        if level < len(thr) and src >= thr[level] and self.rng.random() < lad["p_up"]:
            level += 1
            self.event("fbi_up", level)
        elif level > 0 and src < thr[level - 1] - lad["drop_margin"] and self.rng.random() < lad["p_down"]:
            level -= 1
        self.state[lad["var"]] = float(level)

    def _lawsuit(self) -> None:
        lw = self.rules["lawsuit"]
        stage = int(self.state[lw["var"]])
        if stage < 1 or self.rng.random() >= lw["p_advance"]:
            return
        if stage < 3:
            self.state[lw["var"]] = float(stage + 1)
            self.event("lawsuit_stage", stage + 1)
            return
        won = self.rng.random() < self.state[lw["strength"]] / 100
        for var, delta in lw["win" if won else "lose"].items():
            self.state[var] += delta
            self._clamp(var)
        self.state[lw["var"]] = 0.0
        self.state[lw["strength"]] = 0.0
        self.event("lawsuit_result", won)

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
        sim.begin_day()
        sim.step(policy(sim))
    return sim

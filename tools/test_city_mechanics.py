"""A city's mechanics, setup choices and overrides do what the city file says.

    python tools/test_city_mechanics.py        (exit code 1 if anything fails)
"""
from __future__ import annotations

import copy
import json
import random
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from devnull.core import save, setup as cs                        # noqa: E402
from devnull.core.policies import POLICIES                        # noqa: E402
from devnull.core.sim import Sim, load_rules                      # noqa: E402
import citycheck                                                  # noqa: E402
import newcity                                                    # noqa: E402

CITY = yaml.safe_load((ROOT / "cities" / "grand_rapids.yaml").read_text(encoding="utf-8"))
RULES = load_rules()
START = date(2026, 11, 7)                                         # a Saturday
failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f"  {detail}"))
    if not ok:
        failures.append(name)


def sim(picks=None, city=CITY, start=START, seed=1) -> Sim:
    return Sim(seed=seed, rules=RULES, start_date=start, city=city, setup=picks)


# ---- business days
check("business days skip the weekend", cs.add_business_days(date(2026, 11, 6), 1) == date(2026, 11, 9))
check("five business days from a Monday is next Monday", cs.add_business_days(date(2026, 11, 9), 5) == date(2026, 11, 16))

# ---- defaults are the baseline
base = Sim(seed=1, rules=RULES, start_date=START)
dflt = sim()
check("defaults come from the city file", dflt.setup == {"neighborhood": "eastown", "job": "health_billing", "cushion": "steady"}, str(dflt.setup))
check("defaults leave the daily rules alone", dflt.rules["daily"] == base.rules["daily"])
check("defaults leave the starting values alone", dflt.state == base.state)

# ---- choices apply, and never leak into the shared rules
shared = copy.deepcopy(RULES["daily"])
c = sim({"neighborhood": "downtown", "job": "manufacturing", "cushion": "saved_up"})
d = c.rules["daily"]
check("neighborhood changes upkeep and commute", d["upkeep"] == shared["upkeep"] + 10 and d["free_hours"]["workday"] == shared["free_hours"]["workday"] + 1, str(d))
check("job changes pay and burnout", d["job"]["pay"] == shared["job"]["pay"] + 15 and abs(d["job"]["burnout_gain"] - (shared["job"]["burnout_gain"] + 0.3)) < 1e-9, str(d["job"]))
check("cushion changes cash and burnout", c.state["cash"] == base.state["cash"] + 450 and c.state["burnout"] == base.state["burnout"] + 20)
check("job gives a starting skill", c.skill_level("hardware") == 1, str(c.skill_xp))
check("the shared rules are untouched", RULES["daily"] == shared)
check("an unknown pick falls back to the default", sim({"job": "astronaut"}).setup["job"] == "health_billing")

# ---- city start and daily overrides
over = copy.deepcopy(CITY)
over["start"] = {"cash": 123}
over["daily"] = {"upkeep": 50, "free_hours.workday": 5}
o = sim(city=over, picks={"neighborhood": "downtown"})
check("city start replaces the baseline", o.state["cash"] == 123)
check("city daily replaces the baseline, then choices add", o.rules["daily"]["upkeep"] == 60 and o.rules["daily"]["free_hours"]["workday"] == 6, str(o.rules["daily"]))

# ---- records timing follows the statute
rule = CITY["mechanics"]["records"]
lo_hi = lambda day: [cs.records_delay(day, rule, random.Random(i)) for i in range(400)]   # noqa: E731
mon, fri = date(2026, 11, 9), date(2026, 11, 13)
for label, day in (("Monday", mon), ("Friday", fri), ("Saturday", START)):
    ds = lo_hi(day)
    top = (cs.add_business_days(day, rule["receive_lag_business_days"] + rule["respond_business_days"] + rule["extension_business_days"]) - day).days
    check(f"records filed on a {label} never exceed lag + 5 + 10 business days ({top} days)", 1 <= min(ds) and max(ds) <= top, f"{min(ds)}..{max(ds)}")
check("some answers use the extension", max(lo_hi(mon)) > (cs.add_business_days(mon, 6) - mon).days)
r = sim(seed=5)
r.begin_day()
r.hours_left = 24
ok, msgs = r.act("records")
check("filing a records request shows the city's law", ok and any("e-mailed request" in m for m in msgs), str(msgs))
due = [p for p in r.pending if p[1] == "evidence"]
check("the answer is scheduled", len(due) == 1 and 1 <= due[0][0] - r.turn <= 22, str(due))

# ---- local elections
def election_events(years: int) -> dict[int, list[str]]:
    s = sim(seed=2)
    out: dict[int, list[str]] = {}
    for _ in range(365 * years):
        s.begin_day()
        s.step([])
        if s.ending:
            break
    for turn, code, data in s.log:
        if code == "local_election":
            out[(s.start_date + timedelta(turn)).year] = data
    return out

ev = election_events(5)                                           # Nov 2026 to Nov 2031
check("no city race in odd years", 2027 not in ev and 2029 not in ev and 2031 not in ev, str(ev))
check("commission seats are on the ballot in 2028 and 2030", 2028 in ev and 2030 in ev and "City Commission" in ev[2028][0], str(ev))
check("the mayor is on the ballot in a presidential year only", len(ev.get(2028, [])) == 2 and len(ev.get(2030, [])) == 1, str(ev))

# ---- saving keeps the choices, and an old save still loads
picks = {"neighborhood": "alger_heights", "job": "retail", "cushion": "lean"}
def fp(s: Sim) -> str:
    snap = save.snapshot(s, "grand_rapids")
    snap.pop("saved_at")
    return json.dumps(snap, default=save._encode, sort_keys=True)

def run(cut: set[int], folder: Path) -> Sim:
    s = sim(picks, seed=7)
    for i in range(400):
        if i in cut:
            save.write(s, "grand_rapids", f"t{i}", folder)
            s = save.restore(save.read(f"t{i}", folder), RULES, CITY.get("events") or [], city=CITY)
        if s.ending:
            break
        s.begin_day()
        s.step(POLICIES["activist"](s))
    return s

with tempfile.TemporaryDirectory() as td:
    folder = Path(td)
    a, b = run(set(), folder), run({3, 40, 41, 200}, folder)
    check("a saved and loaded run with choices matches one that never stopped", fp(a) == fp(b))
    check("the choices come back from the save", b.setup == picks and b.rules["daily"]["job"]["pay"] == RULES["daily"]["job"]["pay"] - 15)
    save.write(sim(), "grand_rapids", "old", folder)
    data = save.read("old", folder)
    data.pop("setup")
    data["save_version"] = 1
    old = save.restore(data, RULES, CITY.get("events") or [], city=CITY)
    check("a save from before setup loads with the defaults", old.setup == cs.default_picks(CITY))

# ---- citycheck catches a bad city file
def blockers_for(edit) -> list[str]:
    bad = copy.deepcopy(CITY)
    edit(bad)
    return citycheck.check_mechanics(bad)[0]

check("a clean city file has no mechanics blockers", citycheck.check_mechanics(CITY)[0] == [], str(citycheck.check_mechanics(CITY)[0]))
check("citycheck: unknown neighborhood", any("not in real.geography.neighborhoods" in b for b in blockers_for(
    lambda c: c["setup"]["neighborhood"]["options"].append({"id": "x", "name": "Atlantis", "blurb": "b"}))))
check("citycheck: default option with effects", any("must have no effects" in b for b in blockers_for(
    lambda c: c["setup"]["job"]["options"][0].update(daily={"job.pay": 5}))))
check("citycheck: source_fact that does not exist", any("source_fact" in b for b in blockers_for(
    lambda c: c["mechanics"]["records"].update(source_fact="real.law.nothing"))))
check("citycheck: unknown daily path", any("not a number" in b for b in blockers_for(
    lambda c: c["setup"]["job"]["options"][1].update(daily={"job.salary": 5}))))
check("citycheck: unknown skill", any("skill catalog" in b for b in blockers_for(
    lambda c: c["setup"]["job"]["options"][1].update(skills={"juggling": 1}))))
check("citycheck: missing mechanics", any("mechanics: is missing" in b for b in blockers_for(lambda c: c.pop("mechanics"))))
check("citycheck: bad election years", any("even or presidential" in b for b in blockers_for(
    lambda c: c["mechanics"]["elections"]["contests"][0].update(years="odd"))))

# ---- a new city from the template starts with blockers in these blocks
with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    (root / "tools").mkdir()
    (root / "tools" / "city_template.yaml").write_text((ROOT / "tools" / "city_template.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    (root / "cities").mkdir()
    (root / "pools").mkdir()
    newcity.scaffold("testville", "Testville", "Ohio", root)
    new = yaml.safe_load((root / "cities" / "testville.yaml").read_text(encoding="utf-8"))
    nb = citycheck.check_mechanics(new)[0]
    check("a fresh city lists its mechanics and setup as to-do", any("mechanics.records.done" in b for b in nb) and any("setup.job" in b for b in nb), str(nb[:3]))

print("\n%d failure(s)" % len(failures))
sys.exit(1 if failures else 0)

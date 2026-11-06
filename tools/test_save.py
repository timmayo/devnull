"""Save/load proof: a run that is saved and loaded at many points ends exactly like one that never stopped.

    python tools/test_save.py        (exit code 1 if anything differs)
"""
import json, sys, random, tempfile
from datetime import date
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import yaml
from devnull.core.sim import Sim, load_rules
from devnull.core.policies import POLICIES
from devnull.core import save

city = yaml.safe_load(open(ROOT / "cities" / "grand_rapids.yaml", encoding="utf-8"))
events = city.get("events") or []
print("events:", len(events), "sample date types:", {type(v).__name__ for e in events for v in e.values()})
quotes = {"NVDA": {"price": 100.0, "change_pct": 1.5}, "MSFT": {"price": 400.0, "change_pct": -0.5}}
feed = {"local": [{"title": "t", "url": "u"}]}
rules = load_rules()

def fp(sim):
    d = save.snapshot(sim, "grand_rapids"); d.pop("saved_at")
    return json.dumps(d, default=save._encode, sort_keys=True)

def run(seed, policy, days, cut_points, folder):
    sim = Sim(seed=seed, rules=rules, start_date=date(2026, 11, 6), events=events, quotes=quotes, feed=feed)
    for i in range(days):
        if i in cut_points:
            save.write(sim, "grand_rapids", f"t{i}", folder)
            data = save.read(f"t{i}", folder)
            sim = save.restore(data, rules, events)
        if sim.ending: break
        sim.begin_day(); sim.step(POLICIES[policy](sim))
    return sim

bad = 0
with tempfile.TemporaryDirectory() as td:
    folder = Path(td)
    for policy in ("careful", "activist", "hacker", "schemer", "lawyer", "reckless"):
        for seed in (1, 2, 3):
            a = run(seed, policy, 500, set(), folder)
            b = run(seed, policy, 500, {1, 5, 17, 40, 41, 100, 250}, folder)
            ok = fp(a) == fp(b)
            bad += not ok
            if not ok: print("MISMATCH", policy, seed)
    print("runs compared:", 18, "mismatches:", bad)
    # mid-day save (after some actions, before sleep)
    sim = Sim(seed=9, rules=rules, start_date=date(2026, 11, 6), events=events)
    sim.begin_day(); sim.act("rest")
    d = save.restore(save.read(save.write(sim, "x", "mid", folder).stem, folder), rules, events)
    print("mid-day equal:", fp(sim) == fp(d), "hours_left", d.hours_left)
    # errors
    for bad_name in ("../x", "a b", ""):
        try: save.clean_name(bad_name if bad_name else None); print("ok name", repr(bad_name))
        except save.SaveError as e: print("rejected", repr(bad_name))
    try: save.read("nope", folder)
    except save.SaveError as e: print(e)
    (folder / "broken.json").write_text("{not json")
    try: save.read("broken", folder)
    except save.SaveError as e: print(e)
    print([s["name"] for s in save.list_saves(folder)][:4], len(save.list_saves(folder)))


sys.exit(1 if bad else 0)

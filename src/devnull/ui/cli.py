"""Plain command-line front end (`devnull`). A placeholder for the Textual UI.

Start a run, read the morning news digest, spend the day's free hours on
actions, then `sleep`. Plain ASCII output so it works in any terminal.
"""

from __future__ import annotations

import argparse
import random
import textwrap
from datetime import date
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Callable

import yaml

from devnull import __version__
from devnull.core.digest import describe, render
from devnull.ui import intro
from devnull.core.termlinks import GREEN, RED, enable_vt, fill_link, mode, paint
from devnull.core import commands as cmdtable
from devnull.core.sim import Sim, load_rules

CITIES_DIR = Path(__file__).resolve().parents[3] / "cities"

ENDINGS = {
    "caught": "Federal agents are at your door at dawn. Your run is over.",
    "broke": "You cannot make rent. The fight goes on without you.",
    "pressure_won": "Public opinion has turned. The buildout slows, and the people who run it have to answer to voters.",
    "reform": "You did not stop the machine, but you made it accountable: signed terms on power, water and audits.",
    "runaway": "The systems keep growing and nobody stopped them. You are still here, still watching.",
    "stalemate": "Eight years on, nothing is settled. The fight continues.",
}

BANDS = [(10, "low"), (25, "moderate"), (45, "high"), (101, "severe")]
WAKE_EVENTS = ("records_arrived", "lawsuit_stage", "lawsuit_result", "election", "person_met")

def band(x: float) -> str:
    return next(label for edge, label in BANDS if x < edge)


def load_cities() -> list[dict[str, Any]]:
    cities = []
    for path in sorted(CITIES_DIR.glob("*.yaml")):
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if isinstance(data, dict) and "city" in data:
            cities.append(data)
    return cities


def choose_city(cities: list[dict[str, Any]], wanted: str | None) -> dict[str, Any]:
    if wanted:
        for c in cities:
            if wanted.lower() in (c["city"]["id"], c["city"]["display_name"].lower()):
                return c
        raise SystemExit(f"No city named {wanted!r}.")
    print("Choose a city:")
    for i, c in enumerate(cities, 1):
        print(f"  {i}) {c['city']['display_name']}, {c['city']['state']}")
    while True:
        try:
            raw = input("> ").strip()
        except EOFError:
            raise SystemExit(0)
        if raw.isdigit() and 1 <= int(raw) <= len(cities):
            return cities[int(raw) - 1]
        for c in cities:
            if raw.lower() == c["city"]["display_name"].lower():
                return c
        print("Type a number from the list.")


def wrap(text: str, indent: str = "") -> str:
    return textwrap.fill(text, width=78, initial_indent=indent, subsequent_indent=indent)


def trust_band(sim: Sim, trust: float) -> str:
    for edge, label in sim.rules["people"]["trust_bands"]:
        if trust < edge:
            return label
    return "inner circle"


def visible_keys(sim: Sim, admin: bool) -> list[str]:
    """Commands the player may type right now (data/commands.yaml: always_available, hidden_until, unlocks)."""
    return sim.rules["cmdset"].visible_keys(sim.state, sim.unlocked, admin)


def show_commands(sim: Sim, admin: bool) -> None:
    cmds = sim.rules.get("commands", {}).get("commands", {})
    print("\nLOOK AROUND (free)")
    for c in cmds.values():
        if c["group"] != "look_around":
            continue
        need = c.get("unlock")
        if not admin and isinstance(need, dict) and not all(sim.state.get(k, 0) >= v for k, v in need.items()):
            continue
        children = [x for x in cmds.values() if x.get("parent") == next(k for k, v in cmds.items() if v is c)]
        print(f"  {c['usage']:<22} {c['help'][:1].upper() + c['help'][1:]}")
        for ch in children:
            tag = f"{ch['hours']}h" if ch["hours"] else "free"
            print(f"    then: {ch['usage']:<15} ({tag}) {ch['help']}")
    print("\nACTIONS            hours  now   what it does")
    for name, spec in sim.rules["actions"].items():
        locked = name not in sim.unlocked
        if locked and not admin:
            continue
        reason = sim.why_not(name)
        mark = "yes" if reason is None else "no "
        tag = " [locked]" if locked else ""
        print(f"  {name:<16} {spec['hours']:>4}   {mark}   {spec['help']}{tag}")
        if reason and not locked and sim.hours_left >= spec["hours"]:
            print(f"  {'':<16} {'':>4}         ({reason})")
    for market, title in (("public", "INTERNET (public web)"), ("darknet", "DARKNET")):
        items = [i for i, sp in sim.rules["shop"].items()
                 if sp["market"] == market and (admin or f"buy {i}" in sim.unlocked)]
        if not items:
            continue
        print(f"\n{title:<18} hours  now   what it does")
        for item in items:
            spec = sim.rules["shop"][item]
            reason = sim.why_not(f"buy {item}")
            mark = "yes" if reason is None else "no "
            tag = " [locked]" if f"buy {item}" not in sim.unlocked else ""
            print(f"  {'buy ' + item:<16} {1:>4}   {mark}   ${spec['price']}. {spec['note']}{tag}")
    if sim.people or admin:
        print("\nPEOPLE")
        for k, c in cmds.items():
            if c["group"] == "people" and not c.get("parent"):
                print(f"  {c['usage']:<20} {c['help'][:1].upper() + c['help'][1:]}")
                opts = [x["usage"].split()[-1] for x in cmds.values() if x.get("parent") == k]
                if opts:
                    print(f"  {'':<20} options (open as you know them better): {', '.join(opts)}")
    if admin:
        print(f"\nADMIN: {cmds['admin']['usage']}")
    print("New commands appear as you unlock them.")


def burnout_note(sim: Sim, x: float) -> str:
    cuts = sim.rules["daily"]["burnout_hours_penalty"]            # [[60, 1], [85, 2], [95, 99]]
    state = ("fresh" if x < 30 else "tired" if x < cuts[0][0] else "worn down" if x < cuts[1][0]
             else "exhausted" if x < cuts[2][0] else "collapsing")
    return (f"{state}. Past {cuts[0][0]} you lose an hour of free time a day, past {cuts[1][0]} two, "
            f"past {cuts[2][0]} you cannot function. Work raises it; rest and days off lower it.")


def stat_line(label: str, value: str, note: str = "") -> None:
    head = f"  {label:<12} {value:<9}"
    print(textwrap.fill(note, width=78, initial_indent=head, subsequent_indent=" " * len(head)) if note
          else head.rstrip())


def show_status(sim: Sim, admin: bool = False) -> None:
    s = sim.state
    laptop = ("Linux" if s["os"] >= 1 else "Windows 11") + (
        ", works on battery" if s["laptop"] >= 1 else ", battery dead (plugged in only)")
    gear = [n for n, f in (("burner phone", "gear_burner"), ("VPN", "gear_vpn")) if s[f]]
    leads = []
    if s["lead_store"] and not s["laptop"]:
        leads.append("a pawn shop sells laptops with new batteries ($420)")
    if s["lead_npc"] and not s["laptop"]:
        leads.append("someone you trust can swap a battery (their trust 35, $150)")
    if s["lead_linux"] and not s["os"]:
        leads.append("you know how to install Linux")
    law = {0: "none", 1: "filed", 2: "hearing", 3: "awaiting ruling"}[int(s["filed"])]
    print(f"\n{sim.date:%A %B %d, %Y}   Day {sim.turn + 1}   Free hours left: {sim.hours_left}")
    stat_line("Cash", f"${s['cash']:.0f}", f"Bills run about ${sim.rules['daily']['upkeep']} a day.")
    stat_line("Heat", f"{s['heat']:.0f}", "The attention you are drawing right now. It fades if you stay quiet; "
              "loud or risky actions raise it.")
    stat_line("Burnout", f"{s['burnout']:.0f}/100", burnout_note(sim, s["burnout"]))
    stat_line("Legibility", band(s["legibility"]), "(an estimate) How easily watchers can see and track you: "
              "your phone, accounts and routines. Heat and surveillance raise it; a VPN and lying low lower it. "
              "Above roughly 20 the police file on you grows even while you do nothing.")
    stat_line("Know-how", f"{s['skills']:.0f}/100", "Technical ability. It unlocks tools (tracing at 5, a VPN at 6, "
              "hacking at 15). Research and learning from people build it.")
    mine = sim.my_skills()
    stat_line("Skills", "", ", ".join(f"{sim.skill_label(k)} ({sim.level_name(v)})" for k, v in mine)
              or "none yet. Research, or ask someone to teach you ('meet <n> learn').")
    stat_line("Laptop", "", laptop)
    if gear:
        stat_line("Gear", "", ", ".join(gear))
    stat_line("People", "", f"{len(sim.people)} known; best two average trust {s['trust']:.0f}")
    if "evidence" in sim.unlocked or s["evidence"] > 0:
        print(f"  Evidence     {s['evidence']:.0f}   verified {s['verified']:.0f}   "
              f"authenticity about {round(s['auth'], -1):.0f}")
        print(f"  Credibility  {s['cred']:.0f}")
    if s["filed"]:
        print(f"  Lawsuit      {law}")
    if s["terms"]:
        print(f"  Terms won    {s['terms']:.0f}")
    if leads:
        print(f"  Leads        {'; '.join(leads)}")
    hidden = []
    if s["sk_data_analysis"] >= 2:
        print(f"  AI progress  about {round(s['ai'], -1):.0f}/100 (you read the filings)")
    else:
        hidden.append("the AI curve (data analysis)")
    if s["sk_network_security"] >= 2:
        print(f"  Police file  about {band(s['case_file'])} (an estimate)")
    else:
        hidden.append("the police file (network security)")
    if s["sk_network_security"] >= 3:
        fbi = ["none", "a file is open", "an active inquiry", "surveillance and warrants", "arrest is close"]
        print(f"  FBI interest {fbi[min(int(s['fbi']), len(fbi) - 1)]}")
        print(f"  NSA coverage about {round(s['nsa'], -1):.0f}/100 of your traffic")
    else:
        hidden.append("FBI status and NSA coverage (advanced network security)")
    if hidden:
        print("  (Hidden for now: " + "; ".join(hidden) + ". Research a topic to see it, and read the news.)")
    if admin:
        print("  [admin] type 'admin reveal' to see everything.")


def show_people(sim: Sim, admin: bool) -> None:
    if not sim.people:
        print("  You do not know anyone yet. Go to a meeting ('attend').")
        return
    print(f"\n  {'#':>2}  {'name':<20} {'who':<24} {'standing':<13} last seen")
    for c in sim.people:
        who = sim.rules["people"]["types"][c.type]["label"]
        flags = []
        if c.ally:
            flags.append("ally")
        if c.hostile:
            flags.append("hostile")
        if c.leverage >= 1:
            flags.append("you have leverage")
        if admin and c.plant:
            flags.append("PLANT")
        ago = sim.turn - c.last_turn
        seen = "today" if ago == 0 else f"{ago}d ago"
        extra = f"  [{', '.join(flags)}]" if flags else ""
        print(f"  {c.id:>2}  {c.name:<20} {who:<24} {trust_band(sim, c.trust):<13} {seen}{extra}")


def show_person(sim: Sim, c: Any, admin: bool) -> None:
    spec = sim.rules["people"]["types"][c.type]
    print(f"\n  {c.name}, {a_or_an(spec['label'])}.  Met {c.history[0]['date']}.")
    print(f"  Standing: {trust_band(sim, c.trust)}"
          + ("   Ally." if c.ally else "") + ("   Hostile." if c.hostile else ""))
    if c.owes >= 1:
        print(f"  They owe you ({c.owes:.0f}).")
    if c.leverage >= 1:
        print("  You have something on them.")
    if admin:
        print(f"  [admin] trust {c.trust:.1f} bond {c.bond:.1f} exposure {c.exposure:.1f} "
              f"plant {c.plant} agent {c.agent} traits {c.traits}")
    def fmt(skills: dict[str, int]) -> str:
        return ", ".join(f"{sim.skill_label(k)} ({sim.level_name(v)})"
                         for k, v in sorted(skills.items(), key=lambda kv: -kv[1]))
    print(wrap("Skills: " + (fmt(c.skills) or "none you know of"), "  "))
    if c.trust >= 30 or admin:
        print(wrap("Also: " + fmt(c.side), "  "))
    else:
        print("  Also: you do not know them well enough to know what else they can do.")
    print("  History:")
    for h in c.history[-12:]:
        print(wrap(f"{h['date']}  {h['action']} ({h['outcome']}): {h['text']}", "    "))


def show_events(sim: Sim, days: int) -> None:
    """Today's gatherings, then the next occurrence of each one coming up."""
    def line(text: str, m: dict[str, Any]) -> str:
        url = m["real"]["url"] if m.get("real") else m.get("listing_url")
        return fill_link(text, url, 78, "    ", "      ")

    today = sim.meetings_today()
    print("\n  TODAY")
    if not today:
        print("    Nothing on today.")
    for i, (_, m) in enumerate(today, 1):
        print(line(f"{i}. {describe(m)}", m))
    items = sim.upcoming(days)
    print(f"\n  EVENTS (next {days} days)")
    if not items:
        print("    Nothing scheduled.")
    for d, key, m in items:
        end = m["real"].get("end") if m.get("real") else None
        span = f" (through {end:%b} {end.day})" if end and end != d else ""
        print(line(f"{d:%a %b} {d.day}: {describe(m)}{span}", m))
    print("\n  'events more' shows the next 30 days; 'events <days>' any range. 'attend <n>' goes to one of today's list.")
    print("  Dated events with a link are real. Recurring meetings are typical for the city; their link opens")
    print("  the page where real ones are listed.")


def show_markets(sim: Sim) -> None:
    tape = sim.rules.get("market_tape")
    if not tape or not sim.prices:
        print("  No quotes. They are fetched when a run starts (offline, or started with --no-quotes).")
        return
    if sim.prices_real:
        q = next(iter(sim.quotes.values()))
        print(f"\n  MARKETS - real delayed quotes ({q['source']}, {q['asof']})")
    else:
        print("\n  MARKETS - simulated from the last real quotes")
    for g in tape["groups"].values():
        print("\n  " + g["title"])
        for sym, name in g["tickers"].items():
            if sym in sim.prices:
                print("    %-6s %-22s %9.2f  %+6.2f%%" % (sym, name, sim.prices[sym], sim.price_change[sym]))


def a_or_an(label: str) -> str:
    return ("an " if label[0].lower() in "aeiou" else "a ") + label


def pick_from(prompt: str, options: list[str]) -> str | None:
    """Ask for a number or a name from a list. Blank cancels."""
    try:
        raw = input(prompt).strip().lower()
    except EOFError:
        return None
    if not raw:
        return None
    if raw.isdigit() and 1 <= int(raw) <= len(options):
        return options[int(raw) - 1]
    hits = [o for o in options if o.startswith(raw)]
    return hits[0] if len(hits) == 1 else None


def do_attend(sim: Sim, args: list[str]) -> tuple[bool, list[str]]:
    ms = sim.meetings_today()
    if not ms:
        return False, ["There are no meetings today."]
    arg = args[0] if args else None
    if arg is None and len(ms) > 1:
        print("  On today:")
        for i, (_, m) in enumerate(ms, 1):
            print(f"    {i}) {m['label']}, {m['time']} ({m['hours']}h)")
        chosen = pick_from("  Which one? (blank to cancel) ", [str(i) for i in range(1, len(ms) + 1)])
        if chosen is None:
            return False, ["You stay home."]
        arg = chosen
    return sim.act("attend" + (f" {arg}" if arg else ""))


def do_research(sim: Sim, args: list[str]) -> tuple[bool, list[str]]:
    """`research` opens the menu; `research <topic> [method]` studies directly."""
    r = sim.rules["research"]
    if args:
        return sim.act("research " + " ".join(args))
    methods = r["methods"]
    print("  Methods: " + "; ".join(
        f"{n} ({m['hours']}h{', $' + str(m['cost']) if m['cost'] else ''}: {m['label']})" for n, m in methods.items()))
    print(f"\n  {'#':>2}  {'topic':<26} {'level':<10} {'progress':<9} next level gives")
    keys = list(r["topics"])
    for i, key in enumerate(keys, 1):
        topic = r["topics"][key]
        lvl, xp, need = sim.research_progress(key)
        level = sim.level_name(lvl) if lvl else "-"
        prog = f"{xp:.0f}/{need}" if need else "done"
        nxt = topic["levels"][lvl + 1]["gives"] if lvl < 3 else "nothing more"
        print(f"  {i:>2}  {topic['label']:<26} {level:<10} {prog:<9} {nxt}")
    try:
        raw = input("  Topic and method, e.g. '3' or 'linux library' (blank to cancel) ").strip()
    except EOFError:
        return False, []
    if not raw:
        return False, ["You close the books."]
    first, *rest = raw.split()
    if first.isdigit() and 1 <= int(first) <= len(keys):
        first = keys[int(first) - 1]
    return sim.act(" ".join(["research", first] + rest))


def do_meet(sim: Sim, args: list[str]) -> tuple[bool, list[str]]:
    if not args or not args[0].isdigit():
        return False, ["Usage: meet <person number> [action]. See 'people'."]
    c = sim.person(int(args[0]))
    if c is None:
        return False, ["You do not know anyone with that number."]
    names = [a for a in sim.rules["people"]["people_actions"] if sim.person_action_visible(c, a)]
    action = None
    if len(args) > 1:
        hits = [n for n in names if n.startswith(args[1].lower())]
        if len(hits) != 1:
            return False, [f"Unknown action. Options: {', '.join(names)}."]
        action = hits[0]
    else:
        print(f"  What do you do with {c.name}?")
        opts = []
        for i, (a, spec, reason) in enumerate(sim.person_menu(c.id), 1):
            cost = f" ${spec['cost']}" if spec.get("cost") else ""
            line = f"    {i}) {a:<8} {spec['hours']}h{cost:<6} {spec['help']}"
            print(line + (f"  ({reason})" if reason else ""))
            opts.append(a)
        print("  (More options open up as you get to know them.)")
        action = pick_from("  Choose (blank to cancel) ", opts)
        if action is None:
            return False, ["You let it go."]
    return sim.act(f"meet {c.id} {action}")


def admin_cmd(sim: Sim, args: list[str]) -> None:
    if not args:
        print("  admin set <var> <value> | skill <key> <0-3> | reveal | spawn <type> | unlock all | skip <days> | hours <n>")
        return
    sub = args[0]
    if sub == "set" and len(args) == 3 and args[1] in sim.state:
        sim.state[args[1]] = float(args[2])
        sim._refresh_unlocks()
        print(f"  {args[1]} = {sim.state[args[1]]}")
    elif sub == "skill" and len(args) == 3 and args[1] in sim.rules["people"]["skills"]["catalog"] \
            and args[2] in ("0", "1", "2", "3"):
        th = sim.rules["people"]["skills"]["xp_thresholds"]
        sim.skill_xp[args[1]] = 0.0 if args[2] == "0" else float(th[int(args[2]) - 1])
        sim._refresh_derived()
        print(f"  {sim.skill_label(args[1])}: level {args[2]}")
    elif sub == "reveal":
        for k, v in sim.state.items():
            print(f"  {k:<16} {v:>9.2f}")
        print("  pending:", [(d, v) for d, v, _ in sim.pending])
    elif sub == "spawn" and len(args) == 2 and args[1] in sim.rules["people"]["types"]:
        c = sim.new_person(args[1], where="the admin console")
        c.trust = 30
        print(f"  Created person #{c.id} {c.name}.")
    elif sub == "spawn":
        print("  types: " + ", ".join(sim.rules["people"]["types"]))
    elif sub == "unlock":
        sim.unlock_all()
        print("  Everything unlocked.")
    elif sub == "hours" and len(args) == 2 and args[1].isdigit():
        sim.hours_left = int(args[1])
        print(f"  hours left = {sim.hours_left}")
    elif sub == "skip" and len(args) == 2 and args[1].isdigit():
        for _ in range(int(args[1])):
            sim.end_day()
            if sim.ending:
                break
            sim.begin_day()
        print(f"  Skipped to {sim.date:%Y-%m-%d}.")
    else:
        print("  Unknown admin command.")


def flush_unlocks(sim: Sim) -> None:
    for name in sim.new_unlocks:
        spec = sim.rules["actions"].get(name)
        what = spec["help"] if spec else sim.rules["shop"][name[4:]]["note"]
        print(wrap(f"New command unlocked: {name}. {what}", "  * "))
    sim.new_unlocks.clear()


def snap(sim: Sim) -> dict[str, int]:
    return {"cash": round(sim.state["cash"]), "heat": round(sim.state["heat"])}


def arrow(now: int, then: int | None) -> str:
    if then is None or now == then:
        return ""
    return "^" if now > then else "v"


def prompt(sim: Sim, admin: bool, ref: dict[str, int] | None = None) -> str:
    """[hours $cash heat]. ^ or v marks a change since the morning of the previous day:
    green when it is good for you (more cash, less heat), red when it is bad."""
    now = snap(sim)
    ref = ref or {}

    def part(label: str, key: str, good_when_up: bool, fmt: str) -> str:
        arr = arrow(now[key], ref.get(key))
        text = fmt.format(now[key]) + arr
        if not arr:
            return text
        good = (arr == "^") == good_when_up
        return paint(text, GREEN if good else RED, prompt=True)

    return (f"\n[{sim.hours_left}h {part('cash', 'cash', True, '${}')} "
            f"{part('heat', 'heat', False, 'heat {}')}"
            f"{' ADMIN' if admin else ''}] > ")


@dataclass
class Session:
    """What a command handler needs: the sim, the city, admin mode and where the player is."""
    sim: Sim
    city: dict[str, Any]
    admin: bool = False
    context: str = "world"


def _report(s: Session, done: bool, msgs: list[str]) -> bool:
    for m in msgs:
        print(wrap(m, "  "))
    if done:
        print(f"  ({s.sim.hours_left}h left today)")
    flush_unlocks(s.sim)
    return False


def cmd_help(s: Session, key: str, args: list[str]) -> bool:
    print(wrap("Each day you have a few free hours after your job. Spend them on actions "
               "(see 'commands'), then 'sleep' to end the day. Meetings happen on certain "
               "days: type 'events' to see them, then 'attend' one and you may meet people. 'people' lists them; "
               "'meet <n>' lets you spend time with one. The news is how you learn what "
               "the world is doing. 'wait 7' sleeps a week without acting."))
    print("Commands: commands, status, news, sleep, wait <days>, quit, and whatever you unlock.")
    return False


def cmd_commands(s: Session, key: str, args: list[str]) -> bool:
    show_commands(s.sim, s.admin)
    return False


def cmd_status(s: Session, key: str, args: list[str]) -> bool:
    show_status(s.sim, s.admin)
    return False


def cmd_news(s: Session, key: str, args: list[str]) -> bool:
    print(render(s.sim, s.city, view="news"))
    return False


def cmd_events(s: Session, key: str, args: list[str]) -> bool:
    days = 7
    if args and args[0].isdigit():
        days = int(args[0])
    elif args and args[0].startswith("m"):
        days = 30
    show_events(s.sim, days)
    return False


def cmd_markets(s: Session, key: str, args: list[str]) -> bool:
    show_markets(s.sim)
    return False


def cmd_people(s: Session, key: str, args: list[str]) -> bool:
    show_people(s.sim, s.admin)
    return False


def cmd_person(s: Session, key: str, args: list[str]) -> bool:
    c = s.sim.person(int(args[0])) if args and args[0].isdigit() else None
    if c is None:
        print("  Usage: person <number>. See 'people'.")
    else:
        show_person(s.sim, c, s.admin)
    return False


def cmd_sleep(s: Session, key: str, args: list[str]) -> bool:
    """`sleep` ends the day; `wait [days]` sleeps several and stops early when something happens."""
    sim = s.sim
    days = 1
    if key == "wait":
        days = int(args[0]) if args and args[0].isdigit() else 7
    for _ in range(days):
        mark = len(sim.log)
        sim.end_day()
        if sim.ending:
            break
        sim.begin_day()
        if days > 1 and any(c in WAKE_EVENTS for _, c, _ in sim.log[mark:]):
            break
    if sim.ending:
        print("\n" + wrap(ENDINGS[sim.ending]))
        print(f"The run lasted {sim.turn} days.")
        return True
    print(render(sim, s.city))
    print("\n  Headlines: 'news'.   What is on today: 'events'.")
    flush_unlocks(sim)
    return False


def cmd_quit(s: Session, key: str, args: list[str]) -> bool:
    return True


def cmd_attend(s: Session, key: str, args: list[str]) -> bool:
    return _report(s, *do_attend(s.sim, args))


def cmd_research(s: Session, key: str, args: list[str]) -> bool:
    return _report(s, *do_research(s.sim, args))


def cmd_meet(s: Session, key: str, args: list[str]) -> bool:
    return _report(s, *do_meet(s.sim, args))


def cmd_buy(s: Session, key: str, args: list[str]) -> bool:
    item = args[0] if args else ""
    if not s.admin and f"buy {item}" not in s.sim.unlocked:
        return _report(s, False, ["Nothing like that is for sale where you know to look."])
    return _report(s, *s.sim.act(" ".join(["buy"] + args)))


def cmd_action(s: Session, key: str, args: list[str]) -> bool:
    """Any action whose numbers live in slice_rules.yaml (the command's `rule`)."""
    return _report(s, *s.sim.act(" ".join([key] + args)))


def cmd_admin(s: Session, key: str, args: list[str]) -> bool:
    admin_cmd(s.sim, args)
    return False


# Every `handler:` in data/commands.yaml must be a key here (checked at startup).
HANDLERS: dict[str, Callable[[Session, str, list[str]], bool]] = {
    "cmd_help": cmd_help, "cmd_commands": cmd_commands, "cmd_status": cmd_status, "cmd_news": cmd_news,
    "cmd_events": cmd_events, "cmd_markets": cmd_markets, "cmd_people": cmd_people, "cmd_person": cmd_person,
    "cmd_sleep": cmd_sleep, "cmd_wait": cmd_sleep, "cmd_quit": cmd_quit, "cmd_attend": cmd_attend,
    "cmd_research": cmd_research, "cmd_meet": cmd_meet, "cmd_buy": cmd_buy, "cmd_action": cmd_action,
    "cmd_admin": cmd_admin,
}


def check_commands(sim: Sim) -> list[str]:
    """The same checks as tools/cmdtree.py --check, plus: every handler exists, every gate variable is real."""
    return cmdtable.check(sim.rules["cmdset"].data, handlers=set(HANDLERS), rules=sim.rules, state_keys=set(sim.state))


def play(sim: Sim, city: dict[str, Any], admin: bool = False) -> None:
    print(wrap(city.get("display", {}).get("disclaimer", "")))
    print(render(sim, city))
    print("\nStart with 'commands' to see what you can do. Try 'events' to see what is on today, 'news' for the headlines.")
    if mode() == "plain":
        print("(Your terminal does not show clickable links, so links print after the text. "
              "Windows Terminal or VS Code's terminal make them clickable.)")
    s = Session(sim, city, admin)
    cs: cmdtable.CommandSet = sim.rules["cmdset"]
    morning, ref = snap(sim), None          # ref = yesterday morning (none on day 1)
    day = sim.turn
    while True:
        if sim.turn != day:                  # a new day started (sleep, wait, admin skip)
            ref, morning, day = morning, snap(sim), sim.turn
        try:
            raw = input(prompt(sim, s.admin, ref)).strip()
        except EOFError:
            print()
            return
        if not raw:
            continue
        word, *rest = raw.split()
        if word.lower() == "admin":          # typing `admin` turns admin mode on, so it is handled before lookup
            if not rest and not s.admin:
                s.admin = True
                sim.unlock_all()
                print("  Admin mode on. Everything is unlocked. Type 'admin' again for options.")
            elif rest and s.admin:
                admin_cmd(sim, rest)
            elif not rest:
                admin_cmd(sim, [])
            else:
                print("Unknown command. Type 'help'.")
            continue
        res = cs.resolve(word, visible_keys(sim, s.admin))
        if res.key is None:
            if res.how == "ambiguous":
                print(wrap(f"That could be {', '.join(res.matches)}. Type more of the word.", "  "))
            else:
                print("Unknown command. Type 'help'.")
            continue
        why = cs.why_not(res.key, sim.state, s.context, s.admin)
        if why:
            print(wrap(why, "  "))
            continue
        if HANDLERS[cs.handler(res.key)](s, res.key, rest):
            return


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="devnull", description="/dev/null: Take the Power Back!")
    parser.add_argument("--seed", type=int, default=None, help="RNG seed (default: random)")
    parser.add_argument("--city", default=None, help="city id or name (default: choose)")
    parser.add_argument("--start-date", type=date.fromisoformat, default=None,
                        help="override the start date (default: today)")
    parser.add_argument("--no-quotes", action="store_true",
                        help="do not fetch live stock quotes or headlines (offline play)")
    parser.add_argument("--no-intro", action="store_true", help="skip the opening screen")
    parser.add_argument("--admin", action="store_true",
                        help="testing: unlock every command and show hidden state on request")
    args = parser.parse_args(argv)

    enable_vt()
    cities = load_cities()
    if not args.no_intro:
        intro.show(animate=True)
    else:
        print(f"/dev/null  v{__version__}")
        print("Take the Power Back!\n")
    city = choose_city(cities, args.city)
    seed = args.seed if args.seed is not None else random.randrange(2**31)
    quotes: dict[str, Any] = {}
    rules = load_rules()
    tape = rules.get("market_tape")
    if tape and not args.no_quotes:
        from devnull.core.market import fetch_quotes
        print("\nFetching delayed stock quotes...")
        quotes = fetch_quotes([s for g in tape["groups"].values() for s in g["tickers"]])
    feed: dict[str, Any] = {}
    if not args.no_quotes:
        from devnull.core.feeds import fetch_feeds
        print("Fetching today's headlines...")
        feed = fetch_feeds(city["city"]["display_name"], city["city"]["state"])
    sim = Sim(seed=seed, rules=rules, quotes=quotes, feed=feed, start_date=args.start_date or date.today(),
              events=city.get("events") or [])
    print(f"\n{city['city']['display_name']}, {city['city']['state']}. "
          f"Your run begins {sim.start_date:%B %d, %Y} and lasts up to 8 years "
          f"(to {sim.end_date:%B %d, %Y}).   seed {seed}")
    problems = check_commands(sim)
    if problems:
        print(f"data/commands.yaml has {len(problems)} problem(s):")
        for p in problems:
            print("  - " + p)
        return 1
    if args.admin:
        sim.unlock_all()
    play(sim, city, admin=args.admin)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

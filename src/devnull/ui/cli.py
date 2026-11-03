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
from typing import Any

import yaml

from devnull import __version__
from devnull.core.digest import describe, render
from devnull.core.termlinks import enable_vt, fill_link, mode
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
WAKE_EVENTS = ("records_arrived", "lawsuit_stage", "lawsuit_result", "election", "contact_met")

# Always available, whatever you have unlocked.
BASIC = ["help", "commands", "status", "news", "events", "markets", "sleep", "wait", "quit"]


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
    for edge, label in sim.rules["contacts"]["trust_bands"]:
        if trust < edge:
            return label
    return "inner circle"


def available_words(sim: Sim, admin: bool) -> list[str]:
    """Command words the player may type right now."""
    words = list(BASIC)
    actions = list(sim.rules["actions"]) if admin else sim.visible_actions()
    words += actions
    if sim.contacts or admin:
        words += ["contacts", "contact", "meet"]
    if admin or sim.visible_shop():
        words.append("buy")
    if admin:
        words.append("admin")
    return words


def show_commands(sim: Sim, admin: bool) -> None:
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
    shop = [i for i in sim.rules["shop"] if admin or f"buy {i}" in sim.unlocked]
    if shop:
        print("\nSHOP               hours  now   what it does")
        for item in shop:
            spec = sim.rules["shop"][item]
            reason = sim.why_not(f"buy {item}")
            mark = "yes" if reason is None else "no "
            tag = " [locked]" if f"buy {item}" not in sim.unlocked else ""
            print(f"  {'buy ' + item:<16} {1:>4}   {mark}   ${spec['price']}. {spec['note']}{tag}")
    if sim.contacts or admin:
        print("\nPEOPLE")
        print("  contacts         list the people you know")
        print("  contact <n>      what you know about one person and what has happened")
        print("  meet <n> [act]   spend time with a contact (coffee, favor, ask, ...)")
    print("\nOTHER: help, commands, status, news, events [days], markets, sleep, wait <days>, quit"
          + (", admin" if admin else ""))
    print("New commands appear as you unlock them.")


def show_status(sim: Sim, admin: bool = False) -> None:
    s = sim.state
    laptop = ("Linux" if s["os"] >= 1 else "Windows 11") + (
        ", works on battery" if s["laptop"] >= 1 else ", battery dead (plugged in only)")
    gear = [n for n, f in (("burner phone", "gear_burner"), ("VPN", "gear_vpn")) if s[f]]
    leads = []
    if s["lead_store"] and not s["laptop"]:
        leads.append("a pawn shop sells laptops with new batteries ($420)")
    if s["lead_npc"] and not s["laptop"]:
        leads.append("a contact can swap a battery (their trust 35, $150)")
    if s["lead_linux"] and not s["os"]:
        leads.append("you know how to install Linux")
    law = {0: "none", 1: "filed", 2: "hearing", 3: "awaiting ruling"}[int(s["filed"])]
    print(f"\n{sim.date:%A %B %d, %Y}   Day {sim.turn + 1}   Free hours left: {sim.hours_left}")
    print(f"  Cash         ${s['cash']:.0f}")
    print(f"  Heat         {s['heat']:.0f}")
    print(f"  Burnout      {s['burnout']:.0f}")
    print(f"  Skills       {s['skills']:.0f}")
    print(f"  Laptop       {laptop}")
    if gear:
        print(f"  Gear         {', '.join(gear)}")
    print(f"  People       {len(sim.contacts)} known; best two average trust {s['trust']:.0f}")
    print(f"  Legibility   about {band(s['legibility'])} (an estimate)")
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
    print("  (Case file, FBI status, NSA coverage and the AI curve are hidden; read the news.)")
    if admin:
        print("  [admin] type 'admin reveal' to see everything.")


def show_contacts(sim: Sim, admin: bool) -> None:
    if not sim.contacts:
        print("  You do not know anyone yet. Go to a meeting ('attend').")
        return
    print(f"\n  {'#':>2}  {'name':<20} {'who':<24} {'standing':<13} last seen")
    for c in sim.contacts:
        who = sim.rules["contacts"]["types"][c.type]["label"]
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


def show_contact(sim: Sim, c: Any, admin: bool) -> None:
    spec = sim.rules["contacts"]["types"][c.type]
    print(f"\n  {c.name}, {a_or_an(spec['label'])}.  Met {c.history[0]['date']}.")
    print(f"  Standing: {trust_band(sim, c.trust)}"
          + ("   Ally." if c.ally else "") + ("   Hostile." if c.hostile else ""))
    if c.owes >= 1:
        print(f"  They owe you ({c.owes:.0f}).")
    if c.leverage >= 1:
        print("  You have something on them.")
    if admin:
        print(f"  [admin] trust {c.trust:.1f} bond {c.bond:.1f} exposure {c.exposure:.1f} "
              f"plant {c.plant} traits {c.traits}")
    print("  History:")
    for h in c.history[-12:]:
        print(wrap(f"{h['date']}  {h['action']} ({h['outcome']}): {h['text']}", "    "))


def show_events(sim: Sim, days: int) -> None:
    """Today's gatherings, then the next occurrence of each one coming up."""
    def line(text: str, m: dict[str, Any]) -> str:
        url = m["real"]["url"] if m.get("real") else None
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
    print("\n  Events with a link are real; click or Ctrl+click it. 'attend' goes to something on today.")


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
        print("  Meetings today:")
        for i, (_, m) in enumerate(ms, 1):
            print(f"    {i}) {m['label']}, {m['time']} ({m['hours']}h)")
        chosen = pick_from("  Which one? (blank to cancel) ", [str(i) for i in range(1, len(ms) + 1)])
        if chosen is None:
            return False, ["You stay home."]
        arg = chosen
    return sim.act("attend" + (f" {arg}" if arg else ""))


def do_meet(sim: Sim, args: list[str]) -> tuple[bool, list[str]]:
    if not args or not args[0].isdigit():
        return False, ["Usage: meet <contact number> [action]. See 'contacts'."]
    c = sim.contact(int(args[0]))
    if c is None:
        return False, ["You do not know anyone with that number."]
    names = list(sim.rules["contacts"]["contact_actions"])
    action = None
    if len(args) > 1:
        hits = [n for n in names if n.startswith(args[1].lower())]
        if len(hits) != 1:
            return False, [f"Unknown action. Options: {', '.join(names)}."]
        action = hits[0]
    else:
        print(f"  What do you do with {c.name}?")
        opts = []
        for i, (a, spec, reason) in enumerate(sim.contact_menu(c.id), 1):
            cost = f" ${spec['cost']}" if spec.get("cost") else ""
            line = f"    {i}) {a:<8} {spec['hours']}h{cost:<6} {spec['help']}"
            print(line + (f"  ({reason})" if reason else ""))
            opts.append(a)
        action = pick_from("  Choose (blank to cancel) ", opts)
        if action is None:
            return False, ["You let it go."]
    return sim.act(f"meet {c.id} {action}")


def admin_cmd(sim: Sim, args: list[str]) -> None:
    if not args:
        print("  admin set <var> <value> | reveal | spawn <type> | unlock all | skip <days> | hours <n>")
        return
    sub = args[0]
    if sub == "set" and len(args) == 3 and args[1] in sim.state:
        sim.state[args[1]] = float(args[2])
        sim._refresh_unlocks()
        print(f"  {args[1]} = {sim.state[args[1]]}")
    elif sub == "reveal":
        for k, v in sim.state.items():
            print(f"  {k:<16} {v:>9.2f}")
        print("  pending:", [(d, v) for d, v, _ in sim.pending])
    elif sub == "spawn" and len(args) == 2 and args[1] in sim.rules["contacts"]["types"]:
        c = sim.new_contact(args[1], where="the admin console")
        c.trust = 30
        print(f"  Created contact #{c.id} {c.name}.")
    elif sub == "spawn":
        print("  types: " + ", ".join(sim.rules["contacts"]["types"]))
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


def resolve_command(text: str, sim: Sim, admin: bool) -> str | None:
    """Exact name, or a unique prefix among the commands the player can use."""
    parts = text.split()
    word, rest = parts[0].lower(), parts[1:]
    names = available_words(sim, admin)
    if word in names:
        return " ".join([word] + rest)
    matches = [n for n in names if n.startswith(word)]
    return " ".join([matches[0]] + rest) if len(matches) == 1 else None


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
    """[hours $cash heat]; ^ or v marks a change since the morning of the previous day."""
    now = snap(sim)
    ref = ref or {}
    return (f"\n[{sim.hours_left}h ${now['cash']}{arrow(now['cash'], ref.get('cash'))} "
            f"heat {now['heat']}{arrow(now['heat'], ref.get('heat'))}"
            f"{' ADMIN' if admin else ''}] > ")


def play(sim: Sim, city: dict[str, Any], admin: bool = False) -> None:
    print(wrap(city.get("display", {}).get("disclaimer", "")))
    print(render(sim, city))
    print("\nType 'events' to see what is on today, 'commands' for what you can do, 'status' for where you stand.")
    if mode() == "plain":
        print("(Your terminal does not show clickable links, so links print after the text. "
              "Windows Terminal or VS Code's terminal make them clickable.)")
    morning, ref = snap(sim), None          # ref = yesterday morning (none on day 1)
    day = sim.turn
    while True:
        if sim.turn != day:                  # a new day started (sleep, wait, admin skip)
            ref, morning, day = morning, snap(sim), sim.turn
        try:
            raw = input(prompt(sim, admin, ref)).strip()
        except EOFError:
            print()
            return
        if not raw:
            continue
        if raw.split()[0].lower() == "admin":
            args = raw.split()[1:]
            if not args and not admin:
                admin = True
                sim.unlock_all()
                print("  Admin mode on. Everything is unlocked. Type 'admin' again for options.")
            elif args and admin:
                admin_cmd(sim, args)
            elif not args:
                admin_cmd(sim, [])
            else:
                print("Unknown command. Type 'help'.")
            continue
        cmd = resolve_command(raw, sim, admin)
        if cmd is None:
            print("Unknown command. Type 'help'.")
            continue
        word, *args = cmd.split()
        if word == "quit":
            return
        if word == "help":
            print(wrap("Each day you have a few free hours after your job. Spend them on actions "
                       "(see 'commands'), then 'sleep' to end the day. Meetings happen on certain "
                       "days: 'attend' one and you may meet people. 'contacts' lists them; "
                       "'meet <n>' lets you spend time with one. The news is how you learn what "
                       "the world is doing. 'wait 7' sleeps a week without acting."))
            print("Commands: commands, status, news, sleep, wait <days>, quit, and whatever you unlock.")
        elif word == "commands":
            show_commands(sim, admin)
        elif word == "status":
            show_status(sim, admin)
        elif word == "news":
            print(render(sim, city))
        elif word == "events":
            show_events(sim, int(args[0]) if args and args[0].isdigit() else 30)
        elif word == "markets":
            show_markets(sim)
        elif word == "contacts":
            show_contacts(sim, admin)
        elif word == "contact":
            c = sim.contact(int(args[0])) if args and args[0].isdigit() else None
            if c is None:
                print("  Usage: contact <number>. See 'contacts'.")
            else:
                show_contact(sim, c, admin)
        elif word in ("sleep", "wait"):
            days = 1
            if word == "wait":
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
                return
            print(render(sim, city))
            flush_unlocks(sim)
        else:
            if word == "attend":
                done, msgs = do_attend(sim, args)
            elif word == "meet":
                done, msgs = do_meet(sim, args)
            elif word == "buy" and not admin and f"buy {args[0] if args else ''}" not in sim.unlocked:
                done, msgs = False, ["There is nothing like that for sale that you know of."]
            else:
                done, msgs = sim.act(cmd)
            for m in msgs:
                print(wrap(m, "  "))
            if done:
                print(f"  ({sim.hours_left}h left today)")
            flush_unlocks(sim)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="devnull", description="/dev/null: Know Your Enemy.")
    parser.add_argument("--seed", type=int, default=None, help="RNG seed (default: random)")
    parser.add_argument("--city", default=None, help="city id or name (default: choose)")
    parser.add_argument("--start-date", type=date.fromisoformat, default=None,
                        help="override the start date (default: today)")
    parser.add_argument("--no-quotes", action="store_true",
                        help="do not fetch live stock quotes or headlines (offline play)")
    parser.add_argument("--admin", action="store_true",
                        help="testing: unlock every command and show hidden state on request")
    args = parser.parse_args(argv)

    enable_vt()
    print(f"/dev/null  v{__version__}")
    print("Know Your Enemy.\n")
    cities = load_cities()
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
    if args.admin:
        sim.unlock_all()
    play(sim, city, admin=args.admin)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

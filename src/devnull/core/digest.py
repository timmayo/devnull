"""The morning news digest.

The player never sees most of the world state. The digest is how they infer
it: coverage is lagged, noisy and sometimes wrong. Text is plain ASCII so it
prints on any terminal. Stories with a link are real and point to their source;
everything else is generic and fictional.

Uses its own random stream (seed + turn) so reading the digest never changes
the simulation.
"""

from __future__ import annotations

import random
from typing import Any

from devnull.core.news import game_stories
from devnull.core.sim import Sim
from devnull.core.termlinks import fill_link

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]
MAX_STORIES = 10
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

AI_LINES = [
    (40, "Another round of data center announcements; analysts call the buildout steady."),
    (60, "New data centers come online across the Midwest as chip supply improves."),
    (80, "Utilities warn that AI-driven demand is outrunning planned capacity."),
    (101, "Officials say AI systems now do work that once took whole departments."),
]
OPINION_LINES = [
    (-30, "Protests against data centers draw crowds in several states."),
    (-10, "More residents tell pollsters they want limits on new data centers."),
    (10, "A poll finds voters split on AI and data centers."),
    (30, "Polls show support for AI, with growing worry about power bills."),
    (101, "A new poll finds most people welcome AI in daily life."),
]
ELITE_LINES = [
    (35, "Tech executives sound calmer about AI risk this week."),
    (60, "Several tech chiefs say AI will need guardrails, then announce new capacity."),
    (101, "CEOs of the biggest AI companies warn that AI could end humanity, "
          "and say they must keep building to stay ahead."),
]
PUBLIC_LINES = [
    (25, "Most people still treat AI as a faster search engine: homework, recipes, emails."),
    (50, "Ordinary users shrug off the doomsday talk; many say AI is just a better search box."),
    (101, "Public worry about AI is growing; polls show more people asking who it serves."),
]
REG_LINES = [
    (20, "Lawmakers show little appetite for new rules on AI."),
    (40, "A bill on data center disclosure sits in committee."),
    (101, "State lawmakers advance rules on data center power and water use."),
]


def pick(lines: list[tuple[float, str]], x: float) -> str:
    for edge, text in lines:
        if x < edge:
            return text
    return lines[-1][1]


def lagged(sim: Sim, days: int = 3) -> dict[str, float]:
    """Coverage lags reality: values from a few days ago."""
    i = max(0, len(sim.history) - 1 - days)
    return sim.history[i]


def header(sim: Sim) -> str:
    d = sim.date
    return f"{DAYS[d.weekday()]}, {MONTHS[d.month - 1]} {d.day}, {d.year}    Day {sim.turn + 1}"


def calendar_note(d) -> str | None:
    """Real calendar facts that follow from the date alone (no source needed)."""
    from datetime import date, timedelta
    if (d.month, d.day) == (12, 25):
        return "Christmas Day. Most shops are closed."
    if (d.month, d.day) == (1, 1):
        return "New Year's Day."
    if (d.month, d.day) == (7, 4):
        return "Independence Day."
    nov1 = date(d.year, 11, 1)
    thanks = nov1 + timedelta((3 - nov1.weekday()) % 7) + timedelta(21)
    if d == thanks:
        return "Thanksgiving."
    dst_end = nov1 + timedelta((6 - nov1.weekday()) % 7)
    if d == dst_end:
        return "Clocks fell back an hour overnight."
    mar1 = date(d.year, 3, 1)
    dst_start = mar1 + timedelta((6 - mar1.weekday()) % 7) + timedelta(7)
    if d == dst_start:
        return "Clocks sprang forward an hour overnight."
    return None


def season(d) -> str:
    return {12: "winter", 1: "winter", 2: "winter", 3: "spring", 4: "spring", 5: "spring",
            6: "summer", 7: "summer", 8: "summer"}.get(d.month, "fall")


def real_lines(items: list[dict[str, Any]], d) -> list[Any]:
    """Curated real items whose window covers the date: (text, url) pairs."""
    return [("%s (%s)" % (i["text"], i["source"]), i["url"])
            for i in items if i["window"][0] <= d <= i["window"][1]]


def feed_lines(sim: Sim, scope: str) -> list[Any]:
    """Live headlines; only on day 1, when they describe the same day."""
    if sim.turn != 0:
        return []
    return [("%s (%s)" % (it["title"], it["source"]), it["link"]) for it in sim.feed.get(scope, [])]


def filler_lines(city: dict[str, Any] | None, sim: Sim, rng: random.Random, n: int) -> list[str]:
    fillers = ((city or {}).get("news") or {}).get("fillers") or {}
    pool = list(fillers.get("all", [])) + list(fillers.get(season(sim.date), []))
    return rng.sample(pool, min(n, len(pool))) if pool else []


def election_line(sim: Sim) -> str | None:
    for t in sorted(sim.election_turns):
        if t == sim.turn:
            return "Election Day. Polls are open."
        if t - 45 <= sim.turn < t:
            return f"Election Day is in {t - sim.turn} days."
        if t + 1 == sim.turn:
            return "Ballots from yesterday's election are being counted."
    return None


def describe(m: dict[str, Any]) -> str:
    where = " - " + m["real"]["venue"] if m.get("real") and m["real"].get("venue") else ""
    return "%s, %s (%dh)%s" % (m["label"], m["time"], m["hours"], where)


def morning(sim: Sim, city: dict[str, Any] | None = None) -> list[tuple[str, list[str]]]:
    """Sections of (title, lines). Call after begin_day()."""
    sim.begin_day()
    s = sim.state
    rng = random.Random(f"{sim.seed}-{sim.turn}")
    lag = lagged(sim)
    sections: list[tuple[str, list[str]]] = []

    # -- your morning ----------------------------------------------------
    me: list[str] = []
    if sim.turn == 0:
        me.append("You wake up in a cheap apartment. The radiator ticks. On the desk "
                  "the laptop is plugged into the wall, because it dies the moment you "
                  "pull the cord. Windows 11 wants to restart for updates. Again.")
    me.append("Workday. About %d free hours after your shift." % sim.hours_left
              if sim.is_workday else
              "Day off. About %d free hours." % sim.hours_left)
    if s["burnout"] > 85:
        me.append("You can barely keep your eyes open.")
    elif s["burnout"] > 60:
        me.append("You are running on fumes.")
    me.append("Cash: $%d. Bills run about $%d a day.%s" % (
        s["cash"], sim.rules["daily"]["upkeep"], " Money is tight." if s["cash"] < 150 else ""))
    if s["laptop"] < 1:
        me.append("Laptop: Windows 11. The battery is dead; it only runs plugged in.")
    else:
        me.append("Laptop: %s. It runs on battery." % ("Linux" if s["os"] >= 1 else "Windows 11"))
    sections.append(("YOUR MORNING", me))

    # -- overnight events ------------------------------------------------
    news: list[str] = []
    for turn, code, data in sim.log:
        if turn not in (sim.turn - 1, sim.turn):
            continue
        if code == "records_arrived":
            news.append("A reply to one of your records requests arrives.")
        elif code == "lawsuit_stage":
            news.append("Your case is set for a hearing." if data == 2 else
                        "The judge has your case under advisement. A ruling is coming.")
        elif code == "lawsuit_result":
            news.append("The court rules in your favor. It is on the front page of the local paper."
                        if data else "The court rules against you.")
        elif code == "election":
            if data >= 2:
                news.append("Votes are counted. Analysts say the result tilts toward tougher oversight of the data center boom.")
            elif data <= -2:
                news.append("Votes are counted. Analysts say the result tilts toward looser rules for the data center boom.")
            else:
                news.append("Votes are counted. Analysts say little has changed on AI policy.")
    if news:
        sections.append(("OVERNIGHT", news))

    news_cfg = (city or {}).get("news") or {}
    meetings = sim.meetings_today()

    # -- local news: real stories, then this game's own ------------------
    local: list[str] = real_lines(news_cfg.get("real_events", []), sim.date)
    local += feed_lines(sim, "local")
    local += game_stories(sim, "local", rng)
    local.append(pick(AI_LINES, lag["ai"] + rng.gauss(0, 4)))
    local.append(pick(OPINION_LINES, lag["opinion"] + rng.gauss(0, 8)))
    line = election_line(sim)
    if line:
        local.append(line)
    note = calendar_note(sim.date)
    if note:
        local.append(note)
    if city and sim.date.weekday() == 1 and not meetings:
        tue = (city.get("display", {}).get("digest_notes") or {}).get("tuesday")
        if tue:
            local.append(tue)
    local += filler_lines(city, sim, rng, 1)
    sections.append(("LOCAL NEWS", local[:MAX_STORIES]))

    # -- national news ---------------------------------------------------
    nat: list[str] = real_lines(news_cfg.get("national_real", []), sim.date)
    nat += feed_lines(sim, "national")
    if sim.turn == 0:                     # every run opens with the same split
        nat.append(ELITE_LINES[-1][1])
        nat.append("Meanwhile, most people say they use AI as a glorified search engine "
                   "and do not see what the fuss is about.")
    else:
        nat.append(pick(ELITE_LINES, lag["elite_alarm"] + rng.gauss(0, 6)))
        nat.append(pick(PUBLIC_LINES, lag["public_concern"] + rng.gauss(0, 5)))
    nat += game_stories(sim, "national", rng)
    week_ago = sim.history[max(0, len(sim.history) - 8)]["market"]
    move = lag["market"] - week_ago + rng.gauss(0, 3)
    nat.append("Tech shares rally." if move > 5 else
               "Tech shares slide on talk of tighter scrutiny." if move < -5 else
               "Markets are flat.")
    nat.append(pick(REG_LINES, lag["regulation"] + rng.gauss(0, 5)))
    sections.append(("NATIONAL NEWS", nat[:MAX_STORIES]))

    # -- signs you are being watched (hidden state, inferred) ------------
    signs: list[str] = []

    def sign(true_if: bool, text: str) -> None:
        if true_if and rng.random() < 0.8:
            signs.append(text)

    sign(lag["case_file"] > 30, "A patrol car has been parked across the street more than once this week.")
    sign(lag["case_file"] > 55, "A neighbor says an officer was asking about you.")
    sign(lag["fbi"] >= 1, "A call from a blocked number. Nobody spoke.")
    sign(lag["fbi"] >= 2, "Your landlord mentions that someone asked about your lease.")
    sign(lag["fbi"] >= 3, "Your bank sends a notice: your account is under review.")
    sign(lag["heat"] > 20, "Your phone shows a login alert you did not trigger.")
    sign(lag["legibility"] > 30, "The ads on your phone are eerily specific. Someone knows your routines.")
    if lag["case_file"] < 15 and rng.random() < 0.05:
        signs.append("You think you saw the same car twice. Probably nothing.")
    if signs:
        sections.append(("ON YOUR MIND", signs))
    return sections


NEWS_TITLES = ("LOCAL NEWS", "NATIONAL NEWS")


def render(sim: Sim, city: dict[str, Any] | None = None, width: int = 78, view: str = "morning") -> str:
    """view='morning' is the day's opening without headlines; view='news' is only the headlines."""
    import textwrap
    out = ["", "=" * width, header(sim), "=" * width]
    for title, lines in morning(sim, city):
        if (title in NEWS_TITLES) != (view == "news"):
            continue
        out.append("")
        out.append(title)
        for ln in lines:
            if isinstance(ln, tuple):                 # (text, url): the whole item is a link
                out.append(fill_link(ln[0], ln[1], width, "  - ", "    "))
            else:
                out.append(textwrap.fill(ln, width=width, initial_indent="  - ",
                                         subsequent_indent="    "))
    return "\n".join(out)

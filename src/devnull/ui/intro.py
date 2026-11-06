"""Opening screen: plain text, a frame, a few redacted bars. Any key skips the animation."""
from __future__ import annotations

import os
import random
import sys
import time

from devnull import __version__
from devnull.core.termlinks import colors_enabled, paint

W = 64
BAR = "█"
SHADE = "░"


def _key_pressed() -> bool:
    """True if a key is waiting (and consume it). Never blocks."""
    try:
        if os.name == "nt":
            import msvcrt
            if msvcrt.kbhit():
                while msvcrt.kbhit():
                    msvcrt.getwch()
                return True
            return False
        import select
        import termios
        import tty
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            if select.select([sys.stdin], [], [], 0)[0]:
                sys.stdin.read(1)
                return True
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
    except Exception:
        pass
    return False


def spaced(s: str) -> str:
    return " ".join(s)


def frame(lines: list[str]) -> list[str]:
    out = ["╔" + "═" * W + "╗"]
    out += ["║" + l.center(W) + "║" for l in lines]
    out.append("╚" + "═" * W + "╝")
    return out


LAST_RUN = {
    "caught": "last run ended in custody",
    "broke": "last run ended broke",
    "pressure_won": "last run: they backed off, for now",
    "reform": "last run: terms signed, still watched",
    "runaway": "last run: it got away from everyone",
    "stalemate": "last run ended in a stalemate",
}


def bars(rng: random.Random, widths: list[int]) -> str:
    """Redaction bars; their widths shift a little on every launch."""
    return " ".join(BAR * max(3, w + rng.randint(-2, 2)) for w in widths)


def screen(profile: dict | None = None, city: str | None = None, years: int = 8,
           rng: random.Random | None = None) -> list[tuple[str, str | None]]:
    """(text, style) per row. Style is an ANSI code for the title lines, or None.
    No profile = the first launch: the plain static file. Otherwise the file shows what is on record."""
    title = [(spaced("HUMANITY TRAINED IT."), "2"), (spaced("THEY OWN IT."), "2"),
             (spaced("YOUR JOB IS TO BREAK IT."), "2")]
    if not profile:
        return [("", None), (spaced("/dev/null"), "1"), ("", None), *title, ("", None),
                (f"FILE 0000-0000    CLASSIFICATION: {BAR * 11}", None),
                (f"SUBJECT: you  ·  CITY: {city or 'your choice'}  ·  YEARS: {years}", None),
                (f"OPPONENTS: {BAR * 10} {BAR * 8}, {BAR * 6} {BAR * 6}", None),
                (f"STATUS: {SHADE * 10} not yet under observation", None),
                ("", None), (f"v{__version__}", "2"), ("", None)]

    rng = rng or random.Random()
    runs = profile.get("runs") or []
    total = int(profile.get("total_runs", len(runs)))
    last = runs[-1] if runs else {}
    first = str(profile.get("first_seen", ""))[:7].replace("-", "")
    where = city or last.get("city_name") or "your choice"
    rows: list[tuple[str, str | None]] = [
        ("", None), (spaced("/dev/null"), "1"), ("", None), *title, ("", None),
        (f"FILE {total:04d}-{first or '0000'}    CLASSIFICATION: {bars(rng, [11])}", None),
        (f"SUBJECT: you  ·  CITY: {where}  ·  YEARS: {years}", None),
        (f"OPPONENTS: {bars(rng, [10, 8])}, {bars(rng, [6, 6])}", None),
        (f"STATUS: {SHADE * 10} under observation ({total} run{'s' if total != 1 else ''} on file)", None),
    ]
    if last:
        ended = LAST_RUN.get(last.get("ending") or "", "last run unfinished")
        days = f"day {last['days']}" if last.get("days") else "in progress"
        rows.append((f"LAST: {last.get('city_name', '?')}, {days} - {ended}", None))
    rows += [("", None), (f"v{__version__}", "2"), ("", None)]
    return rows


def show(profile: dict | None = None, city: str | None = None, years: int = 8, animate: bool = True) -> None:
    """Print the opening screen. The first launch (no profile) is static: it appears at once. Later launches
    are dynamic: the file reflects the player's history and is drawn line by line on a real terminal;
    any key skips the animation."""
    rows = screen(profile, city, years)
    framed = frame([r[0] for r in rows])
    styles = [None] + [r[1] for r in rows] + [None]
    live = bool(profile) and animate and sys.stdout.isatty() and colors_enabled()
    print()
    skipped = not live
    for text, style in zip(framed, styles):
        if style:
            inner = text[1:-1]
            text = text[0] + paint(inner, style) + text[-1]
        print("  " + text)
        if not skipped:
            time.sleep(0.07)
            if _key_pressed():
                skipped = True
    print()

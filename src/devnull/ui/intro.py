"""Opening screen: plain text, a frame, a few redacted bars. Any key skips the animation."""
from __future__ import annotations

import os
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


def screen(city: str | None = None, years: int = 8) -> list[tuple[str, str | None]]:
    """(text, style) per row. Style is an ANSI code for the title, or None."""
    where = city or "your choice"
    rows: list[tuple[str, str | None]] = [
        ("", None),
        (spaced("/dev/null"), "1"),
        ("", None),
        (spaced("TAKE THE POWER BACK!"), "2"),
        ("", None),
        (f"FILE 0000-0000    CLASSIFICATION: {BAR * 11}", None),
        (f"SUBJECT: you  ·  CITY: {where}  ·  YEARS: {years}", None),
        (f"OPPONENTS: {BAR * 10} {BAR * 8}, {BAR * 6} {BAR * 6}", None),
        (f"STATUS: {SHADE * 10} not yet under observation", None),
        ("", None),
        (f"v{__version__}", "2"),
        ("", None),
    ]
    return rows


def show(city: str | None = None, years: int = 8, animate: bool = True) -> None:
    """Print the opening screen. Animated only on a real terminal; any key skips."""
    rows = screen(city, years)
    framed = frame([r[0] for r in rows])
    styles = [None] + [r[1] for r in rows] + [None]
    live = animate and sys.stdout.isatty() and colors_enabled()
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

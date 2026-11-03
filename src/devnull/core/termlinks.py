"""Clickable terminal hyperlinks (OSC 8), with a plain-text fallback.

Windows Terminal and VS Code's terminal support them (Ctrl+click). Terminals that
do not get "text <url>" instead. Override with DEVNULL_LINKS=osc8 or plain.
"""

from __future__ import annotations

import os
import sys
import textwrap

ESC = "\x1b"


def enable_vt() -> None:
    """Let older Windows consoles accept escape codes. Harmless elsewhere."""
    if os.name != "nt":
        return
    try:
        import ctypes
        k = ctypes.windll.kernel32            # type: ignore[attr-defined]
        h = k.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if k.GetConsoleMode(h, ctypes.byref(mode)):
            k.SetConsoleMode(h, mode.value | 0x0004)
    except Exception:
        pass


def mode() -> str:
    forced = os.environ.get("DEVNULL_LINKS", "").lower()
    if forced in ("osc8", "plain"):
        return forced
    if not sys.stdout.isatty():
        return "plain"
    if os.name == "nt" and not (os.environ.get("WT_SESSION") or os.environ.get("TERM_PROGRAM")):
        return "plain"                         # classic console: no hyperlink support
    return "osc8"


def link(text: str, url: str) -> str:
    return f"{ESC}]8;;{url}{ESC}\\{text}{ESC}]8;;{ESC}\\"


def fill_link(text: str, url: str | None, width: int = 78, initial: str = "", subsequent: str = "") -> str:
    """Wrap text to a width, then make each wrapped line a link to the url.

    Wrapping happens first on the plain text, so escape codes never break a line."""
    if not url:
        return textwrap.fill(text, width=width, initial_indent=initial, subsequent_indent=subsequent)
    if mode() == "plain":
        return textwrap.fill(f"{text} <{url}>", width=width, initial_indent=initial,
                             subsequent_indent=subsequent, break_long_words=False, break_on_hyphens=False)
    lines = textwrap.wrap(text, width=width, initial_indent=initial, subsequent_indent=subsequent)
    out = []
    for ln in lines:
        body = ln.lstrip(" -")
        pad = ln[: len(ln) - len(body)]
        out.append(pad + link(body, url))
    return "\n".join(out)


GREEN, RED = "32", "31"


def colors_enabled() -> bool:
    """ANSI colors on a real terminal. Off for pipes, NO_COLOR, or DEVNULL_COLOR=off."""
    if os.environ.get("NO_COLOR") or os.environ.get("DEVNULL_COLOR", "").lower() == "off":
        return False
    return sys.stdout.isatty() and os.environ.get("TERM") != "dumb"


def paint(text: str, color: str, prompt: bool = False) -> str:
    """Wrap text in a color. In an input() prompt on non-Windows, mark the codes as zero-width."""
    if not colors_enabled():
        return text
    start, end = f"{ESC}[{color}m", f"{ESC}[0m"
    if prompt and os.name != "nt":
        start, end = f"\x01{start}\x02", f"\x01{end}\x02"
    return start + text + end

#!/usr/bin/env python3
"""Offline test of tools/cityfetch.py: a local web server plays working, changed, moved and dead pages.
Exit code 0 = all good. Run:  python tools/test_cityfetch.py"""
from __future__ import annotations

import os
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["NO_PROXY"] = "127.0.0.1,localhost"
os.environ["no_proxy"] = "127.0.0.1,localhost"

import cityfetch as cf  # noqa: E402

STATE = {"n": 1, "text": "Seven members."}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet
        pass

    def do_GET(self):
        route = self.path.split("?")[0]
        if route == "/council":
            body = f"<html><head><script>var t={STATE['n']}</script><style>p{{color:red}}</style></head><body><h1>Council</h1><p>{STATE['text']}</p></body></html>".encode()
            self.send_response(200); self.send_header("Content-Type", "text/html"); self.end_headers(); self.wfile.write(body)
        elif route == "/old":
            self.send_response(301); self.send_header("Location", "/new-home"); self.end_headers()
        elif route == "/new-home":
            self.send_response(200); self.send_header("Content-Type", "text/html"); self.end_headers(); self.wfile.write(b"<p>hi</p>")
        elif route == "/forbidden":
            self.send_response(403); self.end_headers()
        elif route == "/file.pdf":
            self.send_response(200); self.send_header("Content-Type", "application/pdf"); self.end_headers(); self.wfile.write(b"%PDF-1.4 fake")
        else:
            self.send_response(404); self.end_headers()


def main() -> int:
    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_port}"
    data = {"city": {"display_name": "Test City", "state": "Testland"}, "resources": [
        {"id": "council", "kind": "facts", "url": base + "/council"},
        {"id": "pdf", "kind": "events", "url": base + "/file.pdf"},
        {"id": "moved", "kind": "facts", "url": base + "/old"},
        {"id": "gone", "kind": "facts", "url": base + "/missing"},
        {"id": "blocked", "kind": "facts", "url": base + "/forbidden"},
        {"id": "nowhere", "kind": "feed", "url": "http://127.0.0.1:1/x"},
        {"id": "todo", "kind": "roster", "url": None, "note": "NEEDED: roster"},
        {"id": "feed", "kind": "feed", "url": base + "/council?q={city}+{state}"},
    ]}
    bad = 0

    def expect(label: str, got, want) -> None:
        nonlocal bad
        ok = got == want
        bad += 0 if ok else 1
        print(("ok   " if ok else "FAIL ") + label + ("" if ok else f"  got {got!r}, wanted {want!r}"))

    def states(lock):
        return {r["id"]: r["state"] for r in cf.check_resources(data, lock, timeout=3)}

    first = states({})
    expect("first check: pages with nothing saved are NEW", first["council"], "NEW")
    expect("a pdf is NEW", first["pdf"], "NEW")
    expect("a redirect is MOVED", first["moved"], "MOVED")
    expect("a 404 is DEAD", first["gone"], "DEAD")
    expect("a 403 is BLOCKED, not DEAD", first["blocked"], "BLOCKED")
    expect("an unreachable host is DEAD", first["nowhere"], "DEAD")
    expect("no url is NEEDED", first["todo"], "NEEDED")
    expect("{city} and {state} are filled in", cf.concrete("http://x/?q={city}+{state}", data["city"]), "http://x/?q=Test+City+Testland")

    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "test_city.yaml"
        f.write_text("x: 1")
        rows = cf.check_resources(data, {}, timeout=3)
        cf.write_lock(f, rows, {})
        lock = cf.read_lock(f)
        expect("only readable pages are saved", sorted(lock), ["council", "feed", "moved", "pdf"])
        expect("the saved check holds a hash, not the page", set(lock["council"]), {"url", "hash", "checked"})
        again = states(lock)
        expect("unchanged page is ok", again["council"], "ok")
        expect("unchanged pdf is ok", again["pdf"], "ok")
        STATE["n"] = 2                                   # only a script value changes
        expect("a script-only change is still ok", states(lock)["council"], "ok")
        STATE["text"] = "Nine members."                  # what a reader sees changes
        expect("a text change is CHANGED", states(lock)["council"], "CHANGED")
        expect("a missing lock file reads as empty", cf.read_lock(Path(tmp) / "none.yaml"), {})
    live = {"city": data["city"], "resources": [{"id": "feed", "kind": "feed", "url": base + "/council"}]}
    STATE["text"] = "A"; lk = {"feed": {"hash": "old"}}
    expect("a feed whose content changed is still ok", cf.check_resources(live, lk, timeout=3)[0]["state"], "ok")
    srv.shutdown()
    print("\nall passed" if not bad else f"\n{bad} FAILED")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())

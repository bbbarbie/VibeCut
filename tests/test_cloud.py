"""Preferences follow the creator: the Supabase mirror, against a fake PostgREST.

A tiny HTTP server stands in for Supabase's REST endpoint (upsert on POST,
filtered rows on GET). Pushes carry the device, kind, key, value and time;
defaults, confirmed rules and a learnt reel push themselves; pull brings
back rows with their time and `newer` keeps only what beats the local copy;
offline nothing raises and the failure is logged; at server start, newer
defaults and rules from the mirror are applied; the profile round-trips.

    python tests/test_cloud.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

os.environ.setdefault("VIBECUT_CACHE", tempfile.mkdtemp(prefix="vibecut-cloud-"))
os.environ.setdefault("VIBECUT_EXPORTS", os.path.join(os.environ["VIBECUT_CACHE"], "out"))
os.environ.setdefault("VIBECUT_BED", "0")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROWS: dict[tuple, dict] = {}
failures: list[str] = []


def check(name: str, cond: bool, got: str = "") -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{': ' + got if got else ''}")
    if not cond:
        failures.append(name)


class Fake(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n) or b"[]")
        for r in body if isinstance(body, list) else [body]:
            ROWS[(r["device"], r["kind"], r["key"])] = r
        self.send_response(201); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(b"[]")

    def do_GET(self):
        q = parse_qs(urlparse(self.path).query)
        dev = q.get("device", [""])[0].replace("eq.", "")
        kind = q.get("kind", [""])[0].replace("eq.", "")
        out = [r for (d, k, _), r in ROWS.items() if d == dev and (not kind or k == kind)]
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(json.dumps(out).encode())


def wait_for(cond, s=5.0) -> bool:
    t0 = time.time()
    while time.time() - t0 < s:
        if cond():
            return True
        time.sleep(0.05)
    return cond()


def main() -> int:
    srv = HTTPServer(("127.0.0.1", 0), Fake)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    os.environ["SUPABASE_URL"] = f"http://127.0.0.1:{srv.server_port}"
    os.environ["SUPABASE_ANON_KEY"] = "test-key"
    from web.backend import cloud, defaults, preferences

    print("push and pull")
    check("configured", cloud.available())
    dev = cloud.device()
    check("a device id is made once and kept", dev and cloud.device() == dev)
    cloud.push("default", "look", "hype", wait=True)
    r = ROWS.get((dev, "default", "look"))
    check("a push is an upsert row with the device, kind, key, value and time", r and r["value"] == "hype" and r["updated_at"].endswith("Z"), json.dumps(r))
    defaults.forget()
    defaults.note(format="wide")
    check("a default pushes itself", wait_for(lambda: (dev, "default", "format") in ROWS), str(sorted(k[1:] for k in ROWS)))
    prefs = preferences.Preferences(preferences.Path(os.environ["VIBECUT_CACHE"]) / "preferences.json")
    prefs.rules.append({"id": "r1", "rule": "never two identical shots", "created": time.time(), "klass": "long_term"})
    prefs._save()
    check("a saved rule pushes itself", wait_for(lambda: (dev, "rule", "r1") in ROWS))
    rows = cloud.pull()
    check("pull brings the device's rows back, timed", len(rows) >= 3 and all("at" in x for x in rows), str(len(rows)))
    check("newer keeps only what beats the local copy", cloud.newer(rows, time.time() + 100) == [] and len(cloud.newer(rows, 0)) == len(rows))

    print("offline")
    os.environ["SUPABASE_URL"] = "http://127.0.0.1:9"
    cloud.push("default", "look", "cozy", wait=True)
    check("a failed push never raises, and is logged", cloud.LOG and cloud.LOG[-1]["ok"] is False, json.dumps(cloud.LOG[-1]))
    check("a failed pull is empty", cloud.pull() == [])
    check("the failed row waits to be retried", cloud.status()["pending"] >= 1)
    os.environ["SUPABASE_URL"] = f"http://127.0.0.1:{srv.server_port}"
    cloud.push("default", "music", "on", wait=True)
    check("the next push carries the waiting row too", ROWS[(dev, "default", "look")]["value"] == "cozy" and cloud.status()["pending"] == 0)

    print("at server start")
    future = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(time.time() + 3600)) + "Z"
    ROWS[(dev, "default", "look")] = {"device": dev, "kind": "default", "key": "look", "value": "film", "updated_at": future}
    ROWS[(dev, "rule", "r2")] = {"device": dev, "kind": "rule", "key": "r2", "value": {"id": "r2", "rule": "end on the sunset", "created": time.time(), "klass": "long_term"}, "updated_at": future}
    ROWS[(dev, "profile", "me")] = {"device": dev, "kind": "profile", "key": "me", "value": {"name": "Sarah", "handle": "@s"}, "updated_at": future}
    from fastapi.testclient import TestClient
    from web.backend import app as backend
    with TestClient(backend.app) as c:
        check("a newer default from the mirror is applied", wait_for(lambda: defaults.get().get("look") == "film"), str(defaults.get()))
        check("a rule from the mirror is absorbed", wait_for(lambda: any(r.get("id") == "r2" for r in backend.PREFS.rules)))
        check("the profile from the mirror is here", wait_for(lambda: (c.get("/api/profile").json().get("profile") or {}).get("name") == "Sarah"))
        r = c.post("/api/profile", json={"profile": {"name": "Sarah A", "handle": "@s"}}).json()
        check("a saved profile is kept and pushed", r["profile"]["name"] == "Sarah A" and wait_for(lambda: ROWS[(dev, "profile", "me")]["value"]["name"] == "Sarah A"))
        check("the capability line says the mirror is on", c.get("/api/projects").json()["capabilities"]["cloud"] is True)
        backend._close_project()
    srv.shutdown()

    print()
    if failures:
        print(f"{len(failures)} failed: {failures}")
        return 1
    print("all passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

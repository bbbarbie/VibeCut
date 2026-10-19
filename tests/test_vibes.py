"""A vibe is what a set of reels has in common, and Make can cut like it.

Three synthetic reels (quick, hard cuts, a long last shot) become one vibe:
its record names them, its fingerprint is their median, it lists under
"Cut it like" beside the creator's own reels, and a Make with it takes its
shot length instead of the frame's prior. Fewer than three reels is refused.

    python tests/test_vibes.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("VIBECUT_CACHE", tempfile.mkdtemp(prefix="vibecut-vibes-"))
os.environ.setdefault("VIBECUT_EXPORTS", os.path.join(os.environ["VIBECUT_CACHE"], "out"))
os.environ.setdefault("VIBECUT_BED", "0")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

failures: list[str] = []


def check(name: str, cond: bool, got: str = "") -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{': ' + got if got else ''}")
    if not cond:
        failures.append(name)


def main() -> int:
    from tests.test_style import build
    from web.backend import make, vibes
    d = Path(tempfile.mkdtemp(prefix="vibecut-vibes-reels-"))
    reels = []
    for i, lens in enumerate([[0.6, 0.8, 0.7, 0.9, 0.6, 3.0], [0.7, 0.7, 0.9, 0.8, 0.7, 2.5], [0.8, 0.6, 0.8, 0.7, 0.9, 3.5]]):
        p = str(d / f"reel{i}.mp4")
        build(p, lens)
        reels.append(p)

    print("learning a set")
    try:
        vibes.learn_set("test niche", reels[:2], say=lambda *_: None)
        check("fewer than three reels is refused", False)
    except ValueError as e:
        check("fewer than three reels is refused", "at least" in str(e))
    rec = vibes.learn_set("day in my life", reels, name="Test days", say=lambda *_: None)
    check("the record names its reels and its shape", rec["n"] == 3 and len(rec["sources"]) == 3 and rec["fingerprint"]["median_s"] < 1.2
          and rec["fingerprint"]["last_s"] and rec["fingerprint"]["last_s"] > 2.0, json.dumps({k: rec[k] for k in ("id", "n", "words")}))
    check("it is saved and listed", any(v["id"] == rec["id"] for v in vibes.list_all()))
    ch = vibes.choices()
    check("it is offered under Cut it like, before the creator's own reels",
          ch and ch[0]["id"] == rec["id"] and ch[0]["kind"] == "library" and sum(c["kind"] == "reference" for c in ch) == 3, str([(c["kind"], c["name"][:12]) for c in ch]))
    fp = vibes.fingerprint_for(rec["id"])
    check("its fingerprint can be fetched, and one reel's too", fp and fp["median_s"] == rec["fingerprint"]["median_s"]
          and vibes.fingerprint_for(ch[-1]["id"]) and vibes.fingerprint_for("nope") is None)

    print("make cuts like it")
    f = make.fingerprint("short", "calm", 60.0, vibe=fp)
    check("a vibe beats the frame's prior", f["median_s"] == fp["median_s"] and f["refs_used"] and f["duration"] <= 60.0, json.dumps({"median": f["median_s"], "dur": f["duration"]}))
    check("without one the prior stands", make.fingerprint("short", "calm", 60.0)["median_s"] == make.PRIOR["short"]["median"]["calm"])

    print("through the API")
    from fastapi.testclient import TestClient
    from web.backend import app as backend, defaults
    with TestClient(backend.app) as c:
        r = c.get("/api/vibes").json()
        check("the route lists it", any(v["id"] == rec["id"] for v in r["vibes"]))
        check("too few reels is refused in the app", c.post("/api/vibes", json={"niche": "x", "links": reels[:2]}).status_code == 400)
        import time
        job = c.post("/api/vibes", json={"niche": "cinematic", "name": "In-app", "links": reels}).json()
        for _ in range(600):
            if job["stage"] in ("done", "error"):
                break
            time.sleep(0.5)
            job = c.get(f"/api/vibes/jobs/{job['id']}").json()
        check("learnt from inside the app as a job", job["stage"] == "done" and job["vibe"] and job["done"] == 3, json.dumps(job))
        check("…and it shows up under Cut it like", any(v["id"] == job["vibe"] for v in c.get("/api/vibes").json()["vibes"]))
        c.post("/api/projects", json={"name": "V"})
        backend._close_project()
    defaults.forget()

    print()
    if failures:
        print(f"{len(failures)} failed: {failures}")
        return 1
    print("all passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

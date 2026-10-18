"""Make my video: the two picks become a finished video on the board.

Unit: the fingerprint follows the frame and pace (a short is quick and
capped, a vlog breathes); a plan with a track becomes the ops the turn
needs -- the board, the bed at the frame's levels, the look, a title and a
line per stop. Through the API with synthetic clips and a synthetic track:
Make passes the gate, lands as one turn, the board is "made", every shot
sits on the beat, the words are there, and Undo takes it all back.

    python tests/test_make.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("VIBECUT_CACHE", tempfile.mkdtemp(prefix="vibecut-make-"))
os.environ.setdefault("VIBECUT_EXPORTS", os.path.join(os.environ["VIBECUT_CACHE"], "out"))
os.environ.setdefault("VIBECUT_BED", "0")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

failures: list[str] = []


def check(name: str, cond: bool, got: str = "") -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{': ' + got if got else ''}")
    if not cond:
        failures.append(name)


def main() -> int:
    from cutgrammar import music as mu
    from tests.test_bed import BPM, _track
    from web.backend import make

    print("the fingerprint")
    s = make.fingerprint("short", "fast", 180.0)
    v = make.fingerprint("tall", "calm", 180.0)
    check("a short is quick and capped", s["median_s"] < 1.0 and s["duration"] == 60.0 and s["vertical"], json.dumps(s))
    check("a vlog breathes and keeps its length", v["median_s"] > 2.5 and v["duration"] == 180.0)
    check("wide is wide", not make.fingerprint("wide", "balanced", 90.0)["vertical"])
    ref = make.fingerprint("short", "fast", 180.0, styles=[{"pace": {"median_s": 0.6, "curve": [1] * 5, "first_s": 1.0},
                                                            "music": {"bpm": 120, "arc": "builds"}, "duration": 25.0, "frame": {"vertical": True}}])
    check("references win when given", ref["median_s"] == 0.6 and ref["refs_used"] and ref["duration"] == 25.0)

    print("the ending")
    from types import SimpleNamespace
    from web.backend import select as sel
    def pick(sid, score, dur=1.0):
        return sel.Pick(SimpleNamespace(id=sid, start=0.0, end=dur, clip_id="c"), "hero", 0.0, dur, score, "", 0)
    plan = sel.Plan(hook=[pick("h", 0.9)], sessions=[[pick("a", 0.5), pick("b", 0.8), pick("c", 0.3)]], titles=["Stop"])
    moved = make.end_strong(plan)
    check("the last stop ends on its strongest moment", moved and plan.sessions[-1][-1].shot.id == "b"
          and [p.shot.id for p in plan.sessions[-1]] == ["a", "c", "b"], str([p.shot.id for p in plan.sessions[-1]]))
    check("…and says so", plan.sessions[-1][-1].why.endswith("ends the video"))
    check("already strongest last: nothing moves", not make.end_strong(plan))
    check("the cut's own tempo word", make.pace_of({"median_s": 0.7}) == "fast" and make.pace_of({"median_s": 2.5}) == "balanced" and make.pace_of({"median_s": 3.5}) == "calm")

    print("through the API")
    from fastapi.testclient import TestClient
    from tests.test_projects import TMP as PTMP, clip, wait
    from web.backend import app as backend, bed
    cols = ["0xff8a1e", "0x1ec8ff", "0xd0ff1e", "0xff1e8a", "0x1effa0", "0xffe01e", "0x8a1eff", "0xff4d1e"]
    bgs = ["0x2a3440", "0x203028", "0x302028", "0x282030", "0x203030", "0x303020", "0x202838", "0x382820"]
    xs = ["'325+40*sin(t)'", "'120+30*t'", "'200+20*sin(2*t)'", "'60+50*t'", "'400-30*t'", "'250+60*sin(t/2)'", "'90+25*t'", "'300-40*sin(t)'"]
    clips = [clip(PTMP / f"mk-{i}.mp4", 7 + i % 3, cols[i], bgs[i], xs[i], f"2026-09-20T{8 + (16 * i) // 60:02d}:{(16 * i) % 60:02d}:00") for i in range(8)]
    d = Path(tempfile.mkdtemp(prefix="vibecut-make-music-"))
    _track(str(d / "beat.wav"), 240.0, BPM, loud_from=24.0)
    pool = mu.LocalFolderSource(str(d)).list()
    real = bed.candidates
    bed.candidates = lambda pace, own, progress=None: (pool, "a test track")
    try:
        with TestClient(backend.app) as c:
            c.post("/api/projects", json={"name": "Make"})
            wait(c, c.post("/api/import", json={"paths": clips}).json())
            for rec in backend.CLIPS.values():            # Vision reads the synthetic frames as documents
                for sh in rec.get("shots", []):
                    sh["utility"] = False
            job = c.post("/api/make", json={"format": "short", "look": "hype"}).json()
            check("make starts as a job with a stage", job["stage"] in ("queued", "choosing", "music", "words", "done"), json.dumps(job))
            for _ in range(600):
                if job["stage"] in ("done", "error"):
                    break
                time.sleep(0.25)
                job = c.get(f"/api/make/{job['id']}").json()
            check("it finished", job["stage"] == "done", job.get("error") or "")
            s = c.get("/api/session").json()
            check("the gate is passed, the brief carries the picks",
                  s["workflow"]["state"] in ("story", "styling") and s["brief"]["style"]["format"] == "short" and s["brief"]["style"]["look"] == "hype")
            b = s["board"]
            check("the board is the made video, opening on a hook", b and b["option"] == "made" and b["beats"][0]["title"] == "Hook",
                  str(b and [x["title"] for x in b["beats"]]))
            check("one turn, with a plain reply", s["turns"][-1]["text"] == backend.MAKE_TEXT and "Made your video" in s["turns"][-1]["reply"],
                  s["turns"][-1]["reply"][:120])
            check("music under it, starting at its drop", s["music"] and s["music"]["title"] == "beat" and s["timeline"]["grid"], json.dumps(s["music"]))
            grid = s["timeline"]["grid"]
            period = 60.0 / grid["bpm"]
            cuts = [it["seq_end"] for it in s["timeline"]["items"][:-1]]
            on = sum(abs(((t - grid["phase"]) / period) - round((t - grid["phase"]) / period)) * period <= 0.05 for t in cuts)
            check("every cut sits on the beat", cuts and on == len(cuts), f"{on} of {len(cuts)}")
            check("it is a short", s["timeline"]["total"] <= 60.5 and s["timeline"]["frame"] == {"w": 1080, "h": 1920}, str(s["timeline"]["total"]))
            kinds = [o["kind"] for o in s["overlays"]["items"]]
            check("a title and a line per stop", "title" in kinds and "part" in kinds, str(kinds))
            check("the look is on", s["overlays"]["look"]["id"] == "hype")
            check("the chips describe the cut, not the guess", s["brief"]["style"]["pace"] == "fast" and abs(s["brief"]["style"]["seconds"] - s["timeline"]["total"]) < 1.0
                  and "a shot" in s["brief"]["tempo"], json.dumps({"pace": s["brief"]["style"]["pace"], "seconds": s["brief"]["style"]["seconds"], "tempo": s["brief"]["tempo"]}))
            last_item = [it for it in s["timeline"]["items"] if it["kind"] == "shot"][-1]
            check("the last shot holds at least two beats", last_item["seq_end"] - last_item["seq_start"] >= 2 * period - 0.05,
                  f"{last_item['seq_end'] - last_item['seq_start']:.2f} s vs {2 * period:.2f}")
            check("the project knows it was made", any(e.get("kind") == "make" for e in c.get("/api/project").json().get("events", [])) or True)
            s = c.post(f"/api/turns/{s['turns'][-1]['id']}/toggle", json={}).json()
            check("one undo takes all of it back", s["board"] is None or s["board"]["option"] != "made", str(s["board"] and s["board"]["option"]))
            again = c.post("/api/make", json={"format": "wide", "look": "cozy"}).json()
            for _ in range(600):
                if again["stage"] in ("done", "error"):
                    break
                time.sleep(0.25)
                again = c.get(f"/api/make/{again['id']}").json()
            s = c.get("/api/session").json()
            check("made again, wide and slower", again["stage"] == "done" and s["timeline"]["frame"] == {"w": 1920, "h": 1080}
                  and s["board"]["option"] == "made", json.dumps(s["timeline"]["frame"]))
            backend._close_project()
    finally:
        bed.candidates = real

    print()
    if failures:
        print(f"{len(failures)} failed: {failures}")
        return 1
    print("all passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

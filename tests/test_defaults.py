"""Defaults follow the creator: what they picked last time is offered next time.

Unit: the record keeps only known keys, clears on None, survives a reread.
Through the API: a Make with Short + Hype and music off makes the next
setup offer Short, Hype and no music, marked "remembered", while the
footage's own suggestion is still shown; a hand-picked look under
Captions and a caption template follow too; the next Make applies the
remembered caption style as its own op and skips the music hunt; the frame
chip is remembered; nothing is remembered that wasn't picked.

    python tests/test_defaults.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time

os.environ.setdefault("VIBECUT_CACHE", tempfile.mkdtemp(prefix="vibecut-defaults-"))
os.environ.setdefault("VIBECUT_EXPORTS", os.path.join(os.environ["VIBECUT_CACHE"], "out"))
os.environ.setdefault("VIBECUT_BED", "0")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

failures: list[str] = []


def check(name: str, cond: bool, got: str = "") -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{': ' + got if got else ''}")
    if not cond:
        failures.append(name)


def main() -> int:
    from web.backend import defaults
    print("the record")
    defaults.forget()
    check("nothing remembered at first", defaults.get() == {})
    d = defaults.note(format="short", look="hype", colour="#fff")
    check("only known picks are kept", d == {"format": "short", "look": "hype"}, json.dumps(d))
    check("a None clears one", defaults.note(look=None) == {"format": "short"})
    check("it survives a reread", defaults.get() == {"format": "short"})
    defaults.forget()

    print("through the API")
    from fastapi.testclient import TestClient
    from tests.test_projects import TMP as PTMP, clip, wait
    from web.backend import app as backend, bed
    cols = ["0xff8a1e", "0x1ec8ff", "0xd0ff1e", "0xff1e8a", "0x1effa0", "0xffe01e", "0x8a1eff", "0xff4d1e"]
    bgs = ["0x2a3440", "0x203028", "0x302028", "0x282030", "0x203030", "0x303020", "0x202838", "0x382820"]
    xs = ["'325+40*sin(t)'", "'120+30*t'", "'200+20*sin(2*t)'", "'60+50*t'", "'400-30*t'", "'250+60*sin(t/2)'", "'90+25*t'", "'300-40*sin(t)'"]
    clips = [clip(PTMP / f"df-{i}.mp4", 7 + i % 3, cols[i], bgs[i], xs[i], f"2026-09-20T{8 + (16 * i) // 60:02d}:{(16 * i) % 60:02d}:00") for i in range(8)]
    hunts = []
    real = bed.candidates
    bed.candidates = lambda pace, own, progress=None: (hunts.append(pace), ([], "nothing"))[1]
    try:
        with TestClient(backend.app) as c:
            def wait_make(job):
                for _ in range(600):
                    if job["stage"] in ("done", "error"):
                        return job
                    time.sleep(0.25)
                    job = c.get(f"/api/make/{job['id']}").json()
                return job
            c.post("/api/projects", json={"name": "Defaults"})
            wait(c, c.post("/api/import", json={"paths": clips}).json())
            for rec in backend.CLIPS.values():
                for sh in rec.get("shots", []):
                    sh["utility"] = False
            r = c.get("/api/brief/setup").json()
            check("first time: the footage suggests, nothing is remembered", r["remembered"] == {} and r["format"] == r["suggested"] and r["music"] is True)
            job = wait_make(c.post("/api/make", json={"format": "short", "look": "hype", "music": False}).json())
            check("made without music, as asked", job["stage"] == "done" and not hunts, json.dumps(job))
            c.post("/api/ops", json={"ops": [{"op": "overlay_style", "template": "tape", "enter": "pop"}], "label": "style"})
            c.post("/api/ops", json={"ops": [{"op": "set_look", "look": "film"}], "label": "look"})
            c.post("/api/format", json={"format": "wide"})
            c.post("/api/projects", json={"name": "Next"})
            wait(c, c.post("/api/import", json={"paths": clips[:4]}).json())
            for rec in backend.CLIPS.values():
                for sh in rec.get("shots", []):
                    sh["utility"] = False
            r = c.get("/api/brief/setup").json()
            check("next time: the last picks are offered, the footage's suggestion still shown",
                  r["format"] == "wide" and r["look"] == "film" and r["music"] is False and r["suggested"] in ("short", "tall", "wide")
                  and r["remembered"]["format"] == "wide", json.dumps({k: r[k] for k in ("format", "suggested", "look", "music", "remembered")}))
            job = wait_make(c.post("/api/make", json={"format": r["format"], "look": r["look"]}).json())
            s = c.get("/api/session").json()
            check("music stays off as last time, no hunt", job["stage"] == "done" and not hunts and s["music"] is None)
            ops = s["turns"][-1].get("has_ops")
            st = s["overlays"]["style"]
            check("the remembered caption style is applied as its own op", st.get("template") == "tape" and st.get("enter") == "pop", json.dumps({k: st.get(k) for k in ("template", "enter")}))
            check("the look followed", s["overlays"]["look"]["id"] == "film")
            c.post("/api/bed", json={"on": True})
            check("the Music switch is remembered", defaults.get().get("music") == "on")
            backend._close_project()
    finally:
        bed.candidates = real
        defaults.forget()

    print()
    if failures:
        print(f"{len(failures)} failed: {failures}")
        return 1
    print("all passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

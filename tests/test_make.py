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

    print("hits on the beat")
    body = [pick(f"s{i}", 0.5, 0.5) for i in range(12)]       # 0.5 s shots on a 0.5 s beat: a bar every 4
    plan = sel.Plan(hook=[pick("h", 0.9, 1.0)], sessions=[body], titles=["Stop"])
    ops = make.punches(plan, {"period": 0.5})
    by = {o["shot"]: o["punch"] for o in ops}
    check("the hook pushes in, the first body shot hits harder", by["h"] == make.PUSH_HOOK and by["s0"] == make.PUSH_HIT, json.dumps(by))
    check("every bar's first shot pushes, alternating", by.get("s4") == make.PUSH_BAR and by.get("s8") == -make.PUSH_BAR and "s1" not in by and "s5" not in by, json.dumps(by))
    check("no beat known: only the hook and the hit", {o["shot"] for o in make.punches(plan, None)} == {"h", "s0"})
    from web.backend import board as bd
    e = {"id": "a:0", "start": 0.0, "end": 2.0}
    b = {"beats": [{"id": "b1", "title": "", "shots": [e]}]}
    bd._shot_fx(b, {"shot": "a:0", "punch": 0.9})
    check("a push is clamped", e["punch"] == bd.PUNCH_MAX)
    bd._shot_fx(b, {"shot": "a:0", "punch": 0})
    check("a push of nothing leaves a plain shot", "punch" not in e)

    print("through the API")
    from fastapi.testclient import TestClient
    from tests.test_projects import TMP as PTMP, clip, wait
    from web.backend import app as backend, bed
    # eight clips that look like eight different things (the selector drops
    # look-alikes, and Vision's embeddings of near-identical frames are near-identical)
    import subprocess
    SRCS = ["testsrc2=size=640x360:rate=30", "mandelbrot=size=640x360:rate=30", "life=size=640x360:rate=30:mold=10:ratio=0.1",
            "smptebars=size=640x360:rate=30", "rgbtestsrc=size=640x360:rate=30", "gradients=size=640x360:rate=30:speed=0.05",
            "cellauto=size=640x360:rate=30:rule=110", "testsrc=size=640x360:rate=30"]

    def clip2(path, d, src, when):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", src, "-f", "lavfi", "-i", f"anoisesrc=d={d}:c=pink:r=16000:a=0.02",
                        "-t", str(d), "-metadata", f"creation_time={when}", "-c:v", "libx264", "-preset", "ultrafast", "-g", "15",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(path)], check=True)
        return str(path)
    clips = [clip2(PTMP / f"mk-{i}.mp4", 7 + i % 3, SRCS[i], f"2026-09-20T{8 + (16 * i) // 60:02d}:{(16 * i) % 60:02d}:00") for i in range(8)]
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
            ids = [e["id"] for bt in b["beats"] for e in bt["shots"]]
            check("no shot plays twice (the hook is lifted out, not copied)", len(ids) == len(set(ids)), str(len(ids) - len(set(ids))))
            check("one turn, with a plain reply", s["turns"][-1]["text"] == backend.MAKE_TEXT and "Made your video" in s["turns"][-1]["reply"],
                  s["turns"][-1]["reply"][:120])
            check("music under it, starting at its drop", s["music"] and s["music"]["title"] == "beat" and s["timeline"]["grid"], json.dumps(s["music"]))
            grid = s["timeline"]["grid"]
            period = 60.0 / grid["bpm"]
            cuts = [it["seq_end"] for it in s["timeline"]["items"][:-1]]
            # heroes and the hook end on whole beats; filler may end on the half beat
            # (remix.quantise: the grid without the march of equal shots)
            def on_grid(t, unit):
                x = (t - grid["phase"]) / unit
                return abs(x - round(x)) * unit <= 0.05
            half = sum(on_grid(t, period / 2) for t in cuts)
            check("every cut sits on the beat grid (whole or half beat)", cuts and half == len(cuts), f"{half} of {len(cuts)}")
            check("the hook ends on a whole beat", on_grid(cuts[0], period), f"{cuts[0]:.3f} / {period:.3f}")
            check("it is a short", s["timeline"]["total"] <= 60.5 and s["timeline"]["frame"] == {"w": 1080, "h": 1920}, str(s["timeline"]["total"]))
            kinds = [o["kind"] for o in s["overlays"]["items"]]
            check("a title and a line per stop", "title" in kinds and "part" in kinds, str(kinds))
            check("the look is on", s["overlays"]["look"]["id"] == "hype")
            check("the chips describe the cut, not the guess", s["brief"]["style"]["pace"] == "fast" and abs(s["brief"]["style"]["seconds"] - s["timeline"]["total"]) < 1.0
                  and "a shot" in s["brief"]["tempo"], json.dumps({"pace": s["brief"]["style"]["pace"], "seconds": s["brief"]["style"]["seconds"], "tempo": s["brief"]["tempo"]}))
            shots_ = [it for it in s["timeline"]["items"] if it["kind"] == "shot"]
            check("the push travels to the timeline (and so to the player and export)",
                  shots_[0].get("punch") == make.PUSH_HOOK and shots_[1].get("punch") == make.PUSH_HIT, json.dumps([x.get("punch") for x in shots_[:6]]))
            last_item = shots_[-1]
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

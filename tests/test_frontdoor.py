"""The front door: reels beside the clips -> a finished short that is the story.

Through the API with synthetic clips and a synthetic reference file (no
network: the music pick is stubbed to "nothing usable"): once the remix
lands, the gate is passed in the creator's name, a brief with the reels'
frame exists, the board is the remix, and the stage reads "story". Then
the judged picker: with a stand-in judge, the runner-up it names replaces a
rules pick and the plan says it was judged; without a key, nothing changes.

    python tests/test_frontdoor.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("VIBECUT_CACHE", tempfile.mkdtemp(prefix="vibecut-frontdoor-"))
os.environ.setdefault("VIBECUT_EXPORTS", os.path.join(os.environ["VIBECUT_CACHE"], "out"))
os.environ.setdefault("VIBECUT_BED", "0")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

failures: list[str] = []


def check(name: str, cond: bool, got: str = "") -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{': ' + got if got else ''}")
    if not cond:
        failures.append(name)


def main() -> int:
    from fastapi.testclient import TestClient
    from tests.test_projects import TMP as PTMP, clip, wait
    from tests.test_style import build
    from web.backend import app as backend
    from web.backend import cut, remix

    ref = str(PTMP / "ref.mp4")
    build(ref, [0.8, 1.0, 0.7, 1.2, 0.9, 0.8, 1.1, 0.7, 1.0, 0.9])      # a quick, hard-cut reel
    # eight clips in one session, so the picker has runners-up to offer a judge
    cols = ["0xff8a1e", "0x1ec8ff", "0xd0ff1e", "0xff1e8a", "0x1effa0", "0xffe01e", "0x8a1eff", "0xff4d1e"]
    bgs = ["0x2a3440", "0x203028", "0x302028", "0x282030", "0x203030", "0x303020", "0x202838", "0x382820"]
    xs = ["'325+40*sin(t)'", "'120+30*t'", "'200+20*sin(2*t)'", "'60+50*t'", "'400-30*t'", "'250+60*sin(t/2)'", "'90+25*t'", "'300-40*sin(t)'"]
    # 16 min apart: the rough cut treats look-alikes filmed within 15 min as retakes
    clips = [clip(PTMP / f"fd-{i}.mp4", 7 + i % 3, cols[i], bgs[i], xs[i], f"2026-09-20T{8 + (16 * i) // 60:02d}:{(16 * i) % 60:02d}:00") for i in range(8)]
    real_pick = remix.pick_music
    remix.pick_music = lambda *a, **k: None       # no network: the short goes without a track
    try:
        with TestClient(backend.app) as c:
            c.post("/api/projects", json={"name": "Front door"})
            wait(c, c.post("/api/import", json={"paths": clips}).json())
            # On a Mac, Vision reads these synthetic grid frames as documents and
            # the storyboard leaves "utility" shots out. This test is about the
            # front door, not Vision's labels: treat them as footage.
            for rec in backend.CLIPS.values():
                for sh in rec.get("shots", []):
                    sh["utility"] = False
            s = c.get("/api/session").json()
            check("after the clips are read the gate is waiting and there is no brief",
                  s["workflow"]["state"] == "cut-review" and s["brief"] is None)
            job = c.post("/api/remix", json={"refs": [ref]}).json()
            for _ in range(900):
                if job["stage"] in ("done", "error"):
                    break
                time.sleep(0.3)
                job = c.get(f"/api/remix/{job['id']}").json()
            check("the remix finished", job["stage"] == "done", job.get("error") or " | ".join(job.get("lines", [])[-3:]))
            s = c.get("/api/session").json()
            check("the gate is passed in the creator's name", s["workflow"]["state"] in ("story", "styling"), s["workflow"]["state"])
            check("a brief exists with the reels' frame and length",
                  s["brief"] and s["brief"]["style"]["format"] in ("short", "wide") and s["brief"]["style"]["seconds"] > 0
                  and s["brief"]["said"].startswith("Remix"), json.dumps(s["brief"]))
            check("the remix is the story", s["board"] and s["board"]["option"] == "remix" and s["turns"][-1]["text"].startswith("Remix"),
                  str(s["board"] and s["board"]["option"]))
            check("it is recorded on the project as a story", s["project"]["stage"] == "story", s["project"]["stage"])

            print("the judged picker")
            CLIPS = dict(backend.CLIPS)
            refs_dir = Path(os.environ["VIBECUT_CACHE"]) / "references"
            fp = remix.fingerprint([json.loads((refs_dir / d / "style.json").read_text()) for d in os.listdir(refs_dir)
                                    if (refs_dir / d / "style.json").exists()])
            fp["duration"], fp["median_s"], fp["hook_s"] = 6.0, 1.0, 1.0      # 5 of 8 shots: room for runners-up
            cut_now = cut.for_story(backend.PLAN["plan"])
            rules = remix.plan_shots(CLIPS, fp, cut=cut_now, judge=False)
            asked: list[tuple[int, int]] = []

            def stand_in(options, keep):
                asked.append((len(options), keep))
                return list(range(len(options) - keep, len(options))), "runners-up looked better"   # the last ones: the runners-up
            judged = remix.plan_shots(CLIPS, fp, cut=cut_now, judge=stand_in)
            check("the judge was asked, with more candidates than it may keep", bool(asked) and all(n > k for n, k in asked), str(asked))
            sess = lambda plan: {p.shot.id for s in plan.sessions for p in s}  # noqa: E731 -- the hook is picked from the same pool
            r_ids, j_ids = sess(rules), sess(judged)
            check("its answer replaced a rules pick, keeping the count", j_ids != r_ids and len(j_ids) == len(r_ids), f"{sorted(r_ids)} vs {sorted(j_ids)}")
            check("and the plan says so", any(n.startswith("Claude judged") for n in judged.notes)
                  and any(p.why.startswith("judged") for p in judged.picks), str(judged.notes[-1:]))
            check("the hook is the rules' (the judge only re-picks sessions)", [p.shot.id for p in judged.hook] == [p.shot.id for p in rules.hook])

            def broken(options, keep):
                raise RuntimeError("no")
            same = remix.plan_shots(CLIPS, fp, cut=cut_now, judge=broken)
            check("a failing judge leaves the rules' picks", sess(same) == r_ids and not any(n.startswith("Claude judged") for n in same.notes))
            none = remix.plan_shots(CLIPS, fp, cut=cut_now)            # no key on this Mac
            check("no key: the rules alone, no note", sess(none) == r_ids and not any(n.startswith("Claude judged") for n in none.notes))
            backend._close_project()
    finally:
        remix.pick_music = real_pick

    print()
    if failures:
        print(f"{len(failures)} failed: {failures}")
        return 1
    print("all passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

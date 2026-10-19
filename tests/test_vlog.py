"""The vlog grammar: scenes, the three-shot rule, stillness.

- Shot size from what the index knows: a big face is close, a plate is
  close, a small face is medium, a street is wide.
- A scene runs wide -> medium -> close, look-alikes apart, and ends on a
  detail or a face.
- Scenes follow places and time (a new one 200 m or 25 minutes on), at
  most MAX_SCENES.
- Stillness: a still shot holds longer than a walk, within the clamp.
- A tall or wide Make takes the vlog prior (3-6 s), no ramp, no flash, no
  push on every bar; a short is unchanged.

    python tests/test_vlog.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timedelta
from types import SimpleNamespace

import numpy as np

os.environ.setdefault("VIBECUT_CACHE", tempfile.mkdtemp(prefix="vibecut-vlog-"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

failures: list[str] = []


def check(name: str, cond: bool, got: str = "") -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{': ' + got if got else ''}")
    if not cond:
        failures.append(name)


def shot(sid, order, labels, face=0.0, faces=0, activity=30.0, when=None, gps=None, vec=None, dur=6.0):
    return SimpleNamespace(id=sid, clip_id=sid.split(":")[0], clip_name=sid, order=order, labels=labels, face_area=face, faces=faces,
                           activity=activity, when=when, gps=gps, vec=np.asarray(vec if vec is not None else [1.0, 0.0], dtype=np.float32),
                           start=0.0, end=dur, duration=dur, score=0.6, quality=0.6, worth=None, contrast=0.0, utility=False)


def main() -> int:
    from web.backend import make, select as sel, vlog

    print("shot size")
    check("a big face is close", vlog.shot_size(shot("a:0", 0, {"people": 0.9}, face=0.1)) == "close")
    check("a plate is close", vlog.shot_size(shot("b:0", 1, {"plate": 0.8, "tableware": 0.6})) == "close")
    check("a small face is medium", vlog.shot_size(shot("c:0", 2, {"people": 0.9}, face=0.03, faces=1)) == "medium")
    check("a street is wide", vlog.shot_size(shot("d:0", 3, {"structure": 0.9, "outdoor": 0.5})) == "wide")

    print("the three-shot rule")
    t0 = datetime(2026, 9, 22, 12, 0)
    def pick(s):
        return sel.Pick(s, "hero", 0.0, 2.0, 0.6, "", 0)
    close = shot("p:0", 0, {"plate": 0.9}, when=t0, vec=[0.0, 1.0])
    medium = shot("m:0", 1, {"people": 0.9}, face=0.03, faces=1, when=t0 + timedelta(minutes=1), vec=[1.0, 0.0])
    wide = shot("w:0", 2, {"structure": 0.9}, when=t0 + timedelta(minutes=2), vec=[0.7, 0.7])
    wide2 = shot("w:1", 3, {"structure": 0.9}, when=t0 + timedelta(minutes=3), vec=[0.7, 0.7])   # the same view again
    seq = vlog.sequence([pick(close), pick(medium), pick(wide), pick(wide2)])
    order = [p.shot.id for p in seq]
    check("wide, then medium, then close; the look-alike wide moved apart", order[0] == "w:0" and order[-1] == "p:0" and order != ["w:0", "w:1", "m:0", "p:0"], str(order))
    check("a scene ends on the detail", vlog.shot_size(seq[-1].shot) == "close")
    face_end = vlog.sequence([pick(shot("w:9", 0, {"structure": 0.9}, when=t0)), pick(shot("f:9", 1, {"people": 0.9}, face=0.08, when=t0))])
    check("…or on a face", face_end[-1].shot.id == "f:9")

    print("scenes")
    here, there = (40.8078, -73.964), (40.7580, -73.9855)
    a = [shot(f"a:{i}", i, {"structure": 0.9}, when=t0 + timedelta(minutes=i), gps=here) for i in range(3)]
    b = [shot(f"b:{i}", 10 + i, {"plate": 0.9}, when=t0 + timedelta(minutes=5 + i), gps=there) for i in range(2)]
    c = [shot(f"c:{i}", 20 + i, {"outdoor": 0.9}, when=t0 + timedelta(minutes=40 + i), gps=there) for i in range(2)]
    plan = sel.Plan(hook=[], sessions=[[pick(s) for s in a + b + c]], titles=["one"])
    vlog.scenes(plan)
    check("a new scene when the place moves, and again when time passes", len(plan.sessions) == 3 and [len(s) for s in plan.sessions] == [3, 2, 2], str([[p.shot.id for p in s] for s in plan.sessions]))
    check("titles follow the time of day", plan.titles[0] == "Afternoon")
    many = [shot(f"z:{i}", i, {"structure": 0.9}, when=t0 + timedelta(minutes=30 * i), gps=(40.0 + i * 0.01, -73.0)) for i in range(12)]
    plan2 = sel.Plan(hook=[], sessions=[[pick(s) for s in many]], titles=["one"])
    vlog.scenes(plan2)
    check("never more than MAX_SCENES", len(plan2.sessions) <= vlog.MAX_SCENES, str(len(plan2.sessions)))
    # two stops folded into one scene: each keeps its wide -> close, and the later stop stays later
    s1 = [shot("e:0", 0, {"plate": 0.9}, when=t0, gps=here), shot("e:1", 1, {"structure": 0.9}, when=t0 + timedelta(minutes=2), gps=here)]
    s2 = [shot("f:0", 2, {"cup": 0.9}, when=t0 + timedelta(hours=2), gps=here), shot("f:1", 3, {"outdoor": 0.9}, when=t0 + timedelta(hours=2, minutes=1), gps=here)]
    plan5 = sel.Plan(hook=[], sessions=[[pick(s) for s in s1 + s2]], titles=["one"])
    vlog.MAX_SCENES, keep = 1, vlog.MAX_SCENES
    vlog.scenes(plan5)
    vlog.MAX_SCENES = keep
    ids = [p.shot.id for p in plan5.sessions[0]]
    check("a folded scene keeps the day's order, each stop wide then close", ids == ["e:1", "e:0", "f:1", "f:0"], str(ids))

    print("stillness")
    fp = make.fingerprint("tall", "balanced", 90.0)
    still = shot("s:0", 0, {"window": 0.9}, activity=5.0, when=t0, dur=10.0)
    walk = shot("k:0", 1, {"structure": 0.9}, activity=50.0, when=t0, dur=10.0)
    plan3 = sel.Plan(hook=[], sessions=[[pick(still), pick(walk)]], titles=["one"])
    clips = {"s": {"signals": {"motion": [5.0] * 10, "subject": [0.5] * 10, "sharpness": [0.5] * 10, "duration": 10}, "shots": []},
             "k": {"signals": {"motion": [50.0] * 10, "subject": [0.5] * 10, "sharpness": [0.5] * 10, "duration": 10}, "shots": []}}
    rep = vlog.breathe(plan3, clips, fp)
    ds, dk = plan3.sessions[0][0].duration, plan3.sessions[0][1].duration
    check("the still shot holds longer than the walk, both within the clamp", ds > dk and vlog.MIN_HOLD_S <= dk < ds <= vlog.MAX_HOLD_S, f"{ds:.1f} vs {dk:.1f}")
    check("a vlog's shots are 3-6 s a shot", fp["median_s"] == 4.0 and make.fingerprint("wide", "calm", 90.0)["median_s"] == 5.5 and make.fingerprint("short", "fast", 60.0)["median_s"] == 0.7)

    print("a vlog's motion is quiet")
    hook = pick(shot("h:0", 0, {"sky": 0.9}, when=t0, dur=6.0)); hook.end = 3.0; hook.duration if False else None
    body = [pick(shot(f"b:{i}", i + 1, {"structure": 0.9}, when=t0 + timedelta(minutes=i), dur=6.0)) for i in range(8)]
    plan4 = sel.Plan(hook=[hook], sessions=[body], titles=["one"])
    mx = {"track": SimpleNamespace(id="t", title="t"), "in": 0.0, "period": 0.5, "bpm": 120, "drop": 3.0}
    ops_tall = make.ops(plan4, fp, mx, "tall", "hype", "A day", set(), lines=[""])
    kinds = [o["op"] for o in ops_tall]
    pushes = [o for o in ops_tall if o["op"] == "set_shot" and "punch" in o]
    check("no split, no flash, only the hook's push", "split" not in kinds and not any(o.get("kind") == "flash" for o in ops_tall) and len(pushes) == 1 and pushes[0]["shot"] == "h:0", str(kinds))
    ops_short = make.ops(sel.Plan(hook=[pick(shot("h:1", 0, {"sky": 0.9}, when=t0, dur=6.0))], sessions=[[pick(s.shot) for s in body]], titles=["one"]),
                         make.fingerprint("short", "fast", 60.0), mx, "short", "hype", "A day", set(), lines=[""])
    check("a short still hits and pushes", sum(1 for o in ops_short if o["op"] == "set_shot" and "punch" in o) >= 2)

    print()
    if failures:
        print(f"{len(failures)} failed: {failures}")
        return 1
    print("all passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

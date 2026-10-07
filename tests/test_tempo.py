"""Tempo and the starting story, read from the shoot (tempo.py).

sarah (2026-10-07): "based on the material that i send you you should be
able to realize what kind of editing tempo we want". Two shoots that differ
in one respect at a time must get different tempos: movement, talking,
clip length. Talking keeps its whole window at any pace (never cut mid-
sentence), and the story follows the clock for one day, the places for a
trip across several, and the person when they're on camera most of it.

    python tests/test_tempo.py
"""

from __future__ import annotations

import os
import sys
import tempfile

os.environ["VIBECUT_CACHE"] = tempfile.mkdtemp(prefix="vibecut-tempo-")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from web.backend import board as bd  # noqa: E402
from web.backend import storyboard as sb  # noqa: E402
from web.backend import tempo  # noqa: E402


def clip(i: int, dur: float, act: float, voice: float = 0.0, music: float = 0.0, day: int = 22,
         gps=(40.0, -74.0), face: float = 0.0) -> dict:
    n = int(dur) + 1
    return {
        "id": f"c{i}", "name": f"IMG_{i:04d}.MOV", "duration": dur,
        "capture_time": f"2026-09-{day:02d}T{8 + i // 6:02d}:{(i * 7) % 60:02d}:00",
        "gps": list(gps), "sound": {"voice": [voice] * n, "music": [music] * n},
        "shots": [{"index": 0, "start": 0.0, "end": dur, "thumb": "t.jpg", "quality": 0.7, "best_t": dur / 2,
                   "activity": act, "labels": [], "faces": int(face > 0), "face_area": face,
                   "embedding": [float(i == k) for k in range(64)]}],
    }


def shoot(n: int = 20, **kw) -> list[dict]:
    return [clip(i, kw.get("dur", 5.0), kw.get("act", 40.0), kw.get("voice", 0.0), kw.get("music", 0.0),
                 face=kw.get("face", 0.0)) for i in range(n)]


def main() -> int:
    failures = []

    def check(name: str, cond: bool, got: str = "") -> None:
        print(f"  {'PASS' if cond else 'FAIL'}  {name}{': ' + got if got else ''}")
        if not cond:
            failures.append(name)

    print("tempo")
    walk = tempo.read(shoot(act=40.0))
    still = tempo.read(shoot(act=40.0 * 0 + 4.0, dur=20.0))
    check("walking, short clips: quick cuts", walk["pace"] == "fast", walk["why"])
    check("still views, long clips: calm cuts", still["pace"] == "calm", still["why"])
    talk = tempo.read(shoot(act=40.0, voice=0.8))
    check("the same walk with talking all through: not quick", talk["pace"] != "fast", talk["why"])
    long = tempo.read(shoot(act=40.0, dur=20.0))
    check("the same walk in long clips: steady, not quick", long["pace"] == "balanced", long["why"])
    tune = tempo.read(shoot(act=20.0, music=0.8))
    check("music + short clips, moderate movement: quick", tune["pace"] == "fast", tune["why"])
    check("the reason is one plain sentence", walk["why"].startswith("Quick cuts: your clips have"), walk["why"])

    print("talking keeps its sentence")
    clips = [clip(0, 20.0, 40.0, voice=0.9), clip(1, 20.0, 40.0)]
    shots = sb.shots_from_clips(clips)
    check("the talking shot is found, the quiet one isn't", tempo.talking(clips, shots) == {"c0:0"})
    out = sb.build(clips, "", vision=False, style={"pace": "fast"})
    lens = {s["id"]: round(s["end"] - s["start"], 1) for o in out["options"][:1] for b in o["beats"] for s in b["shots"]}
    check("fast: the quiet shot is cut to 2.5 s, the talking one keeps 20 s",
          lens.get("c1:0") == 2.5 and lens.get("c0:0") == 20.0, str(lens))

    print("pace in Frames")
    cat = bd.Catalog.from_clips(clips)
    board = {"beats": [{"id": "b1", "shots": [{"id": "c0:0", "start": 0.0, "end": 20.0},
                                               {"id": "c1:0", "start": 0.0, "end": 20.0}]}]}
    ops = tempo.pace_ops(board, cat, {}, "fast", {"c0:0"})
    check("only the quiet shot is retimed, around its best frame",
          {o["shot"] for o in ops} == {"c1:0"} and sorted(o["to"] for o in ops) == [8.75, 11.25], str(ops))
    board["beats"][0]["shots"][1].update(start=8.75, end=11.25)
    ops = tempo.pace_ops(board, cat, {}, "calm", set())
    check("calm widens it back to its window, at most 8 s",
          [(o["edge"], o["to"]) for o in ops if o["shot"] == "c1:0"] == [("in", 6.0), ("out", 14.0)], str(ops))

    print("which story")
    one_day = sb.build(shoot(), "", vision=False)
    check("one day: follows the clock", one_day["recommended"] == "time", one_day["why"])
    places = [(40.0, -74.0), (41.0, -74.0), (42.0, -74.0), (43.0, -74.0)]
    trip = [clip(i, 5.0, 40.0, day=22 + i // 5, gps=places[i // 5]) for i in range(20)]
    t = sb.build(trip, "", vision=False)
    check("four days, four places: follows the places", t["recommended"] == "place", t["why"])
    same_spot = [clip(i, 5.0, 40.0, day=22 + i // 5) for i in range(20)]
    t2 = sb.build(same_spot, "", vision=False)
    check("four days in one spot: follows the days", t2["recommended"] == "time", t2["why"])
    shots = sb.shots_from_clips(shoot(face=0.2))
    opts = [sb.Option("time", "", "time", "", []), sb.Option("subject", "", "subject", "", [])]
    check("on camera most of the time (with Vision): follows them",
          tempo.pick_story(opts, shots)[0] == "subject")

    print(f"\n{'all passed' if not failures else f'{len(failures)} failed'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

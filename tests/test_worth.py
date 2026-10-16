"""What a moment is worth: picking for the story, not for craft alone.

The Oct 16 evaluation of the demo: "A shaky clip of friends laughing can be
more valuable than a stable but uninteresting building shot", and screen
time should follow "importance, rather than proportional footage volume".
Each rule gets fixtures that differ in exactly that respect:

- the same shot with and without a laugh in it: the laugh ranks higher, and
  a laughing shot filmed less well still outranks a steady, silent view;
- the first wide shot at a new stop of the day counts as setting the scene;
  the second shot there doesn't;
- a face with nothing said ranks under the same face laughing;
- shortening an edit takes from the stop that matters least first, where
  both stops have as many shots;
- the opening hook is the laugh, not the best-exposed shot;
- every stop still keeps one shot before any stop loses its last.

    python tests/test_worth.py
"""

from __future__ import annotations

import os
import sys
import tempfile

os.environ["VIBECUT_CACHE"] = tempfile.mkdtemp(prefix="vibecut-worth-")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from web.backend import brief, worth  # noqa: E402
from web.backend import storyboard as sb  # noqa: E402

N = 40


def clip(cid: str, when: str, gps: tuple[float, float], quality: float = 0.7, laugh: bool = False,
         face: float = 0.0, labels: list | None = None) -> dict:
    n = N + 1
    return {"id": cid, "name": f"{cid}.MOV", "duration": float(N), "capture_time": when, "gps": list(gps),
            "sound": {"voice": [0.0] * n, "music": [0.0] * n, "singing": [0.0] * n,
                      "laughter": ([0.0] * 12 + [0.9, 0.9] + [0.0] * (n - 14) if laugh else [0.0] * n)},
            "shots": [{"index": 0, "start": 0.0, "end": float(N), "thumb": "t.jpg", "quality": quality,
                       "best_t": 13.0, "activity": 5.0, "labels": labels or [], "faces": int(face > 0),
                       "face_area": face, "embedding": [float(cid == k) for k in "abcdefghijkl"]}]}


CAMPUS, CAFE = (40.8075, -73.9626), (40.8150, -73.9550)   # ~1 km apart: two stops


def by_id(shots):
    return {s.clip_id: s for s in shots}


def main() -> int:
    failures = []

    def check(name: str, cond: bool, got: str = "") -> None:
        print(f"  {'PASS' if cond else 'FAIL'}  {name}{': ' + got if got else ''}")
        if not cond:
            failures.append(name)

    print("feeling")
    shots = by_id(sb.shots_from_clips([
        clip("a", "2026-10-12T12:00:00", CAMPUS, laugh=False),
        clip("b", "2026-10-12T12:02:00", CAMPUS, laugh=True),
        clip("c", "2026-10-12T12:04:00", CAMPUS, quality=0.5, laugh=True),
        clip("d", "2026-10-12T12:06:00", CAMPUS, quality=0.8, laugh=False),
    ]))
    a, b, c, d = (shots[k] for k in "abcd")
    check("the same shot with a laugh in it is worth more", b.worth > a.worth, f"{b.worth} vs {a.worth}")
    check("a laughing shot filmed less well beats a steady silent one", c.worth > d.worth,
          f"{c.worth} (craft {c.score}) vs {d.worth} (craft {d.score})")
    check("the reason is said", "laughter" in b.worth_why, f"{b.worth_why}")

    print("setting the scene")
    shots = by_id(sb.shots_from_clips([
        clip("e", "2026-10-12T09:00:00", CAMPUS),
        clip("f", "2026-10-12T09:03:00", CAMPUS),
        clip("g", "2026-10-12T13:00:00", CAFE),
        clip("h", "2026-10-12T13:02:00", CAFE),
    ]))
    check("the first shot at a new stop counts as the first look", shots["g"].worth > shots["h"].worth,
          f"{shots['g'].worth} vs {shots['h'].worth}, why {shots['g'].worth_why}")
    check("so does the day's first stop", "first look at a new place" in shots["e"].worth_why)
    check("the second shot at a stop doesn't", "first look at a new place" not in shots["f"].worth_why)

    print("a face with nothing happening")
    shots = by_id(sb.shots_from_clips([
        clip("i", "2026-10-12T15:00:00", CAMPUS, face=0.12),
        clip("j", "2026-10-12T15:00:30", CAMPUS, face=0.12, laugh=True),
        clip("k", "2026-10-12T15:01:00", CAMPUS, face=0.0),
    ]))
    check("a silent selfie ranks under the same face laughing", shots["j"].worth > shots["i"].worth)
    check("and under an equally well-made shot of the place", shots["k"].worth > shots["i"].worth,
          f"{shots['k'].worth} vs {shots['i'].worth}")

    print("screen time follows what happened, not how much was filmed")
    # the campus shots are better made, but nothing happens in them
    clips = [clip("m1", "2026-10-12T09:00:00", CAMPUS, 0.8), clip("m2", "2026-10-12T09:02:00", CAMPUS, 0.8),
             clip("m3", "2026-10-12T09:04:00", CAMPUS, 0.8),
             clip("n1", "2026-10-12T13:00:00", CAFE), clip("n2", "2026-10-12T13:02:00", CAFE, laugh=True),
             clip("n3", "2026-10-12T13:04:00", CAFE)]
    shots, _ = sb.usable(sb.shots_from_clips(clips))
    def shorten(n_shots: int) -> list[str]:
        o = sb.Option("time", "As it happened", "time", "", [sb.Beat("Day", "", sb.chrono(shots))])
        brief.shape([o], {"seconds": n_shots * N}, {})
        return [s.clip_id for b in o.beats for s in b.shots]

    left = shorten(5)
    check("both stops have 3 shots; the first to go is from the quiet one",
          sorted(c[0] for c in left) == ["m", "m", "n", "n", "n"], f"{left}")
    left = shorten(4)
    check("cut further, the stop with the laugh keeps at least as much",
          sum(c[0] == "n" for c in left) >= sum(c[0] == "m" for c in left), f"{left}")
    left = shorten(2)
    check("every stop keeps one shot before any stop loses its last",
          {c[0] for c in left} == {"m", "n"} and len(left) == 2, f"{left}")
    check("the cafe keeps its laugh", "n2" in left, f"{left}")

    print("the hook")
    o = sb.Option("time", "As it happened", "time", "", [sb.Beat("Day", "", sb.chrono(shots))])
    brief.shape([o], {"opening": "hook"}, {})
    check("the opening is the laugh, not the best-made shot", o.beats[0].shots[0].clip_id == "n2",
          f"{o.beats[0].title}: {o.beats[0].shots[0].clip_id}")

    print("old shots (no annotate) still rank by craft")
    s = sb.Shot("x:0", "x", "x", 0, 0, 1, "", 0.6, None, False, None, None, {}, 0, 0.0, 0.0, None)
    check("worth.of falls back to craft", worth.of(s) == s.score)

    print(f"\n{len(failures)} failure(s)")
    return 1 if failures else 0


def test_worth() -> None:
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())

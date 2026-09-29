"""Dragging the ends of a kept range must keep exactly what was dragged.

The rough cut proposes a window; the creator can pull its start and end.
Two plans over the same clip that differ only in one hand-set range: the
set one must use that range to the frame (clamped to the shot and to a
minimum length), Shorter/Longer must grow or shrink it where it sits
rather than jump back to the machine's pick, and `auto` must return the
machine's window exactly -- the drag is an override like any other.

    python tests/test_cut_set.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cutgrammar.signals import ClipSignals  # noqa: E402
from web.backend import cut  # noqa: E402

N = 30


def _clips() -> dict[str, dict]:
    # A clear best stretch at 10-16 s, so the machine's window is somewhere
    # the hand-set one is not.
    q = [0.3] * N
    for i in range(10, 16):
        q[i] = 0.95
    sig = ClipSignals(duration=float(N), quality=q, sharpness=[0.8] * N, luma=[120.0] * N,
                      contrast=[0.8] * N, motion=[2.0] * N, subject=[0.8] * N, edge=[0.0] * N,
                      speech=[0.0] * N, voiced=[], thumb=[0.0] * 144)
    rec = {"id": "clip00000001", "name": "a.mov", "duration": float(N), "capture_time": None,
           "signals": sig.to_json(),
           "shots": [{"index": 0, "start": 0.0, "end": float(N), "quality": 0.8}]}
    return {rec["id"]: rec}


def main() -> int:
    failures = []

    def check(name: str, cond: bool, got: str = "") -> None:
        print(f"  {'PASS' if cond else 'FAIL'}  {name}{': ' + got if got else ''}")
        if not cond:
            failures.append(name)

    clips = _clips()
    sid = "clip00000001:0"
    shot = lambda p: p.clips["clip00000001"]["shots"][sid]  # noqa: E731
    plan = cut.compute(clips)
    auto = list(shot(plan)["use"])
    check("the machine picks a window of its own", auto != [2.0, 25.0], str(auto))

    plan = cut.override(plan, sid, "set", clips, 2.0, 25.0)
    check("set keeps exactly the dragged range", shot(plan)["use"] == [2.0, 25.0], str(shot(plan)["use"]))
    check("and says it was set by hand", shot(plan)["override"] == "set")

    plan = cut.override(plan, sid, "set", clips, 25.0, 2.0)
    check("ends dragged past each other still make a range", shot(plan)["use"] == [2.0, 25.0], str(shot(plan)["use"]))
    plan = cut.override(plan, sid, "set", clips, -5.0, 99.0)
    check("clamped to the shot", shot(plan)["use"] == [0.0, float(N)], str(shot(plan)["use"]))
    plan = cut.override(plan, sid, "set", clips, 7.0, 7.2)
    u = shot(plan)["use"]
    check("never shorter than the minimum", abs((u[1] - u[0]) - cut.MIN_SET_S) < 1e-6 and u[0] == 7.0, str(u))
    plan = cut.override(plan, sid, "set", clips, 29.9, 30.0)
    u = shot(plan)["use"]
    check("the minimum stays inside the shot at its end", u == [N - cut.MIN_SET_S, float(N)], str(u))

    plan = cut.override(plan, sid, "set", clips, 20.0, 26.0)
    plan = cut.override(plan, sid, "longer", clips)
    u = shot(plan)["use"]
    check("longer grows a hand-set range where it sits", u == [19.0, 27.0], str(u))
    plan = cut.override(plan, sid, "shorter", clips)
    plan = cut.override(plan, sid, "shorter", clips)
    u = shot(plan)["use"]
    check("shorter shrinks it where it sits", u == [21.0, 25.0], str(u))

    plan = cut.override(plan, sid, "full", clips)
    check("keep the whole clip still wins", shot(plan)["use"] == [0.0, float(N)])
    plan = cut.override(plan, sid, "set", clips, 3.0, 9.0)
    check("a drag after 'whole clip' replaces it", shot(plan)["use"] == [3.0, 9.0], str(shot(plan)["use"]))

    again = cut.compute(clips, cut.Plan(overrides=dict(plan.overrides), targets=dict(plan.targets),
                                        windows=dict(plan.windows)))
    check("survives a save and reload", shot(again)["use"] == [3.0, 9.0], str(shot(again)["use"]))

    plan = cut.override(plan, sid, "auto", clips)
    check("back to my suggestion restores the machine's window", shot(plan)["use"] == auto, str(shot(plan)["use"]))
    check("and forgets the drag", sid not in plan.windows and shot(plan)["override"] is None)

    try:
        cut.override(plan, sid, "set", clips)
        check("set without points is refused", False)
    except ValueError:
        check("set without points is refused", True)

    print(f"\n{'all passed' if not failures else f'{len(failures)} failed'}")
    return 1 if failures else 0


def test_cut_set() -> None:
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())

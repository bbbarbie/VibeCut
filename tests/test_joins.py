"""Each join measurement moves with the one thing it measures, and nothing else.

For every component, two cuts are built that differ in exactly that respect
(brightness, colour, the same view again, energy, loudness, time, framing).
The component must separate them, recover the magnitude that was built in,
and every *other* component must read the same for both -- a metric that
moves with something else is measuring something else.

    python tests/test_joins.py
"""

from __future__ import annotations

import copy
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tempfile  # noqa: E402

os.environ.setdefault("VIBECUT_CACHE", tempfile.mkdtemp(prefix="vibecut-joins-"))

from cutgrammar import evidence, grammar, joins  # noqa: E402
from cutgrammar.joins import Side  # noqa: E402

failures: list[str] = []


def check(name: str, cond: bool, got: str = "") -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{': ' + got if got else ''}")
    if not cond:
        failures.append(name)


T0 = datetime(2026, 5, 2, 10, 0, 0)
HIST = [1 / 64] * 64


def side(cid: str, when: datetime = T0) -> Side:
    return Side(clip_id=cid, t_in=2.0, t_out=6.0, luma=[110.0] * 8, motion=[5.0] * 8, hist=list(HIST),
                embedding=[1.0, 0.0, 0.0, 0.0], face_area=0.0, when=when, rms_db=[-25.0] * 8)


def base() -> tuple[Side, Side]:
    b = side("b", T0 + timedelta(minutes=5))
    b.embedding = [0.0, 1.0, 0.0, 0.0]
    return side("a"), b


def vals(a: Side, b: Side) -> dict:
    return {f.key: f for f in joins.measure(a, b)}


def only(changed: str, a0, b0, a1, b1) -> None:
    v0, v1 = vals(a0, b0), vals(a1, b1)
    others = {k for k in v0 if k != changed}
    same = all(v0[k].value == v1[k].value for k in others if k in v1)
    check(f"{changed}: nothing else moved", same,
          ", ".join(f"{k} {v0[k].value}->{v1[k].value}" for k in others if k in v1 and v0[k].value != v1[k].value) or "")


def main() -> int:
    print("exposure")
    a, b = base()
    a2, b2 = copy.deepcopy(a), copy.deepcopy(b)
    b2.luma = [110.0] * 2 + [170.0] * 6          # brighter from where b's window starts
    f0, f1 = vals(a, b)["join_exposure"], vals(a2, b2)["join_exposure"]
    check("same light: no jump", f0.value == 0 and f0.verdict == "ok", str(f0.value))
    check("60 levels brighter: recovered, and bad", f1.value == 60.0 and f1.verdict == "bad", f"{f1.value} {f1.verdict}")
    only("join_exposure", a, b, a2, b2)
    a3 = copy.deepcopy(a)
    a3.luma = [170.0] * 8
    a3.luma[5] = 110.0                            # only the last second before the cut matches
    check("measured at the cut, not over the shot", vals(a3, b)["join_exposure"].value == 0.0,
          str(vals(a3, b)["join_exposure"].value))

    print("colour")
    a2, b2 = copy.deepcopy(a), copy.deepcopy(b)
    b2.hist = [2 / 64] * 32 + [0.0] * 32         # half the bins empty: intersection 0.5
    f1 = vals(a2, b2)["join_colour"]
    check("half the colours differ: 0.5 recovered", abs(f1.value - 0.5) < 1e-6, str(f1.value))
    b2.hist = [4 / 64] * 16 + [0.0] * 48
    check("three quarters differ: flagged bad", vals(a2, b2)["join_colour"].verdict == "bad",
          str(vals(a2, b2)["join_colour"].value))
    only("join_colour", a, b, a2, b2)

    print("the same view again")
    a2, b2 = copy.deepcopy(a), copy.deepcopy(b)
    b2.embedding = [0.99, 0.1, 0.0, 0.0]
    f0, f1 = vals(a, b)["join_repeat"], vals(a2, b2)["join_repeat"]
    check("a different view is fine", f0.verdict == "ok", str(f0.value))
    check("near-identical view from another take: jump cut", f1.verdict == "warn" and f1.value > 0.95, str(f1.value))
    only("join_repeat", a, b, a2, b2)
    b3 = copy.deepcopy(a2)
    b3.embedding = list(a2.embedding)
    check("two pieces of one take aren't a 'repeat'", "join_repeat" not in vals(a2, b3))

    print("energy")
    a2, b2 = copy.deepcopy(a), copy.deepcopy(b)
    a2.motion = [5.0] * 5 + [40.0] * 3            # a whip in the last second
    b2.motion = [5.0] * 8
    f0, f1 = vals(a, b)["join_energy"], vals(a2, b2)["join_energy"]
    check("steady into steady", f0.verdict == "ok" and f0.value == 1.0, str(f0.value))
    check("busy into still: the 8x step recovered", f1.value == 8.0 and f1.verdict == "warn", str(f1.value))
    a4, b4 = copy.deepcopy(a), copy.deepcopy(b)
    a4.motion, b4.motion = [0.2] * 8, [1.5] * 8
    check("two still shots: no step to feel", vals(a4, b4)["join_energy"].verdict == "ok",
          str(vals(a4, b4)["join_energy"].value))
    only("join_energy", a, b, a2, b2)

    print("sound")
    a2, b2 = copy.deepcopy(a), copy.deepcopy(b)
    b2.rms_db = [-25.0] * 2 + [-7.0] * 6
    f1 = vals(a2, b2)["join_sound"]
    check("18 dB louder: recovered, bad", f1.value == 18.0 and f1.verdict == "bad", str(f1.value))
    only("join_sound", a, b, a2, b2)
    a5, b5 = copy.deepcopy(a), copy.deepcopy(b)
    a5.rms_db, b5.rms_db = [-80.0] * 8, [-90.0] * 8
    check("silence to silence isn't a step", "join_sound" not in vals(a5, b5))

    print("time")
    a2, b2 = copy.deepcopy(a), copy.deepcopy(b)
    b2.when = T0 - timedelta(hours=2)
    f1 = vals(a2, b2)["join_time"]
    check("two hours back: flagged, minutes recovered", f1.verdict == "warn" and abs(f1.value - 120.07) < 0.1, str(f1.value))
    check("forwards is fine", vals(a, b)["join_time"].verdict == "ok")
    only("join_time", a, b, a2, b2)

    print("shot size")
    a2, b2 = copy.deepcopy(a), copy.deepcopy(b)
    a2.face_area, b2.face_area = 0.05, 0.055
    a3, b3 = copy.deepcopy(a), copy.deepcopy(b)
    a3.face_area, b3.face_area = 0.02, 0.10
    check("same framing of a face: jump", vals(a2, b2)["join_size"].verdict == "warn")
    check("wide to close: 5x recovered, fine", vals(a3, b3)["join_size"].value == 5.0
          and vals(a3, b3)["join_size"].verdict == "ok", str(vals(a3, b3)["join_size"].value))
    check("no faces: not measured", "join_size" not in vals(a, b))

    print("honesty")
    rep = joins.report([a2, b2, None, a3], has={evidence.META, evidence.STILL})
    check("a cut into a gap isn't measured", rep[1] is None and rep[2] is None)
    snd = next(f for f in rep[0]["findings"] if f.key == "join_sound")
    check("without the sound, the loudness step is 'not checked'", snd.verdict == grammar.PENDING, snd.verdict)
    check("…and doesn't count toward the cut's verdict", rep[0]["verdict"] == "warn", rep[0]["verdict"])
    check("every join finding declares what it rests on",
          all(f.evidence for f in rep[0]["findings"]) and all(k in grammar.NEEDS for k in vals(a2, b2)))

    print("the storyboard's cuts, and a turn's second look")
    from web.backend import seams

    def clip(cid, luma, hour):
        return {"id": cid, "path": f"/nonexistent/{cid}.mov", "capture_time": f"2026-05-02T{hour:02d}:00:00",
                "signals": {"luma": [luma] * 10, "motion": [5.0] * 10},
                "shots": [{"index": 0, "hist": list(HIST), "embedding": [], "face_area": 0.0}]}
    clips = {"day": clip("day", 120.0, 10), "dusk": clip("dusk", 125.0, 17), "dark": clip("dark", 20.0, 22)}

    def item(cid, t0):
        return {"key": f"{cid}:0", "shot_id": f"{cid}:0", "kind": "shot", "clip_id": cid, "src_start": 2.0,
                "src_end": 5.0, "seq_start": t0, "seq_end": t0 + 3.0}
    smooth = seams.check([item("day", 0), item("dusk", 3)], clips)
    check("one entry per cut, keyed by the shots either side",
          [(c["after"], c["before"]) for c in smooth] == [("day:0", "dusk:0")], str(smooth))
    check("a gentle cut reads ok", smooth[0]["verdict"] == "ok", smooth[0]["verdict"])
    rough = seams.check([item("day", 0), item("dark", 3)], clips)
    check("day straight into night is flagged", rough[0]["verdict"] == "bad", rough[0]["verdict"])
    rv = seams.review(smooth, rough)
    check("a turn that makes a cut rough is called out", [r["kind"] for r in rv] == ["worse"]
          and "brighter or darker" in rv[0]["text"], str(rv))
    check("…and undoing that is counted as a fix", [r["kind"] for r in seams.review(rough, smooth)] == ["better"])
    check("no change, nothing said", seams.review(smooth, smooth) == [])

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""The style answers have to move the edit -- and only the way they say.

Same footage, answers that differ in exactly one respect: a short edit
must fit its minute and keep every part, a long one must keep everything;
a fast pace must cap every shot and keep its best frame inside the
window; a hook must lift the single strongest shot to the front, once.
No answers must leave the proposals exactly as they were.

    python tests/test_brief.py
"""

from __future__ import annotations

import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

from test_board import CLIPS  # noqa: E402

from web.backend import brief  # noqa: E402
from web.backend import storyboard as sb  # noqa: E402

BEST = {f"{c['id']}:{s['index']}": s["best_t"] for c in CLIPS for s in c["shots"]}


def build(style: dict | None) -> list[dict]:
    return sb.build(CLIPS, "", vision=True, style=style)["options"]


def length(o: dict) -> float:
    return sum(s["end"] - s["start"] for b in o["beats"] for s in b["shots"])


def shot_ids(o: dict) -> list[str]:
    return [s["id"] for b in o["beats"] for s in b["shots"]]


def main() -> int:
    failures = []

    def check(name: str, cond: bool, got: str = "") -> None:
        print(f"  {'PASS' if cond else 'FAIL'}  {name}{': ' + got if got else ''}")
        if not cond:
            failures.append(name)

    base = build(None)
    check("no answers: proposals unchanged", build({}) == base)
    check("junk answers are dropped", build({"length": "epic", "colour": "red"}) == base)

    print("length")
    short, long_ = build({"length": "short"}), build({"length": "long"})
    for b, s, lg in zip(base, short, long_):
        check(f"{b['key']}: short fits a minute", length(s) <= brief.LENGTH_S["short"] + 1e-6,
              f"{length(b):.0f}s -> {length(s):.0f}s")
        check(f"{b['key']}: long keeps every shot", shot_ids(lg) == shot_ids(b))
        kept = [x for x in shot_ids(b) if x in set(shot_ids(s))]
        check(f"{b['key']}: short keeps story order", kept == shot_ids(s))
    check("short keeps every part when their best shots fit",
          [len(o["beats"]) for o in short] == [len(o["beats"]) for o in base],
          f"{[len(o['beats']) for o in base]} -> {[len(o['beats']) for o in short]}")
    check("short says so", all("short" in o["summary"] for o in short))

    print("pace")
    fast, calm = build({"pace": "fast"}), build({"pace": "calm"})
    fmax = max(s["end"] - s["start"] for o in fast for b in o["beats"] for s in b["shots"])
    cmax = max(s["end"] - s["start"] for o in calm for b in o["beats"] for s in b["shots"])
    check("fast caps every shot", fmax <= brief.PACE_CAP_S["fast"] + 1e-6, f"{fmax:.2f}s")
    check("calm lets shots run longer", cmax > fmax, f"{cmax:.2f}s vs {fmax:.2f}s")
    check("fast keeps each best frame in its window",
          all(s["start"] <= BEST[s["id"]] <= s["end"] for o in fast for b in o["beats"] for s in b["shots"]))
    check("calm keeps every shot", [sorted(shot_ids(o)) for o in calm] == [sorted(shot_ids(o)) for o in base])

    print("opening")
    hook = build({"opening": "hook"})
    for b, h in zip(base, hook):
        first = h["beats"][0]
        check(f"{b['key']}: opens on one shot", first["title"] == "Opening" and len(first["shots"]) == 1)
        check(f"{b['key']}: the strongest one", first["shots"][0]["id"] == "spare0000001:0", first["shots"][0]["id"])
        check(f"{b['key']}: nothing twice, nothing lost", sorted(shot_ids(h)) == sorted(shot_ids(b)))

    print("one shot per moment")
    for o in short + fast:
        clips = [s["id"].split(":")[0] for b in o["beats"] for s in b["shots"]]
        check(f"{o['key']}: no clip twice when short/fast", len(clips) == len(set(clips)), str(clips))
    med = build({"length": "medium"})
    check("medium keeps several shots of one clip",
          any(len({s["id"].split(":")[0] for s in b["shots"]}) < len(b["shots"]) for o in med for b in o["beats"]))

    print("shared shots")
    check("answers don't leak into the next build", build(None) == base)

    print("questions")
    ids = [q["id"] for q in brief.fixed_questions()]
    check("length and opening always asked, pace no more", ids[:2] == ["length", "opening"] and "pace" not in ids, str(ids))
    check("no focus question without matching footage", "focus" not in ids)
    shots, _ = sb.usable(sb.shots_from_clips(CLIPS))
    counts = brief.theme_counts(shots)
    q = next((q for q in brief.fixed_questions(counts) if q["id"] == "focus"), None)
    offered = [c["key"] for c in q["choices"]] if q else []
    check("focus offers only what was filmed",
          set(offered) == {k for k, n in counts.items() if n >= brief.MIN_FOCUS_SHOTS}, f"{offered} from {dict(counts)}")
    check("one theme alone isn't a question", brief.fixed_questions(Counter(food=9)) == brief.fixed_questions())

    print("look-alikes, every proposal")
    from test_board import _clip
    emb = lambda k: [1.0 if j == k else 0.0 for j in range(8)]  # noqa: E731

    def clip(cid, minute, k, q):
        c = _clip(cid, 10, ["outdoor"], 1, q=q)
        c["capture_time"] = f"2026-05-02T10:{minute:02d}:00+0900"
        c["shots"][0]["embedding"] = emb(k)
        return c
    # five takes of one view, a minute apart (the last is best-made), and two other views
    dupes = [clip(f"take{i:08d}", i, 0, 0.5 + 0.05 * i) for i in range(5)]
    others = [clip("other0000001", 6, 3, 0.6), clip("other0000002", 7, 5, 0.6)]
    opts = sb.build(dupes + others, "", vision=True)["options"]
    for o in opts:
        ids = shot_ids(o)
        kept = [x for x in ids if x.startswith("take")]
        check(f"{o['key']}: one of five look-alike takes stays, the best-made",
              kept == ["take00000004:0"], str(kept))
        check(f"{o['key']}: different views all stay", {"other0000001:0", "other0000002:0"} <= set(ids))
    check("the proposal says what it left out", any("look-alike" in n for n in opts[0]["notes"]), str(opts[0]["notes"]))
    later = clip("take0000late", 59, 0, 0.55)
    later["capture_time"] = "2026-05-02T18:00:00+0900"      # the same view, that evening
    ids = shot_ids(sb.build(dupes + [later], "", vision=True)["options"][0])
    check("the same view hours later is a new moment, not a retake", "take0000late:0" in ids, str(ids))
    import math
    seat = [math.cos(0.7), math.sin(0.7)] + [0.0] * 6      # cosine with emb(0): 0.765, under SIMILAR
    near = [clip("hall0000000a", 1, 0, 0.7), clip("hall0000000b", 14, 0, 0.6)]
    near[1]["shots"][0]["embedding"] = seat

    def placed(cs, gps):
        for c, g in zip(cs, gps):
            c["gps"] = g
        return shot_ids(sb.build(cs, "", vision=True)["options"][0])
    ids = placed([dict(c, shots=[dict(c["shots"][0])]) for c in near], [[40.8091, -73.9625], [40.8091, -73.9625]])
    check("same seat, same hall, 13 min apart (0.77): one shot, the better", ids == ["hall0000000a:0"], str(ids))
    ids = placed([dict(c, shots=[dict(c["shots"][0])]) for c in near], [[40.8091, -73.9625], [40.8191, -73.9625]])
    check("the same similarity a kilometre apart: two moments", len(ids) == 2, str(ids))
    print("repeats in an edit that already exists (her shots 18 and 19)")
    from web.backend import board as bd
    hall = [dict(c, shots=[dict(c["shots"][0])]) for c in near]
    for c in hall:
        c["gps"] = [40.8091, -73.9625]
    hall[1]["capture_time"] = "2026-05-02T10:14:00+0900"       # 13 minutes after the first
    cat = bd.Catalog.from_clips(hall + others)
    ent = lambda sid: {"id": sid, "start": 0.0, "end": 2.5}  # noqa: E731
    edit = {"beats": [{"id": "b1", "title": "Afternoon", "shots": [ent("other0000001:0"), ent("hall0000000b:0")]},
                      {"id": "b2", "title": "Later", "shots": [ent("hall0000000a:0"), ent("other0000002:0")]}]}
    ops, names = brief.repeat_ops(edit, cat)
    check("the lecture hall twice, even across parts: the weaker one goes",
          ops == [{"op": "drop_shot", "shot": "hall0000000b:0"}], str(ops))
    again = {"beats": [{"id": "b1", "title": "x", "shots": [ent("other0000001:0"),
                                                         {"id": "other0000001:0", "key": "other0000001:0~2", "start": 1.0, "end": 3.0}]}]}
    ops, _ = brief.repeat_ops(again, cat)
    check("the same stretch of one clip twice: one goes", len(ops) == 1, str(ops))
    clean = {"beats": [{"id": "b1", "title": "x", "shots": [ent("other0000001:0"), ent("other0000002:0"), ent("hall0000000a:0")]}]}
    check("an edit without repeats is left alone", brief.repeat_ops(clean, cat) == ([], []))
    no_vision = sb.build(dupes + others, "", vision=False)["options"]
    check("without Vision (colour only) nothing is collapsed",
          sum(x.startswith("take") for x in shot_ids(no_vision[0])) == 5)

    print(f"\n{'all passed' if not failures else f'{len(failures)} failed'}")
    return 1 if failures else 0


def test_brief() -> None:
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())

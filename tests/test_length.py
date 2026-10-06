"""The length slider: its marks come from the footage, and the edit lands on it.

sarah (2026-10-06): "fast is under a minute 3 minutes or full length" didn't
help; how long a video should be depends on how much there is and what kind
of video it is. So the slider runs from 15 s to everything the rough cut
kept, with Short / Medium / Long marks read from both, one suggested with
why. Checks that the marks move with the material (more footage, a longer
suggestion; a trip earns more than a day vlog), that two targets which differ
only in seconds build edits that land under each, and that in Frames the same
slider shortens and lengthens an edit that already exists as one undoable
turn: weakest shots out first, put back in filming order, only their rough-cut
window, never a look-alike of a shot already in.

    python tests/test_length.py
"""

from __future__ import annotations

import os
import sys
import tempfile

os.environ["VIBECUT_CACHE"] = tempfile.mkdtemp(prefix="vibecut-length-")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

from test_board import CLIPS, PROPOSALS, session  # noqa: E402

from web.backend import board as bd  # noqa: E402
from web.backend import brief  # noqa: E402
from web.backend import storyboard as sb  # noqa: E402


def total(board: dict) -> float:
    return sum(e["end"] - e["start"] for b in board["beats"] for e in b["shots"])


def ids(board: dict) -> list[str]:
    return [e["id"] for b in board["beats"] for e in b["shots"]]


def main() -> int:
    failures = []

    def check(name: str, cond: bool, got: str = "") -> None:
        print(f"  {'PASS' if cond else 'FAIL'}  {name}{': ' + got if got else ''}")
        if not cond:
            failures.append(name)

    print("the marks")
    her = brief.length_marks(233, "A day in my life, morning to night, with friends")
    keys = [m["key"] for m in her["marks"]]
    check("her shoot: 15 s to 3:53, Short / Medium / Long", (her["min"], her["max"], keys) == (15, 233, ["short", "medium", "long"]),
          str((her["min"], her["max"], keys)))
    check("a day vlog from 3:53 of footage: about a minute, suggested", her["suggest"] == "short" and her["seconds"] == 60)
    check("the reason names the footage and the kind", "3:53" in her["why"] and "day vlog" in her["why"], her["why"])
    secs = [m["seconds"] for m in her["marks"]]
    check("marks in order, all inside the slider", secs == sorted(secs) and her["min"] <= secs[0] and secs[-1] <= her["max"], str(secs))
    sugg = [brief.length_marks(u, "day in my life")["seconds"] for u in (60, 233, 480, 1800)]
    check("more footage, a suggestion at least as long", sugg == sorted(sugg) and sugg[-1] > sugg[0], str(sugg))
    trip, day = brief.length_marks(1800, "weekend trip to Kyoto"), brief.length_marks(1800, "a day in my life")
    check("the same footage: a trip earns more than a day vlog", trip["seconds"] > day["seconds"], f"{trip['seconds']} vs {day['seconds']}")
    tiny = brief.length_marks(40, "my cat")
    check("40 s of footage: one mark, it all fits", [m["key"] for m in tiny["marks"]] == ["short"] and tiny["max"] == 40, str(tiny["marks"]))
    q = brief.fixed_questions(None, 233, "a day in my life")[0]
    check("the length question carries the slider", q["id"] == "length" and q["slider"]["max"] == 233
          and [c["key"] for c in q["choices"]] == keys)
    check("without the footage known, the old three choices", "slider" not in brief.fixed_questions()[0])

    print("building to a length")
    style = lambda s: {"seconds": s}  # noqa: E731
    short, longer = (sb.build(CLIPS, "", vision=True, style=style(s))["options"] for s in (45, 120))
    for a, b in zip(short, longer):
        la = sum(x["end"] - x["start"] for bt in a["beats"] for x in bt["shots"])
        lb = sum(x["end"] - x["start"] for bt in b["beats"] for x in bt["shots"])
        check(f"{a['key']}: 45 s lands under 45, 120 under 120, and they differ", la <= 45 and lb <= 120 and la < lb, f"{la:.0f} / {lb:.0f}")
    check("seconds win over an old length answer", brief.target_s({"length": "medium", "seconds": 90}) == 90)
    check("seconds survive cleaning, junk doesn't", brief.clean_style({"seconds": "95", "x": 1}) == {"seconds": 95.0}
          and brief.clean_style({"seconds": "lots"}) is None)

    print("the slider in Frames")
    s, cat = session()
    pool, _ = sb.usable(sb.shots_from_clips(CLIPS))
    before, n0 = ids(s.board), len(s.turns)
    full = total(s.board)
    ops, said = brief.length_ops(s.board, cat, pool, 60, vision=True)
    s.add({"kind": "direct", "text": "Make it about 1 minute", "ops": ops, "reply": said}, cat, lambda d: PROPOSALS)
    check("shorter: lands near the minute", abs(total(s.board) - 60) <= 12, f"{full:.0f}s -> {total(s.board):.0f}s; {said}")
    check("every part keeps a shot", all(b["shots"] for b in s.board["beats"]) and len(s.board["beats"]) == 4)
    check("one turn", len(s.turns) == n0 + 1)
    shrunk = ids(s.board)
    ops, said = brief.length_ops(s.board, cat, pool, 140, vision=True)
    s.add({"kind": "direct", "text": "Make it about 2:20", "ops": ops, "reply": said}, cat, lambda d: PROPOSALS)
    grown = ids(s.board)
    check("longer: shots go back in", len(grown) > len(shrunk) and abs(total(s.board) - 140) <= 12, f"{total(s.board):.0f}s; {said}")
    order = [cat.shots[i].when for i in grown]
    check("in filming order", order == sorted(order), str(grown))
    check("the best-made spare shot comes back first", "spare0000001:0" in grown)
    s.toggle(s.turns[-1].id, cat, lambda d: PROPOSALS)
    check("Undo takes them out again", ids(s.board) == shrunk)
    ops, said = brief.length_ops(s.board, cat, pool, 10_000, vision=True)
    check("asking for more than there is: everything, and says so", "all the good footage" in said, said)

    print("only the rough cut's window, never a look-alike")
    win = [sb.Shot(**{**p.__dict__, "start": p.start + 2, "end": p.start + 6}) if p.id == "spare0000001:0" else p for p in pool]
    sb_ = {"beats": [{"id": "b1", "title": "Day", "shots": [{"id": "hotel0000001:0", "start": 0.0, "end": 12.0}]}]}
    ops, _ = brief.length_ops(sb_, cat, win, 30, vision=True)
    add = next((o for o in ops if o["shot"] == "spare0000001:0"), None)
    check("a shot put back is its trimmed window", add is not None and (add["start"], add["end"]) == (2.0, 6.0), str(add))
    b2, _ = bd.apply(sb_, dict(add), cat, None, lambda: "x")
    check("add_shot keeps the window", (b2["beats"][0]["shots"][-1]["start"], b2["beats"][0]["shots"][-1]["end"]) == (2.0, 6.0))
    b3, _ = bd.apply(sb_, {k: v for k, v in add.items() if k not in ("start", "end")}, cat, None, lambda: "x")
    check("without one, the whole shot as before", b3["beats"][0]["shots"][-1]["end"] - b3["beats"][0]["shots"][-1]["start"] == 12.0)
    import copy
    twin = copy.deepcopy(CLIPS[1])
    twin.update(id="markettwin01", name="markettwin01.MOV", capture_time="2026-05-02T10:05:00+0900")
    cat2 = bd.Catalog.from_clips(CLIPS + [twin])
    pool2, _ = sb.usable(sb.shots_from_clips(CLIPS + [twin]))
    one = {"beats": [{"id": "b1", "title": "Day", "shots": [{"id": "market000001:0", "start": 0.0, "end": 12.0}]}]}
    ops, _ = brief.length_ops(one, cat2, pool2, 600, vision=True)
    check("the same view filmed 5 minutes later is never put back", not any(o["shot"].startswith("markettwin") for o in ops),
          str([o["shot"] for o in ops]))
    print("the slider's end is what the edit can reach (her 2:28 that stopped at 1:34)")
    every = sum(p.end - p.start for p in pool2)
    reach = brief.reachable_s(one, cat2, pool2, vision=True)
    got = 12.0 + sum(o["end"] - o["start"] for o in brief.length_ops(one, cat2, pool2, reach, vision=True)[0] if o["op"] == "add_shot")
    check("look-alikes count once, so the end is less than every usable second", reach < every, f"{reach:.0f} < {every:.0f}")
    check("dragging to the end gets there", abs(got - reach) <= max(2.0, 0.03 * reach), f"{got:.0f} vs {reach:.0f}")
    fresh = brief.reachable_s(None, cat2, pool2, vision=True)
    check("before there's an edit, the same count", abs(fresh - reach) <= 12.0, f"{fresh:.0f} vs {reach:.0f}")
    check("without Vision nothing is a look-alike", brief.reachable_s(None, cat2, pool2, vision=False) == every)

    print("through the app")
    from web.backend import app as A
    s, cat = session()
    A.SESSION, A.CATALOG["cat"], A.PLAN["plan"] = s, cat, None
    A.CLIPS.clear()
    A.CLIPS.update({c["id"]: c for c in CLIPS})
    A._make_proposals = lambda d: PROPOSALS
    A._session = lambda: {}
    info = A.api_length()
    check("the slider's range is the usable footage", info["max"] == 168 and info["current"] == 156, str((info["max"], info["current"])))
    check("its marks read the description (a day in Tokyo)", info["kind"] in ("day", "trip", "other"), info["why"])
    n = len(s.turns)
    out = A.api_length_set(A.LengthReq(seconds=60))
    check("letting go at 1:00: one turn, near a minute", len(A.SESSION.turns) == n + 1 and abs(total(A.SESSION.board) - 60) <= 12,
          out["length_note"])
    out = A.api_length_set(A.LengthReq(seconds=total(A.SESSION.board)))
    check("letting go where it already is changes nothing", len(A.SESSION.turns) == n + 1, out["length_note"])
    q = A.api_brief_questions(A.QuestionsReq(message="A day in my life, morning to night"))["questions"][0]
    check("the questions popup gets the same slider", q.get("slider", {}).get("max") == 168)

    print(f"\n{'all passed' if not failures else f'{len(failures)} failed'}")
    return 1 if failures else 0


def test_length() -> None:
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())

"""Smoother cuts: each move happens exactly when it pays, and not otherwise.

Order: one part of four shots filmed bright, dark, bright, dark. In filming
order every cut is a brightness jump; putting like with like leaves one.
The search must find that, apply it as move_shot ops (a normal, undoable
turn), keep the rest of the edit untouched -- and do nothing when putting
shots out of filming order costs more than it saves (the weight is the
single thing changed), or when the shots already cut smoothly.

Nudge: a shot whose window's edges sit on still seconds, with movement one
second later at both ends. The window must slide one second onto the
movement, keeping its length -- and must not when that second is a word.

    python tests/test_smooth.py
"""

from __future__ import annotations

import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
os.environ.setdefault("VIBECUT_CACHE", tempfile.mkdtemp(prefix="vibecut-smooth-"))

from test_board import _clip  # noqa: E402

from web.backend import board as bd  # noqa: E402
from web.backend import seams, smooth  # noqa: E402
from web.backend import timeline as tlm  # noqa: E402

failures: list[str] = []


def check(name: str, cond: bool, got: str = "") -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{': ' + got if got else ''}")
    if not cond:
        failures.append(name)


def clip(cid: str, minute: int, luma: float, motion: list[float] | None = None, speech: list[float] | None = None) -> dict:
    c = _clip(cid, 10, ["outdoor"], 1, dur=10.0)
    c["capture_time"] = f"2026-05-02T10:{minute:02d}:00"
    c["path"] = f"/nonexistent/{cid}.mov"
    c["duration"] = 10.0
    c["signals"] = {"luma": [luma] * 10, "motion": motion or [5.0] * 10, "quality": [0.6] * 10,
                    "speech": speech or [0.0] * 10}
    c["shots"][0].update(hist=[1 / 64] * 64, embedding=[])
    return c


def board_of(parts: list[list[str]]) -> dict:
    return {"option": "t", "name": "n", "structure": "", "beats": [
        {"id": f"t{i + 1}", "title": f"Part {i + 1}", "detail": "",
         "shots": [{"id": f"{cid}:0", "start": 2.0, "end": 5.0} for cid in p]} for i, p in enumerate(parts)]}


def rough(board: dict, clips: dict) -> int:
    return sum(c["verdict"] != "ok" for c in seams.check(tlm.layout(board), clips))


def main() -> int:
    print("order within a part")
    clips = {c["id"]: c for c in [clip("brightA00001", 0, 150), clip("darkB0000001", 5, 30),
                                  clip("brightC00001", 10, 150), clip("darkD0000001", 15, 30),
                                  clip("next00000001", 30, 30)]}
    b = board_of([["brightA00001", "darkB0000001", "brightC00001", "darkD0000001"], ["next00000001"]])
    cat = bd.Catalog.from_clips(list(clips.values()))
    ops, stats = smooth.order_ops(b, clips)
    s = bd.Session()
    mk = lambda d: None  # noqa: E731
    s.add({"kind": "direct", "text": "use", "ops": [{"op": "choose_option", "option": "t", "snapshot": b}]}, cat, mk)
    before = rough(s.board, clips)
    t = s.add({"kind": "direct", "text": "Smoother cuts", "ops": ops}, cat, mk)
    order = [x["id"].split(":")[0] for x in s.board["beats"][0]["shots"]]
    check("like goes with like", order in (["brightA00001", "brightC00001", "darkB0000001", "darkD0000001"],
                                           ["brightA00001", "brightC00001", "darkD0000001", "darkB0000001"]), str(order))
    check("fewer rough cuts than filming order", rough(s.board, clips) < before, f"{before} -> {rough(s.board, clips)}")
    check("only move_shot ops, applied cleanly", ops and all(o["op"] == "move_shot" for o in ops) and not t.skipped)
    check("the other part is untouched", s.board["beats"][1] == b["beats"][1])
    check("shots keep their windows", all(x["start"] == 2.0 and x["end"] == 5.0 for x in s.board["beats"][0]["shots"]))
    s.toggle(t.id, cat, mk)
    check("undo restores filming order",
          [x["id"].split(":")[0] for x in s.board["beats"][0]["shots"]] == ["brightA00001", "darkB0000001", "brightC00001", "darkD0000001"])

    saved = smooth.TIME_WEIGHT
    smooth.TIME_WEIGHT = 10.0
    check("when filming order matters more than smoothness, nothing moves", smooth.order_ops(b, clips)[0] == [])
    smooth.TIME_WEIGHT = saved
    even = {c["id"]: c for c in [clip("evenA0000001", 0, 100), clip("evenB0000001", 5, 102), clip("evenC0000001", 10, 98)]}
    check("shots that already cut smoothly stay put",
          smooth.order_ops(board_of([["evenA0000001", "evenB0000001", "evenC0000001"]]), even)[0] == [])

    print("cut on the action")
    still_then_busy = [1.0] * 10
    still_then_busy[3] = still_then_busy[5] = 30.0      # movement one second after each edge
    nclips = {"mover0000001": clip("mover0000001", 0, 100, motion=still_then_busy),
              "after0000001": clip("after0000001", 5, 100)}
    nb = board_of([["mover0000001", "after0000001"]])
    ncat = bd.Catalog.from_clips(list(nclips.values()))
    ops, st = smooth.nudge_ops(nb, nclips, ncat)
    s = bd.Session()
    s.add({"kind": "direct", "text": "use", "ops": [{"op": "choose_option", "option": "t", "snapshot": nb}]}, ncat, mk)
    s.add({"kind": "direct", "text": "nudge", "ops": ops}, ncat, mk)
    e = s.board["beats"][0]["shots"][0]
    check("the window slides one second onto the movement", (e["start"], e["end"]) == (3.0, 6.0), f"{e['start']}–{e['end']}")
    check("…keeping its length, and nothing else moves", s.board["beats"][0]["shots"][1] == nb["beats"][0]["shots"][1])
    worded = dict(nclips)
    sp = [0.0] * 10
    sp[5] = 0.9                                          # a word on the second it would cut at
    worded["mover0000001"] = clip("mover0000001", 0, 100, motion=still_then_busy, speech=sp)
    wops = smooth.nudge_ops(nb, worded, ncat)[0]
    to = {o["edge"]: o["to"] for o in wops}
    check("never onto a word: it takes the next-best movement instead",
          to == {"in": 1.0, "out": 4.0}, str(to))
    flat = {"mover0000001": clip("mover0000001", 0, 100), "after0000001": nclips["after0000001"]}
    check("no movement nearby, no nudge", smooth.nudge_ops(nb, flat, ncat)[0] == [])

    print("one turn")
    ops, said = smooth.propose(b, clips, cat)
    check("says what it did, in words", "reordered" in said.lower() and bool(ops), said)
    check("nothing to do is said, not faked", smooth.propose(board_of([["evenA0000001", "evenB0000001"]]), even,
                                                             bd.Catalog.from_clips(list(even.values())))[0] == [])

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

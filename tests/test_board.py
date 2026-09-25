"""Does a turn change exactly what it says, and nothing else?

The storyboard is edited by operations, never regenerated. These checks pin
that down without a language model: the ops the model would emit for
"make the opening punchier and cut the market section" are applied, and
everything outside the opening and the market must come out identical.
Then undo: any turn, not just the last, by replaying the log without it.

    python tests/test_board.py
"""

from __future__ import annotations

import copy
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web.backend import board as bd  # noqa: E402


def _clip(cid: str, hour: int, labels: list[str], n_shots: int = 1, dur: float = 12.0, q: float = 0.6):
    return {
        "id": cid, "name": f"{cid}.MOV", "duration": dur * n_shots,
        "capture_time": f"2026-05-02T{hour:02d}:00:00+0900", "gps": None,
        "shots": [{
            "index": i, "start": i * dur, "end": (i + 1) * dur, "thumb": f"shot{i:03d}.jpg",
            "best_t": i * dur + dur / 2, "quality": q, "aesthetic": None, "utility": False,
            "labels": [[l, 0.8] for l in labels], "faces": 0, "face_area": 0.0,
            "embedding": [1.0 if j == hash(labels[0]) % 8 else 0.0 for j in range(8)],
        } for i in range(n_shots)],
    }


CLIPS = [
    _clip("hotel0000001", 8, ["structure", "bed"], 3),
    _clip("market000001", 10, ["food", "market", "crowd"], 4),
    _clip("temple000001", 13, ["temple", "structure"], 3),
    _clip("dinner000001", 19, ["food", "restaurant"], 3),
    _clip("spare0000001", 11, ["food", "market"], 1, q=0.9),   # not on the board
]

OPTION = {
    "key": "time", "name": "As it happened", "summary": "Chronological.",
    "beats": [
        {"title": t, "detail": "", "shots": [
            {"id": f"{cid}:{i}", "start": i * 12.0, "end": (i + 1) * 12.0}
            for i in range(n)]}
        for t, cid, n in [("Morning", "hotel0000001", 3), ("Market", "market000001", 4),
                          ("Temple", "temple000001", 3), ("Dinner", "dinner000001", 3)]
    ],
}
PROPOSALS = {"options": [OPTION]}


def session() -> tuple[bd.Session, bd.Catalog]:
    s = bd.Session()
    cat = bd.Catalog.from_clips(CLIPS)
    s.add({"kind": "chat", "text": "a day in Tokyo", "ops": [], "direction": {"text": "a day in Tokyo"}},
          cat, lambda d: PROPOSALS)
    s.add({"kind": "direct", "text": "apply", "ops": [{"op": "choose_option", "option": "time"}]},
          cat, lambda d: PROPOSALS)
    return s, cat


def main() -> int:
    failures = []

    def check(name: str, cond: bool, got: str) -> None:
        print(f"  {'PASS' if cond else 'FAIL'}  {name}: {got}")
        if not cond:
            failures.append(name)

    mk = lambda d: PROPOSALS  # noqa: E731

    # The acceptance request, as the two ops the model should emit.
    s, cat = session()
    before = copy.deepcopy(s.board)
    t = s.add({"kind": "chat", "text": "make the opening punchier and cut the market section",
               "ops": [{"op": "set_pace", "beat": "t1", "direction": "tighter", "amount": "a_lot"},
                       {"op": "drop_beat", "beat": "t2"}]}, cat, mk)
    d = t.diff
    check("market beat removed", [r["title"] for r in d["beats"]["removed"]] == ["Market"],
          str([r["title"] for r in d["beats"]["removed"]]))
    check("only the opening's shots were trimmed",
          {x["beat"] for x in d["shots"]["trimmed"]} == {"t1"} and len(d["shots"]["trimmed"]) == 3,
          f"{len(d['shots']['trimmed'])} trims in {sorted({x['beat'] for x in d['shots']['trimmed']})}")
    check("opening is half as long",
          abs(sum(x["to"] for x in d["shots"]["trimmed"]) - 18.0) < 0.01, f"{sum(x['to'] for x in d['shots']['trimmed'])}s")
    check("nothing moved, added or renamed",
          not (d["beats"]["moved"] or d["beats"]["added"] or d["beats"]["retitled"]
               or d["shots"]["moved"] or d["shots"]["added"]), "clean")
    untouched = [b for b in before["beats"] if b["id"] in ("t3", "t4")]
    check("every other beat is byte-identical",
          untouched == [b for b in s.board["beats"] if b["id"] in ("t3", "t4")], "t3, t4 equal")
    check("the diff reads as exactly two lines", len(t.lines) == 2,
          " | ".join(l["text"] for l in t.lines))

    # Undo an *earlier* turn: later edits survive.
    s, cat = session()
    a = s.add({"kind": "chat", "text": "call the temple bit Shrine",
               "ops": [{"op": "retitle_beat", "beat": "t3", "title": "Shrine"}]}, cat, mk)
    s.add({"kind": "chat", "text": "lose dinner", "ops": [{"op": "drop_beat", "beat": "t4"}]}, cat, mk)
    s.toggle(a.id, cat, mk)
    titles = [b["title"] for b in s.board["beats"]]
    check("undoing turn 2 of 3 keeps turn 3", titles == ["Morning", "Market", "Temple"], str(titles))
    s.toggle(a.id, cat, mk)
    check("redo brings it back", [b["title"] for b in s.board["beats"]][2] == "Shrine",
          str([b["title"] for b in s.board["beats"]]))

    # An op that depended on the undone turn is skipped and reported, not guessed.
    s, cat = session()
    a = s.add({"kind": "direct", "text": "add", "ops": [
        {"op": "add_shot", "shot": "spare0000001:0", "beat": "t2", "to_index": 0}]}, cat, mk)
    b = s.add({"kind": "direct", "text": "drop it", "ops": [
        {"op": "drop_shot", "shot": "spare0000001:0"}]}, cat, mk)
    s.toggle(a.id, cat, mk)
    check("dependent op is skipped with a reason", len(b.skipped) == 1, b.skipped[0] if b.skipped else "none")

    # Swap with no target picks a better-made similar shelf shot, and replay is exact.
    s, cat = session()
    t = s.add({"kind": "chat", "text": "better market shot", "ops": [
        {"op": "swap_shot", "shot": "market000001:1", "with_shot": None}]}, cat, mk)
    check("swap picks the better market shot", t.ops[0].get("with_shot") == "spare0000001:0",
          str(t.ops[0].get("with_shot")))
    slot = next(x for x in s.board["beats"][1]["shots"] if x["id"] == "spare0000001:0")
    check("swap keeps the slot's length", abs((slot["end"] - slot["start"]) - 12.0) < 0.01,
          f"{slot['end'] - slot['start']}s")
    snap = copy.deepcopy(s.board)
    s.replay(cat, mk)
    check("replay reproduces the board exactly", snap == s.board, "equal")

    # Reordering a beat reports a move and nothing else.
    s, cat = session()
    t = s.add({"kind": "chat", "text": "open at the temple",
               "ops": [{"op": "move_beat", "beat": "t3", "to_index": 0}]}, cat, mk)
    check("move_beat is one move", [m["title"] for m in t.diff["beats"]["moved"]] == ["Temple"]
          and not t.diff["shots"]["trimmed"], " | ".join(l["text"] for l in t.lines))

    # Unknown ids never crash the session.
    s, cat = session()
    t = s.add({"kind": "chat", "text": "nonsense", "ops": [{"op": "drop_beat", "beat": "zz"}]}, cat, mk)
    check("unknown beat is skipped", t.skipped == ["no beat zz"] and len(s.board["beats"]) == 4, str(t.skipped))

    # ---- precise timeline edits ------------------------------------------
    def total(board):
        return round(sum(e["end"] - e["start"] for b in board["beats"] for e in b["shots"]), 3)

    def seq(board):
        return [(bd.key(e), e["start"], e["end"]) for b in board["beats"] for e in b["shots"]]

    s, cat = session()
    t0 = total(s.board)
    t = s.add({"kind": "direct", "text": "cut", "ops": [{"op": "split", "shot": "market000001:1", "at": 17.5}]}, cat, mk)
    pieces = [x for x in seq(s.board) if x[0].startswith("market000001:1")]
    check("a cut makes two pieces that meet exactly",
          len(pieces) == 2 and pieces[0][2] == pieces[1][1] == 17.5, str(pieces))
    check("a cut doesn't change the running time", total(s.board) == t0, f"{total(s.board)} vs {t0}")
    check("the diff names it a cut, nothing else",
          [l["kind"] for l in t.lines] == ["cut"], " | ".join(l["text"] for l in t.lines))
    second = pieces[1][0]

    # ripple delete closes the gap; lift leaves one
    s2, _ = session()
    s2.add({"kind": "direct", "text": "cut", "ops": [{"op": "split", "shot": "market000001:1", "at": 17.5}]}, cat, mk)
    s2.add({"kind": "direct", "text": "del", "ops": [{"op": "drop_shot", "shot": second}]}, cat, mk)
    check("delete ripples: running time shrinks by the piece", total(s2.board) == round(t0 - 6.5, 3),
          f"{t0} -> {total(s2.board)}")
    s.add({"kind": "direct", "text": "lift", "ops": [{"op": "drop_shot", "shot": second, "leave_gap": True}]}, cat, mk)
    gaps = [e for b in s.board["beats"] for e in b["shots"] if bd.is_gap(e)]
    check("delete with the modifier leaves a gap of the same length",
          total(s.board) == t0 and len(gaps) == 1 and gaps[0]["end"] == 6.5, f"gap {gaps[0]['end'] if gaps else None}")

    # trim: ripple by default, clamped to the source
    s, cat = session()
    s.add({"kind": "direct", "text": "trim", "ops": [{"op": "trim", "shot": "temple000001:0", "edge": "out", "to": 11.0}]}, cat, mk)
    check("trim out by one second ripples", total(s.board) == t0 - 1.0, f"{t0} -> {total(s.board)}")
    s.add({"kind": "direct", "text": "trim", "ops": [{"op": "trim", "shot": "temple000001:0", "edge": "in", "to": -5}]}, cat, mk)
    e = next(x for b in s.board["beats"] for x in b["shots"] if bd.key(x) == "temple000001:0")
    check("trim can't reach past the source shot", e["start"] == 0.0, f"start {e['start']}")

    # range delete across a cut boundary, as I/O + Delete does
    s, cat = session()
    t = s.add({"kind": "direct", "text": "extract", "ops": [{"op": "drop_range",
        "from_shot": "market000001:0", "from_at": 6.0, "to_shot": "market000001:1", "to_at": 15.0}]}, cat, mk)
    check("range delete removes exactly the marked 9s", total(s.board) == t0 - 9.0, f"{t0} -> {total(s.board)}")
    m = [x for x in seq(s.board) if x[0].startswith("market000001:0") or x[0].startswith("market000001:1")]
    check("what's left either side is intact", m == [("market000001:0", 0.0, 6.0), ("market000001:1~15000", 15.0, 24.0)], str(m))

    # undoing the cut makes the later delete of its second half a no-op, not a guess
    s, cat = session()
    a = s.add({"kind": "direct", "text": "cut", "ops": [{"op": "split", "shot": "market000001:1", "at": 17.5}]}, cat, mk)
    b = s.add({"kind": "direct", "text": "del", "ops": [{"op": "drop_shot", "shot": second}]}, cat, mk)
    s.toggle(a.id, cat, mk)
    check("undoing a cut skips edits to the piece it made", b.skipped and total(s.board) == t0,
          b.skipped[0] if b.skipped else "not skipped")
    snap = copy.deepcopy(s.board)
    s.replay(cat, mk)
    check("replay after cuts and undo is exact", snap == s.board, "equal")

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

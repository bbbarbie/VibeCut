"""Frames' two piles: a clip moved between Kept and Left out changes the video.

sarah (2026-10-13): the Media panel in Frames was every clip mixed together,
the left-out ones greyed with long red notes; she wanted "just the two piles
of kept and left out", as on Footage. Kept means in the video. Checks that
putting a clip in adds its rough-cut window where it was filmed, as one
undoable turn; that taking one out drops every shot of it the edit has; that
a clip already where it's asked to go changes nothing; and the same through
the app.

    python tests/test_pile.py
"""

from __future__ import annotations

import os
import sys
import tempfile

os.environ["VIBECUT_CACHE"] = tempfile.mkdtemp(prefix="vibecut-pile-")
os.environ.setdefault("VIBECUT_BED", "0")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

from test_board import CLIPS, PROPOSALS, session  # noqa: E402

from web.backend import brief  # noqa: E402
from web.backend import storyboard as sb  # noqa: E402


def ids(board: dict) -> list[str]:
    return [e["id"] for b in board["beats"] for e in b["shots"]]


def main() -> int:
    failures = []

    def check(name: str, cond: bool, got: str = "") -> None:
        print(f"  {'PASS' if cond else 'FAIL'}  {name}{': ' + got if got else ''}")
        if not cond:
            failures.append(name)

    s, cat = session()
    pool, _ = sb.usable(sb.shots_from_clips(CLIPS))
    keep = lambda cid: [p for p in pool if p.clip_id == cid]  # noqa: E731
    before, n0 = ids(s.board), len(s.turns)

    print("into Kept")
    win = [sb.Shot(**{**p.__dict__, "start": p.start + 2, "end": p.start + 7}) for p in keep("spare0000001")]
    ops = brief.clip_ops(s.board, cat, "spare0000001", True, win)
    s.add({"kind": "direct", "text": "in", "ops": ops}, cat, lambda d: PROPOSALS)
    after = ids(s.board)
    check("one turn, the clip is in", len(s.turns) == n0 + 1 and "spare0000001:0" in after, str(after))
    order = [cat.shots[i].when for i in after]
    check("where it was filmed (after the market, before the temple)", order == sorted(order))
    e = next(e for b in s.board["beats"] for e in b["shots"] if e["id"] == "spare0000001:0")
    check("only its rough-cut window", (e["start"], e["end"]) == (2.0, 7.0), str(e))
    check("already in: nothing to do", brief.clip_ops(s.board, cat, "spare0000001", True, win) == [])
    s.toggle(s.turns[-1].id, cat, lambda d: PROPOSALS)
    check("Undo takes it out again", ids(s.board) == before)
    ops = brief.clip_ops(s.board, cat, "spare0000001", True, [])
    check("left out by the rough cut (no window): its best shot whole",
          [(o["shot"], o["end"] - o["start"]) for o in ops] == [("spare0000001:0", 12.0)], str(ops))

    print("into Left out")
    ops = brief.clip_ops(s.board, cat, "market000001", False, keep("market000001"))
    s.add({"kind": "direct", "text": "out", "ops": ops}, cat, lambda d: PROPOSALS)
    check("every shot of it leaves the edit", not any(i.startswith("market") for i in ids(s.board)), str(ids(s.board)))
    check("nothing else moves", [i for i in before if not i.startswith("market")] == ids(s.board))
    check("already out: nothing to do", brief.clip_ops(s.board, cat, "market000001", False, []) == [])
    ops = brief.clip_ops(s.board, cat, "market000001", True, keep("market000001"))
    s.add({"kind": "direct", "text": "back", "ops": ops}, cat, lambda d: PROPOSALS)
    check("back in: all four shots, in their places", ids(s.board) == before, str(ids(s.board)))

    print("through the app")
    from web.backend import app as A
    s, cat = session()
    A.SESSION, A.CATALOG["cat"], A.PLAN["plan"] = s, cat, None
    A.CLIPS.clear()
    A.CLIPS.update({c["id"]: c for c in CLIPS})
    A._make_proposals = lambda d: PROPOSALS
    A._session = lambda: {}
    n = len(s.turns)
    A.api_pile(A.PileReq(clip="spare0000001", into=True))
    check("Move to Kept: one turn, in the video", len(A.SESSION.turns) == n + 1 and "spare0000001:0" in ids(A.SESSION.board))
    check("the turn says so in plain words", A.SESSION.turns[-1].text == "You put spare0000001.MOV in the video",
          A.SESSION.turns[-1].text)
    A.api_pile(A.PileReq(clip="temple000001", into=False))
    check("Move to Left out: gone", not any(i.startswith("temple") for i in ids(A.SESSION.board)))
    A.api_pile(A.PileReq(clip="temple000001", into=False))
    check("asking twice adds no empty turn", len(A.SESSION.turns) == n + 2)

    print(f"\n{'all passed' if not failures else f'{len(failures)} failed'}")
    return 1 if failures else 0


def test_pile() -> None:
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())

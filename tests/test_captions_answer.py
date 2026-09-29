"""The captions answer must change what's on screen -- and only that way.

Same story, answers that differ in one respect: "No words" adds nothing;
"Simple" labels every part in the clean look; "Bold" uses the hype look
(capitals, slam entrance, beat lock); "Key words" gives a title and no part
labels. Every word comes from the edit (its parts, the description), and
one Undo takes the words away without touching the cut.

    python tests/test_captions_answer.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.test_board import PROPOSALS, session  # noqa: E402
from web.backend import brief  # noqa: E402
from web.backend import overlays as ov  # noqa: E402

mk = lambda d: PROPOSALS  # noqa: E731


def main() -> int:
    failures = []

    def check(name: str, cond: bool, got: str = "") -> None:
        print(f"  {'PASS' if cond else 'FAIL'}  {name}{': ' + got if got else ''}")
        if not cond:
            failures.append(name)

    def words(answer):
        s, cat = session()
        cut = [[x["id"] for x in b["shots"]] for b in s.board["beats"]]
        ops, notes = brief.caption_ops(s.board, cat, answer, "A day in Tokyo")
        t = s.add({"kind": "direct", "text": "words", "ops": ops}, cat, mk) if ops else None
        return s, cat, t, cut, notes

    s, *_ = words("none")
    check("no words: nothing added", not s.board.get("overlays") and not s.board.get("look"))
    s, *_ = words(None)
    check("no answer: nothing added", not s.board.get("overlays"))

    s, cat, t, cut, _ = words("simple")
    kinds = [o["kind"] for o in s.board["overlays"]]
    check("simple: a title", kinds.count("title") == 1, str(kinds))
    check("simple: every part after the first is labelled", kinds.count("part") == len(s.board["beats"]) - 1, str(kinds))
    check("simple: the clean look", ov.style_of(s.board).get("look") == "clean")
    check("the title is the description", next(o["text"] for o in s.board["overlays"] if o["kind"] == "title") == "A day in Tokyo")
    labels = {o["text"] for o in s.board["overlays"] if o["kind"] == "part"}
    check("part labels are the parts' own titles", labels <= {b["title"] for b in s.board["beats"]}, str(labels))
    check("the words draw in preview and export", len(ov.resolve(s.board)) == len(s.board["overlays"]))
    s.toggle(t.id, cat, mk)
    check("one undo takes the words away", not s.board.get("overlays") and not s.board.get("look"))
    check("and leaves the cut as it was", [[x["id"] for x in b["shots"]] for b in s.board["beats"]] == cut)

    s, *_ = words("bold")
    st = ov.style_of(s.board)
    check("bold: the hype look", st.get("look") == "hype")
    check("bold: slams in on the beat", (st.get("motion") or {}).get("enter") == "slam"
          and (st.get("motion") or {}).get("beat_lock") is True)
    check("bold: parts labelled", any(o["kind"] == "part" for o in s.board["overlays"]))

    s, *_ = words("key")
    kinds = [o["kind"] for o in s.board["overlays"]]
    check("key words: a title, no part labels", "title" in kinds and "part" not in kinds, str(kinds))
    check("key words: the quiet look", ov.style_of(s.board).get("look") == "quiet")

    check("the question is asked", "captions" in [q["id"] for q in brief.fixed_questions()])
    check("the answer survives cleaning", brief.clean_style({"captions": "bold"}) == {"captions": "bold"})
    check("a made-up answer doesn't", brief.clean_style({"captions": "neon"}) is None)

    print(f"\n{'all passed' if not failures else f'{len(failures)} failed'}")
    return 1 if failures else 0


def test_captions_answer() -> None:
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())

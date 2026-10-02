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
import re
import sys
from datetime import timedelta

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

    print("day in my life")
    from web.backend import daylog
    s, cat, t, cut, notes = words("day")
    caps = [o for o in s.board["overlays"] if o["kind"] == "caption"]
    check("day: a caption per moment the day moves on", len(caps) >= 3, str([o["text"] for o in caps]))
    check("day: each starts with the clock", all(re.match(r"\d{1,2}:\d\d (am|pm)", o["text"]) for o in caps),
          str([o["text"] for o in caps]))
    first = s.board["beats"][0]["shots"][0]
    sh = cat.shots[first["id"]]
    want = daylog.clock(sh.when + timedelta(seconds=first["start"] - sh.start))
    check("day: the time is the recording time of that shot", caps[0]["text"].startswith(want), f"{caps[0]['text']} vs {want}")
    check("day: what's happening comes from the labels",
          any(o["text"].endswith("· eating out") for o in caps) and any(o["text"].endswith("· market") for o in caps),
          str([o["text"] for o in caps]))
    check("day: the cozy look", ov.style_of(s.board).get("look") == "cozy")
    check("day: captions are ordinary overlays, retypable by hand",
          all(set(ov.EDITABLE) >= {"text"} for _ in caps))
    s.toggle(t.id, cat, mk)
    check("day: one undo takes them away", not s.board.get("overlays"))

    check("the most specific label speaks", daylog.phrase({"food": 0.9, "sushi": 0.6}) == "sushi time")
    check("an unsure label stays quiet", daylog.phrase({"coffee": 0.1}) is None)
    check("unknown labels give the time alone", daylog.phrase({"structure": 0.9}) is None)

    s, cat = session()
    auto, _ = brief.caption_ops(s.board, cat, None, None, "A day in my life in Tokyo")
    check("a day-in-my-life description gets these captions by default",
          any(o.get("kind") == "caption" for o in auto) and auto[0] == {"op": "set_look", "look": "cozy"})
    off, _ = brief.caption_ops(s.board, cat, "none", None, "A day in my life in Tokyo")
    check("but 'No words' still means no words", off == [])
    plain, _ = brief.caption_ops(s.board, cat, None, None, "trip to Tokyo")
    check("other descriptions get nothing unasked", plain == [])

    from web.backend import llm
    real = llm.day_phrases
    llm.day_phrases = lambda items, about="": ["slow start", "", "temple hopping", "dinner with friends"][:len(items)]
    ops, _ = daylog.caption_ops(s.board, cat, "A day in my life", ask_model=True)
    check("with a key, Claude's phrase replaces the table's",
          [o["text"].split(" · ")[-1] for o in ops] == ["slow start", "market", "temple hopping", "dinner with friends"],
          str([o["text"] for o in ops]))

    def fail(items, about=""):
        raise llm.LLMError("down")
    llm.day_phrases = fail
    ops, _ = daylog.caption_ops(s.board, cat, "", ask_model=True)
    check("and if Claude can't be reached, the table's phrases stand", ops[0]["text"].endswith("slow morning"))
    llm.day_phrases = real

    for sh in cat.shots.values():
        sh.when = None
    ops, notes = daylog.caption_ops(s.board, cat, ask_model=False)
    check("no recording times: no invented clock, and it says so", ops == [] and "recording time" in notes[0])

    check("the question is asked", "captions" in [q["id"] for q in brief.fixed_questions()])
    check("the answer survives cleaning", brief.clean_style({"captions": "bold"}) == {"captions": "bold"})
    check("a made-up answer doesn't", brief.clean_style({"captions": "neon"}) is None)

    print(f"\n{'all passed' if not failures else f'{len(failures)} failed'}")
    return 1 if failures else 0


def test_captions_answer() -> None:
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())

"""The voiceover decides what's shown and for how long -- and gaps stay gaps.

Two scripts that differ in exactly one line (one names food, the other
says something abstract) must produce edits that differ in exactly that
part: food footage for one, a gap of the same length for the other, and
every other part identical. Timing has to come from the subtitles, the
same clip may not play twice in a row, and nothing may claim the picture
is locked to the voice.

    python tests/test_voiceover.py
"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

from test_board import CLIPS, _clip  # noqa: E402

from web.backend import board as bd  # noqa: E402
from web.backend import storyboard as sb  # noqa: E402
from web.backend import voiceover as vo  # noqa: E402

SRT = """1
00:00:00,500 --> 00:00:04,000
We started the morning at the temple.

2
00:00:04,200 --> 00:00:10,000
Then the market — so much food everywhere.

3
00:00:10,000 --> 00:00:13,000
{third}

4
00:00:13,500 --> 00:00:16,000
Dinner was the best food of the trip.
"""
FOOD = "More food, street stalls and snacks."
ABSTRACT = "I finally felt like I could breathe."


def voice(clips: list[dict], text: str) -> dict:
    return sb.build(clips, "", vision=True, voiceover=vo.parse(text))["options"][0]


def main() -> int:
    failures = []

    def check(name: str, cond: bool, got: str = "") -> None:
        print(f"  {'PASS' if cond else 'FAIL'}  {name}{': ' + got if got else ''}")
        if not cond:
            failures.append(name)

    s = vo.parse(SRT.format(third=FOOD))
    check("subtitles parse into timed lines", [round(l["start"], 1) for l in s["lines"]] == [0.5, 4.2, 10.0, 13.5],
          str([l["start"] for l in s["lines"]]))
    check("each line holds the screen until the next starts",
          [(l["from"], l["to"]) for l in s["lines"]] == [(0.0, 4.2), (4.2, 10.0), (10.0, 13.5), (13.5, 16.0)])
    check("subtitle timing is 'estimated', never locked", s["timing"] == "estimated")

    script = vo.parse("我们去了市场，吃了很多东西。晚上去看了寺庙！Then we walked home.")
    check("a plain script is split into sentences", len(script["lines"]) == 3, str([l["text"] for l in script["lines"]]))
    check("…and its timing is 'text_only'", script["timing"] == "text_only")
    check("…with lengths from the words", 2.0 < script["lines"][0]["to"] - script["lines"][0]["from"] < 4.0,
          f"{script['lines'][0]['to'] - script['lines'][0]['from']:.2f}s")

    clips = CLIPS + [_clip("stalls000001", 12, ["food", "market"], 2, q=0.7)]
    a = voice(clips, SRT.format(third=FOOD))
    b = voice(clips, SRT.format(third=ABSTRACT))

    def length(o: dict) -> float:
        return round(sum(x["end"] - x["start"] for bt in o["beats"] for x in bt["shots"]), 3)

    check("it comes first, as its own proposal", a["key"] == "voice")
    check("one part per spoken line", len(a["beats"]) == 4 and a["beats"][1]["line"].startswith("Then the market"))
    check("the edit is exactly as long as the voice", length(a) == 16.0 and length(b) == 16.0, f"{length(a)} / {length(b)}")
    check("each part is exactly as long as its line",
          [round(sum(x["end"] - x["start"] for x in bt["shots"]), 2) for bt in a["beats"]] == [4.2, 5.8, 3.5, 2.5])

    labels = lambda sid: {l for c in clips for s in c["shots"] if f"{c['id']}:{s['index']}" == sid for l, _ in s["labels"]}  # noqa: E731
    food = [x for x in a["beats"][1]["shots"] if not x.get("gap")]
    check("a line about food is shown with food", food and all("food" in labels(x["id"]) for x in food),
          str([x["id"] for x in food]))
    check("a line about the temple is shown with the temple",
          all("temple" in labels(x["id"]) for x in a["beats"][0]["shots"] if not x.get("gap")))

    third_a, third_b = a["beats"][2], b["beats"][2]
    check("the concrete line gets footage", not any(x.get("gap") for x in third_a["shots"]))
    check("the abstract line gets a gap, not a pretty shot",
          len(third_b["shots"]) == 1 and third_b["shots"][0]["gap"], str(third_b["shots"]))
    check("…of the line's length, listed with a reason",
          third_b["shots"][0]["end"] == 3.5 and any(g["line"] == 3 and "action" in g["reason"] for g in b["gaps"]))
    check("the other parts are identical",
          [a["beats"][i] for i in (0, 1)] == [b["beats"][i] for i in (0, 1)],
          "parts 1–2 equal")

    flat = [x for bt in a["beats"] for x in bt["shots"] if not x.get("gap")]
    check("no clip plays twice in a row",
          all(p["clip_id"] != q["clip_id"] for p, q in zip(flat, flat[1:])), " ".join(x["clip_id"][:6] for x in flat))
    check("no shot is used twice", len({x["id"] for x in flat}) == len(flat))

    # Choosing it gives a storyboard with the gaps in place, editable like any other.
    board = bd.board_from_option(b)
    gaps = [x for bt in board["beats"] for x in bt["shots"] if bd.is_gap(x)]
    check("choosing it keeps the gaps on the storyboard", len(gaps) >= 1 and gaps[0]["end"] == 3.5, str(gaps))
    cat = bd.Catalog.from_clips(clips)
    s2 = bd.Session()
    s2.add({"kind": "direct", "text": "vo", "ops": [], "direction": {"text": "", "voiceover": vo.parse(SRT.format(third=ABSTRACT))}},
           cat, lambda d: sb.build(clips, "", vision=True, voiceover=d.get("voiceover")))
    s2.add({"kind": "direct", "text": "use", "ops": [{"op": "choose_option", "option": "voice"}]},
           cat, lambda d: sb.build(clips, "", vision=True, voiceover=d.get("voiceover")))
    check("the voice proposal can be chosen", s2.board and s2.board["option"] == "voice")
    t = s2.add({"kind": "direct", "text": "fill", "ops": [{"op": "drop_shot", "shot": gaps[0]["key"]}]},
               cat, lambda d: sb.build(clips, "", vision=True, voiceover=d.get("voiceover")))
    check("…and edited like any other", not t.skipped and bd._total(s2.board) == 12.5, f"{bd._total(s2.board)}")

    none = sb.build(clips, "", vision=True)
    check("without a voiceover, nothing changes", [o["key"] for o in none["options"]] == ["time", "place", "subject"])

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

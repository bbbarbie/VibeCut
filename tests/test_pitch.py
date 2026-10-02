"""Suggested descriptions must come from the footage -- and move with it.

Shoots that differ in one respect at a time: one day vs a weekend, morning
to night vs one evening, food vs beach, talking to camera or not. The
lines must follow each difference, never name what wasn't filmed, and
Claude (when asked) only ever sees text facts.

    python tests/test_pitch.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.test_board import _clip  # noqa: E402
from web.backend import llm, pitch  # noqa: E402


def shoot(days=("2026-05-02",), hours=(9, 13, 20), labels=("food",), talking=False, n=4):
    out = []
    for d in days:
        for i, h in enumerate(hours):
            for j in range(n):
                c = _clip(f"c{d[-2:]}{h:02d}{j:02d}00000"[:12], h, [labels[(i + j) % len(labels)]])
                c["capture_time"] = f"{d}T{h:02d}:{j * 5:02d}:00+0900"
                if talking:
                    c["signals"] = {"duration": 12.0, "quality": [0.7] * 12, "sharpness": [0.8] * 12,
                                    "luma": [120.0] * 12, "contrast": [0.8] * 12, "motion": [2.0] * 12,
                                    "subject": [0.8] * 12, "edge": [0.0] * 12, "speech": [0.9] * 12,
                                    "voiced": [], "thumb": [0.0] * 144}
                out.append(c)
    return out


def main() -> int:
    failures = []

    def check(name: str, cond: bool, got: str = "") -> None:
        print(f"  {'PASS' if cond else 'FAIL'}  {name}{': ' + got if got else ''}")
        if not cond:
            failures.append(name)

    def lines(clips):
        return pitch.suggest(clips, ask_model=False)["suggestions"]

    one = lines(shoot())
    check("three lines", len(one) == 3 and len(set(one)) == 3, str(one))
    check("one day, morning to night, says so", one[0].startswith("A day in my life, morning to night"), str(one))
    check("mostly food says food", any("food" in l.lower() or "eating" in l.lower() for l in one), str(one))
    check("nothing about the beach that wasn't filmed", not any("beach" in l.lower() or "water" in l.lower() for l in one))

    wk = lines(shoot(days=("2026-05-02", "2026-05-03")))      # a Saturday and Sunday
    check("two weekend days read as a weekend", wk[0].startswith("A weekend away"), str(wk))
    long = lines(shoot(days=("2026-05-04", "2026-05-05", "2026-05-06", "2026-05-07")))
    check("four days read as days away", long[0].startswith("4 days away"), str(long))
    eve = lines(shoot(hours=(19, 21)))
    check("one evening reads as an evening", eve[0].startswith("An evening out"), str(eve))

    sea = lines(shoot(labels=("beach", "ocean", "sand")))
    check("a beach shoot says water, not food", any("water" in l.lower() or "beach" in l.lower() for l in sea)
          and not any("food" in l.lower() for l in sea), str(sea))
    talk = lines(shoot(talking=True))
    check("talking to camera is noticed", any("talking" in l.lower() for l in talk), str(talk))
    check("and not when nobody talks", not any("talking" in l.lower() for l in one))

    seen = {}
    real = llm.suggest_briefs
    llm.suggest_briefs = lambda text: seen.setdefault("text", text) and ["A", "B", "C"]
    r = pitch.suggest(shoot(), ask_model=True)
    check("with a key, Claude's lines are used", r == {"suggestions": ["A", "B", "C"], "source": "claude"}, str(r))
    check("Claude is shown text facts only", isinstance(seen.get("text"), str) and "labels" in seen["text"])

    def down(text):
        raise llm.LLMError("down")
    llm.suggest_briefs = down
    r = pitch.suggest(shoot(), ask_model=True)
    check("if Claude can't be reached, the footage's own lines stand", r["source"] == "footage" and len(r["suggestions"]) == 3)
    llm.suggest_briefs = real

    bare = lines([dict(c, capture_time=None) for c in shoot(labels=("structure",))])
    check("no dates, nothing clear: still three honest lines", len(bare) == 3, str(bare))

    print(f"\n{'all passed' if not failures else f'{len(failures)} failed'}")
    return 1 if failures else 0


def test_pitch() -> None:
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())

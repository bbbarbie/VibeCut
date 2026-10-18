"""Layer 3: what you undo and what you refuse become suggested rules -- never applied by themselves.

An undone turn of the machine's own (the bed, the captions) and a "no" at
export with a note are offered once; the creator turns one into a rule
for every video (with when / when not) or this video, or dismisses it, and
it doesn't come back. Undone hand edits are not suggested. Decisions
survive a reload.

    python tests/test_learn3.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

failures: list[str] = []


def check(name: str, cond: bool, got: str = "") -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{': ' + got if got else ''}")
    if not cond:
        failures.append(name)


def main() -> int:
    from tests.test_board import PROPOSALS, session
    from web.backend import preferences
    mk = lambda d: PROPOSALS  # noqa: E731
    s, cat = session()
    path = Path(tempfile.mkdtemp(prefix="vibecut-learn3-")) / "preferences.json"
    prefs = preferences.Preferences(path)
    first = s.board["beats"][0]["shots"][0]["id"]
    t_music = s.add({"kind": "direct", "text": "Music and the beat", "ops": [{"op": "set_music", "track": None}]}, cat, mk)
    t_hand = s.add({"kind": "direct", "text": "You removed a shot", "ops": [{"op": "drop_shot", "shot": first}]}, cat, mk)
    check("nothing suggested before anything is undone", prefs.suggestions(s) == [])
    s.toggle(t_music.id, cat, mk)
    s.toggle(t_hand.id, cat, mk)
    sug = prefs.suggestions(s, [{"verdict": {"post": False, "note": "the ending drags"}}, {"verdict": {"post": True, "note": "great"}}])
    check("an undone machine turn and a no at export are suggested; a hand undo and a yes are not",
          [x["source"] for x in sug] == ["undo", "verdict"] and sug[0]["rule"].startswith("No music") and sug[1]["rule"] == "the ending drags",
          json.dumps(sug))
    try:
        prefs.take(sug[0]["id"], "long_term", "user", rule="No music unless I ask")
        check("every video needs when and when not", False)
    except preferences.PreferenceError as e:
        check("every video needs when and when not", "when" in str(e))
    d = prefs.take(sug[0]["id"], "long_term", "user", rule="No music unless I ask", scope="every video", counter="when I pick a vibe")
    check("taken for every video: a rule exists and the model sees it", d.get("rule_id") and "No music unless I ask" in prefs.for_model(), prefs.for_model()[:80])
    prefs.take(sug[1]["id"], "rejected", "user")
    check("decided ones don't come back", prefs.suggestions(s, [{"verdict": {"post": False, "note": "the ending drags"}}]) == [])
    try:
        prefs.take(sug[1]["id"], "project", "user", rule="x")
        check("a decision is final", False)
    except preferences.PreferenceError:
        check("a decision is final", True)
    again = preferences.Preferences(path)
    check("decisions and the rule survive a reload", again.suggested.keys() == prefs.suggested.keys() and any(r["rule"] == "No music unless I ask" for r in again.rules))
    check("the public view carries them", "suggestions" in prefs.public(s, []))

    print()
    if failures:
        print(f"{len(failures)} failed: {failures}")
        return 1
    print("all passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

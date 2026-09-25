"""An edit is not a taste until the creator says so.

Two sessions that differ in exactly one respect -- whether the creator
sorted an edit as "always" -- must differ in exactly one respect afterwards:
whether a rule exists and reaches the model. Everything that should *not*
teach (silence, a "system" confirmation, an undone edit, a rule without its
limits) is tried and must leave nothing behind.

    python tests/test_preferences.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

from test_board import PROPOSALS, session  # noqa: E402

from web.backend.preferences import PreferenceError, Preferences, says_keep  # noqa: E402

mk = lambda d: PROPOSALS  # noqa: E731
DROP_MARKET = {"kind": "chat", "text": "cut the market, it's boring",
               "ops": [{"op": "drop_beat", "beat": "t2"}]}
TIGHTEN = {"kind": "chat", "text": "openings should be quick — from now on",
           "ops": [{"op": "set_pace", "beat": "t1", "direction": "tighter", "amount": "a_lot"}]}


def main() -> int:
    failures = []

    def check(name: str, cond: bool, got: str = "") -> None:
        print(f"  {'PASS' if cond else 'FAIL'}  {name}{': ' + got if got else ''}")
        if not cond:
            failures.append(name)

    def raises(fn) -> str | None:
        try:
            fn()
        except PreferenceError as e:
            return str(e)
        return None

    with tempfile.TemporaryDirectory() as d:
        store = Path(d) / "preferences.json"
        s, cat = session()
        p = Preferences(store)
        a = s.add(DROP_MARKET, cat, mk)
        b = s.add(TIGHTEN, cat, mk)

        c = {x["turn"]: x for x in p.candidates(s)}
        check("each edit becomes a candidate; choosing a proposal does not",
              sorted(c) == [a.id, b.id], str(sorted(c)))
        check("a candidate carries the computed before/after and the words",
              c[a.id]["lines"] and c[a.id]["said"] == DROP_MARKET["text"], " | ".join(c[a.id]["lines"]))
        check("nothing is learned by silence", not p.active() and p.for_model() == "" and not store.exists())
        check("'from now on' only suggests", c[b.id]["suggested"] == "long_term" and c[b.id]["status"] == "candidate")
        check("a plain edit suggests nothing lasting", c[a.id]["suggested"] == "single_edit")

        check("the system can't confirm", raises(lambda: p.classify(s, b.id, "long_term", "system",
              "quick openings", "any trip vlog", "not a slow-cinema piece")) is not None)
        check("'always' needs where it applies and where it doesn't",
              raises(lambda: p.classify(s, b.id, "long_term", "user", "quick openings")) is not None)
        check("a learned rule needs words", raises(lambda: p.classify(s, a.id, "project", "user")) is not None)

        s.toggle(a.id, cat, mk)
        check("an undone edit can't be confirmed",
              raises(lambda: p.classify(s, a.id, "project", "user", "no markets")) is not None)
        s.toggle(a.id, cat, mk)

        p.classify(s, a.id, "single_edit", "user")
        check("'just this once' is recorded but teaches nothing", not p.active()
              and {x["turn"]: x for x in p.candidates(s)}[a.id]["status"] == "confirmed")

        p.classify(s, b.id, "long_term", "user", "Keep openings quick", "trip vlogs", "slow, quiet pieces")
        rules = p.for_model()
        check("a confirmed rule reaches the model, with its limits",
              "Keep openings quick" in rules and "slow, quiet pieces" in rules and "market" not in rules.lower(), rules)
        check("confirming twice is refused",
              raises(lambda: p.classify(s, b.id, "long_term", "user", "x", "y", "z")) is not None)

        again = Preferences(store)
        check("an every-video rule survives a restart", [r["rule"] for r in again.active()] == ["Keep openings quick"])

        s2, cat2 = session()
        p2 = Preferences(Path(d) / "other.json")
        t2 = s2.add({"kind": "chat", "text": "blur that kid's face out — cut it", "ops": [{"op": "drop_beat", "beat": "t3"}]}, cat2, mk)
        p2.classify(s2, t2.id, "compliance_fix", "user")
        check("a privacy fix is never taste", not p2.active() and p2.for_model() == "")

        s3, cat3 = session()
        p3 = Preferences(Path(d) / "p3.json")
        e = s3.add(DROP_MARKET, cat3, mk)
        s3.add({"kind": "chat", "text": "以后也这样", "ops": []}, cat3, mk)
        check("'以后也这样' after an edit suggests keeping that edit",
              p3.candidates(s3)[0]["suggested"] == "long_term" and p3.candidates(s3)[0]["turn"] == e.id)
        p3.classify(s3, e.id, "project", "user", "Skip the market footage")
        check("a this-video rule is not written to disk", not (Path(d) / "p3.json").exists())
        p3.new_project()
        check("…and is gone with the project", not p3.active())

        rid = again.active()[0]["id"]
        again.narrow(rid, "user")
        check("narrowing keeps the every-video record, retired",
              [r["klass"] for r in again.active()] == ["project"]
              and not Preferences(store).active() and len(Preferences(store).rules) == 1
              and Preferences(store).rules[0]["history"][-1]["action"] == "narrowed")
        again.revoke(again.active()[0]["id"], "user")
        check("forgetting leaves nothing active", not again.active() and again.for_model() == "")

    check("keep phrases", says_keep("以后都这样剪") and says_keep("Always do this") and not says_keep("cut the market"))

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""The single gate: nothing passes the rough cut without a person saying so.

    python tests/test_workflow.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web.backend.workflow import Workflow, WorkflowError  # noqa: E402


def main() -> int:
    failures = []

    def check(name: str, cond: bool, got: str = "") -> None:
        print(f"  {'PASS' if cond else 'FAIL'}  {name}{': ' + got if got else ''}")
        if not cond:
            failures.append(name)

    def raises(fn) -> str | None:
        try:
            fn()
        except WorkflowError as e:
            return str(e)
        return None

    w = Workflow()
    for s in ("indexing", "rough-cut", "cut-review"):
        w.advance(s)
    check("reaches the gate and waits", w.state == "cut-review" and w.decision == "pending")
    check("can't walk past the gate without approval", raises(lambda: w.advance("story")) is not None,
          raises(lambda: w.advance("story")) or "")
    check("the system can't approve", raises(lambda: w.approve("system")) is not None)
    check("can't skip states", raises(lambda: Workflow().advance("story")) is not None)
    w.revise("user", "keep IMG_4471")
    check("an override at the gate stays at the gate", w.state == "cut-review" and w.decision == "pending")
    w.approve("user", "looks right")
    check("a person's approval moves it on", w.state == "story" and w.decision == "approved")
    w.reopen("system", "3 new clips")
    check("new material after approval reopens the gate",
          w.state == "cut-review" and w.decision == "pending" and w.revision == 1)
    acts = [(h["action"], h["actor"]) for h in w.history]
    check("every step is in the history, with who did it",
          ("approve", "user") in acts and ("revise", "user") in acts and ("reopen", "system") in acts,
          f"{len(acts)} entries")

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

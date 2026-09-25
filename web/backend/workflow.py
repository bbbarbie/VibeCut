"""Where the edit is, and the one place it stops for a person.

The staged structure and the single human gate are adapted from the workflow
state machine in cut-motion (github.com/Endless1936/cut-motion, Apache-2.0;
see NOTICE): one authoritative state; it moves only by an explicit
transition, never because the next artifact happens to exist; exactly one
approval gate; every decision recorded with who made it; silence is never
approval; and a later change that touches what was approved reopens the
gate rather than slipping past it.

What VibeCut does *not* take from it is the transcript as spine -- vlog
footage has none. The gate here is the rough cut: what reject and trim
threw away, and why.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

ROUTE = ["intake", "indexing", "rough-cut", "cut-review", "story", "styling"]
GATE = "cut-review"


class WorkflowError(Exception):
    pass


@dataclass
class Workflow:
    state: str = "intake"
    decision: str | None = None        # at the gate: "pending" | "approved"
    revision: int = 0
    history: list[dict] = field(default_factory=list)

    def _log(self, action: str, to: str, actor: str, note: str) -> None:
        self.history.append({"at": time.time(), "action": action, "from": self.state, "to": to,
                             "actor": actor, "note": note, "revision": self.revision})

    def advance(self, to: str, note: str = "", actor: str = "system") -> None:
        """Move forward one state (or re-enter the current one)."""
        if to not in ROUTE:
            raise WorkflowError(f"unknown state {to!r}")
        i, j = ROUTE.index(self.state), ROUTE.index(to)
        if j > i + 1 or j < i:
            raise WorkflowError(f"can't go from {self.state} to {to}")
        if self.state == GATE and to != GATE and self.decision != "approved":
            raise WorkflowError("the rough cut hasn't been approved")
        self._log("advance", to, actor, note)
        self.state = to
        if to == GATE:
            self.decision = "pending"

    def approve(self, actor: str, note: str = "") -> None:
        """The gate. Only a person, only here, only explicitly."""
        if self.state != GATE:
            raise WorkflowError(f"nothing to approve in {self.state}")
        if actor != "user":
            raise WorkflowError("only the user can approve the rough cut")
        self.decision = "approved"
        self._log("approve", GATE, actor, note)
        self.advance("story", "rough cut approved", actor)

    def revise(self, actor: str, note: str) -> None:
        """A person overrode a decision. At the gate it stays at the gate;
        after it, the override is their decision and is recorded as such."""
        self._log("revise", self.state, actor, note)

    def reopen(self, actor: str, note: str) -> None:
        """New material or a changed plan after approval: back to the gate."""
        if ROUTE.index(self.state) <= ROUTE.index(GATE):
            return
        self.revision += 1
        self._log("reopen", GATE, actor, note)
        self.state, self.decision = GATE, "pending"

    def public(self) -> dict:
        return {"state": self.state, "gate": GATE, "decision": self.decision,
                "revision": self.revision, "history": self.history[-20:]}

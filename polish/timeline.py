"""The layers over a finished edit, as a turn log: apply, diff, undo.

Same rule as the storyboard (web/backend/board.py): a sentence never
regenerates anything, it becomes operations applied by deterministic code,
and the layers are a pure function of the log. Undo any turn = replay the
log without it; an operation that no longer makes sense is skipped and
reported, never guessed. Whatever is decided at apply time -- which caption
"this one" meant, where an effect snapped to, the recipe's settings at that
moment -- is written into the recorded op, so replay is exact even after
the recipe file changes.

Operations:
    add_caption {text, anchor, recipe, dur?}   -> id recorded
    edit_caption {id, text?, scale?, recipe?}  (scale multiplies)
    drop_caption {id}
    add_effect {kind, anchor, t, why}          -> id recorded (t already snapped)
    drop_effect {id}
"""

from __future__ import annotations

import copy
import time
from dataclasses import dataclass, field

EFFECTS = {"boom": 0.4}      # kind -> length in seconds
OPS = ("add_caption", "edit_caption", "drop_caption", "add_effect", "drop_effect")
MIN_SCALE, MAX_SCALE = 0.5, 2.5


class OpError(Exception):
    pass


def empty() -> dict:
    return {"captions": [], "effects": []}


def _find(items: list[dict], iid: str | None, what: str) -> dict:
    for x in items:
        if x["id"] == iid:
            return x
    raise OpError(f"that {what} isn't there any more")


def apply(state: dict, op: dict, new_id) -> tuple[dict, dict]:
    kind = op.get("op")
    if kind not in OPS:
        raise OpError(f"unknown operation {kind!r}")
    s = copy.deepcopy(state)
    op = dict(op)
    if kind == "add_caption":
        text = (op.get("text") or "").strip()
        if not text:
            raise OpError("a caption needs words")
        if not op.get("recipe"):
            raise OpError("a caption needs a style")
        a = op["anchor"]
        op.setdefault("id", new_id("c"))
        dur = float(op.get("dur") or op["recipe"].get("hold_s", 3.0))
        s["captions"].append({"id": op["id"], "text": text[:120], "t": float(a["t"]), "dur": round(dur, 3),
                              "anchor": a, "recipe": op["recipe"], "scale": 1.0})
    elif kind == "edit_caption":
        c = _find(s["captions"], op.get("id"), "caption")
        if op.get("text"):
            c["text"] = op["text"].strip()[:120]
        if op.get("scale"):
            c["scale"] = round(min(max(c["scale"] * float(op["scale"]), MIN_SCALE), MAX_SCALE), 3)
        if op.get("recipe"):
            c["recipe"] = op["recipe"]
            c["scale"] = 1.0
    elif kind == "drop_caption":
        c = _find(s["captions"], op.get("id"), "caption")
        s["captions"].remove(c)
    elif kind == "add_effect":
        if op.get("kind") not in EFFECTS:
            raise OpError(f"no effect called {op.get('kind')!r}")
        op.setdefault("id", new_id("e"))
        s["effects"].append({"id": op["id"], "kind": op["kind"], "t": float(op["t"]), "dur": EFFECTS[op["kind"]],
                             "anchor": op["anchor"], "why": op.get("why", "")})
    elif kind == "drop_effect":
        e = _find(s["effects"], op.get("id"), "effect")
        s["effects"].remove(e)
    s["captions"].sort(key=lambda c: (c["t"], c["id"]))
    s["effects"].sort(key=lambda e: (e["t"], e["id"]))
    return s, op


def diff(a: dict, b: dict) -> dict:
    out = {}
    for layer in ("captions", "effects"):
        A = {x["id"]: x for x in a[layer]}
        B = {x["id"]: x for x in b[layer]}
        out[layer] = {"added": [B[k] for k in B if k not in A], "removed": [A[k] for k in A if k not in B],
                      "changed": [(A[k], B[k]) for k in B if k in A and A[k] != B[k]]}
    return out


def _mmss(t: float) -> str:
    return f"{int(t // 60)}:{t % 60:04.1f}"


def describe(d: dict, placed: dict | None = None) -> list[dict]:
    """The diff in words. `placed`: caption id -> its placement (for 'moved')."""
    placed = placed or {}
    lines = []
    for c in d["captions"]["added"]:
        p = placed.get(c["id"]) or {}
        extra = f" — {p['moved']}" if p.get("moved") else ""
        lines.append({"kind": "added", "id": c["id"],
                      "text": f"Added “{c['text']}” at {_mmss(c['t'])} in your “{c['recipe']['name']}” style{extra}"})
    for c in d["captions"]["removed"]:
        lines.append({"kind": "removed", "id": c["id"], "text": f"Removed “{c['text']}”"})
    for a, b in d["captions"]["changed"]:
        what = []
        if a["text"] != b["text"]:
            what.append(f"now reads “{b['text']}”")
        if a["scale"] != b["scale"] and a["recipe"] == b["recipe"]:
            what.append(f"{'bigger' if b['scale'] > a['scale'] else 'smaller'} ({b['scale']:.0%} of the recipe)")
        if a["recipe"] != b["recipe"]:
            what.append(f"now in your “{b['recipe']['name']}” style")
        p = placed.get(b["id"]) or {}
        if p.get("moved"):
            what.append(p["moved"])
        lines.append({"kind": "changed", "id": b["id"], "text": f"“{b['text']}”: " + ", ".join(what or ["changed"])})
    for e in d["effects"]["added"]:
        lines.append({"kind": "added", "id": e["id"], "text": f"Boom at {_mmss(e['t'])}, {e['why']}"})
    for e in d["effects"]["removed"]:
        lines.append({"kind": "removed", "id": e["id"], "text": f"Removed the boom at {_mmss(e['t'])}"})
    return lines or [{"kind": "none", "text": "No change"}]


@dataclass
class Turn:
    id: int
    said: str
    anchor: dict | None
    ops: list[dict]
    reply: str = ""
    undone: bool = False
    at: float = field(default_factory=time.time)
    skipped: list[str] = field(default_factory=list)
    lines: list[dict] = field(default_factory=list)


class Session:
    """One finished video's layers. `placer(state)` -> {caption id: placement}
    lets the diff say where a caption actually went."""

    def __init__(self, placer=None) -> None:
        self.turns: list[Turn] = []
        self.state = empty()
        self._next = 1
        self.placer = placer

    def replay(self) -> None:
        state = empty()
        for t in self.turns:
            if t.undone:
                continue
            before = state
            t.skipped, rec = [], []
            for k, op in enumerate(t.ops):
                try:
                    state, r = apply(state, op, lambda p, t=t, k=k: f"{p}{t.id}{chr(97 + k)}")
                    rec.append(r)
                except OpError as e:
                    t.skipped.append(str(e))
                    rec.append(op)
            t.ops = rec
            placed = self.placer(state) if self.placer else {}
            t.lines = describe(diff(before, state), placed)
        self.state = state

    def add(self, said: str, anchor: dict | None, ops: list[dict], reply: str = "") -> Turn:
        t = Turn(id=self._next, said=said, anchor=anchor, ops=ops, reply=reply)
        self._next += 1
        self.turns.append(t)
        self.replay()
        return t

    def toggle(self, tid: int) -> None:
        for t in self.turns:
            if t.id == tid:
                t.undone = not t.undone
        self.replay()

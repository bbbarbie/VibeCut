"""The working storyboard, and the operations that edit it.

The rule this module exists for: a conversation *edits* a storyboard, it
never regenerates one. "The opening is too slow" changes the opening and
leaves everything else exactly where the creator put it. Regenerating loses
their edits and makes the tool feel random.

So the storyboard is a pure function of a turn log: each turn is a list of
operations, applied in order by deterministic code. Undoing any turn --
not just the last -- is replaying the log without it. An operation that no
longer makes sense after an undo (it touched a beat that turn created) is
skipped and reported, never guessed at.

Operations reference beats and shots by stable id. Anything decided at
apply time (which shelf shot replaces another, what a proposal looked like
when it was chosen) is written back into the recorded op, so replay is
exact even after the proposals or the shelf change.
"""

from __future__ import annotations

import copy
import time
from dataclasses import dataclass, field

import numpy as np

from . import overlays as ov
from . import restyle
from . import storyboard as sb

# Pace. Trimming keeps each shot centred on its best frame, so a tighter
# section loses handling and dead air before it loses the moment.
PACE = {("tighter", "a_little"): 0.75, ("tighter", "a_lot"): 0.5,
        ("looser", "a_little"): 1.33, ("looser", "a_lot"): 2.0}
MIN_SHOT_S = 1.5

# What the chat model may emit.
LLM_OPS = ("choose_option", "move_beat", "drop_beat", "drop_shot", "swap_shot",
           "add_shot", "move_shot", "retitle_beat", "set_pace", "open_with", "end_with",
           "add_overlay", "edit_overlay", "drop_overlay")
# Plus the precise timeline edits, which come from the keyboard, never from
# a sentence: cut at a point, trim an edge to a point, remove a range.
OPS = LLM_OPS + ("split", "trim", "drop_range", "overlay_style", "apply_style")
# Words on screen (overlays.py): same log, same undo, but they never touch a shot.
OVERLAY_OPS = ("add_overlay", "edit_overlay", "drop_overlay", "overlay_style")

FRAME = 1 / 30  # sequence frame; the smallest piece a cut or trim may leave


# A storyboard entry is {"id": source shot, "start", "end"} in source seconds,
# optionally with "key" when one source shot appears more than once (after a
# cut). A gap is {"key", "id": None, "gap": True, "start": 0, "end": length}:
# same duration arithmetic, nothing to show.
def key(e: dict) -> str:
    return e.get("key") or e["id"]


def is_gap(e: dict) -> bool:
    return bool(e.get("gap"))


def _gap(k: str, dur: float) -> dict:
    return {"key": k, "id": None, "gap": True, "start": 0.0, "end": round(dur, 3)}


class OpError(Exception):
    pass


# --------------------------------------------------------------------------
# catalogue: every shot on the shelf, with what the ops need to know
# --------------------------------------------------------------------------

@dataclass
class Catalog:
    shots: dict[str, sb.Shot]
    best_t: dict[str, float]

    @classmethod
    def from_clips(cls, clips: list[dict]) -> "Catalog":
        shots = {s.id: s for s in sb.shots_from_clips(clips)}
        best = {f"{c['id']}:{s['index']}": s["best_t"] for c in clips for s in c["shots"]}
        return cls(shots, best)

    def get(self, sid: str) -> sb.Shot:
        if sid not in self.shots:
            raise OpError(f"no shot {sid} on the shelf")
        return self.shots[sid]


def board_from_option(option: dict) -> dict:
    prefix = option["key"][0]
    return {
        "option": option["key"],
        "name": option["name"],
        "structure": option["summary"],
        "beats": [{
            "id": f"{prefix}{i + 1}",
            "title": b["title"],
            "detail": b["detail"],
            **({"line": b["line"]} if b.get("line") else {}),
            # a voiceover line nothing shows stays a gap of its length
            "shots": [_gap(s["key"], s["end"] - s["start"]) if s.get("gap")
                      else {"id": s["id"], "start": s["start"], "end": s["end"]} for s in b["shots"]],
        } for i, b in enumerate(option["beats"])],
    }


# --------------------------------------------------------------------------
# lookups
# --------------------------------------------------------------------------

def _beat(board: dict, bid: str | None) -> dict:
    for b in board["beats"]:
        if b["id"] == bid:
            return b
    raise OpError(f"no beat {bid}")


def _where(board: dict, sid: str | None) -> tuple[dict, int]:
    for b in board["beats"]:
        for i, s in enumerate(b["shots"]):
            if key(s) == sid:
                return b, i
    raise OpError(f"shot {sid} is not in the storyboard")


def _on_board(board: dict) -> set[str]:
    return {s["id"] for b in board["beats"] for s in b["shots"] if s["id"]}


def _keys(board: dict) -> set[str]:
    return {key(s) for b in board["beats"] for s in b["shots"]}


def _fresh_key(board: dict, base: str) -> str:
    keys, k, n = _keys(board), base, 2
    while k in keys:
        k, n = f"{base}.{n}", n + 1
    return k


def _flat(board: dict) -> list[tuple[dict, int, float]]:
    """(beat, index, sequence start) for every entry, in playing order."""
    out, t = [], 0.0
    for b in board["beats"]:
        for i, s in enumerate(b["shots"]):
            out.append((b, i, t))
            t += s["end"] - s["start"]
    return out


def seq_start(board: dict, k: str) -> float | None:
    for b, i, t in _flat(board):
        if key(b["shots"][i]) == k:
            return t
    return None


def _split(board: dict, k: str, at: float) -> str | None:
    """Cut entry `k` at source time `at`. Returns the second piece's key,
    or None when `at` is already an edge (nothing to cut)."""
    beat, i = _where(board, k)
    e = beat["shots"][i]
    if abs(at - e["start"]) < FRAME / 2 or abs(at - e["end"]) < FRAME / 2:
        return None
    if is_gap(e):
        raise OpError("a gap can't be cut — delete it instead")
    if not (e["start"] < at < e["end"]):
        raise OpError(f"{at:.2f}s is outside that shot ({e['start']:.2f}–{e['end']:.2f}s)")
    second = {"key": _fresh_key(board, f"{e['id']}~{int(round(at * 1000))}"), "id": e["id"],
              "start": round(at, 3), "end": e["end"]}
    e["end"] = round(at, 3)
    beat["shots"].insert(i + 1, second)
    return second["key"]


def _insert_at(beat: dict, entry: dict, op: dict) -> None:
    """Insert before `op.before` (a shot id) if given, else at `op.to_index`, else at the end."""
    if op.get("before"):
        for i, s in enumerate(beat["shots"]):
            if key(s) == op["before"]:
                beat["shots"].insert(i, entry)
                return
        raise OpError(f"shot {op['before']} is not in beat {beat['id']}")
    k = op.get("to_index")
    k = len(beat["shots"]) if k is None else max(0, min(int(k), len(beat["shots"])))
    beat["shots"].insert(k, entry)


def _span(cat: Catalog, sid: str, dur: float) -> tuple[float, float]:
    """A window of `dur` seconds inside the shot, centred on its best frame."""
    s = cat.get(sid)
    dur = max(min(dur, s.end - s.start), min(MIN_SHOT_S, s.end - s.start))
    c = cat.best_t.get(sid, (s.start + s.end) / 2)
    a = min(max(s.start, c - dur / 2), s.end - dur)
    return round(a, 3), round(a + dur, 3)


def _prune(board: dict) -> None:
    board["beats"] = [b for b in board["beats"] if b["shots"]]


# --------------------------------------------------------------------------
# apply
# --------------------------------------------------------------------------

def apply(board: dict | None, op: dict, cat: Catalog, proposals: dict | None,
          new_id: callable) -> tuple[dict | None, dict]:
    """Apply one op to a copy of `board`. Returns (board, op as recorded)."""
    kind = op.get("op")
    if kind not in OPS:
        raise OpError(f"unknown operation {kind!r}")
    # null means "not given" -- except an overlay's length, where it means
    # "as long as what it hangs off" (a caption filling its spoken line).
    op = {k: v for k, v in op.items() if v is not None or (k == "dur" and kind in OVERLAY_OPS)}

    if kind == "choose_option":
        snap = op.get("snapshot")
        if snap is None:
            opts = {o["key"]: o for o in (proposals or {}).get("options", [])}
            if op.get("option") not in opts:
                raise OpError(f"no proposal {op.get('option')!r} to choose")
            snap = board_from_option(opts[op["option"]])
            op["snapshot"] = snap
        return copy.deepcopy(snap), op

    if board is None:
        if kind not in ("add_shot", "open_with", "end_with"):
            raise OpError("there is no storyboard yet — choose one of the proposals first")
        # Dragging a shot onto an empty timeline starts a hand-built storyboard.
        board = {"option": "manual", "name": "Your cut", "structure": "Built by hand from the shelf.",
                 "beats": []}
    b = copy.deepcopy(board)

    if kind in OVERLAY_OPS:
        try:
            {"add_overlay": lambda: ov.add(b, op, new_id), "edit_overlay": lambda: ov.edit(b, op),
             "drop_overlay": lambda: ov.drop(b, op), "overlay_style": lambda: ov.set_style(b, op)}[kind]()
        except (ov.OverlayError, ValueError, TypeError) as e:
            raise OpError(str(e)) from e
        return b, op

    if kind == "apply_style":
        # A borrowed style (restyle.py): retimes shots, and records the look
        # and transitions for export. Comes from the style card, never chat.
        try:
            restyle.apply(b, op, cat)
        except restyle.StyleError as e:
            raise OpError(str(e)) from e
        return b, op

    if kind == "move_beat":
        beat = _beat(b, op.get("beat"))
        b["beats"].remove(beat)
        k = max(0, min(int(op.get("to_index", 0)), len(b["beats"])))
        b["beats"].insert(k, beat)

    elif kind == "drop_beat":
        b["beats"].remove(_beat(b, op.get("beat")))

    elif kind == "drop_shot":
        beat, i = _where(b, op.get("shot"))
        e = beat["shots"].pop(i)
        if op.get("leave_gap") and not is_gap(e):  # lift: keep everything after in place
            beat["shots"].insert(i, _gap(f"gap~{key(e)}", e["end"] - e["start"]))
        _prune(b)

    elif kind == "split":
        if _split(b, op.get("shot"), float(op.get("at", -1))) is None:
            raise OpError("that point is already a cut")

    elif kind == "trim":
        beat, i = _where(b, op.get("shot"))
        e = beat["shots"][i]
        if is_gap(e):
            raise OpError("trim a shot, not a gap")
        src = cat.get(e["id"])
        to, edge = float(op.get("to", 0)), op.get("edge")
        if edge == "in":
            to = max(src.start, min(to, e["end"] - FRAME))
            removed, e["start"] = to - e["start"], round(to, 3)
            if op.get("leave_gap") and removed > FRAME / 2:
                beat["shots"].insert(i, _gap(f"gap~in~{key(e)}", removed))
        elif edge == "out":
            to = min(src.end, max(to, e["start"] + FRAME))
            removed, e["end"] = e["end"] - to, round(to, 3)
            if op.get("leave_gap") and removed > FRAME / 2:
                beat["shots"].insert(i + 1, _gap(f"gap~out~{key(e)}", removed))
        else:
            raise OpError("trim needs edge 'in' or 'out'")

    elif kind == "drop_range":
        # Both ends are (entry, source time), so replay can't drift.
        t0 = seq_start(b, op.get("from_shot"))
        t1 = seq_start(b, op.get("to_shot"))
        if t0 is None or t1 is None:
            raise OpError("the marked range refers to a shot that's no longer there")
        f_e = _where(b, op["from_shot"])
        t_e = _where(b, op["to_shot"])
        a = t0 + float(op["from_at"]) - f_e[0]["shots"][f_e[1]]["start"]
        z = t1 + float(op["to_at"]) - t_e[0]["shots"][t_e[1]]["start"]
        if z - a < FRAME / 2:
            raise OpError("mark an out point after the in point")
        k2 = _split(b, op["to_shot"], float(op["to_at"]))
        _split(b, op["from_shot"], float(op["from_at"]))
        doomed = []
        for bt, i, t in _flat(b):
            e = bt["shots"][i]
            if t >= a - FRAME / 2 and t + (e["end"] - e["start"]) <= z + FRAME / 2:
                doomed.append((bt, key(e)))
        if not doomed:
            raise OpError("nothing inside that range")
        first_beat, first_i = _where(b, doomed[0][1])
        for bt, k in doomed:
            bt["shots"] = [x for x in bt["shots"] if key(x) != k]
        if op.get("leave_gap"):
            first_beat["shots"].insert(min(first_i, len(first_beat["shots"])),
                                       _gap(f"gap~{doomed[0][1]}", z - a))
        _prune(b)
        del k2

    elif kind == "retitle_beat":
        title = (op.get("title") or "").strip()
        if not title:
            raise OpError("a new title is needed")
        _beat(b, op.get("beat"))["title"] = title

    elif kind == "set_pace":
        beat = _beat(b, op.get("beat"))
        pace = (op.get("direction", "tighter"), op.get("amount", "a_little"))
        if pace not in PACE:
            raise OpError(f"pace must be tighter/looser, a_little/a_lot, not {pace}")
        f = PACE[pace]
        for s in beat["shots"]:
            if not is_gap(s):
                s["start"], s["end"] = _span(cat, s["id"], (s["end"] - s["start"]) * f)

    elif kind == "swap_shot":
        beat, i = _where(b, op.get("shot"))
        old = beat["shots"][i]
        if is_gap(old):
            raise OpError("that's a gap, not a shot")
        with_id = op.get("with_shot") or _better_than(b, cat, old["id"])
        if with_id in _on_board(b):
            raise OpError(f"shot {with_id} is already in the storyboard")
        a, e = _span(cat, with_id, old["end"] - old["start"])  # keep the slot's length
        beat["shots"][i] = {"id": with_id, "start": a, "end": e}
        op["with_shot"] = with_id

    elif kind in ("add_shot", "move_shot"):
        sid = op.get("shot")
        if kind == "add_shot":
            s = cat.get(sid)
            if sid in _on_board(b):
                raise OpError(f"shot {sid} is already in the storyboard")
            entry = {"id": sid, "start": s.start, "end": s.end}
        else:
            src, i = _where(b, sid)
            entry = src["shots"].pop(i)
        if op.get("beat"):
            target = _beat(b, op["beat"])
        elif b["beats"]:
            target = b["beats"][-1]
        else:
            target = {"id": new_id(), "title": "New", "detail": "", "shots": []}
            b["beats"].append(target)
            op["beat"] = target["id"]
        _insert_at(target, entry, op)
        _prune(b)

    elif kind in ("open_with", "end_with"):
        sid = op.get("shot")
        if sid in _keys(b):
            src, i = _where(b, sid)
            entry = src["shots"].pop(i)
        else:
            s = cat.get(sid)
            entry = {"id": sid, "start": s.start, "end": s.end}
        if not b["beats"]:
            b["beats"].append({"id": new_id(), "title": "Opening", "detail": "", "shots": []})
        if kind == "open_with":
            b["beats"][0]["shots"].insert(0, entry)
        else:
            b["beats"][-1]["shots"].append(entry)
        _prune(b)

    ov.prune(b)  # overlays go with what they hang off
    return b, op


def _better_than(board: dict, cat: Catalog, sid: str) -> str:
    """The shelf shot that could stand in for `sid`: looks like it, but better made."""
    cur = cat.get(sid)
    used = _on_board(board)
    best, best_v = None, -1e9
    for c in cat.shots.values():
        if c.id in used or c.utility:
            continue
        sim = float(np.dot(cur.vec, c.vec)) if cur.vec.shape == c.vec.shape else 0.0
        gain = c.score - cur.score
        if gain <= 0:
            continue
        v = 0.6 * sim + 0.4 * gain
        if v > best_v:
            best, best_v = c.id, v
    if best is None:
        raise OpError("nothing on the shelf is better made than that shot")
    return best


# --------------------------------------------------------------------------
# diff
# --------------------------------------------------------------------------

def _stay_put(seq: list[str], order: dict[str, int]) -> set[str]:
    """Longest run of items already in relative order -- everything else 'moved'."""
    import bisect
    keys = [order[x] for x in seq]
    tails, idx, prev = [], [], [-1] * len(keys)
    for i, k in enumerate(keys):
        j = bisect.bisect_left([keys[t] for t in tails], k)
        if j == len(tails):
            tails.append(i)
        else:
            tails[j] = i
        prev[i] = tails[j - 1] if j else -1
    keep, i = set(), tails[-1] if tails else -1
    while i >= 0:
        keep.add(seq[i])
        i = prev[i]
    return keep


def _total(board: dict | None) -> float:
    return sum(e["end"] - e["start"] for bt in (board or {}).get("beats", []) for e in bt["shots"])


def diff(a: dict | None, b: dict | None) -> dict:
    """What changed from a to b, at beat and shot level."""
    A = a["beats"] if a else []
    B = b["beats"] if b else []
    ab = {x["id"]: x for x in A}
    bb = {x["id"]: x for x in B}
    out = {"beats": {"removed": [], "added": [], "moved": [], "retitled": []},
           "shots": {"removed": [], "added": [], "moved": [], "trimmed": []},
           "replaced": (a or {}).get("option") != (b or {}).get("option") or (a is None) != (b is None),
           "total": [round(_total(a), 3), round(_total(b), 3)]}

    common = [x["id"] for x in B if x["id"] in ab]
    stay = _stay_put(common, {x["id"]: i for i, x in enumerate(A)})
    for x in A:
        if x["id"] not in bb:
            out["beats"]["removed"].append({"id": x["id"], "title": x["title"], "n": len(x["shots"]),
                                            "dur": sum(s["end"] - s["start"] for s in x["shots"])})
    for i, x in enumerate(B):
        if x["id"] not in ab:
            out["beats"]["added"].append({"id": x["id"], "title": x["title"]})
        else:
            if x["id"] not in stay:
                out["beats"]["moved"].append({"id": x["id"], "title": x["title"], "to": i})
            if ab[x["id"]]["title"] != x["title"]:
                out["beats"]["retitled"].append({"id": x["id"], "from": ab[x["id"]]["title"], "to": x["title"]})

    def flat(beats):
        return [(bt["id"], s) for bt in beats for s in bt["shots"]]
    fa, fb = flat(A), flat(B)
    sa = {key(s): (bid, s) for bid, s in fa}
    sb_ = {key(s): (bid, s) for bid, s in fb}
    removed_beats = {r["id"] for r in out["beats"]["removed"]}
    before_ids = {s["id"] for _, s in fa if s["id"]}
    for bid, s in fa:
        if key(s) not in sb_:
            out["shots"]["removed"].append({"id": key(s), "beat": bid, "with_beat": bid in removed_beats,
                                            "gap": is_gap(s), "dur": round(s["end"] - s["start"], 2)})
    common = [key(s) for _, s in fb if key(s) in sa]
    stay = _stay_put(common, {key(s): i for i, (_, s) in enumerate(fa)})
    for bid, s in fb:
        k = key(s)
        if k not in sa:
            out["shots"]["added"].append({
                "id": k, "beat": bid, "gap": is_gap(s), "dur": round(s["end"] - s["start"], 2),
                # a new piece of a shot that was already there = a cut
                "split": bool(s["id"]) and s["id"] in before_ids and b is not None,
                "at": seq_start(b, k)})
            continue
        obid, os_ = sa[k]
        if obid != bid or k not in stay:
            out["shots"]["moved"].append({"id": k, "beat": bid, "from_beat": obid})
        d0, d1 = os_["end"] - os_["start"], s["end"] - s["start"]
        if abs(d0 - d1) > 0.02:
            out["shots"]["trimmed"].append({"id": k, "beat": bid, "from": round(d0, 2), "to": round(d1, 2)})
    return out


def describe(d: dict, a: dict | None, b: dict | None, ops: list[dict] | None = None) -> list[dict]:
    """The diff as short lines a creator can read, grouped by beat."""
    title = {x["id"]: x["title"] for x in ((a or {}).get("beats", []) + (b or {}).get("beats", []))}
    lines = []
    # A marked range taken out is one action, however many pieces it touched.
    if ops and all(o.get("op") == "drop_range" for o in ops) and a is not None:
        for o in ops:
            t = seq_start(a, o.get("from_shot", ""))
            if t is None:
                continue
            fb, fi = _where(a, o["from_shot"])
            start = t + float(o["from_at"]) - fb["shots"][fi]["start"]
            removed = d["total"][0] - d["total"][1] if not o.get("leave_gap") else None
            where = f"{int(start // 60)}:{start % 60:05.2f}"
            text = (f"Removed {removed:.2f}s at {where}, closed up" if removed is not None
                    else f"Lifted a range at {where}, gap left")
            lines.append({"kind": "removed" if removed is not None else "gap", "beat": fb["id"], "text": text})
        if lines:
            return lines + ov.describe(a, b)
    if d["replaced"] and b:
        lines.append({"kind": "replaced", "text": f"Started from “{b['name']}”"})
        return lines

    def mmss(s: float) -> str:
        return f"{int(s // 60)}:{int(s % 60):02d}"

    def n(k: int, what: str = "shot") -> str:
        return f"{k} {what}{'s' * (k != 1)}"

    for r in d["beats"]["removed"]:
        lines.append({"kind": "removed", "text": f"Removed “{r['title']}” ({n(r['n'])}, {mmss(r['dur'])})", "beat": r["id"]})
    for m in d["beats"]["moved"]:
        lines.append({"kind": "moved", "text": f"Moved “{m['title']}” to position {m['to'] + 1}", "beat": m["id"]})
    for r in d["beats"]["retitled"]:
        lines.append({"kind": "retitled", "text": f"Renamed “{r['from']}” → “{r['to']}”", "beat": r["id"]})
    for x in d["beats"]["added"]:
        lines.append({"kind": "added", "text": f"New beat “{x['title']}”", "beat": x["id"]})

    def clock(t: float | None) -> str:
        return "" if t is None else f"{int(t // 60)}:{t % 60:05.2f}"

    cuts = [x for x in d["shots"]["added"] if x.get("split")]
    gaps_added = [x for x in d["shots"]["added"] if x.get("gap")]
    added = {x["id"]: x for x in d["shots"]["added"] if not x.get("split") and not x.get("gap")}
    cut_ids = {x["id"].split("~")[0] for x in cuts}
    loose_removed = [r for r in d["shots"]["removed"] if not r["with_beat"]]
    shots_removed = [r for r in loose_removed if not r.get("gap")]

    for c in cuts:
        lines.append({"kind": "cut", "beat": c["beat"], "shot": c["id"],
                      "text": f"Cut “{title.get(c['beat'], c['beat'])}” at {clock(c['at'])}"})

    trims: dict[str, list] = {}
    for t in d["shots"]["trimmed"]:
        # the first piece of a cut shot gets shorter by definition -- not a trim
        if t["id"].split("~")[0] in cut_ids and not shots_removed:
            continue
        trims.setdefault(t["beat"], []).append(t)
    for bid, ts in trims.items():
        a0, a1 = sum(t["from"] for t in ts), sum(t["to"] for t in ts)
        if len(ts) == 1:
            verb = "Trimmed" if a1 < a0 else "Extended"
            text = f"{verb} a shot in “{title.get(bid, bid)}”: {a0:.2f}s → {a1:.2f}s"
        else:
            verb = "Tightened" if a1 < a0 else "Loosened"
            text = f"{verb} “{title.get(bid, bid)}”: {n(len(ts))}, {mmss(a0)} → {mmss(a1)}"
        lines.append({"kind": "trimmed", "beat": bid, "text": text})

    for g in gaps_added:
        lines.append({"kind": "gap", "beat": g["beat"], "text": f"Left a {g['dur']:.2f}s gap in “{title.get(g['beat'], g['beat'])}”"})
    for r in loose_removed:
        if r.get("gap"):
            lines.append({"kind": "removed", "beat": r["beat"], "text": f"Closed a {r['dur']:.2f}s gap"})

    # A removal and an addition in the same beat in one turn reads as a swap.
    by_beat: dict[str, list] = {}
    for r in shots_removed:
        swap = next((x for x in added.values() if x["beat"] == r["beat"]), None)
        if swap:
            lines.append({"kind": "swapped", "beat": r["beat"], "shot": swap["id"],
                          "text": f"Swapped a shot in “{title.get(r['beat'], r['beat'])}” for a better one"})
            added.pop(swap["id"])
        else:
            by_beat.setdefault(r["beat"], []).append(r)
    for bid, rs in by_beat.items():
        total = sum(r["dur"] for r in rs)
        what = "a shot" if len(rs) == 1 else n(len(rs))
        lines.append({"kind": "removed", "beat": bid, "shot": rs[0]["id"] if len(rs) == 1 else None,
                      "text": f"Removed {what} ({total:.2f}s) from “{title.get(bid, bid)}”"})
    for x in added.values():
        lines.append({"kind": "added", "beat": x["beat"], "shot": x["id"],
                      "text": f"Added a shot to “{title.get(x['beat'], x['beat'])}”"})
    moved_beats = {m["id"] for m in d["beats"]["moved"]}
    shot_moves = [m for m in d["shots"]["moved"] if m["beat"] not in moved_beats or m["beat"] != m["from_beat"]]
    if shot_moves and not d["beats"]["moved"]:
        where = {title.get(m["beat"], m["beat"]) for m in shot_moves}
        lines.append({"kind": "moved", "text": f"Moved {n(len(shot_moves))} within “{'”, “'.join(sorted(where))}”"})
    lines += ov.describe(a, b)
    lines += restyle.describe(a, b)
    if not lines:
        lines.append({"kind": "none", "text": "No change"})
    return lines


# --------------------------------------------------------------------------
# session: the turn log
# --------------------------------------------------------------------------

@dataclass
class Turn:
    id: int
    kind: str                       # "chat" | "direct"
    text: str                       # what the user said / did
    ops: list[dict]                 # as recorded (after first application)
    reply: str = ""
    question: str | None = None
    choices: list[str] = field(default_factory=list)
    direction: dict | None = None   # {"text", "themes", "labels"} when this turn set one
    undone: bool = False
    at: float = field(default_factory=time.time)
    # filled by replay
    skipped: list[str] = field(default_factory=list)
    diff: dict | None = None
    lines: list[dict] = field(default_factory=list)


class Session:
    def __init__(self) -> None:
        self.turns: list[Turn] = []
        self.board: dict | None = None
        self.proposals: dict | None = None
        self._next = 1

    def replay(self, cat: Catalog, make_proposals) -> None:
        """Rebuild the board from the log. Each op is applied or skipped, never guessed."""
        board, proposals = None, None
        for t in self.turns:
            if t.undone:
                continue  # keeps its last diff, so the UI can show what Redo would bring back
            t.skipped, t.diff, t.lines = [], None, []
            if t.direction is not None:
                proposals = make_proposals(t.direction)
            before = board
            recorded = []
            for k, op in enumerate(t.ops):
                try:
                    board, rec = apply(board, op, cat, proposals,
                                       new_id=lambda k=k, t=t: f"n{t.id}{chr(97 + k)}")
                    recorded.append(rec)
                except OpError as e:
                    t.skipped.append(str(e))
                    recorded.append(op)
            t.ops = recorded
            if t.ops:
                t.diff = diff(before, board)
                t.lines = describe(t.diff, before, board, t.ops)
        self.board, self.proposals = board, proposals

    def add(self, turn_kwargs: dict, cat: Catalog, make_proposals) -> Turn:
        t = Turn(id=self._next, **turn_kwargs)
        self._next += 1
        self.turns.append(t)
        self.replay(cat, make_proposals)
        return t

    def toggle(self, tid: int, cat: Catalog, make_proposals) -> None:
        for t in self.turns:
            if t.id == tid:
                t.undone = not t.undone
        self.replay(cat, make_proposals)

    def last_active(self) -> Turn | None:
        return next((t for t in reversed(self.turns) if not t.undone and t.ops), None)

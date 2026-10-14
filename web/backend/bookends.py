"""Opening + ending: the video starts on its best moment and finishes on a
closing shot, with the song ending on a phrase. Only when the creator turns
it on (sarah, 2026-10-14: "only make if users want it", the switch in
Frames); off by default.

Why this exists, in editing terms: a vlog that starts at the first clip
filmed spends its first seconds on the camera finding its subject, and
viewers decide in those seconds. Vlog editors open on the most striking
moment as a hook, then go back to the start (research thread "Patterns in
YouTube vlogs", 2026-10-14). Endings are chosen too: a quiet closing shot
(a sunset, a view, lights off) rather than whatever was filmed last, and
the music finishes on a downbeat instead of being faded at a random bar.

What the turn does, all as ordinary ops, so one Undo takes it away:

1. **The hook**: the shot with the most going on (well made, moving,
   people, what the story leans on) moves to the very start, trimmed to
   HOOK_S around its best frame. Never a talking shot -- a hook cut
   mid-sentence is worse than no hook. The shot leaves its old place, so
   nothing is shown twice.
2. **The closer**: from the last stretch of the edit, the shot that best
   reads as an ending -- still, a calm view, late in the day -- moves to
   the very end.
3. **The song's end** (only when music is under the edit, bed.py): the
   closing shot is stretched or shortened, within what was filmed, so the
   edit ends RING_S after a phrase boundary of the track (16 beats from
   its drop; else 8, else a bar); the music fades over that ring, so the
   last downbeat is heard whole. The in-point moves with the new hook so
   the drop still lands on its end, and the cuts go back onto the beat.

Nothing here is calibrated: the weights, HOOK_S, RING_S and the reach are
priors, like every threshold in cutgrammar. No model.
"""

from __future__ import annotations

import copy

import numpy as np

from . import board as bd
from . import timeline
from .tempo import MOVING, STILL

TEXT = "Opening + ending"          # the turn's label: the switch reads its state from it
HOOK_S = {"short": 3.0}            # how long the hook holds, by frame [prior; research: first 3 s for Shorts]
HOOK_DEFAULT_S = 6.0               # longer videos: 5-10 s [prior]
MIN_HOOK_S = 1.5
TAIL_SHARE = 0.25                  # the closer comes from the last quarter of the edit's shots [prior]
MIN_TAIL = 3
# What an ending looks like in Vision's labels: a view, the light going, the
# day winding down. [prior, hand-written]
CALM = ("sunset", "dusk", "night", "night_sky", "sky", "cloud", "skyline", "cityscape", "ocean", "sea", "lake",
        "shore", "beach", "river", "horizon", "mountain", "landscape", "field", "candle", "lamp", "bed",
        "bedroom", "sofa", "window", "harbor", "harbour")
RING_S = 1.5                       # the last downbeat rings this long under the closer, fading [prior]
REACH_S = 3.0                      # the closer stretches or shortens at most this much for the song [prior]
MIN_CLOSE_S = 2.0
PHRASES = ((16, "phrase"), (8, "half phrase"), (4, "bar"))
# How the reply says where the song stopped.
ENDING_WORDS = {"phrase": "where a musical phrase ends", "half phrase": "where a musical phrase ends",
                "bar": "on the first beat of a bar", "beat": "on a beat"}


def _shots(board: dict) -> list[tuple[dict, dict]]:
    return [(bt, e) for bt in board.get("beats", []) for e in bt["shots"] if not bd.is_gap(e) and e.get("id")]


def _moving(s) -> float:
    return float(np.clip((s.activity - STILL) / (MOVING - STILL), 0, 1))


def hook_rank(s) -> float:
    """Something happening, and well made: the moment a viewer stays for."""
    return s.score + (0.15 if s.lean else 0.0) + 0.15 * _moving(s) + (0.05 if s.faces else 0.0)


def close_rank(s, late: float) -> float:
    """Reads as an ending: still, a calm view, late."""
    calm = max((v for k, v in s.labels.items() if k in CALM), default=0.0)
    return s.score + 0.25 * (1 - _moving(s)) + 0.2 * min(1.0, calm / 0.5) + 0.1 * late


def is_on(turns) -> bool:
    return any(t.text == TEXT and not t.undone for t in turns)


def pick(board: dict, cat, talking: set[str]) -> tuple[str | None, str | None]:
    """(hook key, closer key), either None when the edit has no good one."""
    flat = [(bt, e) for bt, e in _shots(board) if e["id"] in cat.shots]
    if len(flat) < 3:
        return None, None
    pool = [e for _, e in flat if e["id"] not in talking]
    hook = max(pool, key=lambda e: hook_rank(cat.shots[e["id"]]), default=None)
    n = max(MIN_TAIL, int(round(len(flat) * TAIL_SHARE)))
    tail = [e for _, e in flat[-n:] if e is not hook]
    when = [cat.shots[e["id"]].when for e in tail]
    order = sorted(range(len(tail)), key=lambda i: (when[i] is None, when[i] or 0, i))
    late = {id(tail[i]): (r / max(1, len(tail) - 1)) for r, i in enumerate(order)}
    closer = max(tail, key=lambda e: close_rank(cat.shots[e["id"]], late[id(e)]), default=None)
    return (bd.key(hook) if hook else None), (bd.key(closer) if closer else None)


def layout_ops(board: dict, cat, talking: set[str], fmt: str | None) -> tuple[list[dict], dict]:
    """The hook to the front (trimmed), the closer to the end. (ops, what was done)."""
    hk, ck = pick(board, cat, talking)
    ops: list[dict] = []
    done = {"hook": None, "closer": None}
    if hk:
        ops.append({"op": "open_with", "shot": hk})
        b, e = _find(board, hk)
        cap = HOOK_S.get(fmt or "", HOOK_DEFAULT_S)
        if e["end"] - e["start"] > cap + 0.05:
            c = cat.best_t.get(e["id"], (e["start"] + e["end"]) / 2)
            a = float(min(max(e["start"], c - cap / 2), e["end"] - cap))
            ops += [{"op": "trim", "shot": hk, "edge": "in", "to": round(a, 3)},
                    {"op": "trim", "shot": hk, "edge": "out", "to": round(a + cap, 3)}]
        done["hook"] = e["id"]
        # its clock caption would put a later time first; the story's own
        # first caption starts the day (Undo / off brings it back)
        ops += [{"op": "drop_overlay", "overlay": o["id"]} for o in board.get("overlays", [])
                if o.get("kind") == "caption" and (o.get("anchor") or {}).get("to") == "shot"
                and o["anchor"].get("id") == hk]
    if ck:
        ops.append({"op": "end_with", "shot": ck})
        done["closer"] = _find(board, ck)[1]["id"]
    return ops, done


def _find(board: dict, k: str) -> tuple[dict, dict]:
    for bt in board["beats"]:
        for e in bt["shots"]:
            if bd.key(e) == k:
                return bt, e
    raise KeyError(k)


def end_on_phrase(board: dict, cat, music: dict, track_s: float, talking: set[str]) -> tuple[dict | None, str]:
    """A trim of the last shot so the edit ends RING_S after a phrase
    boundary of the music. `music` carries in, bpm and (when known) drop,
    all track seconds. (trim op or None, what boundary it is)."""
    if not board.get("beats") or not music.get("bpm"):
        return None, ""
    last = board["beats"][-1]["shots"][-1]
    if bd.is_gap(last) or last["id"] not in cat.shots or last["id"] in talking:
        return None, ""
    src = cat.shots[last["id"]]
    period = 60.0 / float(music["bpm"])
    total = timeline.layout(board)[-1]["seq_end"]
    t_in = float(music.get("in") or 0.0)
    drop = music.get("drop")
    anchor = float(drop) - t_in if drop is not None else (float(music.get("phase") or 0.0) - t_in) % period
    levels = PHRASES if drop is not None else ((4, "beat"),)
    for n, name in levels:
        step = n * period
        k = np.arange(np.floor((total - REACH_S - RING_S - anchor) / step) - 1,
                      np.ceil((total + REACH_S - anchor) / step) + 2)
        ends = anchor + k * step + RING_S
        ok = [float(x) for x in ends
              if abs(x - total) <= REACH_S and x - RING_S > anchor - 1e-6 and t_in + x <= track_s
              and last["start"] + MIN_CLOSE_S <= last["end"] + (x - total) <= src.end]
        if ok:
            x = min(ok, key=lambda v: abs(v - total))
            if abs(x - total) < 1e-3:
                return None, name
            return {"op": "trim", "shot": bd.key(last), "edge": "out", "to": round(last["end"] + x - total, 3)}, name
    return None, ""


def turn(board: dict, cat, talking: set[str], fmt: str | None, music_ops=None) -> tuple[list[dict], str]:
    """Everything the switch does, as one turn's ops, and the reply.
    `music_ops(trial) -> (ops, note)` re-lays the bed on the new order when
    the edit has music (app: bed.relay)."""
    ops, done = layout_ops(board, cat, talking, fmt)
    if not ops:
        return [], ""
    trial = copy.deepcopy(board)
    for o in ops:
        trial, _ = bd.apply(trial, o, cat, None, lambda: "x")
    said = []
    if done["hook"]:
        said.append(f"It opens on {cat.shots[done['hook']].clip_name}, the moment with the most going on, then goes back to the start.")
    if done["closer"]:
        said.append(f"It ends on {cat.shots[done['closer']].clip_name}, the shot that reads most like an ending.")
    if music_ops is not None:
        more, note = music_ops(trial)
        ops += more
        if note:
            said.append(note)
    said.append("Turn it off and everything goes back where it was.")
    return ops, " ".join(said)

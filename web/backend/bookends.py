"""Opening + ending: the video opens on a quick preview of the day and
finishes on a closing shot, with the song ending on a phrase. Only when the
creator turns it on (sarah, 2026-10-14: "only make if users want it", the
switch in Frames); off by default.

Why this exists, in editing terms: a vlog that starts at the first clip
filmed spends its first seconds on the camera finding its subject, and
viewers decide in those seconds. Vlog editors open with a preview: very
short moments from across the whole day, cut on the music's beat, with a
line saying when and where (sarah, 2026-10-14, after trying a single held
hook: "very short clips that match the music's beats throughout the day to
kind of give a preview of whats going on ... and usually there is some
information in the captions"). Endings are chosen too: a quiet closing shot
(a sunset, a view, lights off) rather than whatever was filmed last, and
the music finishes on a downbeat instead of being faded at a random bar.

What the turn does, all as ordinary ops, so one Undo takes it away:

1. **The preview** (op `preview`, its own part at the front): more moments
   the longer the video (`count`), one from each stretch of the story, the
   one with the most going on in each (well made, moving, people), never a
   look-alike or a second from the same clip. Each flash is a *different*
   stretch of its shot from the one the story uses (sarah: never the same
   shot twice), else it's left out. In filming order. Each lasts the beat
   unit (`unit`): about UNIT_S, a whole number of the music's beats.
   Captioned with the date and place, from 1 s in (no words in the first
   second, sarah 2026-10-06).
2. **The closer**: from the last stretch of the story, the shot that best
   reads as an ending -- still, a calm view, late in the day -- moves to
   the very end.
3. **The song** (only when music is under the edit, bed.py): the preview is
   cut on its beat and the in-point moves so the drop lands as the story
   starts; the closing shot is stretched or shortened, within what was
   filmed, so the edit ends RING_S after a phrase boundary of the track
   (16 beats from its drop; else 8, else a bar); the music fades over that
   ring, so the last downbeat is heard whole.

Nothing here is calibrated: the counts, weights, UNIT_S, RING_S and the
reach are priors, like every threshold in cutgrammar. No model.
"""

from __future__ import annotations

import copy

import numpy as np

from . import board as bd
from . import timeline
from .tempo import MOVING, STILL

# Two switches (sarah, 2026-10-14: "separate opening and ending"); each
# turn's label is how its switch reads its state.
TEXTS = {"opening": "Opening", "ending": "Ending"}
PREVIEW = "pv"                     # the preview part's id (one per edit)
UNIT_S = 0.7                       # a preview flash, before it's rounded to whole beats [prior]
NO_MUSIC_UNIT_S = 0.6              # without music: an even half-second-ish rhythm [prior]
MIN_PREVIEW_S = 2.5                # long enough for its date line to be read after the first second [prior]
PAD_S = 0.5                        # a flash stays this far from the stretch the story uses [prior]
SIMILAR = 0.78                     # look-alikes, as brief.SIMILAR
CAPTION_AT_S = 1.0                 # no words in the first second
TAIL_SHARE = 0.25                  # the closer comes from the last quarter of the story's shots [prior]
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
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def count(total_s: float) -> int:
    """How many moments the preview shows, by the video's length [prior]:
    a short gets a taste (3-4), a vlog of a few minutes 5-8, a long one up
    to 12 (sarah, 2026-10-14: "depends on the length of the video")."""
    if total_s <= 90:
        return 3 if total_s < 45 else 4
    if total_s < 600:
        return int(round(5 + 3 * (total_s - 90) / 510))
    return int(min(12, round(8 + (total_s - 600) / 300)))


def unit(period: float | None, n: int) -> float:
    """One flash: a whole number of beats near UNIT_S (more when `n` of them
    would be over before MIN_PREVIEW_S), or the plain rhythm."""
    if not period:
        return max(NO_MUSIC_UNIT_S, MIN_PREVIEW_S / max(1, n))
    beats = max(1, round(UNIT_S / period))
    while n * beats * period < MIN_PREVIEW_S - 1e-6:
        beats += 1
    return round(beats * period, 4)


def _shots(board: dict) -> list[tuple[dict, dict]]:
    return [(bt, e) for bt in board.get("beats", []) if not bt.get("preview")
            for e in bt["shots"] if not bd.is_gap(e) and e.get("id")]


def _moving(s) -> float:
    return float(np.clip((s.activity - STILL) / (MOVING - STILL), 0, 1))


def hook_rank(s) -> float:
    """Something happening, and well made: the moment a viewer stays for."""
    return s.score + (0.15 if s.lean else 0.0) + 0.15 * _moving(s) + (0.05 if s.faces else 0.0)


def close_rank(s, late: float) -> float:
    """Reads as an ending: still, a calm view, late."""
    calm = max((v for k, v in s.labels.items() if k in CALM), default=0.0)
    return s.score + 0.25 * (1 - _moving(s)) + 0.2 * min(1.0, calm / 0.5) + 0.1 * late


def is_on(turns, which: str) -> bool:
    return any(t.text == TEXTS[which] and not t.undone for t in turns)


def preview_of(board: dict) -> dict | None:
    return next((bt for bt in board.get("beats", []) if bt.get("preview")), None)


def opening_end(board: dict) -> float:
    """Where the story proper starts: the end of the preview, else of the first shot."""
    lay = timeline.layout(board) if board.get("beats") else []
    if not lay:
        return 0.0
    pv = preview_of(board)
    if pv is None:
        return float(lay[0]["seq_end"])
    keys = {bd.key(e) for e in pv["shots"]}
    return float(max((it["seq_end"] for it in lay if it.get("key") in keys), default=lay[0]["seq_end"]))


def _free(cat, board: dict, sid: str, length: float) -> tuple[float, float] | None:
    """A `length` window of the shot away from every stretch the story uses,
    as near its best frame as it can be."""
    s = cat.shots[sid]
    used = sorted((e["start"] - PAD_S, e["end"] + PAD_S) for _, e in _shots(board) if e["id"] == sid)
    pieces, at = [], s.start
    for a, z in used:
        if a > at:
            pieces.append((at, min(a, s.end)))
        at = max(at, z)
    if at < s.end:
        pieces.append((at, s.end))
    best = cat.best_t.get(sid, (s.start + s.end) / 2)
    fits = []
    for lo, hi in pieces:
        if hi - lo >= length - 1e-6:
            c = min(max(best, lo + length / 2), hi - length / 2)
            fits.append((abs(c - best), c))
    if not fits:
        return None
    c = min(fits)[1]
    return round(c - length / 2, 3), round(c + length / 2, 3)


def preview_op(board: dict, cat, period: float | None = None) -> dict | None:
    """The preview part as one op: `count` flashes, one per stretch of the
    story, in filming order. None when the story has too few moments."""
    story = [e for _, e in _shots(board) if e["id"] in cat.shots]
    lay = [it for it in timeline.layout(board) if not str(it.get("key", "")).startswith("pv~")] if board.get("beats") else []
    total = sum(it["seq_end"] - it["seq_start"] for it in lay)
    n = min(count(total), len(story))
    if n < 2:
        return None
    u = unit(period, n)
    picked: list = []
    for chunk in np.array_split(np.arange(len(story)), n):
        for i in sorted(chunk, key=lambda i: -hook_rank(cat.shots[story[i]["id"]])):
            sh = cat.shots[story[i]["id"]]
            if any(sh.clip_id == p[0].clip_id or (sh.vec.shape == p[0].vec.shape and float(sh.vec @ p[0].vec) >= SIMILAR)
                   for p in picked):
                continue
            w = _free(cat, board, sh.id, u)
            if w:
                picked.append((sh, w, i))
                break
    if len(picked) < 2:
        return None
    picked.sort(key=lambda p: (p[0].when is None, p[0].when or 0, p[2]))
    return {"op": "preview", "beat": PREVIEW,
            "shots": [{"id": sh.id, "start": a, "end": z} for sh, (a, z), _ in picked]}


def caption(cat, op: dict, place: str | None) -> dict | None:
    """When and where, over the preview: "Sep 22 · Kyoto". Only what the
    clips know (their recording day, the geocoder's name for their GPS)."""
    days = sorted({cat.shots[x["id"]].when.date() for x in op["shots"] if cat.shots[x["id"]].when})
    when = ""
    if days:
        a, b = days[0], days[-1]
        md = lambda d: f"{_MONTHS[d.month - 1]} {d.day}"  # noqa: E731
        when = md(a) if a == b else (f"{md(a)}–{b.day}" if (a.year, a.month) == (b.year, b.month) else f"{md(a)} – {md(b)}")
    text = " · ".join(x for x in (when, place) if x)
    length = sum(x["end"] - x["start"] for x in op["shots"])
    if not text or length < CAPTION_AT_S + 1.0:
        return None
    return {"op": "add_overlay", "kind": "caption", "text": text, "anchor": {"to": "beat", "id": PREVIEW},
            "at": CAPTION_AT_S, "dur": round(length - CAPTION_AT_S, 2)}


def closer_key(board: dict, cat) -> str | None:
    """From the last stretch of the story, the shot that reads most like an ending."""
    flat = [e for _, e in _shots(board) if e["id"] in cat.shots]
    if len(flat) < 3:
        return None
    n = max(MIN_TAIL, int(round(len(flat) * TAIL_SHARE)))
    tail = flat[-n:]
    when = [cat.shots[e["id"]].when for e in tail]
    order = sorted(range(len(tail)), key=lambda i: (when[i] is None, when[i] or 0, i))
    late = {id(tail[i]): (r / max(1, len(tail) - 1)) for r, i in enumerate(order)}
    closer = max(tail, key=lambda e: close_rank(cat.shots[e["id"]], late[id(e)]))
    return bd.key(closer)


def layout_ops(board: dict, cat, which: str, place: str | None = None,
               period: float | None = None) -> tuple[list[dict], dict]:
    """The preview at the front (opening) or the closer at the end (ending).
    (ops, what was done)."""
    ops: list[dict] = []
    done: dict = {"preview": 0, "closer": None}
    if which == "opening":
        pv = preview_op(board, cat, period)
        if pv:
            ops.append(pv)
            done["preview"] = len(pv["shots"])
            cap = caption(cat, pv, place)
            if cap:
                ops.append(cap)
                done["caption"] = cap["text"]
    else:
        ck = closer_key(board, cat)
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


def turn(board: dict, cat, which: str, place: str | None = None, music_ops=None,
         period: float | None = None) -> tuple[list[dict], str]:
    """Everything one switch does, as one turn's ops, and the reply.
    `period` is the beat of the music under the edit, if any; then
    `music_ops(trial) -> (ops, note)` re-lays the bed on the new order
    (app: bed.relay)."""
    ops, done = layout_ops(board, cat, which, place, period)
    if not ops:
        return [], ""
    trial = copy.deepcopy(board)
    for o in ops:
        trial, _ = bd.apply(trial, o, cat, None, lambda: "x")
    said = []
    if done["preview"]:
        said.append(f"It opens on a quick look at the day: {done['preview']} moments, then the story from the start"
                    + (f", with \u201c{done['caption']}\u201d over them." if done.get("caption") else "."))
    if done["closer"]:
        said.append(f"It ends on {cat.shots[done['closer']].clip_name}, the shot that reads most like an ending.")
    if music_ops is not None:
        more, note = music_ops(trial)
        ops += more
        if note:
            said.append(note)
    said.append("Turn it off and everything goes back where it was.")
    return ops, " ".join(said)

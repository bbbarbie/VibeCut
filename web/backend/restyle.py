"""A learned style, applied to the working storyboard as one undoable op.

`apply_style` is recorded in the turn log like every other edit: what it
decided at apply time (the pace targets, the beat grid of the chosen track,
the transition policy, which LUT file) is written into the op, so replaying
the log reproduces it exactly and Undo takes all of it away at once.

What it changes, and what it leaves alone:

- **Pace** retimes each shot towards the reference's shot length at that
  point of the video (its arc, not just its average), centred on the shot's
  best frame. A shot can't be held longer than it was filmed; those are
  counted and reported, never padded.
- **Beat**: when the reference cuts on the beat and a track with a steady
  tempo is under the edit, each cut is moved to the nearest beat.
- **Transitions / look / frame** don't touch timing: they are stored on the
  board as `style` and rendered at export (export.py) -- the only place
  pixels are ever re-encoded.

Beats that follow a voiceover line keep their timing: the voice sets time
there (voiceover.py), and pace must not pull pictures off their words.
"""

from __future__ import annotations

import numpy as np

from cutgrammar import style as st

MIN_SHOT_S = 0.4     # the shortest shot a borrowed pace may leave
MAX_SNAP_S = 0.35    # a cut moves to a beat only if one is this close
TRAITS = ("pace", "beat", "transitions", "look", "frame")


# --------------------------------------------------------------------------
# what a learned style becomes
# --------------------------------------------------------------------------

def transition_policy(tr: dict) -> dict:
    """Instances -> a rule for this edit.

    A soft transition that is the reference's norm (half its joins or more)
    goes everywhere; one it uses now and then goes between parts, which is
    where editors reach for them. Rarer than HABIT_SHARE is noise.
    """
    share, dur = tr.get("share", {}), tr.get("dur", {})
    soft = [k for k in ("dissolve", "dip_black", "flash") if share.get(k, 0) >= st.HABIT_SHARE]
    pol = {"between": "cut", "within": "cut", "dur": 0.0,
           "open": bool(tr.get("open")), "close": bool(tr.get("close"))}
    if soft:
        main = max(soft, key=lambda k: share[k])
        pol["between"] = main
        pol["within"] = main if share[main] >= 0.5 else "cut"
        lo, hi = (0.1, 0.4) if main == "flash" else (0.2, 1.5)
        pol["dur"] = round(float(np.clip(dur.get(main, 0.5), lo, hi)), 3)
    return pol


NAMES = {"cut": "hard cuts", "dissolve": "dissolves", "dip_black": "dips to black", "flash": "white flashes"}


def describe_policy(p: dict) -> str:
    if p["between"] == "cut":
        s = "Hard cuts throughout"
    elif p["within"] == p["between"]:
        s = f"{NAMES[p['between']].capitalize()} ({p['dur']:.1f} s) between every shot"
    else:
        s = f"Hard cuts inside parts, {NAMES[p['between']]} ({p['dur']:.1f} s) between parts"
    ends = [x for x, on in (("fade in from black", p["open"]), ("fade out at the end", p["close"])) if on]
    return s + ("; " + " and ".join(ends) if ends else "")


def snapshot(style: dict) -> dict:
    """The parts of a learned style an op needs to replay -- small and fixed."""
    out: dict = {}
    if style.get("pace"):
        p = style["pace"]
        out["pace"] = {"median_s": p["median_s"], "curve": p["curve"]}
    if style.get("transitions"):
        out["transitions"] = transition_policy(style["transitions"])
    if (style.get("frame") or {}).get("letterbox"):
        out["letterbox"] = style["frame"]["letterbox"]
    return out


# --------------------------------------------------------------------------
# pace and beat
# --------------------------------------------------------------------------

def _window(cat, sid: str, dur: float) -> tuple[float, float]:
    """`dur` seconds inside the source shot, centred on its best frame."""
    s = cat.get(sid)
    dur = float(np.clip(dur, min(MIN_SHOT_S, s.end - s.start), s.end - s.start))
    c = cat.best_t.get(sid, (s.start + s.end) / 2)
    a = min(max(s.start, c - dur / 2), s.end - dur)
    return round(a, 3), round(a + dur, 3)


def _curve_at(curve: list[float], pos: float) -> float:
    """The reference's relative shot length at `pos` (0..1) through the video."""
    n = len(curve)
    x = np.clip(pos * n - 0.5, 0, n - 1)
    return float(np.interp(x, np.arange(n), curve))


def targets(n: int, pace: dict) -> list[float]:
    """Shot k of n -> seconds, following the reference's arc."""
    return [round(pace["median_s"] * _curve_at(pace["curve"], (k + 0.5) / max(n, 1)), 3) for k in range(n)]


def beat_times(grid: dict, until: float) -> np.ndarray:
    period = 60.0 / grid["bpm"]
    return np.arange(grid["phase"], until + period, period)


def retime(b: dict, cat, pace: dict | None, grid: dict | None) -> dict:
    """Retime every shot of the board in place. Returns what happened."""
    entries = [(bt, e) for bt in b["beats"] if not bt.get("line") for e in bt["shots"] if not e.get("gap")]
    held = sum(1 for bt in b["beats"] if bt.get("line"))
    before = [e["end"] - e["start"] for _, e in entries]
    want = targets(len(entries), pace) if pace else before
    short = 0
    for (_, e), t in zip(entries, want):
        s = cat.get(e["id"])
        if t > s.end - s.start + 1e-3:
            short += 1
        e["start"], e["end"] = _window(cat, e["id"], t)
    snapped = 0
    if grid:
        # Walk the edit in order; each cut goes to the nearest beat the
        # shot can reach. Gaps and voiceover beats keep their length but
        # still move what follows them.
        total = sum(x["end"] - x["start"] for bt in b["beats"] for x in bt["shots"]) + 10
        beats = beat_times(grid, total)
        t = 0.0
        for bt in b["beats"]:
            for e in bt["shots"]:
                d = e["end"] - e["start"]
                if e.get("gap") or bt.get("line"):
                    t += d
                    continue
                s = cat.get(e["id"])
                lo, hi = t + min(MIN_SHOT_S, s.end - s.start), t + (s.end - s.start)
                near = beats[(beats >= lo - 1e-6) & (beats <= hi + 1e-6)]
                if len(near):
                    g = float(near[np.argmin(np.abs(near - (t + d)))])
                    if abs(g - (t + d)) <= MAX_SNAP_S:
                        e["start"], e["end"] = _window(cat, e["id"], g - t)
                        snapped += 1
                t += e["end"] - e["start"]
    after = [e["end"] - e["start"] for _, e in entries]
    return {"shots": len(entries), "held_by_voice": held, "filmed_too_short": short, "on_beat": snapped,
            "median_before": round(float(np.median(before)), 2) if before else None,
            "median_after": round(float(np.median(after)), 2) if after else None,
            "target_median": pace["median_s"] if pace else None}


# --------------------------------------------------------------------------
# the op
# --------------------------------------------------------------------------

class StyleError(Exception):
    pass


def apply(b: dict, op: dict, cat) -> None:
    """`apply_style` on a copy of the board (board.apply makes the copy)."""
    traits = [t for t in op.get("traits", []) if t in TRAITS]
    snap = op.get("style") or {}
    if not traits:
        raise StyleError("choose at least one thing to borrow")
    if "pace" in traits and not snap.get("pace"):
        raise StyleError("the reference has no pacing to borrow")
    if "beat" in traits and not op.get("grid"):
        raise StyleError("cutting on the beat needs a track with a steady beat under the edit")
    report = None
    if "pace" in traits or "beat" in traits:
        report = retime(b, cat, snap.get("pace") if "pace" in traits else None,
                        op.get("grid") if "beat" in traits else None)
    look = None
    if "look" in traits:
        if not op.get("lut"):
            raise StyleError("the look wasn't fitted to this footage")
        look = {"lut": op["lut"], "strength": op.get("strength", 1.0), "words": op.get("look_words", [])}
    b["style"] = {
        "ref": op.get("ref"), "name": op.get("name", "a reference"), "traits": traits,
        "transitions": snap.get("transitions") if "transitions" in traits else None,
        "look": look,
        "letterbox": snap.get("letterbox") if "frame" in traits else None,
        "report": report,
    }


def describe(a: dict | None, b: dict | None) -> list[dict]:
    """The style lines of a turn's diff."""
    sa, sb = (a or {}).get("style"), (b or {}).get("style")
    if sa == sb:
        return []
    if not sb:
        return [{"kind": "removed", "text": f"Stopped borrowing from “{sa['name']}”"}]
    what = {"pace": "pacing", "beat": "cuts on the beat", "transitions": "transitions",
            "look": "look", "frame": "frame"}
    lines = [{"kind": "style", "text": f"Borrowed from “{sb['name']}”: "
              + ", ".join(what[t] for t in sb["traits"])}]
    r = sb.get("report")
    if r and r.get("median_after") is not None:
        text = f"Shots now about {r['median_after']:.1f} s (were {r['median_before']:.1f} s"
        text += f"; reference {r['target_median']:.1f} s)" if r.get("target_median") else ")"
        if r.get("filmed_too_short"):
            text += f" — {r['filmed_too_short']} couldn't be held that long, they weren't filmed longer"
        lines.append({"kind": "trimmed", "text": text})
        if r.get("on_beat"):
            lines.append({"kind": "style", "text": f"{r['on_beat']} of {r['shots']} cuts moved onto the beat"})
        if r.get("held_by_voice"):
            lines.append({"kind": "style", "text": f"{r['held_by_voice']} voiceover part(s) kept their timing"})
    if sb.get("transitions"):
        lines.append({"kind": "style", "text": describe_policy(sb["transitions"]) + " (in the export)"})
    if sb.get("look"):
        lines.append({"kind": "style", "text": "One grade over the whole video: "
                      + (", ".join(sb["look"].get("words", [])) or "the reference's look") + " (in the export)"})
    if sb.get("letterbox"):
        lines.append({"kind": "style", "text": f"Cinematic bars at {sb['letterbox']:.2f}:1 (in the export)"})
    return lines

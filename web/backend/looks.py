"""Looks (the "vibe" in the UI): one dated record per look, applied as a turn.

Surface dates and structure lasts (research 06 §4), so a look is data, not
code: `looks/*.json`, one file each, with the date it was written and the
date it must be reviewed by. The values come from the design spec
(redesign-v2 §4.3–4.4); most are priors, and each record says which were
measured. This first cut carries what words on screen need -- font, case,
tracking, palette, backing, and motion (curve, entrance time, stepping,
stagger, beat lock). The spec's grade, joins, camera, texture, sounds and
music per look are listed in each record's `not_yet` and aren't applied.

`set_look` sets the look for the whole video. What the creator already set
by hand (overlay_style after or before) is kept -- the look fills in only
what they left alone -- and the difference is shown, one click from being
reset. Changing look never silently throws a choice away.
"""

from __future__ import annotations

import json
from pathlib import Path

DIR = Path(__file__).resolve().parent / "looks"
STYLE_KEYS = ("font", "color", "accent", "backing")
BEAT_SNAP_S = 0.25   # a word lands on the beat if it was this close already [prior]

_LOOKS: dict[str, dict] | None = None


def all_looks() -> dict[str, dict]:
    global _LOOKS
    if _LOOKS is None:
        _LOOKS = {}
        for p in sorted(DIR.glob("*.json")):
            rec = json.loads(p.read_text())
            _LOOKS[rec["id"]] = rec
    return _LOOKS


def get(look_id: str | None) -> dict | None:
    return all_looks().get(look_id or "")


def overlay_defaults(look: dict) -> dict:
    """The overlay_style fields a look sets when the creator hasn't."""
    t = look["type"]
    return {"font": t["font"], "color": t["palette"][0], "accent": t["palette"][1], "backing": t["backing"]}


def motion_of(look: dict | None) -> dict | None:
    """What overlayDraw needs to move words the look's way."""
    if not look:
        return None
    m, t = look["motion"], look["type"]
    return {"curve": m["curve"], "in_s": m["in_s"], "step_fps": m["step_fps"], "stagger_s": m["stagger_s"],
            "enter": m["enter"], "case": t["case"], "track": t["track"], "beat_lock": m["beat_lock"]}


def public() -> list[dict]:
    return [{"id": r["id"], "name": r["name"], "line": r["line"], "font": r["type"]["font"],
             "palette": r["type"]["palette"], "status": r["status"], "review_by": r["review_by"]}
            for r in all_looks().values()]


# --------------------------------------------------------------------------
# on the board
# --------------------------------------------------------------------------

def apply(b: dict, op: dict) -> None:
    """set_look {look, reset?}. look None = no look (the plain defaults)."""
    lid = op.get("look")
    if lid is not None and lid not in all_looks():
        raise ValueError(f"no look {lid!r} — one of {', '.join(all_looks())}")
    if lid is None:
        b.pop("look", None)
    else:
        b["look"] = lid
    if op.get("reset"):
        # "use the look's": forget what was set by hand, so the look shows through
        b["style_set"] = []
        b["overlay_style"] = {k: v for k, v in (b.get("overlay_style") or {}).items() if k not in STYLE_KEYS}


def style(b: dict | None, base: dict) -> dict:
    """The overlay style the video uses: defaults, then the look, then what
    the creator set by hand. `base` is overlays.DEFAULT_STYLE."""
    b = b or {}
    set_by_hand = b.get("overlay_style") or {}
    look = get(b.get("look"))
    if not look:
        return {**base, **set_by_hand}
    kept = set(b.get("style_set") or [])
    mine = {k: v for k, v in set_by_hand.items() if k in kept or k not in STYLE_KEYS}
    return {**base, **overlay_defaults(look), **mine, "look": look["id"], "motion": motion_of(look)}


def overrides(b: dict | None) -> list[str]:
    """Fields the creator set by hand that differ from the look."""
    b = b or {}
    look = get(b.get("look"))
    if not look:
        return []
    d = overlay_defaults(look)
    mine = b.get("overlay_style") or {}
    return [k for k in b.get("style_set") or [] if k in d and mine.get(k) != d[k]]


def describe(a: dict | None, b: dict | None) -> list[dict]:
    la, lb = (a or {}).get("look"), (b or {}).get("look")
    if la == lb and ((a or {}).get("style_set") or []) == ((b or {}).get("style_set") or []):
        return []
    if lb and la != lb:
        kept = overrides(b)
        extra = f" (kept your {', '.join(kept)})" if kept else ""
        return [{"kind": "style", "text": f"Look: {get(lb)['name']} — {get(lb)['line'].rstrip('.')}{extra}"}]
    if la and not lb:
        return [{"kind": "style", "text": "Look removed: back to the plain words"}]
    if lb:
        return [{"kind": "style", "text": f"Words now follow the {get(lb)['name']} look throughout"}]
    return []


def beat_lock(items: list[dict], grid: dict | None, total: float) -> list[dict]:
    """Words that enter on the music's beat. Each overlay that starts within
    BEAT_SNAP_S of a beat moves (whole, keeping its length) onto it; others
    stay where they are. The same resolved times feed preview and export."""
    if not grid or not grid.get("bpm"):
        return items
    period = 60.0 / float(grid["bpm"])
    phase = float(grid.get("phase") or 0.0)
    out = []
    for o in items:
        if o.get("kind") == "chapters":
            out.append(o)
            continue
        k = round((o["start"] - phase) / period)
        beat = phase + k * period
        d = beat - o["start"]
        if abs(d) <= BEAT_SNAP_S and beat >= 0 and o["shown_end"] + d <= total + 1e-6:
            o = {**o, "start": round(beat, 4), "end": round(o["end"] + d, 4),
                 "shown_end": round(o["shown_end"] + d, 4), "on_beat": True}
        out.append(o)
    return out

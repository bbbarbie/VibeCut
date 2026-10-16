"""What a moment is worth to the story, not only how well it was filmed.

Until now every choice the default edit made -- which shot opens it, which
shots go when it must get shorter -- ranked shots by craft alone (exposure,
sharpness, steadiness: `Shot.score`). Craft says a shot is usable; it says
nothing about whether it is the moment worth keeping. A shaky second of
friends laughing beats a steady shot of a building, and the first look at a
new place is what tells the viewer where the day went (evaluation of the
Oct 16 demo; sarah, 2026-10-14: "it shouldn't all be about my face").

So each shot also gets:

- feeling  -- laughter, singing, talking to the audience (sound.json, which
              was measured and never used for picking)
- rare     -- how unusual what's in it is across the shoot (label rarity)
- context  -- it opens a new stop of the day without a face filling the
              frame: where the viewer learns where we are
- plain face -- a face in frame with nothing said, no laugh: a selfie that
              says less than the day around it (a small penalty, never a
              rule; a well-made one still beats a poor view)

Every weight is a prior, like every threshold here. `tests/test_worth.py`
builds pairs that differ in one respect and checks the ranking moves.
"""

from __future__ import annotations

import math

import numpy as np

# Weights of the parts. Craft stays the largest share: a moment nobody can
# see is worth nothing. [prior]
W_CRAFT, W_FEELING, W_RARE, W_CONTEXT, W_PLAIN_FACE = 0.45, 0.25, 0.15, 0.15, 0.10
# Per-second classifier confidence above which a second counts. [prior]
HEARD = 0.5
FACE_AREA = 0.04   # tempo.FACE_AREA / by_subject's "on camera"
# How the parts of feeling count against each other: a laugh is the clearest
# sign of a moment; someone talking to the lens is the vlog's own voice;
# singing along is close behind. [prior]
LAUGH, TALK, SING = 1.0, 0.8, 0.6


def _secs(rec: dict | None, key: str, a: float, b: float) -> np.ndarray:
    vals = ((rec or {}).get("sound") or {}).get(key) or []
    lo, hi = int(max(0, a)), int(min(len(vals), math.ceil(b)))
    return np.asarray(vals[lo:max(hi, lo)], dtype=np.float32)


def _share(rec: dict | None, key: str, a: float, b: float) -> float:
    x = _secs(rec, key, a, b)
    return float((x >= HEARD).mean()) if x.size else 0.0


def _count(rec: dict | None, key: str, a: float, b: float) -> int:
    return int((_secs(rec, key, a, b) >= HEARD).sum())


def feeling(s, rec: dict | None) -> tuple[float, str | None]:
    """0..1 and the reason: the strongest sign of a moment in the shot's window."""
    # A laugh lasts a second or two inside a longer shot: two heard seconds
    # count fully, however long the shot. Singing along needs a few more.
    laugh = min(1.0, _count(rec, "laughter", s.start, s.end) / 2)
    sing = min(1.0, _count(rec, "singing", s.start, s.end) / 4)
    talk = _share(rec, "voice", s.start, s.end) if s.face_area >= FACE_AREA else 0.0
    parts = [(LAUGH * laugh, "laughter"), (TALK * talk, "talking to you"), (SING * sing, "singing")]
    v, why = max(parts)
    return (v, why) if v > 0 else (0.0, None)


def idf(shots: list) -> dict[str, float]:
    n = max(1, len(shots))
    df: dict[str, int] = {}
    for s in shots:
        for k in s.labels:
            df[k] = df.get(k, 0) + 1
    return {k: math.log((n + 1) / (v + 1)) for k, v in df.items()}


def rarity(s, weights: dict[str, float], top: int = 3) -> float:
    if not s.labels or not weights:
        return 0.0
    keys = sorted(s.labels, key=lambda k: -s.labels[k])[:top]
    hi = max(weights.values()) or 1.0
    return float(np.clip(np.mean([weights.get(k, 0.0) for k in keys]) / hi, 0, 1))


def annotate(shots: list, clips: dict[str, dict]) -> None:
    """Set `worth` (0..1) and `worth_why` (the reasons, plain words) on every shot."""
    if not shots:
        return
    from .brief import spots
    weights = idf(shots)
    stop = spots(shots)
    first: dict[int, str] = {}
    for s in sorted(shots, key=lambda s: (s.when is None, s.when or 0, s.order)):
        first.setdefault(stop.get(s.id, -1), s.id)
    opens = set(first.values()) if len(first) > 1 else set()
    for s in shots:
        rec = clips.get(s.clip_id)
        feel, why = feeling(s, rec)
        rare = rarity(s, weights)
        context = 1.0 if s.id in opens and s.face_area < FACE_AREA else 0.0
        plain = 1.0 if (s.face_area >= FACE_AREA and feel == 0.0) else 0.0
        s.worth = round(W_CRAFT * s.score + W_FEELING * feel + W_RARE * rare
                        + W_CONTEXT * context - W_PLAIN_FACE * plain, 4)
        reasons = [why] if why else []
        if context:
            reasons.append("first look at a new place")
        if rare >= 0.6:
            reasons.append("something the day shows only once")
        s.worth_why = reasons


def of(s) -> float:
    """A shot's worth; craft alone for one `annotate` never saw."""
    w = getattr(s, "worth", None)
    return s.score if w is None else w


def importance(shots: list, spot: dict[str, int]) -> dict[int, float]:
    """Stop of the day -> how much it matters: its best moment's worth.
    Screen time follows this, not how much was filmed there."""
    out: dict[int, float] = {}
    for s in shots:
        k = spot.get(s.id, -1)
        out[k] = max(out.get(k, 0.0), of(s))
    return out

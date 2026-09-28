"""The click, made exact.

"Here" in a sentence is vague; a click is not. One click on the player gives
the time (snapped to the frame the viewer saw), where in the frame it was
(0..1 across and down the picture, not the widget), and which shot of the
finished edit that is -- so a caption knows where to sit and an effect knows
where to start, before a word is parsed.
"""

from __future__ import annotations

import bisect
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Anchor:
    t: float          # seconds into the edit, on a frame
    x: float          # 0..1 across the picture
    y: float          # 0..1 down the picture
    shot: int         # index of the shot of the edit under t
    frame: int        # the frame number of t

    def public(self) -> dict:
        return asdict(self)


def make(t: float, x: float, y: float, cuts: list[float], fps: float, duration: float) -> Anchor:
    """A click at (t, x, y) on an edit whose shots start at `cuts` (first 0)."""
    fps = fps if fps > 0 else 30.0
    t = min(max(0.0, float(t)), max(0.0, duration - 1 / fps))
    frame = int(t * fps + 1e-6)
    t = round(frame / fps, 4)
    starts = sorted(c for c in cuts if c > 0)
    return Anchor(t=t, x=round(min(max(0.0, float(x)), 1.0), 4), y=round(min(max(0.0, float(y)), 1.0), 4),
                  shot=bisect.bisect_right(starts, t + 1e-6), frame=frame)


def from_dict(d: dict) -> Anchor:
    return Anchor(t=float(d["t"]), x=float(d["x"]), y=float(d["y"]), shot=int(d["shot"]), frame=int(d["frame"]))

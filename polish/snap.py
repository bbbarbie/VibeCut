"""An effect starts where the picture or the music gives it a reason to.

A boom that fires on the frame someone happened to click lands a beat late
or mid-gesture and reads as a mistake. An editor starts it on the movement
it punctuates, or on the beat. So the click is only where to look: the
start moves to the nearest movement onset (preferred -- it's what the eye
follows) or beat within reach, and says so. Nothing near: it stays put, and
says that too. Windows are first guesses ([prior]).
"""

from __future__ import annotations

ONSET_REACH_S = 0.4
BEAT_REACH_S = 0.25


def beats(bpm: float | None, phase: float | None, until: float) -> list[float]:
    if not bpm or phase is None:
        return []
    period = 60.0 / bpm
    out, t = [], float(phase)
    while t < until:
        out.append(round(t, 3))
        t += period
    return out


def snap(t: float, onsets: list[float], beat_times: list[float]) -> tuple[float, str]:
    """(start time, why) for an effect clicked at t."""
    near = [o for o in onsets if abs(o - t) <= ONSET_REACH_S]
    if near:
        o = min(near, key=lambda o: abs(o - t))
        return round(o, 3), f"on the movement at {o:.2f} s"
    near = [b for b in beat_times if abs(b - t) <= BEAT_REACH_S]
    if near:
        b = min(near, key=lambda b: abs(b - t))
        return round(b, 3), f"on the beat at {b:.2f} s"
    return round(t, 3), "where you clicked (no movement or beat within reach)"

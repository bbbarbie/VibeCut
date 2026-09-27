"""What happens at each cut of an edit: report only.

The rules in grammar.py measure a finished video. These measure a plan --
the storyboard -- one join at a time, from what the index already holds,
so a jump is found before anything is rendered. Nothing here changes the
edit (that would be cutfix, which waits for calibration); it only says,
per cut, what a viewer will feel there, with the number behind it.

Why each component exists, in editing terms:

- **exposure** -- a jump in brightness across a cut reads as a mistake, not
  a choice (the eye adapts over the next second, and notices).
- **colour** -- two cameras or two lights side by side look like two
  different videos. Measured on each shot's best frame, not the cut frame:
  a proxy, and labelled so.
- **repeat** -- two near-identical views of different takes, cut together,
  are a jump cut: the picture twitches instead of moving on.
- **energy** -- how much the picture changes per second either side of the
  cut. A frantic second slammed into a dead-still one is felt as a stall
  (or a jolt). Second-scale, from stills a second apart: it says nothing
  about the exact frame, so it can't claim "cut on the action".
- **sound** -- the loudness step across the cut, from the source audio
  either side. The biggest single tell an edit is a pile of clips.
- **time** -- the second shot was filmed before the first: the day runs
  backwards unless the story means it to.
- **size** -- the same person at the same size in both shots is another
  jump cut; a change of shot size (wide to close) is what hides a cut.
  Only when both shots have a face.

Every threshold is a first guess ([prior]) like every threshold in
cutgrammar: calibrate against well-cut and badly-cut edits before trusting
the verdicts. The values are reported either way.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import numpy as np

from . import evidence
from .grammar import BAD, OK, WARN, Finding, gate

# [prior] thresholds
EXPOSURE_WARN, EXPOSURE_BAD = 30.0, 55.0     # mean luma step, 0..255
COLOUR_WARN, COLOUR_BAD = 0.55, 0.75         # 1 - histogram intersection
REPEAT_SIM = 0.95                            # embedding cosine: the same view again
ENERGY_RATIO = 6.0                           # one side this many times busier than the other
ENERGY_FLOOR = 2.0                           # below this both sides are "still"; no step to feel
SOUND_WARN_DB, SOUND_BAD_DB = 9.0, 15.0      # loudness step across the cut
SILENT_DB = -50.0                            # quieter than this isn't a sound to step from
SIZE_SAME = 1.25                             # face-area ratio under this: same shot size
EDGE_S = 1.0                                 # how much of each side counts as "at the cut"


@dataclass
class Side:
    """One shot as the cut sees it: its window and what the index knows."""
    clip_id: str
    t_in: float                      # source seconds
    t_out: float
    luma: list[float]                # per second of the clip
    motion: list[float]
    hist: list[float] | None = None  # best frame, 64 bins
    embedding: list[float] | None = None
    face_area: float = 0.0
    when: datetime | None = None     # capture time of t_in
    rms_db: list[float] = field(default_factory=list)   # per second, if the clip has sound


def _edge(x: list[float], a: float, b: float) -> float | None:
    """Mean of per-second values over [a, b) seconds."""
    if not x:
        return None
    i, j = max(0, int(np.floor(a))), min(len(x), int(np.ceil(b)))
    if j <= i:
        i, j = max(0, min(i, len(x) - 1)), max(0, min(i, len(x) - 1)) + 1
    return float(np.mean(x[i:j]))


def _tail(s: Side, x: list[float]) -> float | None:
    return _edge(x, max(s.t_in, s.t_out - EDGE_S), s.t_out)


def _head(s: Side, x: list[float]) -> float | None:
    return _edge(x, s.t_in, min(s.t_out, s.t_in + EDGE_S))


def _grade(v: float, warn: float, bad: float) -> str:
    return BAD if v >= bad else WARN if v >= warn else OK


def measure(a: Side, b: Side) -> list[Finding]:
    """The findings of one cut, from a (outgoing) to b (incoming)."""
    out: list[Finding] = []

    la, lb = _tail(a, a.luma), _head(b, b.luma)
    if la is not None and lb is not None:
        d = abs(lb - la)
        out.append(Finding("join_exposure", "Brightness jump", round(d, 1), "luma", _grade(d, EXPOSURE_WARN, EXPOSURE_BAD),
                           "The picture gets much brighter or darker at the cut." if d >= EXPOSURE_WARN
                           else "Brightness carries across the cut.", {"from": round(la, 1), "to": round(lb, 1)}))

    if a.hist and b.hist and len(a.hist) == len(b.hist):
        d = 1.0 - float(np.minimum(np.asarray(a.hist), np.asarray(b.hist)).sum())
        out.append(Finding("join_colour", "Colour change", round(d, 3), "", _grade(d, COLOUR_WARN, COLOUR_BAD),
                           "The two shots look like different cameras or light." if d >= COLOUR_WARN
                           else "The colours sit together.", {"proxy": "best frames, not the cut frames"}))

    if a.clip_id != b.clip_id and a.embedding and b.embedding and len(a.embedding) == len(b.embedding):
        va, vb = np.asarray(a.embedding, float), np.asarray(b.embedding, float)
        sim = float(va @ vb / (np.linalg.norm(va) * np.linalg.norm(vb) + 1e-9))
        out.append(Finding("join_repeat", "Same view again", round(sim, 3), "cos", WARN if sim >= REPEAT_SIM else OK,
                           "Nearly the same picture from another take: a jump cut." if sim >= REPEAT_SIM
                           else "A different picture."))

    ma, mb = _tail(a, a.motion), _head(b, b.motion)
    if ma is not None and mb is not None:
        hi, lo = max(ma, mb), max(min(ma, mb), 1e-6)
        ratio = hi / lo if hi >= ENERGY_FLOOR else 1.0
        out.append(Finding("join_energy", "Energy step", round(min(ratio, 99.0), 2), "×",
                           WARN if ratio >= ENERGY_RATIO else OK,
                           ("A busy second cuts to a still one." if ma > mb else "A still second cuts to a busy one.")
                           if ratio >= ENERGY_RATIO else "The energy carries across the cut.",
                           {"out": round(ma, 2), "in": round(mb, 2)}))

    ra, rb = _tail(a, a.rms_db), _head(b, b.rms_db)
    if ra is not None and rb is not None and max(ra, rb) > SILENT_DB:
        d = abs(max(ra, SILENT_DB) - max(rb, SILENT_DB))
        out.append(Finding("join_sound", "Loudness step", round(d, 1), "dB", _grade(d, SOUND_WARN_DB, SOUND_BAD_DB),
                           "The sound jumps in level at the cut." if d >= SOUND_WARN_DB
                           else "The sound level carries across the cut.",
                           {"from_db": round(ra, 1), "to_db": round(rb, 1)}))

    if a.when and b.when:
        a_out = a.when.timestamp() + (a.t_out - a.t_in)
        back = a_out - b.when.timestamp()
        out.append(Finding("join_time", "Goes back in time", round(max(0.0, back) / 60, 1), "min",
                           WARN if back > 60 else OK,
                           "The next shot was filmed earlier: the day runs backwards here." if back > 60
                           else "Time moves forward."))

    if a.face_area > 0 and b.face_area > 0:
        r = max(a.face_area, b.face_area) / min(a.face_area, b.face_area)
        out.append(Finding("join_size", "Shot size change", round(r, 2), "×", WARN if r < SIZE_SAME else OK,
                           "The same framing on both sides: the cut twitches rather than moves."
                           if r < SIZE_SAME else "The framing changes, which hides the cut."))
    return out


def cost(findings: list[Finding]) -> float:
    """One number for how rough a cut feels, for comparing orders (not a verdict).

    Graded components count their value against their 'bad' line, capped at
    1; flag-type components count 0.5 when flagged. Components that weren't
    checked (pending) count nothing. Time isn't here: order search weighs
    time separately, so the story's clock is a choice, not a penalty.
    """
    scale = {"join_exposure": EXPOSURE_BAD, "join_colour": COLOUR_BAD, "join_sound": SOUND_BAD_DB}
    c = 0.0
    for f in findings:
        if f.verdict == "pending" or f.value is None:
            continue
        if f.key in scale:
            c += min(1.0, float(f.value) / scale[f.key])
        elif f.key in ("join_repeat", "join_energy", "join_size") and f.verdict != OK:
            c += 0.5
    return c


def verdict(findings: list[Finding]) -> str:
    """The cut's overall verdict: its worst component that was actually checked."""
    rank = {OK: 0, WARN: 1, BAD: 2}
    judged = [f.verdict for f in findings if f.verdict in rank]
    return max(judged, key=rank.get) if judged else OK


def report(sides: list[Side], has: set[str] | None = None) -> list[dict]:
    """One entry per cut between consecutive sides (None = a gap: no cut measured)."""
    have = has if has is not None else {evidence.META, evidence.STILL, evidence.AUDIO}
    out = []
    for a, b in zip(sides, sides[1:]):
        if a is None or b is None:
            out.append(None)
            continue
        fs = measure(a, b)
        gate(fs, have)
        out.append({"verdict": verdict(fs), "findings": fs})
    return out

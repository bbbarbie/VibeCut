"""The editing-grammar measurements.

Every rule here is a number, not a judgement. Whether a vlog is beautiful
is not computable; whether its cuts land on motion, whether its audio is
hard-synced to its picture, whether its rhythm is mechanical -- those are.
That gap is the whole bet: most of what makes amateur footage read as
amateur is craft nobody taught them, and craft is measurable.

Each check returns a Finding with a raw value and a verdict. Thresholds
are first guesses, meant to be recalibrated against real reference videos
(see calibrate.py in the README's next steps) -- not received truth.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from . import evidence, features, shots as shots_mod
from .media import Media, loudness_lufs

OK, WARN, BAD = "ok", "warn", "bad"
# Not a judgement: the media doesn't carry what this rule needs to see
# (see evidence.py). The value is kept; the verdict is withheld.
PENDING = "pending"


@dataclass
class Finding:
    key: str
    label: str
    value: float | None
    unit: str
    verdict: str
    detail: str
    extra: dict = field(default_factory=dict)
    evidence: list[str] = field(default_factory=list)  # readings it rests on


@dataclass
class Report:
    path: str
    duration: float
    fps: float
    n_shots: int
    findings: list[Finding]
    shots: list[shots_mod.Shot]

    def by_verdict(self, v: str) -> list[Finding]:
        return [f for f in self.findings if f.verdict == v]


# --------------------------------------------------------------------------
# rhythm
# --------------------------------------------------------------------------

def check_rhythm(shots: list[shots_mod.Shot]) -> list[Finding]:
    lens = np.array([s.duration for s in shots], dtype=np.float64)
    if len(lens) < 3:
        return [Finding("rhythm", "Shot rhythm", None, "", WARN,
                        "Fewer than 3 shots -- nothing to measure.")]

    mean, median = float(lens.mean()), float(np.median(lens))
    cv = float(lens.std() / (mean + 1e-9))

    # Calibrated 2026-10-11 (design/research/calibration/2026-10-11.md): 18
    # popular vlogs / travel films had CV 0.81 median, VibeCut's own exports
    # 0.56, AUC 0.78, best split 0.70. The edge moves from the 0.35 guess to
    # 0.6 -- short of the split, because the "bad" set was mostly one shoot's
    # Remix iterations, which are beat-quantised and so unusually even.
    if cv < 0.6:
        verdict, detail = WARN, (
            "Shot lengths are near-uniform. Even pacing reads as mechanical; "
            "real edits breathe -- a run of quick cuts, then a long shot."
        )
    elif cv > 1.4:
        verdict, detail = WARN, (
            "Shot lengths are very uneven. Some shots are far longer than "
            "their neighbours, which usually means an unfinished trim."
        )
    else:
        verdict, detail = OK, "Shot lengths vary the way a paced edit does."

    out = [Finding("rhythm_cv", "Rhythm variation", cv, "CV", verdict, detail,
                   {"mean_s": mean, "median_s": median,
                    "p10_s": float(np.percentile(lens, 10)),
                    "p90_s": float(np.percentile(lens, 90))})]

    longest = float(lens.max())
    if longest > 12.0:
        out.append(Finding(
            "long_shot", "Longest shot", longest, "s", WARN,
            f"A {longest:.0f}s shot with no change is where viewers leave. "
            "Cut it, or put something on top of it.",
            {"shot_index": int(lens.argmax())}))
    return out


# --------------------------------------------------------------------------
# cut on motion
# --------------------------------------------------------------------------

def check_cut_on_motion(media: Media, shots: list[shots_mod.Shot]) -> list[Finding]:
    """Cuts should land while the frame is moving, not while it sits still.

    For each cut we compare the motion in the last few frames of the
    outgoing shot against that shot's own median motion, so a static
    tripod clip is judged against itself rather than against a handheld one.
    """
    if len(shots) < 2:
        return []

    m = features.motion(media)
    scores: list[float] = []

    for s in shots[:-1]:
        # exclude the boundary frames themselves: they measure the cut
        body = m[s.start_frame + 1 : max(s.end_frame - 1, s.start_frame + 2)]
        if body.size < 3:
            continue
        tail = body[-min(5, len(body)):]
        med = float(np.median(body)) + 1e-6
        scores.append(float(tail.mean()) / med)

    if not scores:
        return []

    frac = float(np.mean([s > 1.0 for s in scores]))
    # Calibrated 2026-10-11: well-cut edits land 0.47 of their cuts on motion
    # (median), VibeCut's 0.41; AUC 0.65, split 0.41. The old OK edge (0.55)
    # warned on most good edits; 0.45 / 0.30 now. Still ±1 frame-diff motion.
    if frac < 0.30:
        verdict, detail = BAD, (
            "Most cuts land on a still frame. Moving the cut a few frames "
            "into an existing movement hides it -- this is the single "
            "cheapest thing that makes an edit look professional."
        )
    elif frac < 0.45:
        verdict, detail = WARN, "About half the cuts land on static frames."
    else:
        verdict, detail = OK, "Cuts mostly land while the frame is moving."

    return [Finding("cut_on_motion", "Cuts landing on motion", frac, "fraction",
                    verdict, detail, {"n_cuts_measured": len(scores)})]


# --------------------------------------------------------------------------
# J/L cuts
# --------------------------------------------------------------------------

def check_jl_cuts(media: Media, shots: list[shots_mod.Shot],
                  hop_s: float = 0.01) -> list[Finding]:
    """Does the sound change at exactly the same instant as the picture?

    Amateur edits cut audio and video on the same frame. Professional edits
    offset them -- sound arrives early (J) or leaves late (L). Measuring the
    offset between each visual cut and the nearest audible change is a
    direct read on whether that habit is present.
    """
    if not media.has_audio or len(shots) < 2:
        return []

    nov = features.audio_novelty(media, hop_s)
    if nov.size < 10:
        return []

    thresh = float(np.percentile(nov, 96))
    peaks = np.flatnonzero(nov > thresh)
    if peaks.size == 0:
        return []

    peak_t = peaks * hop_s
    offsets: list[float] = []
    for s in shots[1:]:
        near = peak_t[np.argmin(np.abs(peak_t - s.start_t))]
        offsets.append(float(near - s.start_t))

    off = np.array(offsets)
    hard = off[np.abs(off) < 0.6]  # only cuts with an audible event nearby
    if hard.size < 2:
        return []

    synced = float(np.mean(np.abs(hard) < 0.08))
    if synced > 0.70:
        verdict, detail = BAD, (
            "Sound and picture change on the same frame almost every time. "
            "Offsetting the audio by 0.3-1s (J-cut: sound arrives first; "
            "L-cut: sound lingers) is the highest-value single change here."
        )
    # Calibrated 2026-10-11: good edits 0.41 hard-synced (median), VibeCut's
    # 0.70; AUC 0.33, split 0.62. WARN moves 0.45 -> 0.6; BAD stays at 0.7.
    elif synced > 0.6:
        verdict, detail = WARN, "Many cuts are hard-synced; some are offset."
    else:
        verdict, detail = OK, "Audio and picture cuts are offset from each other."

    return [Finding("jl_cuts", "Hard-synced cuts", synced, "fraction", verdict,
                    detail, {"n_measured": int(hard.size),
                             "median_offset_s": float(np.median(hard))})]


# --------------------------------------------------------------------------
# continuity at cuts
# --------------------------------------------------------------------------

def check_continuity(media: Media, shots: list[shots_mod.Shot]) -> list[Finding]:
    """Brightness and colour jumps across a cut read as a mistake."""
    if len(shots) < 2:
        return []

    bright = features.brightness(media)
    chan = features.channel_means(media)

    def shot_stat(arr, s, n=6):
        head = arr[s.start_frame : s.start_frame + n]
        tail = arr[max(s.end_frame - n, s.start_frame) : s.end_frame]
        return (np.asarray(head).mean(axis=0) if len(head) else None,
                np.asarray(tail).mean(axis=0) if len(tail) else None)

    b_jumps, c_jumps, flagged = [], [], []
    for a, b in zip(shots[:-1], shots[1:]):
        _, a_out = shot_stat(bright, a)
        b_in, _ = shot_stat(bright, b)
        _, ac_out = shot_stat(chan, a)
        bc_in, _ = shot_stat(chan, b)
        if a_out is None or b_in is None:
            continue
        db = abs(float(b_in) - float(a_out))
        dc = float(np.abs(bc_in - ac_out).mean())
        b_jumps.append(db)
        c_jumps.append(dc)
        if db > 45 or dc > 38:
            flagged.append({"at_s": round(b.start_t, 2),
                            "brightness_delta": round(db, 1),
                            "colour_delta": round(dc, 1)})

    if not b_jumps:
        return []

    rate = len(flagged) / len(b_jumps)
    if rate > 0.25:
        verdict, detail = BAD, (
            f"{len(flagged)} of {len(b_jumps)} cuts jump hard in exposure or "
            "colour. One LUT across the whole piece fixes most of this."
        )
    elif flagged:
        verdict, detail = WARN, f"{len(flagged)} cuts jump in exposure or colour."
    else:
        verdict, detail = OK, "Exposure and colour stay continuous across cuts."

    return [Finding("continuity", "Exposure/colour continuity", rate, "fraction",
                    verdict, detail,
                    {"median_brightness_delta": float(np.median(b_jumps)),
                     "worst": flagged[:6]})]


# --------------------------------------------------------------------------
# near-duplicate shots
# --------------------------------------------------------------------------

def check_duplicates(media: Media, shots: list[shots_mod.Shot],
                     thresh: float = 0.88) -> list[Finding]:
    """Same thing filmed twice, both takes left in -- the classic vlog tell."""
    if len(shots) < 3:
        return []

    h = shots_mod.shot_histograms(media, shots)
    sim = np.minimum(h[:, None, :], h[None, :, :]).sum(axis=2)
    np.fill_diagonal(sim, 0.0)

    pairs = [
        {"a_s": round(shots[i].start_t, 2), "b_s": round(shots[j].start_t, 2),
         "similarity": round(float(sim[i, j]), 3)}
        for i, j in zip(*np.triu_indices(len(shots), k=1))
        if sim[i, j] > thresh
    ]
    pairs.sort(key=lambda p: -p["similarity"])

    if not pairs:
        return [Finding("duplicates", "Near-duplicate shots", 0.0, "pairs", OK,
                        "No repeated shots detected.")]

    verdict = BAD if len(pairs) > len(shots) * 0.15 else WARN
    return [Finding("duplicates", "Near-duplicate shots", float(len(pairs)),
                    "pairs", verdict,
                    f"{len(pairs)} shot pairs look near-identical -- probably "
                    "repeated takes that should be cut to one.",
                    {"pairs": pairs[:6]})]


# --------------------------------------------------------------------------
# opening pace
# --------------------------------------------------------------------------

def check_opening(media: Media, shots: list[shots_mod.Shot],
                  hop_s: float = 0.01) -> list[Finding]:
    out: list[Finding] = []

    if len(shots) >= 2:
        first = shots[0].duration
        verdict = BAD if first > 8 else (WARN if first > 5 else OK)
        out.append(Finding(
            "first_cut", "Time to first cut", first, "s", verdict,
            "The opening shot runs long before anything changes."
            if verdict != OK else "The opening moves early.",
        ))

    if media.has_audio:
        mask = features.speech_mask(media, hop_s)
        if mask.any():
            t = float(np.argmax(mask) * hop_s)
            verdict = BAD if t > 6 else (WARN if t > 3 else OK)
            out.append(Finding(
                "first_speech", "Time to first voice", t, "s", verdict,
                "Silence at the top costs more viewers than anything else "
                "in the edit." if verdict != OK else "The voice starts early.",
            ))
    return out


# --------------------------------------------------------------------------
# loudness
# --------------------------------------------------------------------------

def check_loudness(media: Media) -> list[Finding]:
    lufs = loudness_lufs(media.path)
    if lufs is None:
        return []
    if lufs > -11 or lufs < -18:
        verdict = BAD
    elif lufs > -12.5 or lufs < -16:
        verdict = WARN
    else:
        verdict = OK
    return [Finding(
        "loudness", "Integrated loudness", lufs, "LUFS", verdict,
        "Platforms normalise to about -14 LUFS. Far from it and playback "
        "turns the whole piece up or down." if verdict != OK
        else "Sits at the platform target.",
    )]


# --------------------------------------------------------------------------

def analyze(media: Media, shot_list: list[shots_mod.Shot] | None = None) -> Report:
    s = shot_list if shot_list is not None else shots_mod.detect(media)
    findings: list[Finding] = []
    for fn in (check_rhythm,):
        findings += fn(s)
    for fn in (check_cut_on_motion, check_jl_cuts, check_continuity,
               check_duplicates, check_opening):
        findings += fn(media, s)
    findings += check_loudness(media)
    gate(findings, evidence.available(media))
    return Report(media.path, media.duration, media.fps, len(s), findings, s)


# What each finding has to see to be believed. Shot lengths, colour jumps
# and repeated views are visible in stills (to index accuracy). Whether a
# cut lands inside a movement, and whether sound and picture change on the
# same frame, need every frame -- a keyframe every second can't say.
NEEDS = {
    "rhythm": [evidence.STILL], "rhythm_cv": [evidence.STILL], "long_shot": [evidence.STILL],
    "cut_on_motion": [evidence.MOTION],
    "jl_cuts": [evidence.MOTION, evidence.AUDIO],
    "continuity": [evidence.STILL],
    "duplicates": [evidence.STILL],
    "first_cut": [evidence.STILL],
    "first_speech": [evidence.AUDIO],
    "loudness": [evidence.AUDIO],
    # joins.py: one cut of a storyboard, from the index. Energy is second-
    # scale change between stills a second apart, so stills suffice for it --
    # it never claims the exact frame of a cut.
    "join_exposure": [evidence.STILL], "join_colour": [evidence.STILL], "join_repeat": [evidence.STILL],
    "join_energy": [evidence.STILL], "join_sound": [evidence.AUDIO], "join_time": [evidence.META],
    "join_size": [evidence.STILL],
}


def gate(findings: list[Finding], have: set[str]) -> None:
    """Withhold the verdict of any finding the media can't support."""
    for f in findings:
        if not f.evidence:
            f.evidence = list(NEEDS.get(f.key, [evidence.STILL]))
        lacking = evidence.missing(f.evidence, have)
        if lacking and f.verdict != PENDING:
            f.extra = {**f.extra, "withheld_verdict": f.verdict, "lacking": lacking}
            f.verdict = PENDING
            f.detail = (f"Not checked: this needs {evidence.describe(lacking)}, which this "
                        f"reading doesn't have. The number is kept, not judged.")

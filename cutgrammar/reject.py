"""Stage 1 of the rough cut: whole clips that shouldn't be used at all.

The lens cap left on, the phone filming the inside of a pocket, a clip dark
or blurred from end to end, two seconds of pavement from a mis-tap, the
same view shot twice. Every one of these is found from the clip's signals
(signals.py) and comes with a reason a person can read. Nothing is ever
dropped silently, and nothing is deleted: a rejected clip goes back to the
shelf with its reason, one click from being used again.

Near-duplicates are the dangerous rule. Two takes of someone talking in
the same room look identical and may say different things -- without a
transcript that difference is invisible. So a talking clip is never
rejected as a duplicate, only flagged as a possible retake.

All thresholds are first guesses (see CLAUDE.md: calibrate before trusting).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import numpy as np

from . import evidence, trim
from .signals import ClipSignals

LENS_CAP_LUMA = 12      # mean brightness, 0..255
FLAT_CONTRAST = 0.06    # bestframe contrast component
DARK_LUMA = 28
DARK_CONTRAST = 0.3     # a lit subject on a black ground measures 0.6+; murk ~0.3 or less
BLURRY_SHARPNESS = 0.2
MOST = 0.85             # "end to end" = this share of the clip's seconds
ACCIDENT_S = 3.0
DUP_SIMILARITY = 0.93   # cosine, on the embedding supplied
DUP_WINDOW_MIN = 15     # takes of the same thing are filmed close together

# What each reason rests on (see evidence.py). Signals come from the index,
# one sample a second: shake is change *between* samples a second apart, so
# "shaking throughout" is a guess about motion made from stills -- the
# reason says so, and the gate is where a person watches it.
NEEDS = {
    "empty": [evidence.META], "lens-cap": [evidence.STILL], "dark": [evidence.STILL],
    "blurry": [evidence.STILL], "duplicate": [evidence.STILL],
    "accident": [evidence.META, evidence.STILL], "shaky": [evidence.MOTION],
}
INDEX_READS = {evidence.META, evidence.STILL}


@dataclass
class Verdict:
    rejected: bool
    code: str = ""
    zh: str = ""
    en: str = ""
    flags: list[dict] = field(default_factory=list)   # warnings that don't reject
    stats: dict = field(default_factory=dict)

    @property
    def evidence(self) -> list[str]:
        return list(NEEDS.get(self.code, []))

    def unverified(self, have: set[str] = INDEX_READS) -> list[str]:
        """Readings the reason needs that the index never had."""
        return evidence.missing(self.evidence, have)


def judge(sig: ClipSignals, faces: np.ndarray | None = None) -> Verdict:
    """Rules that need only this clip."""
    if sig.n == 0:
        return Verdict(True, "empty", "没有可播放的画面", "no playable picture")
    luma, contrast = sig.arr("luma"), sig.arr("contrast")
    sharp, mot = sig.arr("sharpness"), sig.arr("motion")
    subj, _ = trim._subject(sig, faces)
    share = lambda m: float(np.mean(m))  # noqa: E731
    stats = {
        "dark": share(luma < DARK_LUMA), "black": share((luma < LENS_CAP_LUMA) | (contrast < FLAT_CONTRAST)),
        "blurry": share(sharp < BLURRY_SHARPNESS), "shaky": share(mot > trim.SHAKY_FROM),
        "subject": float(subj.mean()), "speech": float(np.mean(sig.speech)), "duration": sig.duration,
    }
    talking = trim.is_talking(sig)

    if stats["black"] >= MOST:
        return Verdict(True, "lens-cap", "几乎全黑或一片纯色——像是镜头盖没开或在口袋里",
                       "black or a single colour throughout — lens cap or pocket", stats=stats)
    if sig.duration < ACCIDENT_S and not talking and (stats["subject"] < 0.3 or stats["shaky"] >= 0.5):
        return Verdict(True, "accident", f"只有 {sig.duration:.1f} 秒，没拍到东西——像是误触",
                       f"only {sig.duration:.1f}s with nothing in it — looks like a mis-tap", stats=stats)
    # Dark alone isn't a failure: a lit dancer on a black stage is a style,
    # and it has strong contrast. Dark *and* murky -- nothing stands out --
    # is the failure.
    if stats["dark"] >= MOST and not talking and float(contrast.mean()) < DARK_CONTRAST:
        return Verdict(True, "dark", "全片太暗，看不清拍的是什么", "too dark to make out anything, start to finish",
                       stats=stats)
    if stats["blurry"] >= MOST:
        return Verdict(True, "blurry", "全片模糊", "blurred from start to finish", stats=stats)
    if stats["shaky"] >= MOST and not talking:
        return Verdict(True, "shaky", "全程剧烈晃动", "shaking hard the whole way through", stats=stats)
    return Verdict(False, stats=stats)


@dataclass
class Candidate:
    id: str
    name: str
    sig: ClipSignals
    embedding: np.ndarray       # any fingerprint; compared by cosine
    quality: float              # higher wins when two are duplicates
    when: datetime | None = None
    faces: np.ndarray | None = None


def _cos(a: np.ndarray, b: np.ndarray) -> float:
    if a.shape != b.shape or not a.size:
        return 0.0
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12))


def reject_all(clips: list[Candidate], dup_threshold: float = DUP_SIMILARITY) -> dict[str, Verdict]:
    out = {c.id: judge(c.sig, c.faces) for c in clips}

    # Near-duplicates, among the clips still standing: keep the better one.
    alive = [c for c in clips if not out[c.id].rejected]
    for i, a in enumerate(alive):
        for b in alive[i + 1:]:
            if out[a.id].rejected or out[b.id].rejected:
                continue
            close = a.when is None or b.when is None or abs((a.when - b.when).total_seconds()) <= DUP_WINDOW_MIN * 60
            sim = _cos(a.embedding, b.embedding)
            if not close or sim < dup_threshold:
                continue
            keep, lose = (a, b) if a.quality >= b.quality else (b, a)
            if trim.is_talking(a.sig) or trim.is_talking(b.sig):
                out[lose.id].flags.append({"code": "retake", "of": keep.id, "similarity": round(sim, 3),
                                           "zh": f"看起来像 {keep.name} 的重拍（说话内容可能不同，没有去掉）",
                                           "en": f"looks like a retake of {keep.name} (what's said may differ, so kept)"})
                continue
            out[lose.id] = Verdict(True, "duplicate", f"和 {keep.name} 几乎一样（留下了拍得更好的那条）",
                                   f"almost the same as {keep.name} (kept the better one)",
                                   stats={**out[lose.id].stats, "similarity": round(sim, 3), "of": keep.id})
    return out

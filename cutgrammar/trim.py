"""Stage 2 of the rough cut: the usable window inside a clip you keep.

Real editing is subtractive. A 23-second clip usually holds five good
seconds: the phone is still being raised, the subject hasn't arrived, the
camera wanders off at the end. This finds those seconds.

Every second gets a score from the clip's signals (signals.py): made well
(sharp, exposed), steady (not shaking -- but a locked-off shot with nothing
in it is dead, not steady), something in frame, and -- for a clip where
someone talks -- the talking. The best contiguous window of the target
length is then an exact max-sum sliding window: prefix sums, one pass, no
model.

A window is also judged by how it *starts and ends*, because a cut that
lands mid-whip-pan, mid-word or on a subject walking out of frame reads as
a mistake however good the middle is. The start counts twice as much as
the end: the first frame of a shot is where the viewer is reoriented.

Nothing is cut out of any file. The result is an in and out point.

All weights and thresholds are first guesses, like everything in grammar.py;
they rank windows, and a human approves every trim before anything uses it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .signals import ClipSignals

# motion is mean luma change over one second, 0..255
SHAKY_FROM, SHAKY_FULL = 8.0, 20.0
DEAD_BELOW = 0.6
TALKING = 0.35          # mean voiced fraction above which a clip is "someone talking"
GOOD = 0.55             # a second worth keeping
W_IN, W_OUT = 0.5, 0.25  # a good start matters twice as much as a good end
MIN_BOUNDARY = 0.45      # windows that start worse than this are a last resort
SNAP_S = 0.6             # how far a boundary may move to get out of a word
RUNNER_UP = 0.1          # a runner-up window may score at most this far below the best [prior]


@dataclass
class Window:
    start: float            # in point, seconds into the clip
    end: float              # out point
    target: float
    score: float
    whole: bool
    reason_zh: str
    reason_en: str
    notes: list[str] = field(default_factory=list)
    seconds: list[float] = field(default_factory=list)   # per-second score, for the UI


def _subject(sig: ClipSignals, faces: np.ndarray | None) -> tuple[np.ndarray, np.ndarray]:
    subj, edge = sig.arr("subject"), sig.arr("edge")
    if faces is not None and len(faces) == sig.n:
        subj = np.maximum(subj, faces[:, 0])
        edge = np.maximum(edge, faces[:, 1])
    return subj, edge


def shake(motion: np.ndarray) -> np.ndarray:
    return np.clip((motion - SHAKY_FROM) / (SHAKY_FULL - SHAKY_FROM), 0, 1)


def is_talking(sig: ClipSignals) -> bool:
    return sig.n > 0 and float(np.mean(sig.speech)) > TALKING


def second_scores(sig: ClipSignals, faces: np.ndarray | None = None) -> np.ndarray:
    q = sig.arr("quality")
    mot = sig.arr("motion")
    subj, edge = _subject(sig, faces)
    speech = sig.arr("speech")
    audio = speech if is_talking(sig) else np.full(sig.n, 0.5)
    # dead: nothing changes, nothing in it, nobody talking
    dead = (mot < DEAD_BELOW) & (subj < 0.3) & (speech < 0.2)
    return (0.35 * q + 0.25 * (1 - shake(mot)) + 0.25 * subj + 0.15 * audio
            - 0.3 * dead - 0.15 * edge)


def _inside_word(t: float, voiced: list[list[float]]) -> list[float] | None:
    for a, b in voiced:
        if a + 0.03 < t < b - 0.03:
            return [a, b]
    return None


def boundary(sig: ClipSignals, t: int, kind: str, subj: np.ndarray, edge: np.ndarray) -> float:
    """How well a window can start (kind='in') or end ('out') at second t."""
    k = min(max(t if kind == "in" else t - 1, 0), sig.n - 1)
    mot = sig.arr("motion")
    steady = 1 - shake(mot[k:k + 1] if kind == "in" else mot[k:k + 1]).max()
    # starting on a pan that is about to begin is as bad as starting mid-pan
    nxt = mot[min(k + 1, sig.n - 1)] if kind == "in" else mot[max(k - 1, 0)]
    steady = min(steady, 1 - float(shake(np.array([nxt]))[0]) * 0.5)
    word = _inside_word(float(t), sig.voiced)
    speech_ok = 1.0 if word is None else (1.0 if min(t - word[0], word[1] - t) <= SNAP_S else 0.0)
    return float(0.4 * steady + 0.3 * subj[k] + 0.3 * speech_ok - 0.4 * edge[k])


def target_length(sig: ClipSignals, scores: np.ndarray, lo: int = 0, hi: int | None = None,
                  short: bool = False) -> float:
    """How much of this clip is worth keeping: its good seconds, within a
    range that fits the kind of clip (someone talking holds longer).
    `short`: the length it would get as a moment without talking."""
    hi = sig.n if hi is None else hi
    good = int((scores[lo:hi] >= GOOD).sum())
    if is_talking(sig) and not short:
        # Which sentences matter can't be known without a transcript, so a
        # talking clip only loses what is unusable -- never a chosen amount
        # of what was said. Shortening it further is the creator's call.
        return float(np.clip(good, 3, hi - lo))
    return float(np.clip(good, 2, 5))


def best_window(sig: ClipSignals, target: float | None = None, faces: np.ndarray | None = None,
                lo: float = 0.0, hi: float | None = None) -> Window:
    """Best contiguous window of `target` seconds inside [lo, hi)."""
    return candidates(sig, target, faces, lo, hi, k=1)[0]


def candidates(sig: ClipSignals, target: float | None = None, faces: np.ndarray | None = None,
               lo: float = 0.0, hi: float | None = None, k: int = 3) -> list[Window]:
    """Up to `k` different windows of `target` seconds inside [lo, hi), best first.

    The scores here know a second is sharp, steady and has *something* in
    it -- not that it is the moment worth keeping (the laugh, the reveal,
    the view opening up). So the runners-up are offered too, for a judge
    that can look at the pictures (web/backend/moments.py) to choose from.
    Each is a genuinely different moment: they share at most a third of their seconds,
    and none scores far below the best.
    """
    hi = sig.duration if hi is None else min(hi, sig.duration)
    s = second_scores(sig, faces)
    subj, edge = _subject(sig, faces)
    a0, b0 = int(np.floor(lo)), min(int(np.ceil(hi - 1e-6)), sig.n)
    span = b0 - a0
    L = int(round(target if target is not None else target_length(sig, s, a0, b0)))
    L = max(1, min(L, span))
    if L >= span:
        return [_finish(sig, float(lo), float(hi), float(L), float(s[a0:b0].mean()) if span else 0.0,
                        True, s, a0, b0)]

    # Exact max over all windows: prefix sums for the body, boundary terms per edge.
    c = np.concatenate([[0.0], np.cumsum(s[a0:b0])])
    starts = np.arange(0, span - L + 1)
    body = (c[starts + L] - c[starts]) / L
    b_in = np.array([boundary(sig, a0 + i, "in", subj, edge) for i in starts])
    b_out = np.array([boundary(sig, a0 + i + L, "out", subj, edge) for i in starts])
    value = body + W_IN * b_in + W_OUT * b_out
    ok = b_in >= MIN_BOUNDARY
    live = np.where(ok, value, -np.inf) if ok.any() else value.copy()
    out: list[Window] = []
    best = float(live.max())
    while len(out) < k and np.isfinite(live).any():
        pick = int(np.argmax(live))
        if out and live[pick] < best - RUNNER_UP:
            break
        start, end = float(a0 + pick), float(a0 + pick + L)
        w = _finish(sig, max(lo, start), min(hi, end), float(L), float(value[pick]), False, s, a0, b0)
        if not ok.any():
            w.notes.append("no clean start anywhere in this clip — least-bad one used")
        out.append(w)
        near = np.abs(starts - pick) < max(1, int(np.ceil(2 * L / 3)))
        live[near] = -np.inf
    return out


def _snap(t: float, voiced: list[list[float]], kind: str, lo: float, hi: float) -> tuple[float, bool]:
    """Move a boundary out of a word: into the pause before (in) / after (out) it."""
    word = _inside_word(t, voiced)
    if word is None:
        return t, False
    options = [word[0] - 0.05, word[1] + 0.05]
    options.sort(key=lambda x: (abs(x - t), x if kind == "out" else -x))
    for x in options:
        if abs(x - t) <= SNAP_S and lo <= x <= hi:
            return round(x, 2), True
    return t, False


PROBLEMS = [  # (test on second k, zh, en)
    ("shaky", "晃动", "shaky"),
    ("nosubject", "主体不在画面里", "nothing in frame"),
    ("blurry", "模糊", "blurry"),
    ("dark", "太暗", "too dark"),
    ("dead", "画面没变化", "nothing happening"),
]


def _problems(sig: ClipSignals, ks: range) -> tuple[list[str], list[str]]:
    if len(ks) == 0:
        return [], []
    mot, subj = sig.arr("motion")[list(ks)], sig.arr("subject")[list(ks)]
    sharp, luma = sig.arr("sharpness")[list(ks)], sig.arr("luma")[list(ks)]
    hits = {
        "shaky": float((mot > SHAKY_FROM).mean()),
        "nosubject": float((subj < 0.3).mean()),
        "blurry": float((sharp < 0.2).mean()),
        "dark": float((luma < 25).mean()),
        "dead": float(((mot < DEAD_BELOW) & (subj < 0.3)).mean()),
    }
    picked = [p for p in PROBLEMS if hits[p[0]] >= 0.5]
    return [p[1] for p in picked][:2], [p[2] for p in picked][:2]


def _finish(sig: ClipSignals, start: float, end: float, target: float, score: float, whole: bool,
            s: np.ndarray, a0: int, b0: int) -> Window:
    start, snapped_in = _snap(start, sig.voiced, "in", a0, end - 1)
    end, snapped_out = _snap(end, sig.voiced, "out", start + 1, b0 if b0 < sig.n else sig.duration)
    end = min(end, sig.duration)
    zh, en = [], []
    if whole:
        zh.append("整段都留着")
        en.append("kept whole")
    else:
        head, tail = range(a0, int(np.floor(start))), range(int(np.ceil(end)), b0)
        hz, he = _problems(sig, head)
        tz, te = _problems(sig, tail)
        if start - a0 >= 0.5:
            zh.append(f"去掉开头 {start - a0:.0f} 秒" + (f"（{'、'.join(hz)}）" if hz else ""))
            en.append(f"dropped the first {start - a0:.0f}s" + (f" ({', '.join(he)})" if he else ""))
        if b0 - end >= 0.5:
            zh.append(f"去掉结尾 {b0 - end:.0f} 秒" + (f"（{'、'.join(tz)}）" if tz else ""))
            en.append(f"dropped the last {b0 - end:.0f}s" + (f" ({', '.join(te)})" if te else ""))
        zh.append(f"留下最好的 {end - start:.0f} 秒")
        en.append(f"kept the best {end - start:.0f}s")
    if snapped_in or snapped_out:
        zh.append("切点避开了说话中间")
        en.append("cut points moved out of mid-word")
    return Window(start=round(start, 2), end=round(end, 2), target=target, score=round(score, 3), whole=whole,
                  reason_zh="，".join(zh), reason_en="; ".join(en), seconds=[round(float(x), 3) for x in s])

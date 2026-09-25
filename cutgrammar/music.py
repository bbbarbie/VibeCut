"""Suggest music whose energy has the same shape as the edit.

A vlog's music is usually picked by genre or mood, which is taste. What is
measurable is *shape*: where the track builds, peaks and drops, against
where the edit gets busy and where it rests. A track that swells while the
picture settles fights the edit; one that peaks with the busiest section
carries it. So this compares curves, not labels, and only ever says what
the curves show.

Everything reads a TrackSource. LocalFolderSource (the creator's own music
folder) is the only one; a licensed library or generated music would be
another adapter behind the same list() -> list[Track].

Numpy only. Audio is decoded once per file by media.load_audio and
measured with the same frame_audio / spectral_flux the grammar rules use.
Features are cached next to the music, so a second run reads no audio.
"""

from __future__ import annotations

import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable

import numpy as np

from . import features
from .media import AUDIO_SR, load_audio

AUDIO_EXT = {".mp3", ".m4a", ".wav", ".flac"}
FEATURE_VERSION = 2  # 2: beat phase, for the snap grid

ENERGY_HZ = 1.0          # energy curve resolution: one value per second
SMOOTH_S = 5.0           # music energy is felt over phrases, not hits
ONSET_HOP_S = 0.01
TEMPO_EXCERPT_S = 60.0   # tempo from the middle minute; intros and outros lie
BPM_RANGE = (60.0, 180.0)
# Tempo is reported only when the periodicity is unmistakable. Both numbers
# are first guesses, tested against a click track and against noise; a wrong
# tempo is worse than none, so they err towards None.
MIN_COMB = 0.25          # mean normalised autocorrelation at 1..4 beats
MIN_SALIENCE = 4.0       # how far that stands above the other candidate tempi (robust z)

MATCH_POINTS = 64        # both curves are resampled to this many points
MIN_SHAPE_R = 0.3        # below this, a match is too weak to explain


# --------------------------------------------------------------------------
# tracks and sources
# --------------------------------------------------------------------------

@dataclass
class Track:
    path: str
    duration: float
    bpm: float | None
    energy: np.ndarray                 # 0..1, ENERGY_HZ values per second
    title: str = ""
    meta: dict = field(default_factory=dict)

    @property
    def id(self) -> str:
        return hashlib.sha1(self.path.encode()).hexdigest()[:12]


class TrackSource:
    """Anything that can hand over analysed tracks."""

    def list(self) -> list[Track]:  # pragma: no cover - interface
        raise NotImplementedError


class LocalFolderSource(TrackSource):
    """The creator's own music folder, walked recursively.

    Features are cached in `.vibecut-music.json` inside the folder, keyed by
    relative path + size + mtime, so only new or changed files are decoded.
    """

    CACHE_NAME = ".vibecut-music.json"

    def __init__(self, path: str, workers: int = 4,
                 progress: Callable[[int, int], None] | None = None) -> None:
        self.root = Path(path).expanduser()
        self.workers = workers
        self.progress = progress
        self.errors: list[tuple[str, str]] = []

    def files(self) -> list[Path]:
        out = []
        for dirpath, dirs, names in os.walk(self.root):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            out += [Path(dirpath) / n for n in names
                    if not n.startswith(".") and Path(n).suffix.lower() in AUDIO_EXT]
        return sorted(out)

    def _cache_path(self) -> Path:
        p = self.root / self.CACHE_NAME
        if os.access(self.root, os.W_OK):
            return p
        # read-only folder (a mounted drive, a shared library): cache beside it in ~
        h = hashlib.sha1(str(self.root.resolve()).encode()).hexdigest()[:12]
        return Path("~/.cache/vibecut/music").expanduser() / f"{h}.json"

    def list(self) -> list[Track]:
        files = self.files()
        cache_file = self._cache_path()
        try:
            cache = json.loads(cache_file.read_text())
            if cache.get("version") != FEATURE_VERSION:
                cache = {}
        except (OSError, ValueError):
            cache = {}
        entries: dict = cache.get("tracks", {})

        def key(p: Path) -> str:
            st = p.stat()
            return f"{p.relative_to(self.root)}|{st.st_size}|{st.st_mtime_ns}"

        keys = {p: key(p) for p in files}
        todo = [p for p in files if keys[p] not in entries]
        done = len(files) - len(todo)
        if self.progress:
            self.progress(done, len(files))

        def work(p: Path) -> tuple[Path, dict | None, str | None]:
            try:
                return p, _to_json(analyse(str(p))), None
            except Exception as e:  # noqa: BLE001 -- one bad file mustn't stop the folder
                return p, None, str(e)[:200]

        self.errors = []
        with ThreadPoolExecutor(max_workers=self.workers) as ex:
            for p, rec, err in ex.map(work, todo):
                if rec is not None:
                    entries[keys[p]] = rec
                else:
                    self.errors.append((str(p), err or "unknown error"))
                done += 1
                if self.progress:
                    self.progress(done, len(files))

        live = {keys[p] for p in files}
        entries = {k: v for k, v in entries.items() if k in live}
        if todo:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            tmp = cache_file.with_suffix(".tmp")
            tmp.write_text(json.dumps({"version": FEATURE_VERSION, "tracks": entries}))
            os.replace(tmp, cache_file)

        out = []
        for p in files:
            rec = entries.get(keys[p])
            if rec:
                out.append(_from_json(str(p), rec))
        return out


def _to_json(t: Track) -> dict:
    return {"duration": round(t.duration, 3), "bpm": t.bpm, "title": t.title,
            "energy": [round(float(x), 4) for x in t.energy], "meta": t.meta}


def _from_json(path: str, d: dict) -> Track:
    return Track(path=path, duration=d["duration"], bpm=d["bpm"],
                 energy=np.asarray(d["energy"], dtype=np.float32),
                 title=d.get("title", ""), meta=d.get("meta", {}))


# --------------------------------------------------------------------------
# features
# --------------------------------------------------------------------------

def analyse(path: str) -> Track:
    m = load_audio(path)
    tags = m.meta.get("tags", {})
    title = tags.get("title") or Path(path).stem
    if tags.get("artist"):
        title = f"{tags['artist']} — {title}"
    bpm, tempo = estimate_bpm(m)
    return Track(path=path, duration=m.duration, bpm=bpm, energy=energy_curve(m),
                 title=title, meta={"tempo": tempo})


def _smooth(x: np.ndarray, n: int) -> np.ndarray:
    if n <= 1 or len(x) < 2:
        return x
    k = np.hanning(n + 2)[1:-1]
    k /= k.sum()
    pad = np.pad(x, (n // 2, n - 1 - n // 2), mode="edge")
    return np.convolve(pad, k, mode="valid")


def energy_curve(m) -> np.ndarray:
    """Short-time RMS -> one value per second, smoothed, normalised 0..1.

    Averaged as power and kept in dB, because loudness is heard on a log
    scale; normalised between the 2nd and 98th percentile so a single hit
    or a silent tail doesn't flatten everything else.
    """
    db, hop_s = features.frame_audio(m, 0.01)
    if db.size == 0:
        return np.zeros(0, dtype=np.float32)
    per = max(1, int(round(1 / (ENERGY_HZ * hop_s))))
    n = len(db) // per
    if n == 0:
        return np.zeros(1, dtype=np.float32)
    power = (10 ** (db[: n * per] / 10)).reshape(n, per).mean(axis=1)
    curve = _smooth(10 * np.log10(power + 1e-12), int(SMOOTH_S * ENERGY_HZ))
    lo, hi = np.percentile(curve, 2), np.percentile(curve, 98)
    if hi - lo < 1.0:  # under 1 dB of movement: there is no shape to speak of
        return np.full(n, 0.5, dtype=np.float32)
    return np.clip((curve - lo) / (hi - lo), 0, 1).astype(np.float32)


def estimate_bpm(m) -> tuple[float | None, dict]:
    """Tempo by autocorrelating the spectral-flux onset envelope, or None.

    A comb over 1..4 beat-lags rewards a steady pulse over a single echo;
    the winning lag must stand clearly above every other candidate tempo.
    If it doesn't, the answer is None -- ambient, rubato, speech and noise
    all land here, which is correct.
    """
    info: dict = {}
    if not m.has_audio:
        return None, info
    n = len(m.audio)
    ex = int(TEMPO_EXCERPT_S * AUDIO_SR)
    a = max(0, (n - ex) // 2)
    env = features.spectral_flux(replace(m, audio=m.audio[a:a + ex]), ONSET_HOP_S).astype(np.float64)
    if len(env) < 4 / ONSET_HOP_S:
        return None, info

    # onsets relative to the local level, so a crescendo isn't a "beat"
    local = np.convolve(env, np.ones(50) / 50, mode="same")
    env = np.maximum(env - local, 0)
    if env.std() < 1e-9:
        return None, info
    env = (env - env.mean()) / env.std()

    f = np.fft.rfft(env, 2 * len(env))
    ac = np.fft.irfft(f * np.conj(f))[: len(env)]
    ac /= ac[0]

    lo = int(round(60 / BPM_RANGE[1] / ONSET_HOP_S))
    hi = int(round(60 / BPM_RANGE[0] / ONSET_HOP_S))
    lags = np.arange(lo, hi + 1)
    comb = np.array([np.mean([ac[k * L] for k in range(1, 5) if k * L < len(ac)]) for L in lags])
    best = int(np.argmax(comb))
    # Several lags tie on a steady pulse (a beat and its double both
    # repeat); prefer the fastest one that is nearly as strong.
    near = np.flatnonzero(comb >= 0.9 * comb[best])
    best = int(near[0]) if len(near) else best

    med = np.median(comb)
    mad = np.median(np.abs(comb - med)) * 1.4826 + 1e-9
    salience = (comb[best] - med) / mad
    info = {"comb": round(float(comb[best]), 3), "salience": round(float(salience), 2)}
    if comb[best] < MIN_COMB or salience < MIN_SALIENCE:
        return None, info

    L = lags[best]
    if 0 < L < len(ac) - 1:  # parabolic refinement of the lag
        y0, y1, y2 = ac[L - 1], ac[L], ac[L + 1]
        den = y0 - 2 * y1 + y2
        L = L + (0.5 * (y0 - y2) / den if abs(den) > 1e-12 else 0.0)
    # Phase: where on the period the onsets actually fall, so the grid is
    # beats and not just a tempo. Measured in the excerpt, carried to t=0.
    period_hops = L
    offsets = np.arange(int(np.ceil(period_hops)))
    k = np.arange(int(len(env) / period_hops))
    strength = [env[np.minimum((o + k * period_hops).round().astype(int), len(env) - 1)].sum() for o in offsets]
    p = float(np.argmax(strength))
    i = int(p)
    if 0 < i < len(strength) - 1:  # sub-hop refinement
        y0, y1, y2 = strength[i - 1], strength[i], strength[i + 1]
        den = y0 - 2 * y1 + y2
        p += 0.5 * (y0 - y2) / den if abs(den) > 1e-12 else 0.0
    period_s = period_hops * ONSET_HOP_S
    # Flux fires as a click enters the analysis window, about half a window
    # before it is heard; label each hop by its window's centre instead.
    win_s = max(int(AUDIO_SR * ONSET_HOP_S) * 4, 512) / AUDIO_SR
    info["phase"] = round(((a / AUDIO_SR) + p * ONSET_HOP_S + win_s / 2) % period_s, 3)
    return round(60.0 / period_s, 1), info


def beat_grid(track: Track, until: float) -> list[float]:
    """Beat times from 0 to `until`, or [] when the track has no reliable tempo."""
    phase = (track.meta.get("tempo") or {}).get("phase")
    if not track.bpm or phase is None:
        return []
    period = 60.0 / track.bpm
    return [round(float(t), 3) for t in np.arange(phase, until, period)]


# --------------------------------------------------------------------------
# the edit's energy shape
# --------------------------------------------------------------------------

@dataclass
class Section:
    """One beat of the storyboard, reduced to what energy is made of."""
    title: str
    shot_durations: list[float]
    shot_motion: list[float]       # per-shot motion magnitude (any consistent scale)

    @property
    def duration(self) -> float:
        return float(sum(self.shot_durations))


def section_energy(sections: list[Section]) -> np.ndarray:
    """0..1 per section: how much the picture moves, and how fast it cuts.

    Motion is duration-weighted across the section's shots; cutting rate
    is shots per minute. Each is min-max scaled across the storyboard, so
    the numbers are relative -- which is all shape matching needs.
    """
    if not sections:
        return np.zeros(0)
    motion = np.array([np.average(s.shot_motion, weights=np.maximum(s.shot_durations, 1e-3))
                       if s.shot_durations else 0.0 for s in sections])
    rate = np.array([60.0 * len(s.shot_durations) / max(s.duration, 1e-3) for s in sections])

    def scale(x: np.ndarray) -> np.ndarray:
        r = x.max() - x.min()
        return (x - x.min()) / r if r > 1e-9 else np.zeros_like(x)
    return 0.5 * scale(motion) + 0.5 * scale(rate)


def edit_curve(sections: list[Section]) -> tuple[np.ndarray, list[tuple[float, float]]]:
    """Section energies laid out over the edit's own time, at ENERGY_HZ.

    Returns the curve and each section's (start, end) in seconds. Smoothed
    like the music, so a hard change of section compares to a musical
    transition rather than to an impossible step.
    """
    e = section_energy(sections)
    spans, t = [], 0.0
    for s in sections:
        spans.append((t, t + s.duration))
        t += s.duration
    n = max(1, int(np.ceil(t * ENERGY_HZ)))
    curve = np.zeros(n)
    for (a, b), v in zip(spans, e):
        curve[int(a * ENERGY_HZ):int(np.ceil(b * ENERGY_HZ))] = v
    return _smooth(curve, int(SMOOTH_S * ENERGY_HZ)), spans


# --------------------------------------------------------------------------
# matching
# --------------------------------------------------------------------------

@dataclass
class Suggestion:
    track: Track
    score: float        # Pearson r of the two shapes, -1..1
    reason: str         # "" when the curves don't support a specific claim


def _resample(x: np.ndarray, n: int = MATCH_POINTS) -> np.ndarray:
    if len(x) == 1:
        return np.full(n, float(x[0]))
    return np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x)


def _z(x: np.ndarray) -> np.ndarray | None:
    s = x.std()
    return None if s < 1e-6 else (x - x.mean()) / s


def shape_score(track_window: np.ndarray, edit: np.ndarray) -> float:
    """Correlation of shape: both curves resampled and z-normalised first,
    so a quiet track and a loud one with the same arc score the same."""
    a, b = _z(_resample(track_window)), _z(_resample(edit))
    if a is None or b is None:
        return 0.0
    return float(np.clip(np.mean(a * b), -1, 1))


def match(sections: list[Section], tracks: list[Track], top: int = 5) -> dict:
    """Rank tracks by how well their energy shape follows the edit's.

    The music is assumed to start with the edit, so each track is compared
    over its first edit-length seconds; tracks shorter than the edit are
    left out rather than looped or stretched.
    """
    curve, spans = edit_curve(sections)
    length = sum(s.duration for s in sections)
    long_enough = [t for t in tracks if t.duration >= length and len(t.energy)]
    result = {"edit_seconds": round(length, 1), "tracks": len(tracks),
              "too_short": len(tracks) - len(long_enough), "flat": False, "suggestions": []}
    if _z(_resample(curve)) is None:
        result["flat"] = True  # one energy level throughout: no shape to match
        return result

    scored = []
    for t in long_enough:
        win = t.energy[: max(1, int(np.ceil(length * ENERGY_HZ)))]
        scored.append((shape_score(win, curve), t, win))
    scored.sort(key=lambda x: -x[0])
    e = section_energy(sections)
    result["suggestions"] = [
        Suggestion(t, round(s, 3), explain(win, t, sections, spans, e) if s >= MIN_SHAPE_R else "")
        for s, t, win in scored[:top]
    ]
    return result


# --------------------------------------------------------------------------
# reasons: only what the curves show
# --------------------------------------------------------------------------

def _mmss(s: float) -> str:
    return f"{int(s // 60)}:{int(s % 60):02d}"


def _section_at(t: float, spans: list[tuple[float, float]]) -> int:
    for i, (a, b) in enumerate(spans):
        if a <= t < b:
            return i
    return len(spans) - 1


def explain(win: np.ndarray, track: Track, sections: list[Section],
            spans: list[tuple[float, float]], e: np.ndarray) -> str:
    """One line built from measured features, or "" if nothing specific holds.

    Claims it can make: where the track peaks and whether that falls in the
    edit's busiest section; how long it builds to get there; a sharp drop
    that lands on a section boundary where the edit also calms down.
    """
    clauses: list[str] = []
    x = win.astype(np.float64)
    if len(x) < 10 or x.max() - x.min() < 0.25:
        return ""
    hz = ENERGY_HZ
    busiest = int(np.argmax(e))
    pk = int(np.argmax(x))
    tp = pk / hz

    # Build: from the quietest point before the peak, a rise of at least a
    # third of the range over at least 15 seconds.
    lo = int(np.argmin(x[: pk + 1])) if pk > 0 else 0
    build = (pk - lo) / hz
    peak_in_busiest = spans[busiest][0] - 5 <= tp <= spans[busiest][1] + 5
    title = sections[busiest].title
    if x[pk] - x[lo] >= 0.33 and build >= 15:
        span = f"{int(build)}s" if build < 90 else _mmss(build)
        c = f"builds for {span} then peaks at {_mmss(tp)}"
        clauses.append(c + (f" — lines up with your {title} section" if peak_in_busiest else ""))
    elif peak_in_busiest and x[pk] - np.median(x) >= 0.25:
        clauses.append(f"peaks at {_mmss(tp)}, inside your {title} section")

    # Drop: largest fall over 8 seconds, if it lands where the edit eases off.
    w = int(8 * hz)
    if len(x) > w:
        falls = x[:-w] - x[w:]
        i = int(np.argmax(falls))
        if falls[i] >= 0.35:
            t_drop = (i + w / 2) / hz
            for k in range(1, len(spans)):
                if abs(spans[k][0] - t_drop) <= 6 and e[k] <= e[k - 1] - 0.3:
                    clauses.append(f"drops at {_mmss(t_drop)} as your edit eases into {sections[k].title}")
                    break

    if not clauses:
        return ""
    line = "; ".join(clauses[:2])
    return line[0].upper() + line[1:] + (f" · {track.bpm:g} BPM" if track.bpm else "")

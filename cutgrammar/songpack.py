"""VibeCut's own songs: the fallback when no track can be found online.

Why this exists: the bed (web/backend/bed.py) looks for music on Openverse.
When that fails -- offline, a blocked network, a Mac whose Python can't
check certificates -- the edit used to go out silent. A finished vlog has
music under it, so there is always something to fall back on.

The pack is *never* preferred. Openverse (or the creator's own folder) is
asked first and its best fit wins; these songs are only read when that
search hands back nothing usable.

The songs are composed here, from a seed, not shipped as audio files:
nothing to licence (they are ours, CC0), nothing to download, a few KB of
code in the repo instead of tens of MB of audio. Each one is rendered once
into the cache and read like any other track (music.LocalFolderSource),
so tempo, energy shape and the drop are measured, not assumed.

Every song has a real arrangement -- an intro, a lighter verse, a build, a
fuller chorus (the drop the bed lands at the end of the hook), a break, a
second chorus and an outro -- because the picker scores a track's energy
shape against the edit's, and a flat loop has no shape to match.

They are simple songs. Real recordings from the online search are better
and stay first; this is only so there is never *no* music.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import music

SR = 44100
VERSION = 2          # bump when the composer changes: old renders are left behind, new ones made
LENGTH_S = 260.0     # long enough for a 4-minute edit (the picker wants need + 8 s)
BITRATE = "128k"

# The pace a bed asks for -> the songs that suit it (bed.PACE_BPM's ranges).
PACES = ("calm", "balanced", "fast")

NOTE = {"C": 0, "C#": 1, "Db": 1, "D": 2, "Eb": 3, "E": 4, "F": 5, "F#": 6, "Gb": 6,
        "G": 7, "Ab": 8, "A": 9, "Bb": 10, "B": 11}
MAJOR = [0, 2, 4, 5, 7, 9, 11]


@dataclass(frozen=True)
class Song:
    id: str
    title: str
    pace: str           # calm | balanced | fast
    bpm: float
    key: str
    chords: tuple       # scale degrees, 1-based, one per bar (7 = seventh chord on that degree)
    lead: str           # keys | pluck | bell | organ
    drums: str          # soft | backbeat | four
    tags: tuple
    seed: int


# Eight per pace. Titles are plain and warm; tags are the words the picker's
# vibe() reads (remix.DRIVING / SLOW), so a calm song reads as calm.
SONGS: tuple[Song, ...] = (
    # calm: 72-90 BPM, soft drums, keys and bells
    Song("calm-morning-light", "Morning Light", "calm", 76, "F", (1, 5, 6, 4), "keys", "soft", ("calm", "piano", "acoustic"), 11),
    Song("calm-slow-coffee", "Slow Coffee", "calm", 82, "D", (1, 6, 4, 5), "pluck", "soft", ("calm", "acoustic", "folk"), 12),
    Song("calm-window-seat", "Window Seat", "calm", 72, "Bb", (4, 1, 5, 6), "bell", "soft", ("calm", "ambient", "peaceful"), 13),
    Song("calm-sunday", "Sunday", "calm", 88, "G", (1, 3, 4, 4), "keys", "soft", ("calm", "relax", "piano"), 14),
    Song("calm-low-tide", "Low Tide", "calm", 80, "Eb", (6, 4, 1, 5), "pluck", "soft", ("calm", "chill", "acoustic"), 15),
    Song("calm-paper-lanterns", "Paper Lanterns", "calm", 74, "A", (1, 4, 6, 5), "bell", "soft", ("calm", "peaceful", "lullaby"), 16),
    Song("calm-long-walk", "Long Walk", "calm", 90, "C", (2, 5, 1, 6), "keys", "backbeat", ("calm", "folk", "chill"), 17),
    Song("calm-evening", "Evening", "calm", 78, "E", (4, 5, 3, 6), "pluck", "soft", ("calm", "relax", "acoustic"), 18),
    # balanced: 92-112 BPM, backbeat, a bit of everything
    Song("steady-postcards", "Postcards", "balanced", 96, "G", (1, 5, 6, 4), "pluck", "backbeat", ("happy", "indie", "travel"), 21),
    Song("steady-good-weather", "Good Weather", "balanced", 104, "D", (1, 4, 6, 5), "keys", "backbeat", ("happy", "uplifting", "indie"), 22),
    Song("steady-side-streets", "Side Streets", "balanced", 100, "A", (6, 4, 1, 5), "organ", "backbeat", ("indie", "folk", "travel"), 23),
    Song("steady-little-things", "Little Things", "balanced", 108, "C", (1, 6, 2, 5), "bell", "backbeat", ("happy", "ukulele", "uplifting"), 24),
    Song("steady-road-snacks", "Road Snacks", "balanced", 112, "F", (4, 1, 5, 6), "pluck", "four", ("happy", "travel", "pop"), 25),
    Song("steady-open-windows", "Open Windows", "balanced", 94, "Eb", (1, 3, 6, 4), "keys", "backbeat", ("uplifting", "indie", "folk"), 26),
    Song("steady-weekend-plans", "Weekend Plans", "balanced", 106, "Bb", (1, 5, 4, 4), "organ", "backbeat", ("happy", "pop", "travel"), 27),
    Song("steady-new-city", "New City", "balanced", 98, "E", (6, 5, 4, 5), "bell", "backbeat", ("indie", "uplifting", "travel"), 28),
    # fast: 118-134 BPM, four on the floor, brighter leads. The odd tempi
    # (6000 / 47) are on purpose: the beat finder works in 10 ms hops, and at
    # 124, 126 and 132 BPM its whole-hop lag drifted off the beat while the
    # half-time lag didn't, so those came back as 62, 63 and 66.
    Song("upbeat-sunburst", "Sunburst", "fast", 125, "A", (1, 5, 6, 4), "organ", "four", ("upbeat", "pop", "summer"), 31),
    Song("upbeat-city-lights", "City Lights", "fast", 128, "F", (6, 4, 1, 5), "pluck", "four", ("upbeat", "electronic", "dance"), 32),
    Song("upbeat-good-day", "Good Day", "fast", 120, "C", (1, 4, 5, 4), "keys", "four", ("upbeat", "happy", "funk"), 33),
    Song("upbeat-high-five", "High Five", "fast", 6000 / 47, "D", (4, 5, 6, 1), "bell", "four", ("upbeat", "pop", "energetic"), 34),
    Song("upbeat-summer-run", "Summer Run", "fast", 6000 / 45, "G", (1, 6, 4, 5), "organ", "four", ("upbeat", "summer", "dance"), 35),
    Song("upbeat-neon", "Neon", "fast", 122, "Eb", (6, 4, 5, 1), "pluck", "four", ("upbeat", "electronic", "synth"), 36),
    Song("upbeat-confetti", "Confetti", "fast", 118, "Bb", (1, 5, 4, 5), "keys", "backbeat", ("upbeat", "funk", "groove"), 37),
    Song("upbeat-rooftop", "Rooftop", "fast", 130, "E", (1, 3, 4, 5), "bell", "four", ("upbeat", "dance", "summer"), 38),
)


def songs_for(pace: str | None) -> list[Song]:
    pace = pace if pace in PACES else "balanced"
    return [s for s in SONGS if s.pace == pace]


# --------------------------------------------------------------------------
# sounds
# --------------------------------------------------------------------------

def _hz(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


def _env(n: int, attack: float, decay: float) -> np.ndarray:
    t = np.arange(n) / SR
    a = np.clip(t / max(attack, 1e-4), 0, 1)
    return a * np.exp(-t / max(decay, 1e-4))


def _tone(freq: float, n: int, partials: list[float], detune: float = 0.0) -> np.ndarray:
    t = np.arange(n) / SR
    out = np.zeros(n)
    for k, amp in enumerate(partials, 1):
        if freq * k > SR / 2.2:
            break
        out += amp * np.sin(2 * np.pi * freq * k * t + k)
        if detune:
            out += amp * 0.6 * np.sin(2 * np.pi * freq * k * (1 + detune) * t)
    return out


_CACHE: dict = {}


def _voice(kind: str, midi: int, dur: float) -> np.ndarray:
    """One note of an instrument, cached by (kind, pitch, length)."""
    key = (kind, midi, round(dur, 2))
    if key in _CACHE:
        return _CACHE[key]
    f = _hz(midi)
    tail = {"pad": 0.6, "keys": 0.8, "bell": 1.2, "pluck": 0.4, "organ": 0.15, "bass": 0.1}.get(kind, 0.2)
    n = int((dur + tail) * SR)
    if kind == "keys":        # soft electric piano: a bright attack that mellows
        x = _tone(f, n, [1, 0.35, 0.12, 0.05], 0.0015) * _env(n, 0.004, 0.9)
        x += 0.25 * _tone(f * 4, n, [1]) * _env(n, 0.002, 0.08)
    elif kind == "bell":      # mallets: inharmonic shimmer, long ring
        t = np.arange(n) / SR
        x = (np.sin(2 * np.pi * f * t) + 0.4 * np.sin(2 * np.pi * f * 2.76 * t) * np.exp(-t / 0.3)
             + 0.2 * np.sin(2 * np.pi * f * 5.4 * t) * np.exp(-t / 0.12)) * _env(n, 0.002, 1.1)
    elif kind == "pluck":     # nylon-ish: many partials dying fast, the fundamental lingering
        t = np.arange(n) / SR
        x = sum((0.8 ** k) * np.sin(2 * np.pi * f * k * t) * np.exp(-t * (2.5 + 3.5 * k)) for k in range(1, 9))
        x *= np.clip(t / 0.003, 0, 1)
    elif kind == "organ":     # bright held chord tone, short release
        x = _tone(f, n, [1, 0.5, 0.3, 0.15, 0.08], 0.002)
        x *= np.clip(np.arange(n) / (0.01 * SR), 0, 1) * np.clip((n - np.arange(n)) / (tail * SR), 0, 1)
    elif kind == "pad":       # warm, slow swell
        x = _tone(f, n, [1, 0.3, 0.12, 0.05], 0.004)
        a = np.clip(np.arange(n) / (0.5 * SR), 0, 1)
        r = np.clip((n - np.arange(n)) / (tail * SR), 0, 1)
        x *= a * r
    elif kind == "bass":
        x = _tone(f, n, [1, 0.35, 0.1]) * _env(n, 0.005, max(dur * 0.9, 0.15))
        x *= np.clip((n - np.arange(n)) / (tail * SR), 0, 1)
    else:
        raise ValueError(kind)
    x = x.astype(np.float32)
    _CACHE[key] = x
    return x


def _drum(kind: str, rng: np.random.Generator) -> np.ndarray:
    if kind == "kick":
        n = int(0.35 * SR)
        t = np.arange(n) / SR
        f = 45 + 80 * np.exp(-t / 0.04)
        x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.12)
    elif kind == "soft_kick":
        n = int(0.3 * SR)
        t = np.arange(n) / SR
        f = 50 + 40 * np.exp(-t / 0.05)
        x = 0.6 * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.1)
    elif kind == "snare":
        n = int(0.25 * SR)
        t = np.arange(n) / SR
        noise = rng.standard_normal(n)
        noise = np.diff(noise, prepend=0)      # tilt towards the top: a crack, not a hiss
        x = 0.35 * noise * np.exp(-t / 0.06) + 0.5 * np.sin(2 * np.pi * 190 * t) * np.exp(-t / 0.05)
    elif kind == "clap":
        n = int(0.2 * SR)
        t = np.arange(n) / SR
        noise = np.diff(rng.standard_normal(n), prepend=0)
        bursts = sum(np.exp(-np.clip(t - d, 0, None) / 0.008) * (t >= d) for d in (0, 0.01, 0.02))
        x = 0.3 * noise * (bursts + np.exp(-t / 0.05))
    elif kind == "hat":
        n = int(0.06 * SR)
        t = np.arange(n) / SR
        noise = np.diff(np.diff(rng.standard_normal(n + 2)))
        x = 0.12 * noise * np.exp(-t / 0.015)
    elif kind == "shaker":
        n = int(0.09 * SR)
        t = np.arange(n) / SR
        noise = np.diff(rng.standard_normal(n + 1))
        x = 0.08 * noise * np.sin(np.pi * t / t[-1]) ** 2
    else:
        raise ValueError(kind)
    return x.astype(np.float32)


# --------------------------------------------------------------------------
# the arrangement
# --------------------------------------------------------------------------

# Sections in bars, and which layers play in each. The chorus is the drop.
SECTIONS = [
    ("intro", 4), ("verse", 8), ("build", 4), ("chorus", 8),
    ("verse", 8), ("build", 4), ("chorus", 8), ("break", 8),
    ("build", 4), ("chorus", 8), ("chorus", 8),
]
LAYERS = {
    # the verse sits well under the chorus: the picker reads a song's shape
    # from its loudness, and a verse at 0.9 of the chorus has none
    "intro":  {"pad": 0.5, "comp": 0.35},
    "verse":  {"pad": 0.45, "comp": 0.5, "bass": 0.45, "drums": 0.3, "hats": 0.25},
    "build":  {"pad": 0.6, "comp": 0.7, "bass": 0.7, "drums": 0.55, "hats": 0.8, "rise": 1.0},
    "chorus": {"pad": 1.0, "comp": 1.0, "bass": 1.0, "drums": 1.0, "hats": 1.0, "lead": 1.0},
    "break":  {"pad": 0.6, "comp": 0.45, "lead": 0.35, "hats": 0.2},
    "outro":  {"pad": 0.5, "comp": 0.35},
}


def _plan(song: Song) -> list[str]:
    """Bar-by-bar section names, cycling the arrangement until LENGTH_S, then an outro."""
    bar = 4 * 60.0 / song.bpm
    want = int(np.ceil(LENGTH_S / bar))
    bars: list[str] = []
    i = 0
    while len(bars) < want - 4:
        name, n = SECTIONS[i % len(SECTIONS)]
        if i >= len(SECTIONS) and name == "intro":
            name = "break"
        bars += [name] * n
        i += 1
    return bars[: want - 4] + ["outro"] * 4


def _chord(song: Song, degree: int, octave: int) -> list[int]:
    root = NOTE[song.key] + 12 * octave
    idx = degree - 1
    tones = [root + MAJOR[(idx + k) % 7] + 12 * ((idx + k) // 7) for k in (0, 2, 4)]
    if degree in (1, 4):   # add the major seventh's softer cousin, the ninth: warmer than a bare triad
        tones.append(root + MAJOR[(idx + 1) % 7] + 12 * ((idx + 1) // 7) + 12)
    return tones


def _motif(song: Song, rng: np.random.Generator, steps: int) -> list[tuple[int, int] | None]:
    """A two-bar melody on the major pentatonic: (step offset, scale index) or rests."""
    penta = [0, 1, 2, 4, 5]   # indices into MAJOR: do re mi so la
    out: list[tuple[int, int] | None] = []
    pos = int(rng.integers(0, 5))
    for s in range(steps):
        if s % 2 == 1 and rng.random() < 0.55:
            out.append(None)
            continue
        if rng.random() < 0.25 and s % 4 != 0:
            out.append(None)
            continue
        pos = int(np.clip(pos + rng.choice([-2, -1, -1, 0, 1, 1, 2]), 0, 9))
        out.append((s, pos))
    return out


def render(song: Song) -> np.ndarray:
    """The whole song, stereo float32 at SR."""
    rng = np.random.default_rng(song.seed)
    beat = 60.0 / song.bpm
    bar = 4 * beat
    plan = _plan(song)
    n = int((len(plan) * bar + 2.0) * SR)
    L = np.zeros(n, dtype=np.float32)
    R = np.zeros(n, dtype=np.float32)

    def put(x: np.ndarray, t: float, gain: float, pan: float = 0.0) -> None:
        i = int(t * SR)
        if i >= n:
            return
        x = x[: n - i]
        L[i:i + len(x)] += x * gain * (1 - max(pan, 0))
        R[i:i + len(x)] += x * gain * (1 + min(pan, 0))

    drums = {k: _drum(k, rng) for k in ("kick", "soft_kick", "snare", "clap", "hat", "shaker")}
    eighth = beat / 2
    swing = 0.06 * eighth if song.pace == "calm" else 0.0
    motif_a = _motif(song, rng, 16)
    motif_b = _motif(song, rng, 16)
    comp_kind = song.lead if song.lead != "organ" else "keys"
    lead_kind = {"keys": "bell", "pluck": "keys", "bell": "keys", "organ": "organ"}[song.lead]
    fade = np.ones(len(plan))
    fade[-4:] = np.linspace(1.0, 0.15, 4)

    for b, name in enumerate(plan):
        t0 = b * bar
        lay = LAYERS[name]
        g = fade[b]
        degree = song.chords[b % len(song.chords)]
        chord = _chord(song, degree, 4)
        root = NOTE[song.key] + 36 + MAJOR[degree - 1]
        if "pad" in lay:
            for i, m in enumerate(chord[:3]):
                put(_voice("pad", m, bar), t0, 0.07 * lay["pad"] * g, pan=(-0.4, 0.0, 0.4)[i])
        if "comp" in lay:
            # the steady pulse the beat finder locks onto: an arpeggio on the eighths
            for k in range(8):
                m = chord[[0, 1, 2, 1, 3 % len(chord), 2, 1, 2][k] % len(chord)] 
                t = t0 + k * eighth + (swing if k % 2 else 0)
                acc = 1.0 if k % 2 == 0 else 0.45     # the beat louder than the "and": a pulse, not a ripple
                put(_voice(comp_kind, m, eighth * 1.5), t, 0.09 * lay["comp"] * acc * g, pan=0.25 if k % 2 else -0.25)
        if "bass" in lay:
            # on the beats only: a dotted bass line reads to the beat finder as a
            # tempo of its own (96 BPM came back as 64 when it was dotted)
            pattern = [(0, 0.9), (1, 0.9), (2, 0.9), (3, 0.9)] if song.drums != "four" else \
                [(0, 0.45), (0.5, 0.45), (1, 0.45), (1.5, 0.45), (2, 0.45), (2.5, 0.45), (3, 0.45), (3.5, 0.45)]
            for k, (at, length) in enumerate(pattern):
                m = root + (12 if song.drums == "four" and k % 2 else 7 if song.drums != "four" and k == 2 else 0)
                put(_voice("bass", m, length * beat), t0 + at * beat, 0.22 * lay["bass"] * g)
        if "drums" in lay:
            dg = lay["drums"] * g
            if song.drums == "four":
                for k in range(4):
                    put(drums["kick"], t0 + k * beat, 0.55 * dg)
                for k in (1, 3):
                    put(drums["clap"], t0 + k * beat, 0.3 * dg, pan=0.05)   # louder read as half time
            elif song.drums == "backbeat":
                for at in (0, 2, 3) if b % 2 else (0, 2):
                    put(drums["kick"], t0 + at * beat, 0.5 * dg)
                for k in (1, 3):
                    put(drums["snare"], t0 + k * beat, 0.45 * dg, pan=0.05)
            else:   # soft: brushes, not a kit
                for k in (0, 2):
                    put(drums["soft_kick"], t0 + k * beat, 0.6 * dg)
                for k in (1, 3):
                    put(drums["snare"], t0 + k * beat, 0.15 * dg)
        if "hats" in lay:
            hk = "shaker" if song.drums == "soft" else "hat"
            per = 16 if name == "build" and song.pace == "fast" else 8
            step = bar / per
            for k in range(per):
                acc = 1.0 if k % 2 else 0.6
                if song.drums == "four" and per == 8:
                    acc = 1.2 if k % 2 else 0.4      # the off-beat open hat of dance music
                put(drums[hk], t0 + k * step + (swing if k % 2 else 0), 0.9 * lay["hats"] * acc * g, pan=0.35)
        if "rise" in lay:
            # a noise swell over the build, so the chorus arrives as a lift
            run_start = b
            while run_start > 0 and plan[run_start - 1] == "build":
                run_start -= 1
            frac0 = (b - run_start) / 4
            m = int(bar * SR)
            ramp = np.linspace(frac0, frac0 + 0.25, m) ** 2
            noise = np.diff(rng.standard_normal(m + 1)).astype(np.float32)
            put(0.03 * noise * ramp, t0, g)
        if "lead" in lay:
            motif = motif_a if (b // 2) % 4 < 3 else motif_b
            half = (b % 2) * 8
            for item in motif[half:half + 8]:
                if item is None:
                    continue
                s, idx = item
                m = NOTE[song.key] + 72 + MAJOR[[0, 1, 2, 4, 5][idx % 5]] + 12 * (idx // 5) - 12
                t = t0 + (s - half) * eighth + (swing if s % 2 else 0)
                put(_voice(lead_kind, m, eighth * 1.8), t, 0.11 * lay["lead"] * g, pan=-0.1)

    x = np.stack([L, R])
    x = _room(x)
    # level: a bed, not a master. Peak to -1 dBFS after a light saturation that
    # only rounds the loudest hits (more would squash the verse/chorus contrast).
    x = np.tanh(x * 0.9 / max(1e-6, np.percentile(np.abs(x[:, ::7]), 99.95)))
    x *= 0.89 / max(1e-6, float(np.abs(x).max()))
    tail = int(1.5 * SR)
    x[:, -tail:] *= np.linspace(1, 0, tail)
    return x.astype(np.float32)


def _room(x: np.ndarray) -> np.ndarray:
    """A small room: a few early reflections and a soft tail, by overlap-add."""
    rng = np.random.default_rng(0)
    m = int(0.8 * SR)
    t = np.arange(m) / SR
    out = x.copy()
    mono = x.mean(axis=0)
    block = 1 << 18
    size = 1 << int(np.ceil(np.log2(block + m)))
    for ch in range(2):   # one tail per side, from different noise: width without a second mix
        ir = rng.standard_normal(m) * np.exp(-t / 0.3) * 0.016
        ir[: int((0.011 + 0.006 * ch) * SR)] = 0
        H = np.fft.rfft(ir, size)
        wet = np.zeros(x.shape[1] + size, dtype=np.float32)
        for i in range(0, x.shape[1], block):
            seg = mono[i:i + block]
            y = np.fft.irfft(np.fft.rfft(seg, size) * H, size)[: len(seg) + m]
            wet[i:i + len(y)] += y
        out[ch] += wet[: x.shape[1]]
    return out


# --------------------------------------------------------------------------
# the source
# --------------------------------------------------------------------------

def cache_dir() -> Path:
    root = Path(os.environ.get("VIBECUT_CACHE", str(Path.home() / ".cache" / "vibecut")))
    return root / "music" / "pack" / f"v{VERSION}"


def record(song: Song) -> dict:
    """The licence record, in the shape openverse.parse gives, so credit() and vibe() read it."""
    return {"id": song.id, "title": song.title, "creator": "VibeCut", "license": "cc0",
            "license_version": "1.0", "source": "vibecut", "duration": None, "url": None,
            "page": "", "tags": list(song.tags), "genres": [], "pack": True}


def ensure(song: Song, folder: Path) -> Path:
    """Render the song into `folder` once; later calls only find the file."""
    f = folder / f"{song.id}.m4a"
    if f.exists():
        return f
    folder.mkdir(parents=True, exist_ok=True)
    x = render(song)
    pcm = (np.clip(x.T, -1, 1) * 32767).astype("<i2").tobytes()
    part = f.with_suffix(".part.m4a")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "s16le", "-ar", str(SR), "-ac", "2", "-i", "-",
                    "-c:a", "aac", "-b:a", BITRATE,
                    "-metadata", f"title={song.title}", "-metadata", "artist=VibeCut",
                    "-metadata", "comment=Composed by VibeCut. CC0: free to use anywhere, no credit needed.",
                    str(part)], input=pcm, check=True, capture_output=True)
    os.replace(part, f)
    return f


class PackSource(music.TrackSource):
    """The pack's songs for one pace, rendered on first use and analysed like a folder."""

    def __init__(self, pace: str | None, progress=None) -> None:
        self.songs = songs_for(pace)
        self.progress = progress

    def list(self) -> list[music.Track]:
        folder = cache_dir() / self.songs[0].pace
        for i, s in enumerate(self.songs):
            if self.progress:
                self.progress(i, len(self.songs))
            ensure(s, folder)
        mine = {f"{s.id}.m4a" for s in self.songs}
        return [t for t in music.LocalFolderSource(str(folder), progress=self.progress).list()
                if Path(t.path).name in mine and dress(t) is not None]


def dress(t: music.Track) -> music.Track | None:
    """A rendered pack song with its licence record and title; None if the
    file isn't one of the pack's."""
    s = next((s for s in SONGS if f"{s.id}.m4a" == Path(t.path).name), None)
    if s is None:
        return None
    t.meta = {**t.meta, "licence": record(s)}
    t.title = f"{s.title} (VibeCut)"
    return t

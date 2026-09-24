"""Per-frame signals the grammar rules are measured against."""

from __future__ import annotations

import numpy as np

from .media import AUDIO_SR, Media


def luma(frames: np.ndarray) -> np.ndarray:
    """(n, H, W, 3) -> (n, H, W) float32 in 0..255."""
    f = frames.astype(np.float32)
    return 0.2126 * f[..., 0] + 0.7152 * f[..., 1] + 0.0722 * f[..., 2]


def motion(media: Media) -> np.ndarray:
    """Mean absolute luma difference between consecutive frames.

    Length n_frames, with motion[i] describing the change INTO frame i.
    A crude proxy for optical-flow magnitude, and good enough to answer
    'is this cut landing on a moving frame or a dead one'. Values at shot
    boundaries are meaningless (they measure the cut itself) and callers
    are expected to exclude them.
    """
    y = luma(media.frames)
    d = np.abs(np.diff(y, axis=0)).mean(axis=(1, 2))
    return np.concatenate([[0.0], d]).astype(np.float32)


def brightness(media: Media) -> np.ndarray:
    return luma(media.frames).mean(axis=(1, 2)).astype(np.float32)


def channel_means(media: Media) -> np.ndarray:
    """(n, 3) mean R/G/B -- a cheap stand-in for white balance."""
    return media.frames.astype(np.float32).mean(axis=(1, 2))


# --------------------------------------------------------------------------
# audio
# --------------------------------------------------------------------------

def frame_audio(media: Media, hop_s: float = 0.01) -> tuple[np.ndarray, float]:
    """Short-time RMS in dB at `hop_s` resolution, plus the hop used.

    10 ms hops: fine enough to time a J-cut, which is the whole point.
    """
    if not media.has_audio:
        return np.zeros(0, dtype=np.float32), hop_s

    hop = max(int(AUDIO_SR * hop_s), 1)
    n = len(media.audio) // hop
    x = media.audio[: n * hop].reshape(n, hop)
    rms = np.sqrt((x.astype(np.float64) ** 2).mean(axis=1)) + 1e-9
    return (20 * np.log10(rms)).astype(np.float32), hop_s


def _stft_mag(x: np.ndarray, hop: int, win_len: int) -> np.ndarray:
    """Magnitude spectrogram, (n_frames, n_bins) float32."""
    if len(x) < win_len:
        x = np.pad(x, (0, win_len - len(x)))
    n = 1 + (len(x) - win_len) // hop
    idx = np.arange(win_len)[None, :] + hop * np.arange(n)[:, None]
    window = np.hanning(win_len).astype(np.float32)
    frames = x[idx] * window
    return np.abs(np.fft.rfft(frames, axis=1)).astype(np.float32)


def audio_novelty(media: Media, hop_s: float = 0.01, win: int = 25) -> np.ndarray:
    """How sharply the sound changes at each hop.

    Spectral flux, not just level. A cut from voice to music, or from one
    room to another, often keeps the same loudness while the timbre changes
    completely -- level alone misses exactly the events a listener notices.
    Peaks here mark the moments the ear hears the scene change, which is
    what a J/L cut deliberately offsets from the visual cut.
    """
    if not media.has_audio:
        return np.zeros(0, dtype=np.float32)

    hop = max(int(AUDIO_SR * hop_s), 1)
    mag = _stft_mag(media.audio, hop, win_len=max(hop * 4, 512))

    # half-wave rectified flux: only energy appearing counts as an onset
    flux = np.diff(mag, axis=0)
    flux = np.maximum(flux, 0.0).sum(axis=1)
    flux = np.concatenate([[0.0], flux])

    # plus the slower level change, so a fade to silence also registers
    db, _ = frame_audio(media, hop_s)
    n = min(len(flux), len(db))
    flux, db = flux[:n], db[:n]

    pad = np.pad(db, win, mode="edge")
    c = np.cumsum(pad, dtype=np.float64)
    means = (c[win:] - c[:-win]) / win
    level_change = np.abs(means[win : win + n] - means[:n])

    def norm(a):
        s = np.percentile(a, 99) + 1e-9
        return np.clip(a / s, 0, 1)

    return (norm(flux) + norm(level_change)).astype(np.float32)


def speech_mask(media: Media, hop_s: float = 0.01) -> np.ndarray:
    """Coarse voiced/unvoiced flag from level alone.

    Not a real VAD -- Silero is the upgrade. Adequate for 'when does the
    talking start', which is all the opening-pace check needs.
    """
    db, _ = frame_audio(media, hop_s)
    if db.size == 0:
        return db.astype(bool)
    active = db[db > db.min() + 1.0]
    if active.size == 0:
        return np.zeros(len(db), dtype=bool)
    thresh = np.percentile(active, 60) - 6.0
    return db > thresh

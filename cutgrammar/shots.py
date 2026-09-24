"""Shot boundary detection.

Histogram-distance with an adaptive threshold -- the same family as
PySceneDetect, which is what the tech plan calls for in v1. Hard cuts are
what vlogs are made of, and this catches them without a GPU or a model
download. Gradual transitions (dissolves, fades) are the known blind spot;
TransNetV2 is the upgrade path when they start to matter.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .media import Media

BINS = 8  # per channel -> 512-bin RGB histogram


@dataclass
class Shot:
    index: int
    start_frame: int
    end_frame: int  # exclusive
    start_t: float
    end_t: float

    @property
    def duration(self) -> float:
        return self.end_t - self.start_t

    @property
    def n_frames(self) -> int:
        return self.end_frame - self.start_frame


def histograms(frames: np.ndarray) -> np.ndarray:
    """(n, H, W, 3) uint8 -> (n, BINS**3) float32, L1-normalised."""
    q = (frames.astype(np.uint16) * BINS) >> 8  # 0..BINS-1
    idx = q[..., 0] * BINS * BINS + q[..., 1] * BINS + q[..., 2]
    idx = idx.reshape(len(frames), -1)

    out = np.zeros((len(frames), BINS ** 3), dtype=np.float32)
    for i, row in enumerate(idx):
        out[i] = np.bincount(row, minlength=BINS ** 3)
    out /= out.sum(axis=1, keepdims=True) + 1e-9
    return out


def hist_distance(h: np.ndarray) -> np.ndarray:
    """Per-frame-pair histogram intersection distance. Length n-1."""
    inter = np.minimum(h[:-1], h[1:]).sum(axis=1)
    return 1.0 - inter


def detect(
    media: Media,
    min_shot_s: float = 0.4,
    k: float = 6.0,
    floor: float = 0.28,
) -> list[Shot]:
    """Find hard cuts.

    Threshold is adaptive: median + k * MAD over the whole distance curve,
    floored so that a very static video doesn't produce phantom cuts.
    """
    if media.n_frames < 3:
        return [Shot(0, 0, media.n_frames, 0.0, media.duration)]

    h = histograms(media.frames)
    d = hist_distance(h)

    med = float(np.median(d))
    mad = float(np.median(np.abs(d - med))) + 1e-9
    thresh = max(med + k * mad, floor)

    min_gap = max(int(min_shot_s * media.fps), 2)
    cuts: list[int] = []
    last = -min_gap
    for i in np.flatnonzero(d > thresh):
        i = int(i) + 1  # boundary belongs to the *next* frame
        if i - last >= min_gap:
            cuts.append(i)
            last = i

    bounds = [0, *cuts, media.n_frames]
    return [
        Shot(n, a, b, media.t(a), media.t(b))
        for n, (a, b) in enumerate(zip(bounds[:-1], bounds[1:]))
    ]


def shot_histograms(media: Media, shots: list[Shot]) -> np.ndarray:
    """One mean histogram per shot -- used for near-duplicate detection."""
    h = histograms(media.frames)
    out = np.zeros((len(shots), h.shape[1]), dtype=np.float32)
    for i, s in enumerate(shots):
        out[i] = h[s.start_frame : s.end_frame].mean(axis=0)
    return out

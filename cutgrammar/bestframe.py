"""Pick the frame that stands for a shot, and score the shot.

Until someone presses play, a shot *is* its thumbnail. Every storyboard,
shelf and timeline in VibeCut shows shots this way, so the choice decides
whether a creator recognises their footage at a glance. The first frame is
the worst candidate a tool can pick: it is where the phone is still being
raised, the exposure is still settling and the subject hasn't turned round.

The score is craft, not taste -- is the frame sharp, is it exposed, is
there anything in it -- which is what "no amateur tells" can promise.

Uses media.preview (thumbnail-size samples from load_index) when present,
because blur is invisible at 48x27; falls back to the 48x27 frames.
The weights and the sharpness scale are first guesses, like every other
number in this package. They only rank frames against each other; nothing
is cut or changed on the strength of them.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field

import numpy as np

from .media import Media
from .shots import Shot

WEIGHTS = {"sharpness": 0.35, "exposure": 0.30, "contrast": 0.20, "steadiness": 0.15}

# The first and last moments of a take are handling, not footage.
EDGE_S = 0.7
EDGE_PENALTY = 0.85


@dataclass
class BestFrame:
    shot_index: int
    frame: int            # index into media.frames / media.preview
    t: float              # seconds into the file
    score: float          # 0..1, this frame
    quality: float        # 0..1, the shot as a whole
    parts: dict = field(default_factory=dict)  # per-component, best frame


def _luma(frames: np.ndarray) -> np.ndarray:
    f = frames.astype(np.float32)
    return 0.299 * f[..., 0] + 0.587 * f[..., 1] + 0.114 * f[..., 2]


def frame_scores(frames: np.ndarray) -> dict[str, np.ndarray]:
    """Per-frame components, each 0..1 where 1 is better. (n, H, W, 3) in."""
    y = _luma(frames)
    n = len(frames)

    # Exposure: mid-grey mean, and not much of the frame crushed or blown.
    mean = y.mean(axis=(1, 2)) / 255.0
    clipped = ((y < 8) | (y > 247)).mean(axis=(1, 2))
    exposure = (1 - np.minimum(1, np.abs(mean - 0.47) / 0.4)) * (1 - np.minimum(1, clipped * 2))

    # Contrast: a flat frame (lens cap, wall, fog) carries no picture.
    contrast = np.minimum(1, y.std(axis=(1, 2)) / 60.0)

    # Sharpness: variance of the Laplacian, on a log scale because it spans
    # orders of magnitude between a blurred pan and a locked-off detail.
    lap = (y[:, 1:-1, :-2] + y[:, 1:-1, 2:] + y[:, :-2, 1:-1] + y[:, 2:, 1:-1]
           - 4 * y[:, 1:-1, 1:-1])
    lv = lap.var(axis=(1, 2))
    sharpness = np.clip((np.log10(lv + 1) - 1.0) / 2.0, 0, 1)

    # Steadiness: a frame that looks like its neighbours isn't mid-whip-pan.
    if n > 1:
        d = np.abs(np.diff(y, axis=0)).mean(axis=(1, 2)) / 255.0
        d = np.concatenate([[d[0]], np.maximum(d[:-1], d[1:]), [d[-1]]])
        steadiness = 1 - np.minimum(1, d / 0.25)
    else:
        steadiness = np.ones(1)

    total = sum(WEIGHTS[k] * v for k, v in
                (("sharpness", sharpness), ("exposure", exposure),
                 ("contrast", contrast), ("steadiness", steadiness)))
    return {"total": total, "sharpness": sharpness, "exposure": exposure,
            "contrast": contrast, "steadiness": steadiness}


def pick(media: Media, shot: Shot, scores: dict[str, np.ndarray] | None = None) -> BestFrame:
    if scores is None:
        scores = frame_scores(media.preview if media.preview is not None else media.frames)
    a, b = shot.start_frame, max(shot.end_frame, shot.start_frame + 1)
    total = scores["total"][a:b].copy()

    ts = np.array([media.t(i) for i in range(a, b)])
    edge = (ts - shot.start_t < EDGE_S) | (shot.end_t - ts < EDGE_S)
    if edge.all():
        edge[:] = False  # a very short shot: nothing but edges
    total[edge] *= EDGE_PENALTY

    i = int(np.argmax(total))
    # A shot is as good as its better half, not its single best frame.
    raw = scores["total"][a:b]
    top = np.sort(raw)[len(raw) // 2:]
    return BestFrame(
        shot_index=shot.index,
        frame=a + i,
        t=float(ts[i]),
        score=float(total[i]),
        quality=float(top.mean()),
        parts={k: float(v[a + i]) for k, v in scores.items() if k != "total"},
    )


def best_frames(media: Media, shots: list[Shot]) -> list[BestFrame]:
    scores = frame_scores(media.preview if media.preview is not None else media.frames)
    return [pick(media, s, scores) for s in shots]


def write_jpegs(images: list[np.ndarray], paths: list[str], quality: int = 3) -> None:
    """Encode same-sized (H, W, 3) uint8 images with one ffmpeg call.

    `quality` is ffmpeg's -q:v, 2 (best) .. 31.
    """
    if not images:
        return
    groups: dict[tuple, list[int]] = {}
    for i, im in enumerate(images):
        groups.setdefault(im.shape, []).append(i)
    for (h, w, _), idx in groups.items():
        raw = b"".join(np.ascontiguousarray(images[i]).tobytes() for i in idx)
        # image2 wants a numbered pattern; write there, then move into place.
        with tempfile.TemporaryDirectory() as d:
            p = subprocess.run(
                ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                 "-s", f"{w}x{h}", "-i", "-", "-q:v", str(quality),
                 os.path.join(d, "%05d.jpg")],
                input=raw, capture_output=True)
            if p.returncode != 0:
                raise RuntimeError(p.stderr.decode(errors="ignore")[:400])
            for n, i in enumerate(idx):
                shutil.move(os.path.join(d, f"{n + 1:05d}.jpg"), paths[i])

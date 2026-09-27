"""Reading a finished edit once: where its cuts are, where things start
moving, and its beat.

The finished video goes through `media.load()` -- the same full-rate
48×27 read the grammar rules use, pixels touched once -- because an effect
snapped to movement needs the frame the movement starts on; the keyframe
index (±0.5 s) can't give that. Cuts come from `shots.detect`, the beat from
`music.estimate_bpm` on the video's own sound (None when there's no steady
pulse, which is honest for speech and ambience).

A movement onset is a frame where the picture starts changing after being
still -- a rise in frame difference well above the shot's own quiet level
-- away from the cut itself (a cut isn't a movement). Thresholds are priors.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import numpy as np

from cutgrammar import features, media, music, shots

ONSET_RISE = 3.0        # x the shot's own median frame difference
ONSET_FLOOR = 1.5       # luma levels: below this nothing is moving
QUIET_BEFORE = 4        # frames of relative calm before an onset
CUT_GUARD = 3           # frames either side of a cut are the cut, not movement


def key(path: str) -> str:
    st = os.stat(path)
    return hashlib.sha1(f"{os.path.realpath(path)}|{st.st_size}|{st.st_mtime_ns}".encode()).hexdigest()[:16]


def onsets(motion: np.ndarray, cut_frames: list[int], fps: float) -> list[float]:
    out: list[float] = []
    bounds = [0, *sorted(cut_frames), len(motion)]
    for a, b in zip(bounds, bounds[1:]):
        seg = motion[a + CUT_GUARD:b - CUT_GUARD] if b - a > 2 * CUT_GUARD + QUIET_BEFORE else np.zeros(0)
        if seg.size < QUIET_BEFORE + 2:
            continue
        base = max(float(np.median(seg)), 1e-3)
        hi = max(base * ONSET_RISE, ONSET_FLOOR)
        calm = base * 1.5
        last = -10 ** 9
        for i in range(QUIET_BEFORE, len(seg)):
            if seg[i] >= hi and np.all(seg[i - QUIET_BEFORE:i] < max(calm, hi / 2)) and i - last > QUIET_BEFORE:
                out.append(round((a + CUT_GUARD + i) / fps, 3))
                last = i
    return out


def analyse(path: str, cache_dir: Path | None = None) -> dict:
    if cache_dir:
        cache_dir.mkdir(parents=True, exist_ok=True)
        hit = cache_dir / f"{key(path)}.json"
        if hit.exists():
            return json.loads(hit.read_text())
    m = media.load(path)
    sh = shots.detect(m)
    fps = m.fps or 30.0
    mot = features.motion(m)
    cut_frames = [s.start_frame for s in sh[1:]]
    bpm, tempo = music.estimate_bpm(m)
    info = media.probe(path)
    v = next(s for s in info["streams"] if s.get("codec_type") == "video")
    w, h = int(v.get("width", 0)), int(v.get("height", 0))
    if media._rotation(v) in (90, 270):
        w, h = h, w
    out = {"path": path, "duration": round(m.duration, 3), "fps": round(fps, 3), "width": w, "height": h,
           "cuts": [round(s.start_t, 3) for s in sh],
           "onsets": onsets(mot, cut_frames, fps),
           "bpm": bpm, "phase": (tempo or {}).get("phase")}
    if cache_dir:
        (cache_dir / f"{key(path)}.json").write_text(json.dumps(out))
    return out

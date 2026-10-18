"""Music that matches a reel's feel: brightness joins tempo and shape.

A 220 Hz tone is darker than a 4 kHz one; a reference reel's brightness
lands in the fingerprint; and of two tracks equal in tempo and shape, the
pick takes the one whose brightness sits near the reel's.

    python tests/test_feel.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

os.environ.setdefault("VIBECUT_CACHE", tempfile.mkdtemp(prefix="vibecut-feel-"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

failures: list[str] = []


def check(name: str, cond: bool, got: str = "") -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{': ' + got if got else ''}")
    if not cond:
        failures.append(name)


def tone(path: str, seconds: float, freq: float, bpm: float = 120.0, sr: int = 16000, loud_from: float | None = 24.0) -> None:
    t = np.arange(int(seconds * sr)) / sr
    x = 0.05 * np.sin(2 * np.pi * freq * t)
    if loud_from is not None:
        x[t >= loud_from] *= 8
    for b in np.arange(0, seconds, 60.0 / bpm):
        i = int(b * sr)
        x[i:i + 40] += 0.5
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())


def main() -> int:
    from cutgrammar import music as mu
    from web.backend import make, remix
    d = Path(tempfile.mkdtemp(prefix="vibecut-feel-tracks-"))
    tone(str(d / "dark.wav"), 200.0, 220.0)
    tone(str(d / "bright.wav"), 200.0, 4000.0)
    pool = mu.LocalFolderSource(str(d)).list()
    by = {t.title: t for t in pool}
    print("brightness")
    check("a low tone is darker than a high one", by["dark"].meta["bright"] < by["bright"].meta["bright"],
          f"{by['dark'].meta['bright']} vs {by['bright'].meta['bright']}")
    check("the feature is cached with its version", mu.FEATURE_VERSION == 3)

    print("the pick")
    fp = make.fingerprint("short", "fast", 60.0)
    fp["bpm"] = (100.0, 140.0)
    dark_fp = {**fp, "bright": by["dark"].meta["bright"]}
    bright_fp = {**fp, "bright": by["bright"].meta["bright"]}
    pd = remix.pick_from(pool, dark_fp, 40.0, 1.5)
    pb = remix.pick_from(pool, bright_fp, 40.0, 1.5)
    check("a dark reel gets the dark track, a bright reel the bright one",
          pd and pb and pd["track"].title == "dark" and pb["track"].title == "bright", f"{pd and pd['track'].title} / {pb and pb['track'].title}")
    none = remix.pick_from(pool, fp, 40.0, 1.5)
    check("no brightness known: the pick still works", none is not None)
    styles = [{"pace": {"median_s": 0.8, "curve": [1] * 5, "first_s": 1.0}, "music": {"bpm": 120, "arc": "builds", "bright": 3100.0}, "duration": 30.0}]
    check("the fingerprint carries the reels' brightness", remix.fingerprint(styles)["bright"] == 3100.0)

    print()
    if failures:
        print(f"{len(failures)} failed: {failures}")
        return 1
    print("all passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

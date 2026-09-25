"""Does trim keep the good middle and cut on stable ground?

Fixtures differ in one respect at a time: an opening that is shaky, an
opening with the subject out of frame, and both. The clean stretch is
8-20s in each. Trim must choose inside it, and its in/out points must sit
on steady frames with the subject present -- a window that merely exists,
or merely scores well on average, doesn't pass.

    python tests/test_trim.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cutgrammar import media, signals, trim  # noqa: E402
from cutgrammar.signals import ClipSignals  # noqa: E402

CLEAN = (8.0, 20.0)


def _fixture(path: str, subject_x: str, shaking: str) -> str:
    """A textured wall, an orange subject, a camera that shakes when told."""
    graph = (
        "color=c=0x2a3440:s=800x450:d=24:r=30,drawgrid=w=18:h=18:t=3:c=0xe0e8f0@0.9[bg];"
        "color=c=0xff8a1e:s=150x150:d=24:r=30[box];"
        f"[bg][box]overlay=x='{subject_x}':y=150[c];"
        f"[c]crop=640:360:x='80+if({shaking},78*sin(t*23),0)':y='45+if({shaking},43*sin(t*31+1),0)'"
    )
    p = subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", graph, "-c:v", "libx264",
                        "-preset", "ultrafast", "-g", "15", "-pix_fmt", "yuv420p", path], capture_output=True)
    if p.returncode:
        raise RuntimeError(p.stderr.decode()[:300])
    return path


def _sig(n: int, **kw) -> ClipSignals:
    base = dict(duration=float(n), quality=[0.7] * n, sharpness=[0.8] * n, luma=[120.0] * n,
                contrast=[0.8] * n, motion=[2.0] * n, subject=[0.8] * n, edge=[0.0] * n,
                speech=[0.0] * n, voiced=[], thumb=[0.0] * 144)
    base.update(kw)
    return ClipSignals(**base)


def main() -> int:
    failures = []

    def check(name: str, cond: bool, got: str) -> None:
        print(f"  {'PASS' if cond else 'FAIL'}  {name}: {got}")
        if not cond:
            failures.append(name)

    with tempfile.TemporaryDirectory() as d:
        print("building fixtures...")
        cases = {
            "shaky and subject out of frame": _fixture(f"{d}/both.mp4", "if(lt(t,8),900,325)", "lt(t,8)+gte(t,20)"),
            "shaky only": _fixture(f"{d}/shaky.mp4", "325", "lt(t,8)+gte(t,20)"),
            "subject out of frame only": _fixture(f"{d}/absent.mp4", "if(lt(t,8),900,325)", "gte(t,20)"),
        }
        for name, path in cases.items():
            sig = signals.from_media(media.load_index(path, audio=False))
            for target in (8, None):
                w = trim.best_window(sig, target)
                label = f"{name}, target {target or 'auto'}"
                check(f"{label}: window is inside the clean middle",
                      CLEAN[0] <= w.start and w.end <= CLEAN[1], f"{w.start}–{w.end}")
                mot, subj = sig.arr("motion"), sig.arr("subject")
                a, b = int(w.start), int(np.ceil(w.end)) - 1
                check(f"{label}: in and out land on steady frames with the subject in",
                      mot[a] < trim.SHAKY_FROM and mot[b] < trim.SHAKY_FROM and subj[a] >= 0.4 and subj[b] >= 0.4,
                      f"motion {mot[a]:.1f}/{mot[b]:.1f}, subject {subj[a]:.2f}/{subj[b]:.2f}")
            check(f"{name}: the reason names what was cut", "去掉开头" in w.reason_zh, w.reason_zh)

    # The start matters more than the average. Window A (0-5s) has the higher
    # mean but opens on the subject at the edge of frame, leaving; window B
    # (6-11s) is a little worse on average and opens clean. A whip-pan at 5s
    # stops A being dodged by starting a second later. Trim must take B --
    # and only because of the start weighting: with it turned off, A wins.
    q = [0.95] * 5 + [0.1] + [0.85] * 5 + [0.5] * 5
    mot = [1.5] * 5 + [30.0] + [1.5] * 10
    edge = [1.0] + [0.0] * 15
    sig = _sig(16, quality=q, motion=mot, edge=edge)
    w = trim.best_window(sig, 5)
    check("a clean start beats a slightly higher average", w.start >= 6, f"{w.start}–{w.end}")
    old = trim.W_IN, trim.MIN_BOUNDARY
    trim.W_IN, trim.MIN_BOUNDARY = 0.0, -9
    w0 = trim.best_window(sig, 5)
    trim.W_IN, trim.MIN_BOUNDARY = old
    check("  …and it's the start weighting that decided", w0.start < 6, f"without it: {w0.start}–{w0.end}")

    # Never mid-word: a clip where every candidate second boundary falls inside
    # speech must have its cut points moved into a pause.
    words = [[0.2, 3.4], [3.6, 7.3], [7.5, 11.6], [11.8, 15.9]]
    sig = _sig(16, speech=[0.9] * 16, voiced=words, quality=[0.6] * 4 + [0.9] * 8 + [0.6] * 4)
    w = trim.best_window(sig, 8)
    inside = [t for t in (w.start, w.end) if trim._inside_word(t, words)]
    check("cut points never land inside a word", not inside, f"{w.start}–{w.end}, words {words}")

    # A talking clip is only cleaned up, never shortened by a chosen amount.
    sig = _sig(30, speech=[0.8] * 30, motion=[20.0, 18.0] + [2.0] * 26 + [19.0, 21.0])
    w = trim.best_window(sig)
    check("a talking clip keeps everything but the unusable ends", w.end - w.start >= 25, f"{w.start}–{w.end}")

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

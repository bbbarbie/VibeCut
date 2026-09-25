"""Does bestframe pick the frame a person would, and does quality move?

Same pattern as test_discriminates: fixtures built from one source that
differ in exactly one respect (blur, or exposure), so a score that shifts
is responding to that and nothing else.

    python tests/test_bestframe.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cutgrammar import bestframe, media, shots  # noqa: E402

SRC = "testsrc2=size=640x360:rate=30"
SEG = 3.0  # seconds per segment


def _ff(args: list[str]) -> None:
    p = subprocess.run(["ffmpeg", "-v", "error", "-y", *args], capture_output=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.decode()[:400])


def _encode(src_filter: str, dur: float, out: str) -> str:
    # keyframe every 0.5s so index mode has something to choose between
    _ff(["-f", "lavfi", "-i", f"{SRC},{src_filter}", "-t", str(dur),
         "-c:v", "libx264", "-preset", "ultrafast", "-g", "15",
         "-pix_fmt", "yuv420p", out])
    return out


def _quality(path: str) -> bestframe.BestFrame:
    m = media.load_index(path, audio=False)
    return bestframe.best_frames(m, shots.detect(m))[0]


def main() -> int:
    failures = []

    def check(name: str, cond: bool, got: str) -> None:
        print(f"  {'PASS' if cond else 'FAIL'}  {name}: {got}")
        if not cond:
            failures.append(name)

    with tempfile.TemporaryDirectory() as d:
        print("building fixtures...")
        # One take: blurred, then sharp, then underexposed. Same picture
        # throughout, so the only reason to prefer the middle is craft.
        mixed = _encode(
            f"gblur=sigma=6:enable='lt(t,{SEG})',"
            f"eq=brightness=-0.45:enable='gte(t,{2 * SEG})'",
            3 * SEG, os.path.join(d, "mixed.mp4"))
        m = media.load_index(mixed, audio=False)
        one = shots.Shot(0, 0, m.n_frames, 0.0, m.duration)
        bf = bestframe.pick(m, one)
        check("best frame lands in the sharp, exposed segment",
              SEG < bf.t < 2 * SEG, f"t={bf.t:.1f}s")

        # Blur ladder: sharpness must fall monotonically as sigma rises.
        ladder = [0, 1.5, 4, 10]
        sharp = [_quality(_encode(f"gblur=sigma={s}" if s else "null", SEG,
                                  os.path.join(d, f"blur{s}.mp4"))).parts["sharpness"]
                 for s in ladder]
        check("sharpness falls as blur rises",
              all(a > b for a, b in zip(sharp, sharp[1:])),
              " > ".join(f"{s:.2f}" for s in sharp))

        clean = _quality(os.path.join(d, "blur0.mp4")).quality
        blurred = _quality(os.path.join(d, "blur10.mp4")).quality
        dark = _quality(_encode("eq=brightness=-0.45", SEG,
                                os.path.join(d, "dark.mp4"))).quality
        check("shot quality separates sharp from blurred",
              clean - blurred > 0.15, f"{clean:.2f} vs {blurred:.2f}")
        check("shot quality separates exposed from underexposed",
              clean - dark > 0.15, f"{clean:.2f} vs {dark:.2f}")

        # A take with nothing to choose between: don't hand back frame 0,
        # which in real footage is the phone still being raised.
        still = _encode("trim=end_frame=1,loop=loop=-1:size=1,setpts=N/30/TB",
                        SEG, os.path.join(d, "still.mp4"))
        m = media.load_index(still, audio=False)
        bf = bestframe.pick(m, shots.Shot(0, 0, m.n_frames, 0.0, m.duration))
        check("first moment of a take is avoided", bf.t >= bestframe.EDGE_S,
              f"t={bf.t:.1f}s")

        # Thumbnails come out as real JPEGs of the chosen frame.
        out = os.path.join(d, "thumb.jpg")
        bestframe.write_jpegs([m.preview[bf.frame]], [out])
        with open(out, "rb") as fh:
            check("thumbnail is written as JPEG", fh.read(2) == b"\xff\xd8",
                  f"{os.path.getsize(out)} bytes")

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

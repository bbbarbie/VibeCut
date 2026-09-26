"""Does the exported file match the timeline -- length, words on screen, sound?

Two synthetic clips (one with sound, one silent) and a gap are exported with
one overlay frame scheduled for a known window. The file must:

- be exactly as many frames long as the timeline says (joins can't drift);
- show the overlay inside its window and not outside it (the schedule is
  honoured to the frame, which is what makes preview == export);
- have one audio track even though one clip is silent and one span is a gap.

Needs ffmpeg. Takes ~10 s.

    python tests/test_export.py
"""

from __future__ import annotations

import os
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TMP = Path(tempfile.mkdtemp(prefix="vibecut-export-"))
os.environ["VIBECUT_EXPORTS"] = str(TMP / "out")
os.environ.setdefault("VIBECUT_CACHE", str(TMP / "cache"))

from web.backend import export  # noqa: E402


def ff(*args: str) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


def red_png(path: Path, w: int, h: int) -> None:
    """Transparent frame with an opaque red block in the middle."""
    img = np.zeros((h, w, 4), np.uint8)
    img[h // 3: 2 * h // 3, w // 3: 2 * w // 3] = (255, 0, 0, 255)
    raw = b"".join(b"\x00" + img[y].tobytes() for y in range(h))

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def frame_at(path: str, t: float, w: int, h: int) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", path, "-frames:v", "1",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(h, w, 3)


def main() -> int:
    failures = []

    def check(name: str, cond: bool, got: str) -> None:
        print(f"  {'PASS' if cond else 'FAIL'}  {name}: {got}")
        if not cond:
            failures.append(name)

    a, b = TMP / "a.mp4", TMP / "b.mp4"
    ff("-f", "lavfi", "-i", "testsrc2=s=640x360:r=30:d=6", "-f", "lavfi", "-i", "sine=f=440:d=6",
       "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(a))
    ff("-f", "lavfi", "-i", "color=c=green:s=640x360:r=30:d=6", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(b))
    clips = {"a": {"id": "a", "path": str(a), "width": 640, "height": 360},
             "b": {"id": "b", "path": str(b), "width": 640, "height": 360}}
    # 1.5 s of a (from 2.0), a 0.5 s gap, 1.2 s of b, a's last 1.2 s: 4.4 s = 132 frames.
    items = [
        {"key": "a:0", "kind": "shot", "clip_id": "a", "src_start": 2.0, "src_end": 3.5, "seq_start": 0.0, "seq_end": 1.5, "n": 1},
        {"key": "g", "kind": "gap", "clip_id": None, "src_start": 0, "src_end": 0.5, "seq_start": 1.5, "seq_end": 2.0, "n": None},
        {"key": "b:0", "kind": "shot", "clip_id": "b", "src_start": 1.0, "src_end": 2.2, "seq_start": 2.0, "seq_end": 3.2, "n": 2},
        # runs to the very last frame of its file, where decoders come up short
        {"key": "a:1", "kind": "shot", "clip_id": "a", "src_start": 4.8, "src_end": 6.0, "seq_start": 3.2, "seq_end": 4.4, "n": 3},
    ]
    job = export.create(items, clips, "Test / edit", None)
    W, H = job.size["w"], job.size["h"]
    check("landscape footage exports landscape 1080p", (W, H) == (1920, 1080), f"{W}x{H}")
    png = TMP / "red.png"
    red_png(png, W, H)
    export.save_frame(job, 0, png.read_bytes())
    export.start(job, [{"frame": 0, "start": 1.0, "end": 2.5}])
    import time
    while job.stage not in ("done", "error"):
        time.sleep(0.2)
    check("export finishes", job.stage == "done", job.error or job.stage)
    if job.stage != "done":
        return 1

    out = job.path
    n = int(subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                            "stream=nb_read_frames", "-of", "csv=p=0", out], capture_output=True, text=True).stdout.strip())
    check("exactly as many frames as the timeline, even to a file's last frame", n == 132, f"{n} frames (timeline: 132)")
    streams = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", out],
                             capture_output=True, text=True).stdout.split()
    check("one audio track despite a silent clip and a gap", streams.count("audio") == 1, str(streams))

    def red(t):
        px = frame_at(out, t, W, H)[H // 2, W // 2].astype(int)
        return px[0] > 200 and px[1] < 60 and px[2] < 60

    inside = [red(t) for t in (1.05, 1.75, 2.45)]
    outside = [red(t) for t in (0.9, 2.6)]
    check("overlay shows throughout its window, across a gap and a cut", all(inside), str(inside))
    check("…and not a frame outside it", not any(outside), str(outside))
    gap = frame_at(out, 1.6, W, H)[10, 10]
    check("a gap is black", int(gap.max()) < 20, str(gap.tolist()))
    check("the export is named from the edit, safely", Path(out).name.startswith("Test edit"), Path(out).name)

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

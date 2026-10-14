"""The shot menu's everyday fixes: speed, volume / mute, turn, fill.

Each fix is built into one shot of an otherwise identical edit, and the
measurement must move by the amount that was built in, and nowhere else:

- speed 2x: the shot lasts half as long in the edit, the next shot moves
  up by that much, its sound is the same tone (pitch kept) over half the
  time, and the exported picture runs through the source twice as fast;
- 0.5x: twice as long;
- volume 50%: half the level; mute: silent; the other shot untouched;
- a quarter turn: a wide clip in a wide frame becomes tall, so bars appear
  at the sides; fill: the picture covers the frame, no bars;
- a cut through a fixed shot keeps the fix on both pieces; undo removes it.

    python tests/test_shot_fixes.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TMP = Path(tempfile.mkdtemp(prefix="vibecut-fixes-"))
os.environ["VIBECUT_CACHE"] = str(TMP / "cache")
os.environ["VIBECUT_EXPORTS"] = str(TMP / "out")

from web.backend import audiomix as am  # noqa: E402
from web.backend import board as bd  # noqa: E402
from web.backend import export  # noqa: E402
from web.backend import timeline  # noqa: E402

SR = am.SR
failures: list[str] = []


def check(name: str, cond: bool, got: str = "") -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{': ' + got if got else ''}")
    if not cond:
        failures.append(name)


def ff(*args: str) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


def energy(x: np.ndarray, freq: float, a: float, b: float) -> float:
    s = x[int(a * SR):int(b * SR), 0]
    if len(s) == 0:
        return 0.0
    t = np.arange(len(s)) / SR
    return float(2 * np.hypot((s * np.cos(2 * np.pi * freq * t)).mean(), (s * np.sin(2 * np.pi * freq * t)).mean()))


def shot(cid: str) -> dict:
    return {"id": cid, "name": f"{cid}.MOV", "capture_time": None, "gps": None, "duration": 8.0,
            "shots": [{"index": 0, "start": 0.0, "end": 8.0, "thumb": "shot000.jpg", "best_t": 4.0,
                       "quality": 0.6, "aesthetic": None, "utility": False, "labels": [["x", 0.8]],
                       "faces": 0, "face_area": 0.0, "embedding": [1.0] + [0.0] * 7}]}


def frame(path: Path, t: float, w: int = 32, h: int = 18) -> np.ndarray:
    p = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(path), "-frames:v", "1",
                        "-vf", f"scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                       capture_output=True, check=True)
    return np.frombuffer(p.stdout, np.uint8).reshape(h, w).astype(float)


def main() -> int:
    A, B = TMP / "a.mov", TMP / "b.mov"
    # A: brightness climbs with time (so speed shows in the picture), 440 Hz.
    ff("-f", "lavfi", "-i", "nullsrc=s=320x180:r=30:d=8,geq=lum='min(255,T*30)':cb=128:cr=128",
       "-f", "lavfi", "-i", "sine=f=440:d=8:sample_rate=48000", "-c:v", "libx264", "-pix_fmt", "yuv420p",
       "-c:a", "pcm_s16le", "-shortest", str(A))
    ff("-f", "lavfi", "-i", "color=c=gray:s=320x180:r=30:d=8", "-f", "lavfi",
       "-i", "sine=f=880:d=8:sample_rate=48000", "-c:v", "libx264", "-pix_fmt", "yuv420p",
       "-c:a", "pcm_s16le", "-shortest", str(B))
    clips = {"A": {"id": "A", "path": str(A), "duration": 8.0, "width": 320, "height": 180},
             "B": {"id": "B", "path": str(B), "duration": 8.0, "width": 320, "height": 180}}
    cat = bd.Catalog.from_clips([shot("A"), shot("B")])
    option = {"key": "o", "name": "Two", "summary": "", "beats": [{"title": "All", "detail": "", "shots": [
        {"id": "A:0", "start": 1.0, "end": 5.0}, {"id": "B:0", "start": 1.0, "end": 3.0}]}]}
    mk = lambda d: {"options": [option]}  # noqa: E731
    s = bd.Session()
    s.add({"kind": "chat", "text": "go", "ops": [], "direction": {"text": "go"}}, cat, mk)
    s.add({"kind": "direct", "text": "pick", "ops": [{"op": "choose_option", "option": "o"}]}, cat, mk)

    def items():
        return timeline.layout(s.board)

    def mix():
        return am.render(items(), clips)[0]

    def fix(**kw):
        return s.add({"kind": "direct", "text": "fix", "ops": [{"op": "set_shot", "shot": "A:0", **kw}]}, cat, mk)

    before = mix()
    full = energy(before, 440, 0.2, 3.8)

    print("speed")
    t2 = fix(speed=2)
    it = items()
    check("2x: the shot lasts half as long", abs((it[0]["seq_end"] - it[0]["seq_start"]) - 2.0) < 1e-3,
          f"{it[0]['seq_end'] - it[0]['seq_start']:.3f}s")
    check("…and the next shot moves up", abs(it[1]["seq_start"] - 2.0) < 1e-3, f"{it[1]['seq_start']:.3f}")
    x = mix()
    check("the mix is the new length", abs(len(x) / SR - 4.0) < 0.01, f"{len(x) / SR:.3f}s")
    kept = energy(x, 440, 0.2, 1.8) / full
    check("its sound keeps its pitch over the shorter time", kept > 0.8, f"{kept:.2f} of the 440 Hz level")
    check("…and stops where the shot ends", energy(x, 440, 2.1, 3.9) < 0.02, f"{energy(x, 440, 2.1, 3.9):.3f}")
    check("the next shot sounds from its new place", energy(x, 880, 2.1, 3.9) > 0.9 * energy(before, 880, 4.1, 5.9))
    check("the turn says so", any("2×" in ln["text"] for ln in t2.lines), str(t2.lines))
    s.toggle(t2.id, cat, mk)
    t5 = fix(speed=0.5)
    check("0.5x: twice as long", abs(items()[0]["seq_end"] - 8.0) < 1e-3, f"{items()[0]['seq_end']:.3f}")
    s.toggle(t5.id, cat, mk)
    check("undo: back to its own length", abs(items()[0]["seq_end"] - 4.0) < 1e-3 and "speed" not in items()[0])

    print("volume and mute")
    tv = fix(gain=0.5)
    half = energy(mix(), 440, 0.2, 3.8) / full
    check("50% is half the level", abs(half - 0.5) < 0.02, f"{half:.3f}")
    tm = fix(mute=True)
    check("muted is silent", energy(mix(), 440, 0.2, 3.8) < 0.01)
    check("…the other shot untouched", abs(energy(mix(), 880, 4.2, 5.8) - energy(before, 880, 4.2, 5.8)) < 0.01)
    s.toggle(tm.id, cat, mk)
    s.toggle(tv.id, cat, mk)

    print("a cut keeps the fixes")
    tc = fix(speed=2, gain=0.5)
    s.add({"kind": "direct", "text": "cut", "ops": [{"op": "split", "shot": "A:0", "at": 3.0}]}, cat, mk)
    it = items()
    check("both pieces keep speed and level", it[0].get("speed") == 2 and it[1].get("speed") == 2
          and it[1].get("gain") == 0.5, str([(i.get("speed"), i.get("gain")) for i in it[:2]]))
    check("…and the edit's length is unchanged by the cut", abs(it[1]["seq_end"] - 2.0) < 1e-3, f"{it[1]['seq_end']:.3f}")
    s.toggle(s.turns[-1].id, cat, mk)
    s.toggle(tc.id, cat, mk)

    print("export: speed, turn, fill")
    def render(**kw) -> Path:
        t = fix(**kw) if kw else None
        job = export.create(items(), clips, "t", None, want="wide")
        job.size = {"w": 320, "h": 180}
        out = TMP / f"shot{len(list(TMP.glob('shot*.mov')))}.mov"
        export._shot(job, job.items[0], out)
        if t:
            s.toggle(t.id, cat, mk)
        return out
    plain, fast = render(), render(speed=2)
    # source brightness = 30 * source seconds; the shot starts at 1 s
    b_plain, b_fast = frame(plain, 1.0).mean(), frame(fast, 1.0).mean()
    check("1 s in, plain shows ~2 s of source, 2x shows ~3 s", b_fast - b_plain > 20,
          f"brightness {b_plain:.0f} -> {b_fast:.0f}")
    turned = frame(render(rotate=90), 0.5, 32, 18)
    side = (turned[:, :4].mean() + turned[:, -4:].mean()) / 2
    check("a quarter turn: tall picture, bars at the sides", side < 8 and turned[:, 12:20].mean() > 20,
          f"sides {side:.0f}, middle {turned[:, 12:20].mean():.0f}")
    filled = frame(render(rotate=90, fill=True), 0.5, 32, 18)
    check("…filled: no bars", filled[:, :4].mean() > 20, f"sides {filled[:, :4].mean():.0f}")

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

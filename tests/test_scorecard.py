"""The scorecard measures what it says, and agreement finds shared moments.

Two edits of the same "shoot" (five distinct generated pictures):

- the reference shows A B C D, three seconds each;
- the edit shows B, then E, then D graded warmer and darker, then a 6 s A.

So the edit shows 3 of the reference's 4 moments (A, B and D; C is missing),
a colour grade must not hide a match, a picture that is in neither must
not be counted, and pace must read 4 shots with the longest 6 s.

Loudness: a quiet mix reads quiet, and the leveller every export can use
brings it to social volume (-14 LUFS); the music bed asks for it.

    python tests/test_scorecard.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from cutgrammar import scorecard  # noqa: E402
from web.backend import audiomix  # noqa: E402

SRC = {"A": "testsrc=size=320x180:rate=30", "B": "smptebars=size=320x180:rate=30",
       "C": "mandelbrot=size=320x180:rate=30", "D": "rgbtestsrc=size=320x180:rate=30",
       "E": "testsrc2=size=320x180:rate=30"}


def render(path: str, parts: list[tuple[str, float, str]]) -> None:
    """parts: (picture, seconds, extra filter)."""
    inputs, chains = [], []
    for i, (k, d, vf) in enumerate(parts):
        inputs += ["-f", "lavfi", "-t", str(d), "-i", SRC[k]]
        chains.append(f"[{i}:v]{vf + ',' if vf else ''}format=yuv420p,setsar=1[v{i}]")
    cat = "".join(f"[v{i}]" for i in range(len(parts))) + f"concat=n={len(parts)}:v=1:a=0[out]"
    subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(chains) + ";" + cat,
                    "-map", "[out]", "-c:v", "libx264", "-preset", "veryfast", path], check=True)


def main() -> int:
    failures = []

    def check(name: str, cond: bool, got: str = "") -> None:
        print(f"  {'PASS' if cond else 'FAIL'}  {name}{': ' + got if got else ''}")
        if not cond:
            failures.append(name)

    d = tempfile.mkdtemp(prefix="vibecut-card-")
    ref, edit = os.path.join(d, "ref.mp4"), os.path.join(d, "edit.mp4")
    render(ref, [("A", 3, ""), ("B", 3, ""), ("C", 3, ""), ("D", 3, "")])
    render(edit, [("B", 3, ""), ("E", 3, ""), ("D", 3, "eq=brightness=-0.12:saturation=1.3,colorbalance=rs=0.2"),
                  ("A", 6, "")])

    e, r = scorecard.card(edit), scorecard.card(ref)
    print("pace")
    check("four shots in the edit", e[0].shots == 4, f"{e[0].shots}")
    check("the longest is the 6 s one", abs(e[0].longest_shot_s - 6.0) < 0.2, f"{e[0].longest_shot_s}")
    check("one of four is over 4 s", e[0].long_share == 0.25, f"{e[0].long_share}")
    check("no sound is said, not made up", e[0].lufs is None, f"{e[0].lufs}")

    print("agreement")
    a = scorecard.agreement(e, r)
    shown = [row["ref_shot"] for row in a["shots"] if row["in_edit"]]
    check("A, B and D are found, C isn't", shown == [1, 2, 4], f"{shown} "
          f"scores {[row['score'] for row in a['shots']]}")
    check("the graded D still matches", a["shots"][3]["in_edit"], f"{a['shots'][3]['score']}")
    check("share is 3 of 4", a["share"] == 0.75, f"{a['share']}")

    print("loudness")
    t = np.arange(audiomix.SR * 4) / audiomix.SR
    quiet = (0.03 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    buf = np.stack([quiet, quiet], axis=1)
    raw, lev = Path(d) / "raw.wav", Path(d) / "lev.wav"
    audiomix.write_wav(buf, raw, level=False)
    audiomix.write_wav(buf, lev, level=True)
    with wave.open(str(lev)) as w:
        check("levelled sound stays at the mixer's rate", w.getframerate() == audiomix.SR, f"{w.getframerate()}")
    lr, ll = (scorecard.media.loudness_lufs(str(p)) for p in (raw, lev))
    check("a quiet mix reads quiet", lr is not None and lr < -25, f"{lr}")
    check("levelled, it reads social volume (-14 LUFS)", ll is not None and abs(ll + 14) <= 1.5, f"{ll}")
    src = (Path(HERE).parent / "web" / "backend" / "bed.py").read_text()
    check("the music bed asks for levelling", '"level": True' in src)

    print(f"\n{len(failures)} failure(s)")
    return 1 if failures else 0


def test_scorecard() -> None:
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())

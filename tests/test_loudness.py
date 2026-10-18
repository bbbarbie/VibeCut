"""The music bed is levelled to social volume, preview and export alike.

The Oct 14 school-day edit came out at -20 LUFS against the creator's own
-15: a quiet mix must read quiet, the leveller must bring it to -14, and
the bed must ask for it.

    python tests/test_loudness.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from cutgrammar import media  # noqa: E402
from web.backend import audiomix  # noqa: E402


def main() -> int:
    failures = []

    def check(name: str, cond: bool, got: str = "") -> None:
        print(f"  {'PASS' if cond else 'FAIL'}  {name}{': ' + got if got else ''}")
        if not cond:
            failures.append(name)

    d = tempfile.mkdtemp(prefix="vibecut-loud-")
    t = np.arange(audiomix.SR * 4) / audiomix.SR
    quiet = (0.03 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    buf = np.stack([quiet, quiet], axis=1)
    raw, lev = Path(d) / "raw.wav", Path(d) / "lev.wav"
    audiomix.write_wav(buf, raw, level=False)
    audiomix.write_wav(buf, lev, level=True)
    with wave.open(str(lev)) as w:
        check("levelled sound stays at the mixer's rate", w.getframerate() == audiomix.SR, f"{w.getframerate()}")
    lr, ll = (media.loudness_lufs(str(p)) for p in (raw, lev))
    check("a quiet mix reads quiet", lr is not None and lr < -25, f"{lr}")
    check("levelled, it reads social volume (-14 LUFS)", ll is not None and abs(ll + 14) <= 1.5, f"{ll}")
    src = (Path(HERE).parent / "web" / "backend" / "bed.py").read_text()
    check("the music bed asks for levelling", '"level": True' in src)

    print(f"\n{len(failures)} failure(s)")
    return 1 if failures else 0


def test_loudness() -> None:
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())

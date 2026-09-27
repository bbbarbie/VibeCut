"""HDR thumbnails must look like the phone showed them, not milky.

An HLG picture decoded straight to 8-bit reads flat: reference white sits
at 75% instead of the top, and BT.2020 colour shown as BT.709 is washed
out. After `to_sdr` reference white must reach the top of the range, black
must stay black, a saturated colour must get more saturated, and anything
not flagged HDR must come back byte for byte.

    python tests/test_hdr.py
"""

from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cutgrammar import media  # noqa: E402

HLG = {"transfer": "arib-std-b67", "primaries": "bt2020"}
PQ = {"transfer": "smpte2084", "primaries": "bt2020"}


def px(*rgb: float) -> np.ndarray:
    return np.array([[[round(c * 255) for c in rgb]]], dtype=np.uint8)


def sat(im: np.ndarray) -> float:
    x = im.astype(float)
    return float((x.max(-1) - x.min(-1)).mean())


def main() -> int:
    failures = []

    def check(name: str, cond: bool, got: str = "") -> None:
        print(f"  {'PASS' if cond else 'FAIL'}  {name}{': ' + got if got else ''}")
        if not cond:
            failures.append(name)

    rng = np.random.default_rng(0)
    frames = rng.integers(0, 256, (20, 9, 16, 3), dtype=np.uint8)
    for meta in ({}, {"transfer": "bt709"}, {"transfer": None}):
        check(f"SDR {meta} unchanged", media.to_sdr(frames, meta) is frames)

    white = media.to_sdr(px(0.75, 0.75, 0.75), HLG)[0, 0]
    check("HLG reference white reaches the top", white.min() >= 235, str(white))
    check("HLG black stays black", media.to_sdr(px(0, 0, 0), HLG).max() == 0)
    mid, out = px(0.6, 0.45, 0.35), media.to_sdr(px(0.6, 0.45, 0.35), HLG)
    check("HLG colour gets more saturated", sat(out) > sat(mid), f"{sat(mid):.0f} -> {sat(out):.0f}")
    grad = np.linspace(0, 1, 64)[None, :, None].repeat(3, -1)
    ramp = media.to_sdr((grad * 255).astype(np.uint8), HLG)[0, :, 0].astype(int)
    check("tone curve never reverses", bool(np.all(np.diff(ramp) >= 0)))
    check("highlights roll off, not clip flat", len(set(ramp[-8:])) > 1, str(ramp[-8:]))

    # 203 nits in PQ is reference white too.
    pq203 = ((0.1593017578125, 78.84375, 0.8359375, 18.8515625, 18.6875), 203 / 10000)
    (m1, m2, c1, c2, c3), y = pq203
    e = ((c1 + c2 * y ** m1) / (1 + c3 * y ** m1)) ** m2
    check("PQ reference white reaches the top", media.to_sdr(px(e, e, e), PQ).min() >= 235)

    big = media.to_sdr(frames, HLG)
    check("chunked batch matches one by one",
          np.array_equal(big, np.concatenate([media.to_sdr(f[None], HLG) for f in frames])))

    print(f"\n{'all passed' if not failures else f'{len(failures)} failed'}")
    return 1 if failures else 0


def test_hdr() -> None:
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())

"""Caption colour must follow what's behind the words, and only that.

Fixtures differ in one respect at a time: the band under a caption bright
or dark, the top of the frame bright or dark, the footage's hue blue or
orange, the background calm or busy. The ink must change only when the
words would blend in, reach a readable contrast when it does, come from the
footage's own hue, and fall back to a halo when no colour can stand out.

    python tests/test_ink.py
"""

from __future__ import annotations

import colorsys
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web.backend import ink  # noqa: E402

COZY = {"color": "#f6ebd9", "accent": "#e9b872", "captions": "bottom", "backing": "none"}
H, W = ink.GRID_H, ink.GRID_W


def frame(top, bottom, n=4) -> np.ndarray:
    g = np.zeros((n, H, W, 3), dtype=np.uint8)
    g[:, : H // 2] = top
    g[:, H // 2:] = bottom
    return g


def run(clips: dict[str, np.ndarray], o: dict, style=COZY) -> dict:
    layout, t = [], 0.0
    for cid in clips:
        layout.append({"kind": "shot", "clip_id": cid, "src_start": 0.0, "src_end": 4.0,
                       "seq_start": t, "seq_end": t + 4.0})
        t += 4.0
    times = {cid: [0.0, 1.0, 2.0, 3.0] for cid in clips}
    return ink.inks([o], style, layout, clips, times)[0]


def cap(start=0.5, end=3.5, sub=""):
    return {"id": "o1", "kind": "caption", "text": "8:35 am", "sub": sub, "pos": "bottom",
            "start": start, "end": end, "shown_end": end}


def hue(h: str) -> float:
    r, g, b = ink.hex_rgb(h) / 255
    return colorsys.rgb_to_hls(r, g, b)[0]


def main() -> int:
    failures = []

    def check(name: str, cond: bool, got: str = "") -> None:
        print(f"  {'PASS' if cond else 'FAIL'}  {name}{': ' + got if got else ''}")
        if not cond:
            failures.append(name)

    blue_sky, pavement = (90, 140, 210), (40, 44, 52)
    white_wall = (236, 236, 232)

    dark = run({"a": frame(blue_sky, pavement)}, cap())
    check("cream over dark pavement: the look's own colour stays", "ink" not in dark and "halo" not in dark, str(dark))

    bright = run({"a": frame(blue_sky, white_wall)}, cap())
    lum = ink.luminance(np.array(white_wall, dtype=float))
    c = ink.contrast(float(ink.luminance(ink.hex_rgb(bright.get("ink", "#f6ebd9")))), float(lum))
    check("cream over a white wall: a different ink", "ink" in bright, str(bright))
    check("and it reads (contrast >= 4.5)", c >= ink.READABLE, f"{c:.2f}")
    check("and it's the footage's own blue, not plain black", abs(hue(bright["ink"]) - hue("#5a8cd2")) < 0.06,
          f"{bright['ink']} hue {hue(bright['ink']):.2f}")

    orange = run({"a": frame((220, 130, 50), white_wall)}, cap())
    check("orange footage: the ink is an orange shade", abs(hue(orange["ink"]) - hue("#dc8232")) < 0.06, orange["ink"])

    flipped = run({"a": frame(white_wall, pavement)}, cap())
    check("only what's under the words counts: a bright top doesn't change a bottom caption", "ink" not in flipped)
    center = run({"a": frame(blue_sky, white_wall)}, cap(), style={**COZY, "captions": "center"})
    check("a centred caption reads the middle of the frame",
          ("ink" in center) == (ink.worst(COZY["color"], ink.luminance(
              frame(blue_sky, white_wall)[:, 6:12, 4:28].reshape(-1, 3).astype(float))) < ink.READABLE))

    second = run({"a": frame(blue_sky, pavement), "b": frame(blue_sky, white_wall)}, cap(5.0, 7.5))
    first = run({"a": frame(blue_sky, pavement), "b": frame(blue_sky, white_wall)}, cap(0.5, 3.5))
    check("only the shot the caption is on counts", "ink" in second and "ink" not in first)

    busy = np.zeros((4, H, W, 3), dtype=np.uint8)
    busy[:, :, ::2] = 250
    busy[:, :, 1::2] = 10
    halo = run({"a": busy}, cap())
    check("a frame both black and white under the words: a halo", "halo" in halo, str(halo))

    split = np.zeros((4, H, W, 3), dtype=np.uint8)
    split[:] = white_wall
    split[:, 12:, 14:20] = (12, 12, 14)   # black trousers in the middle of the band
    sp = run({"a": split}, cap())
    check("pale wall with black trousers under the words: light words on a dark halo, never dark words",
          sp.get("halo") == ink.HALO and ink.luminance(ink.hex_rgb(sp.get("ink", COZY["color"]))) > 0.35, str(sp))
    check("a pale background gets no halo", "halo" not in bright)

    sub = run({"a": frame(blue_sky, white_wall)}, cap(sub="Columbia University"))
    check("the place line gets its own readable colour", "ink2" in sub, str(sub))

    boxed = run({"a": frame(blue_sky, white_wall)}, cap(), style={**COZY, "backing": "box"})
    check("words on a box are left alone", "ink" not in boxed)
    check("no tones (not indexed yet): nothing changes", ink.inks([cap()], COZY, [], {}, {}) == [cap()])

    big = np.zeros((2, 216, 384, 3), dtype=np.uint8)
    big[:, 108:] = 200
    g = ink.grid(big)
    check("the grid is a block mean, 32x18", g.shape == (2, H, W, 3) and g[0, 0, 0, 0] == 0 and g[0, -1, -1, 0] == 200)

    print(f"\n{'all passed' if not failures else f'{len(failures)} failed'}")
    return 1 if failures else 0


def test_ink() -> None:
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())

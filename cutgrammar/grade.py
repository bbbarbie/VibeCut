"""A colour look as numbers, and one LUT that moves footage towards it.

"The look" of an edit you admire is mostly four things a colourist sets
deliberately: the tone curve (crushed or lifted blacks, how hard the
contrast is), the white balance of the midtones (warm, cool, green, magenta),
split toning (shadows pushed one way, highlights another -- teal and orange
is the famous one) and saturation. All four are averages over pixels, so
all four are measurable from the 48x27 frames.

Matching them is deliberately *not* per-channel histogram matching. That
transfers content as well as grade: a reference shot at the beach is blue
because the sea is blue, and matching its histogram turns a desert blue too.
Here the tone curve is matched on luma only and every colour shift is a
small, clipped offset, so what moves is the grade, not the subject. It is
still a guess from averages, so the creator sees before/after stills and
picks the strength.

One LUT for the whole edit, never per shot: "one LUT across the whole
piece" is the surface-consistency rule this whole project is built on.
"""

from __future__ import annotations

import numpy as np

# luma quantiles the tone curve is fitted on; denser at the ends, where
# crushed or lifted blacks and rolled-off highlights live
TONE_Q = np.array([0, 1, 2, 5, 10, 15, 20, 30, 40, 50, 60, 70, 80, 85, 90, 95, 98, 99, 100], dtype=float)
MAX_SHIFT = 14.0                   # largest colour offset a look may apply (0..255 units)
SAT_RANGE = (0.6, 1.6)             # saturation may be scaled no further than this
LUT_SIZE = 33
SHADOW, HIGH = 80.0, 175.0         # luma bands for split toning
LUMA = np.array([0.2126, 0.7152, 0.0722])


def pixels(frames: np.ndarray, limit: int = 400, bars: tuple[int, int] = (0, 0)) -> np.ndarray:
    """(n, H, W, 3) uint8 -> (m, 3) float, from up to `limit` evenly spaced frames,
    letterbox rows excluded (black bars are framing, not grade)."""
    if len(frames) == 0:
        return np.zeros((0, 3))
    idx = np.unique(np.linspace(0, len(frames) - 1, min(limit, len(frames))).astype(int))
    top, bottom = bars
    f = frames[idx, top:frames.shape[1] - bottom]
    return f.reshape(-1, 3).astype(np.float64)


def _luma(px: np.ndarray) -> np.ndarray:
    return px @ LUMA


def _offset(px: np.ndarray, y: np.ndarray, sel: np.ndarray) -> np.ndarray:
    """Mean colour offset from grey of the selected pixels (a 3-vector)."""
    if not sel.any():
        return np.zeros(3)
    return (px[sel] - y[sel, None]).mean(axis=0)


def _sat(px: np.ndarray) -> float:
    """Mean chroma (max - min channel), 0..1. Absolute, not relative to
    brightness: lifting the blacks adds the same amount to every channel
    and must not read as desaturating."""
    if len(px) == 0:
        return 0.0
    return float((px.max(axis=1) - px.min(axis=1)).mean() / 255.0)


def stats(px: np.ndarray) -> dict:
    """What a look is made of, measured over a sample of pixels."""
    if len(px) == 0:
        return {}
    y = _luma(px)
    shadow = _offset(px, y, y < SHADOW)
    mid = _offset(px, y, (y >= SHADOW) & (y <= HIGH))
    high = _offset(px, y, y > HIGH)
    # White balance by grey-world over every pixel, the oldest estimator
    # there is. Content still leaks in (a sunset is warm), which is why
    # colour shifts are clipped when a look is applied.
    cast = _offset(px, y, np.ones(len(y), dtype=bool))
    return {
        "tone": [round(float(v), 2) for v in np.percentile(y, TONE_Q)],
        "shadow": [round(float(v), 2) for v in shadow],
        "mid": [round(float(v), 2) for v in mid],
        "high": [round(float(v), 2) for v in high],
        "cast": [round(float(v), 2) for v in cast],
        "sat": round(_sat(px), 4),
        # the two numbers people actually say out loud
        "warmth": round(float(cast[0] - cast[2]), 2),
        "tint": round(float(cast[1] - (cast[0] + cast[2]) / 2), 2),
        "black": round(float(np.percentile(y, 1)), 2),
        "white": round(float(np.percentile(y, 99)), 2),
        "median": round(float(np.median(y)), 2),
        "contrast": round(float(np.percentile(y, 95) - np.percentile(y, 5)), 2),
    }


def words(s: dict) -> list[str]:
    """Plain-language description. Cut-offs are guesses, like every threshold here."""
    if not s:
        return []
    out = []
    w = s["warmth"]
    out.append("warm" if w > 6 else "cool" if w < -6 else "neutral colour")
    if s["tint"] > 4:
        out.append("a little green")
    elif s["tint"] < -4:
        out.append("a little magenta")
    out.append("muted colour" if s["sat"] < 0.12 else "rich colour" if s["sat"] > 0.3 else "natural saturation")
    if s["black"] > 22:
        out.append("lifted, filmic blacks")
    elif s["black"] < 6:
        out.append("deep blacks")
    out.append("soft contrast" if s["contrast"] < 120 else "punchy contrast" if s["contrast"] > 190 else "")
    out.append("bright and airy" if s["median"] > 150 else "dark and moody" if s["median"] < 70 else "")
    split = np.asarray(s["high"]) - np.asarray(s["shadow"])
    if split[0] - split[2] > 10:
        out.append("warm highlights over cool shadows")
    return [x for x in out if x]


# --------------------------------------------------------------------------
# the transform, and the LUT that bakes it
# --------------------------------------------------------------------------

def _clip_vec(v: np.ndarray, limit: float = MAX_SHIFT) -> np.ndarray:
    v = v - v @ LUMA  # a colour shift, not a brightness change
    n = float(np.abs(v).max())
    return v * (limit / n) if n > limit else v


class Look:
    """src stats + ref stats + strength -> a function on RGB (0..255)."""

    def __init__(self, src_px: np.ndarray, ref: dict, strength: float = 1.0) -> None:
        self.k = float(np.clip(strength, 0.0, 1.0))
        src_tone = np.maximum.accumulate(np.asarray(stats(src_px)["tone"]))
        ref_tone = np.maximum.accumulate(np.asarray(ref["tone"], dtype=np.float64))
        if len(ref_tone) != len(src_tone):   # a look saved with other quantiles
            ref_tone = np.interp(TONE_Q, np.linspace(0, 100, len(ref_tone)), ref_tone)
        # Many pixels at one value (pure black) make several quantiles tie;
        # they are one input, so they map to the average of their targets.
        groups = np.concatenate([[0], np.cumsum(np.diff(src_tone) > 0.5)])
        src_tone = np.array([src_tone[groups == g].mean() for g in range(groups[-1] + 1)])
        ref_tone = np.array([ref_tone[groups == g].mean() for g in range(groups[-1] + 1)])
        # strictly increasing x for interp; ends pinned so nothing is clipped
        # harder than the reference itself clips
        xp = np.concatenate([[-1.0], src_tone, [256.0]])
        xp = xp + np.arange(len(xp)) * 1e-3      # strictly increasing, for interp
        fp = np.concatenate([[max(0.0, ref_tone[0] - src_tone[0] - 1.0)], ref_tone,
                             [min(255.0, ref_tone[-1] + (256.0 - src_tone[-1]))]])
        self.xp, self.fp = xp, np.maximum.accumulate(fp)
        self.sat = 1.0
        self.cast = np.zeros(3)
        self.split = {"shadow": np.zeros(3), "high": np.zeros(3)}
        toned = self._tone(src_px)
        s_now = _sat(toned)
        if s_now > 1e-3 and ref.get("sat"):
            ratio = float(np.clip(ref["sat"] / s_now, *SAT_RANGE))
            self.sat = 1.0 + self.k * (ratio - 1.0)
        after = stats(self._saturate(toned))
        ref_cast = np.asarray(ref.get("cast") or ref["mid"], dtype=np.float64)
        # Split toning is how shadows and highlights differ from the overall
        # cast, so it is matched relative to it; the cast itself is matched
        # on its own.
        for part in self.split:
            want = np.asarray(ref[part]) - ref_cast
            have = np.asarray(after[part]) - np.asarray(after["cast"])
            self.split[part] = _clip_vec(want - have, MAX_SHIFT / 2) * self.k
        self.cast = _clip_vec(ref_cast - np.asarray(after["cast"])) * self.k
        # The split weights don't average to zero over a real picture, so
        # measure the cast once more and take out what is left over.
        got = np.asarray(stats(self(src_px))["cast"])
        self.cast = _clip_vec(self.cast + (ref_cast - got) * self.k)

    def _tone(self, px: np.ndarray) -> np.ndarray:
        y = _luma(px)
        t = np.interp(y, self.xp, self.fp)
        return px + (self.k * (t - y))[:, None]

    def _saturate(self, px: np.ndarray) -> np.ndarray:
        y = _luma(px)[:, None]
        return y + self.sat * (px - y)

    def _shift(self, px: np.ndarray) -> np.ndarray:
        x = np.clip(_luma(px) / 255.0, 0, 1)[:, None]
        ws, wh = (1 - x) ** 2, x ** 2
        return px + self.cast + ws * self.split["shadow"] + wh * self.split["high"]

    def __call__(self, px: np.ndarray) -> np.ndarray:
        """(m, 3) float 0..255 -> (m, 3) float 0..255."""
        return np.clip(self._shift(self._saturate(self._tone(px))), 0, 255)

    def lut(self, n: int = LUT_SIZE) -> np.ndarray:
        """(n, n, n, 3) float 0..1, indexed [r, g, b]."""
        g = np.linspace(0, 255, n)
        r, gg, b = np.meshgrid(g, g, g, indexing="ij")
        grid = np.stack([r, gg, b], axis=-1).reshape(-1, 3)
        return (self(grid) / 255.0).reshape(n, n, n, 3)


def apply_lut(img: np.ndarray, lut: np.ndarray) -> np.ndarray:
    """uint8 (..., 3) through a LUT, trilinear -- for previews and tests.
    Export uses ffmpeg's lut3d on the same .cube, so the two agree."""
    n = lut.shape[0]
    x = img.reshape(-1, 3).astype(np.float64) / 255.0 * (n - 1)
    i0 = np.clip(np.floor(x).astype(int), 0, n - 2)
    f = x - i0
    out = np.zeros_like(x)
    for dr in (0, 1):
        for dg in (0, 1):
            for db in (0, 1):
                w = ((f[:, 0] if dr else 1 - f[:, 0]) * (f[:, 1] if dg else 1 - f[:, 1])
                     * (f[:, 2] if db else 1 - f[:, 2]))
                out += w[:, None] * lut[i0[:, 0] + dr, i0[:, 1] + dg, i0[:, 2] + db]
    return np.clip(out * 255 + 0.5, 0, 255).astype(np.uint8).reshape(img.shape)


def write_cube(lut: np.ndarray, path: str, title: str = "VibeCut look") -> None:
    """Adobe .cube: red changes fastest."""
    n = lut.shape[0]
    lines = [f'TITLE "{title}"', f"LUT_3D_SIZE {n}", "DOMAIN_MIN 0 0 0", "DOMAIN_MAX 1 1 1"]
    for b in range(n):
        for g in range(n):
            for r in range(n):
                v = lut[r, g, b]
                lines.append(f"{v[0]:.6f} {v[1]:.6f} {v[2]:.6f}")
    with open(path, "w") as fh:
        fh.write("\n".join(lines) + "\n")

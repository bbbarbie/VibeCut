"""The colour of words on screen, picked against what's behind them.

One ink for a whole video reads as consistent until a caption lands on a
bright sky or a white wall and disappears into it. A caption you can't read
is the plainest amateur tell there is, so each overlay gets the ink of the
look when it stands out from the picture behind it, and otherwise the
nearest colour from the video's own palette that does: a pale tint or a deep
shade of its dominant hue, so the words still belong to the footage instead
of shouting over it. When nothing reaches a readable contrast (a busy frame
that is both bright and dark under the words) they stay light and get a
soft dark shadow, since dark words vanish into whatever part is dark.

What's "behind" is read from the index samples the viewer sees (SDR, ~1/s),
reduced to a 32x18 colour grid per sample and cached per clip as
`tones.npy`; no frame is decoded again. Thresholds are WCAG's text contrast
ratios (4.5 normal text, 3 large), used as priors for moving footage.
"""

from __future__ import annotations

import colorsys
import os
import subprocess
import threading
from pathlib import Path

import numpy as np

GRID_W, GRID_H = 32, 18
READABLE = 4.5        # WCAG AA for body text [prior for video]
HALO = "rgba(0,0,0,0.85)"         # under light words
HALO_LIGHT = "rgba(255,255,255,0.85)"   # around dark words picked by hand
COVER = 0.95         # share of the background an ink must read over to need no halo [prior]
LOW, HIGH = 15, 85    # percentiles of the background taken as its darkest / brightest

# Where on the frame each position puts its words: (x0, x1, y0, y1) as fractions.
REGIONS = {
    "top-left": (0.04, 0.5, 0.04, 0.3), "top": (0.2, 0.8, 0.04, 0.3), "top-right": (0.5, 0.96, 0.04, 0.3),
    "left": (0.04, 0.5, 0.35, 0.65), "center": (0.15, 0.85, 0.35, 0.65), "right": (0.5, 0.96, 0.35, 0.65),
    # a caption is one or two short centred lines, not the whole band
    "bottom-left": (0.04, 0.5, 0.7, 0.92), "bottom": (0.25, 0.75, 0.72, 0.92),
    "bottom-right": (0.5, 0.96, 0.68, 0.94),
}

_lock = threading.Lock()
_mem: dict[str, np.ndarray | None] = {}


# --------------------------------------------------------------------------
# colour arithmetic
# --------------------------------------------------------------------------

def _lin(c: np.ndarray) -> np.ndarray:
    c = np.asarray(c, dtype=np.float64) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def luminance(rgb: np.ndarray) -> np.ndarray:
    """WCAG relative luminance of sRGB 0-255 colours (last axis = RGB)."""
    l = _lin(rgb)
    return 0.2126 * l[..., 0] + 0.7152 * l[..., 1] + 0.0722 * l[..., 2]


def contrast(a: float, b: float) -> float:
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def hex_rgb(h: str) -> np.ndarray:
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.float64)


def rgb_hex(c) -> str:
    return "#" + "".join(f"{int(round(min(255, max(0, v)))):02x}" for v in c)


def _hls(h: float, l: float, s: float) -> str:
    return rgb_hex(np.array(colorsys.hls_to_rgb(h % 1.0, l, s)) * 255)


def palette(cells: np.ndarray) -> list[str]:
    """Inks drawn from the footage: a pale tint and a deep shade of each of
    its two strongest hues, then near-white and near-black as a last resort."""
    px = cells.reshape(-1, 3).astype(np.float64) / 255.0
    out: list[str] = []
    if len(px):
        hls = np.array([colorsys.rgb_to_hls(*p) for p in px[:: max(1, len(px) // 4000)]])
        h, l, s = hls[:, 0], hls[:, 1], hls[:, 2]
        w = s * (1 - np.abs(2 * l - 1))           # chroma: grey cells say nothing about the scheme
        if w.sum() > 1e-6:
            hist = np.bincount((h * 12).astype(int) % 12, weights=w, minlength=12)
            for b in np.argsort(hist)[::-1][:2]:
                if hist[b] < 0.15 * hist.max():
                    continue
                sel = ((h * 12).astype(int) % 12) == b
                hue = float(np.angle(np.sum(w[sel] * np.exp(2j * np.pi * h[sel]))) / (2 * np.pi))
                out += [_hls(hue, 0.92, 0.55), _hls(hue, 0.16, 0.5)]
    return out + ["#faf7f2", "#16161a"]


# --------------------------------------------------------------------------
# what's behind an overlay
# --------------------------------------------------------------------------

def region(o: dict, style: dict) -> tuple[float, float, float, float]:
    if o.get("place"):
        p = o["place"]
        hw, hh = 0.25 * p.get("scale", 1.0), 0.1 * p.get("scale", 1.0)
        return (max(0.0, p["x"] - hw), min(1.0, p["x"] + hw), max(0.0, p["y"] - hh), min(1.0, p["y"] + hh))
    pos = ("center" if style.get("captions") == "center" else "bottom") if o["kind"] == "caption" else o.get("pos", "bottom")
    return REGIONS.get(pos, REGIONS["bottom"])


def behind(o: dict, style: dict, layout: list[dict], tones: dict[str, np.ndarray],
           times: dict[str, list[float]]) -> np.ndarray:
    """The grid cells under the overlay over the whole time it's on screen."""
    x0, x1, y0, y1 = region(o, style)
    xs = slice(int(x0 * GRID_W), max(int(x0 * GRID_W) + 1, int(np.ceil(x1 * GRID_W))))
    ys = slice(int(y0 * GRID_H), max(int(y0 * GRID_H) + 1, int(np.ceil(y1 * GRID_H))))
    a, z = o["start"], max(o["start"] + 1e-3, o.get("shown_end", o["end"]))
    cells = []
    for it in layout:
        if it["kind"] != "shot" or it["seq_end"] <= a or it["seq_start"] >= z:
            continue
        g, ts = tones.get(it["clip_id"]), times.get(it["clip_id"])
        if g is None or not ts:
            continue
        s0 = it["src_start"] + max(0.0, a - it["seq_start"])
        s1 = it["src_start"] + min(it["seq_end"], z) - it["seq_start"]
        ts_ = np.asarray(ts[: len(g)])
        idx = np.nonzero((ts_ >= s0 - 0.5) & (ts_ <= s1 + 0.5))[0]
        if not len(idx):
            idx = [int(np.argmin(np.abs(ts_ - (s0 + s1) / 2)))]
        cells.append(g[idx][:, ys, xs].reshape(-1, 3))
    return np.concatenate(cells) if cells else np.zeros((0, 3))


def worst(ink: str, lum: np.ndarray) -> float:
    """The contrast of `ink` against the part of the background closest to it."""
    li = float(luminance(hex_rgb(ink)))
    lo, hi = np.percentile(lum, LOW), np.percentile(lum, HIGH)
    return min(contrast(li, lo), contrast(li, hi))


def reads(ink: str, cells: np.ndarray) -> bool:
    """Does `ink` stand out from (nearly) all of what's behind the words?"""
    li = float(luminance(hex_rgb(ink)))
    return float(np.mean([contrast(li, float(x)) >= READABLE for x in luminance(cells)])) >= COVER


def pick(own: str, cells: np.ndarray, pal: list[str]) -> tuple[str | None, str | None]:
    """-> (ink to use instead of `own`, or None to keep it; halo colour or None).

    An ink that reads over (nearly) all of what's behind the words needs
    nothing more: the look's own colour if it does, else the footage's own
    tint or shade, a neutral last. When none does -- a pale floor with black
    trousers in the middle -- dark words vanish into the dark part (seen on
    her footage), so the words stay light on a strong dark edge, the
    subtitle convention, which reads over both."""
    lum = luminance(cells)

    def share(c: str) -> float:
        li = float(luminance(hex_rgb(c)))
        return float(np.mean([contrast(li, float(x)) >= READABLE for x in lum]))

    if share(own) >= COVER:
        return None, None
    scored = [(share(c), k, c) for k, c in enumerate(pal)]
    covers = [x for x in scored if x[0] >= COVER]
    hued = [x for x in covers if x[1] < len(pal) - 2]
    if covers:
        return max(hued or covers)[2], None
    if float(luminance(hex_rgb(own))) > 0.35:
        return None, HALO
    light = [x for x in scored if float(luminance(hex_rgb(x[2]))) > 0.6]
    return (light[0][2] if light else "#faf7f2"), HALO


def inks(items: list[dict], style: dict, layout: list[dict], tones: dict[str, np.ndarray],
         times: dict[str, list[float]]) -> list[dict]:
    """Each overlay gets `ink` / `ink2` (main / accent colour) where the
    style's would blend in, and `halo` where even the best ink is weak."""
    if style.get("backing") == "box" or not tones:
        return items
    every = [g.reshape(-1, 3) for g in tones.values() if g is not None and len(g)]
    if not every:
        return items
    pal = palette(np.concatenate(every))
    out = []
    for o in items:
        cells = behind(o, style, layout, tones, times) if o["kind"] != "chapters" else np.zeros((0, 3))
        if not len(cells):
            out.append(o)
            continue
        o = dict(o)
        mine = style.get("text_color") if o["kind"] == "caption" else None
        if mine:
            # picked by hand: kept as picked; a glow carries it where it would blend in
            if not reads(mine, cells):
                o["halo"] = HALO_LIGHT if float(luminance(hex_rgb(mine))) < 0.35 else HALO
            out.append(o)
            continue
        ink, halo = pick(style["color"], cells, pal)
        if ink:
            o["ink"] = ink
        if o.get("sub"):
            ink2, halo2 = pick(style["accent"], cells, pal)
            # under a halo both lines are light: a dark place name would vanish into it
            if halo and ink2 and float(luminance(hex_rgb(ink2))) < 0.35:
                ink2 = None
            if ink2:
                o["ink2"] = ink2
            halo = halo or halo2
        if halo:
            o["halo"] = halo
        out.append(o)
    return out


# --------------------------------------------------------------------------
# the tone grids
# --------------------------------------------------------------------------

def grid(frames: np.ndarray) -> np.ndarray:
    """(n, H, W, 3) frames -> (n, 18, 32, 3) uint8 by block mean."""
    n, h, w, _ = frames.shape
    ys = (np.arange(GRID_H + 1) * h) // GRID_H
    xs = (np.arange(GRID_W + 1) * w) // GRID_W
    out = np.zeros((n, GRID_H, GRID_W, 3), dtype=np.uint8)
    f = frames.astype(np.float32)
    for i in range(GRID_H):
        for j in range(GRID_W):
            out[:, i, j] = f[:, ys[i]:ys[i + 1], xs[j]:xs[j + 1]].mean(axis=(1, 2))
    return out


def write(d: Path, shown: np.ndarray) -> None:
    np.save(d / "tones.npy", grid(shown))


def _from_samples(d: Path, n: int) -> np.ndarray | None:
    """Older clips: the grid from their sample JPEGs (small, already SDR)."""
    if not n or not (d / "samples" / "0000.jpg").exists():
        return None
    p = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(d / "samples" / "%04d.jpg"),
                        "-vf", f"scale={GRID_W}:{GRID_H}:flags=area", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                       capture_output=True, timeout=60)
    if p.returncode != 0:
        return None
    a = np.frombuffer(p.stdout, dtype=np.uint8)
    k = len(a) // (GRID_W * GRID_H * 3)
    return a[: k * GRID_W * GRID_H * 3].reshape(k, GRID_H, GRID_W, 3) if k else None


def tones_for(rec: dict, build: bool = False) -> np.ndarray | None:
    from .indexer import clip_dir
    cid = rec["id"]
    with _lock:
        if cid in _mem and (_mem[cid] is not None or not build):
            return _mem[cid]
    d = clip_dir(cid)
    g = None
    try:
        g = np.load(d / "tones.npy")
    except (OSError, ValueError):
        if build:
            try:
                g = _from_samples(d, len((rec.get("samples") or {}).get("files", [])))
            except (OSError, subprocess.SubprocessError):
                g = None
            if g is not None:
                try:
                    tmp = d / "tones.tmp.npy"
                    np.save(tmp, g)
                    os.replace(tmp, d / "tones.npy")
                except OSError:
                    pass
    with _lock:
        _mem[cid] = g
    return g


def fill(recs: list[dict]) -> threading.Thread:
    """Clips indexed before this existed get their grid once, in the background."""
    t = threading.Thread(target=lambda: [tones_for(r, build=True) for r in recs], daemon=True)
    t.start()
    return t


def for_board(items: list[dict], style: dict, layout: list[dict], clips: dict[str, dict]) -> list[dict]:
    used = {it["clip_id"] for it in layout if it["kind"] == "shot"}
    tones = {cid: g for cid in used if cid in clips for g in [tones_for(clips[cid])] if g is not None}
    times = {cid: (clips[cid].get("samples") or {}).get("times", []) for cid in tones}
    return inks(items, style, layout, tones, times)

"""Second pass over the bench outputs: does the texture survive the platform?

Position-independent measures (grain is random, so a viewer cares whether it
still *looks* like grain, not whether it is the same grain):
  kept    added high-frequency luma std after the platform / before it,
          in flat-ish midtones of a 512x512 window (where grain shows)
  grid    of the added texture, edge energy on the 8-px transform grid vs
          off it (1.0 = no grid; >1 = the texture is turning into blocks)
  pulse   added texture on platform I-frames / on P+B frames (>1.3 = grain
          'breathes' at every keyframe)
  lp_fid  low-pass fidelity: how much of a slow texture (leak, vignette,
          bloom) is still there, in place, after the platform encode
Frames are streamed one at a time so memory stays flat.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np

FF = "/opt/homebrew/bin/ffmpeg"
WIN = {"v": (284, 560, 512, 512), "h": (1100, 120, 512, 512)}   # x, y, w, h


def box(y: np.ndarray, r: int) -> np.ndarray:
    k = 2 * r + 1
    c = np.cumsum(np.cumsum(np.pad(y, ((r + 1, r), (r + 1, r)), mode="edge"), 0), 1)
    return (c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]) / (k * k)


def stream(path: Path, fmt: str):
    x, y, w, h = WIN[fmt]
    p = subprocess.Popen([FF, "-v", "error", "-i", str(path), "-vf", f"crop={w}:{h}:{x}:{y}",
                          "-f", "rawvideo", "-pix_fmt", "gray", "-"], stdout=subprocess.PIPE)
    n = w * h
    while True:
        b = p.stdout.read(n)
        if len(b) < n:
            break
        yield np.frombuffer(b, np.uint8).reshape(h, w).astype(np.float64)


def types(path: Path) -> list[str]:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "frame=pict_type", "-of", "csv=p=0", str(path)], capture_output=True, text=True).stdout
    return [t.strip().strip(",") for t in out.split() if t.strip()]


def grid_parts(d: np.ndarray) -> tuple[float, float]:
    gx = np.abs(np.diff(d, axis=1))
    on = gx[:, 7::8]
    return float(on.mean()), float(np.delete(gx, np.s_[7::8], axis=1).mean())


def one(work: Path, fmt: str, name: str) -> dict:
    ti = types(work / f"{name}_{fmt}_platform.mp4")
    # the mask comes from the uncompressed graded frames: building it from one
    # of the compared encodes would select that encode's quietest pixels and
    # bias its variance down (regression to the mean).
    it = zip(stream(work / f"{fmt}.y4m", fmt), stream(work / f"base_{fmt}_master.mp4", fmt), stream(work / f"base_{fmt}_platform.mp4", fmt),
             stream(work / f"{name}_{fmt}_master.mp4", fmt), stream(work / f"{name}_{fmt}_platform.mp4", fmt))
    acc = {k: 0.0 for k in ("vm", "vbm", "vp", "vbp", "n", "gm_on", "gm_off", "gp_on", "gp_off", "lpn", "lpd")}
    per, kinds = [], []
    for k, (L0, bm, bp, m, p) in enumerate(it):
        hbm, hbp, hm, hpp = (a - box(a, 3) for a in (bm, bp, m, p))
        mask = (np.abs(L0 - box(L0, 3)) < 3) & (L0 > 60) & (L0 < 190)
        if mask.sum() < 500:
            continue
        v = [float(a[mask].var()) for a in (hm, hbm, hpp, hbp)]
        for key, val in zip(("vm", "vbm", "vp", "vbp"), v):
            acc[key] += val
        acc["n"] += 1
        per.append(np.sqrt(max(v[2] - v[3], 0.0)))
        kinds.append(ti[k] if k < len(ti) else "?")
        if k % 3 == 0:
            a, b = grid_parts(hm - hbm)
            acc["gm_on"] += a; acc["gm_off"] += b
            a, b = grid_parts(hpp - hbp)
            acc["gp_on"] += a; acc["gp_off"] += b
            lm, lp = box(m - bm, 7), box(p - bp, 7)
            acc["lpn"] += float((lm * lp).sum()); acc["lpd"] += float((lm * lm).sum())
    n = acc["n"]
    am = np.sqrt(max(acc["vm"] - acc["vbm"], 0) / n)
    ap = np.sqrt(max(acc["vp"] - acc["vbp"], 0) / n)
    per, kinds = np.array(per), np.array(kinds)
    I = kinds == "I"
    return {"recipe": name, "fmt": fmt, "frames": int(n), "added_hf_master": float(am), "added_hf_platform": float(ap),
            "kept": float(ap / am) if am > 0.3 else None,
            "grid_master": acc["gm_on"] / max(acc["gm_off"], 1e-9), "grid_platform": acc["gp_on"] / max(acc["gp_off"], 1e-9),
            "pulse_I_over_PB": float(per[I].mean() / max(per[~I].mean(), 1e-9)) if I.any() and (~I).any() else None,
            "n_I": int(I.sum()), "lp_fid": acc["lpn"] / max(acc["lpd"], 1e-9)}


if __name__ == "__main__":
    work = Path(sys.argv[1])
    names = sys.argv[2].split(",") if len(sys.argv) > 2 else \
        ["cinematic", "cinematic_fine", "cinematic_twos", "cozy", "hud", "editorial", "playful"]
    out = []
    for fmt in ("v", "h"):
        for name in names:
            r = one(work, fmt, name)
            out.append(r)
            print(json.dumps(r), flush=True)
    (work / "survive.json").write_text(json.dumps(out, indent=1))

"""Atmosphere layer prototype: one ffmpeg filter chain per vibe, plus a bench.

Every recipe processes only the creator's own frames: grain, light and
vignette are arithmetic on the real picture; nothing is generated that a
viewer would read as footage. All recipes use filters present in the
Homebrew ffmpeg (no drawtext, no libass) and sit AFTER lut3d and BEFORE pad
in export._fit, so bars stay black and the grade never re-colours texture.

Usage: python3 atmosphere_bench.py /tmp/atmo   (expects v.y4m and h.y4m there:
30 s graded mezzanines at 1080x1920 and 1920x1080, built with export._fit's
chain from one real clip).
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

FPS = 30
FF = "/opt/homebrew/bin/ffmpeg"


def _e(x: float) -> int:
    return max(2, int(round(x / 2)) * 2)


def grain(W: int, H: int, div: int, s: int, seed: int, rate: int = FPS, mode: str = "overlay") -> str:
    """A zero-mean luma grain plate, made at 1/div resolution so each grain is
    ~div px -- big enough to outlive a platform encoder's quantiser. Overlay
    mode scales it by the picture's own tone (none in black or white), which is
    what film grain does and keeps letterbox and dips clean."""
    return (f"color=c=gray:s={_e(W / div)}x{_e(H / div)}:r={rate},format=yuv420p,"
            f"lutyuv=y=126:u=128:v=128,noise=c0s={s}:c0f=t:c0_seed={seed},"
            f"scale={W}:{H}:flags=bicubic[gp];"
            "[{src}][gp]blend=c0_mode=" + mode + ":shortest=1")


def leak(W: int, H: int, t0: float = 0.0, opacity: float = 0.5) -> str:
    """A warm light leak that drifts along the top-left edge. The shape is one
    luma expression on a 36x64 plate (it is all low frequency; geq is the only
    costly filter here, so it runs on ~2k pixels), tinted amber by a channel
    mix and scaled up. t0 is the shot's position in the edit so the drift is
    continuous across cuts instead of jumping at every one. In export the
    shot's own fade string belongs on this small plate too, so the leak dips
    with the picture instead of glowing on a black dip."""
    T = f"(T+{t0:.3f})"
    I = (f"exp(-2.4*(pow((X/W-(-0.04+0.10*sin(2*PI*{T}/13)))/0.55,2)"
         f"+pow((Y/H-(0.16+0.08*sin(2*PI*{T}/9+1.3)))/0.36,2)))"
         f"*(0.82+0.18*sin(2*PI*{T}/4.7))")
    w, h = (36, 64) if H > W else (64, 36)
    return (f"color=c=black:s={w}x{h}:r={FPS},format=gray,geq=lum='255*{I}',"
            f"format=gbrp,colorchannelmixer=gg=0.59:bb=0.2,"
            f"scale=out_range=pc,format=yuv420p,scale={W}:{H}:flags=bicubic[lk];"
            f"[{{src}}][lk]blend=c0_mode=screen:c1_mode=grainmerge:c2_mode=grainmerge:"
            f"all_opacity={opacity}:shortest=1")


def scanlines(W: int, H: int, period: int = 6, depth: float = 0.18) -> str:
    """Raised-cosine scanlines: band-limited, so a platform downscale to 720p
    can't alias them into moire the way 1-px hard lines would. Rendered once
    and looped -- zero per-frame generation cost."""
    return (f"color=c=white:s={W}x{H}:r={FPS},format=yuv420p,"
            f"geq=lum='255*(1-{depth / 2}*(1+cos(2*PI*Y/{period})))':cb=128:cr=128,"
            f"trim=end_frame=1,loop=loop=-1:size=1,setpts=N/{FPS}/TB[sl];"
            "[{src}][sl]blend=c0_mode=multiply:shortest=1")


def bloom(W: int, H: int, knee: int = 175, sigma: float = 7, opacity: float = 0.45) -> str:
    """Highlights glow outwards (lamps, sky, white shirts). Computed at 1/4
    size: a glow is low frequency, so it is nearly free to encode."""
    return (f"[{{src}}]split[bl_a][bl_b];[bl_b]scale={_e(W / 4)}:{_e(H / 4)}:flags=bilinear,"
            f"lutyuv=y='clip((val-{knee})*255/(235-{knee}),0,255)':u=128:v=128,"
            f"gblur=sigma={sigma},scale={W}:{H}:flags=bicubic[glow];"
            f"[bl_a][glow]blend=c0_mode=screen:c0_opacity={opacity}")


def chain(stages: list[str]) -> str:
    """Join stages; each stage reads the previous label via {src}."""
    out, src = [], "0:v"
    for k, st in enumerate(stages):
        lab = f"s{k}"
        if st.startswith("[{src}]") or "{src}" in st:
            out.append(st.replace("{src}", src) + f"[{lab}]")
        else:   # a plain single-input filter string
            out.append(f"[{src}]{st}[{lab}]")
        src = lab
    return ";".join(out), src


def recipes(W: int, H: int, t0: float = 0.0, seed: int = 1) -> dict[str, list[str]]:
    shift = max(1, round(W / 600))
    return {
        "base": [],
        # 35mm-ish: ~2 px luma grain, std ~5.5 code values at mid-grey, per frame.
        "cinematic": [grain(W, H, 2, 10, seed)],
        # same strength, 1-px grain: the control for 'does grain size matter'.
        "cinematic_fine": [grain(W, H, 1, 8, seed)],
        # same 2-px grain refreshed at 15 Hz ('on twos'): the bitrate knob.
        "cinematic_twos": [grain(W, H, 2, 10, seed, rate=15)],
        # lens -> light -> film: vignette, then the leak, then soft coarse grain.
        "cozy": ["vignette=angle=0.5", leak(W, H, t0), grain(W, H, 3, 7, seed)],
        # scanlines + RGB split (red left, blue right). chromashift=crh=-1:cbh=1
        # gives the same fringe in YUV at ~1/4 the CPU (no gbrp round trip).
        "hud": [f"format=gbrp,rgbashift=rh=-{shift}:bh={shift}:edge=smear,format=yuv420p",
                scanlines(W, H)],
        # near nothing: a whisper of edge falloff, no noise.
        "editorial": ["vignette=angle=0.35"],
        # bright pop: highlight bloom, no grain.
        "playful": [bloom(W, H)],
    }


# --------------------------------------------------------------------------
# bench
# --------------------------------------------------------------------------

def run(cmd: list[str]) -> tuple[float, str]:
    t = time.perf_counter()
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode:
        raise RuntimeError(p.stderr[-2000:])
    return time.perf_counter() - t, p.stderr


def frames(path: Path, W: int, H: int, every: int = 30) -> np.ndarray:
    raw = subprocess.run([FF, "-v", "error", "-i", str(path), "-vf", f"select='not(mod(n\\,{every}))'",
                          "-fps_mode", "passthrough", "-f", "rawvideo", "-pix_fmt", "yuv420p", "-"],
                         capture_output=True).stdout
    n = W * H * 3 // 2
    return np.frombuffer(raw, np.uint8).reshape(-1, n)


def planes(f: np.ndarray, W: int, H: int):
    y = f[:, :W * H].reshape(-1, H, W).astype(np.float32)
    u = f[:, W * H:W * H * 5 // 4].reshape(-1, H // 2, W // 2).astype(np.float32)
    v = f[:, W * H * 5 // 4:].reshape(-1, H // 2, W // 2).astype(np.float32)
    return y, u, v


def hp(y: np.ndarray, r: int = 3) -> np.ndarray:
    """Luma minus its (2r+1)^2 box mean: what grain and scanlines live in."""
    k = 2 * r + 1
    c = np.cumsum(np.cumsum(np.pad(y, ((0, 0), (r + 1, r), (r + 1, r)), mode="edge"), 1), 2)
    box = (c[:, k:, k:] - c[:, :-k, k:] - c[:, k:, :-k] + c[:, :-k, :-k]) / (k * k)
    return y - box


def survival(dm: np.ndarray, dp: np.ndarray) -> tuple[float, float]:
    """(fidelity, energy): fidelity is how much of the delivered texture is
    still there, in place, after the platform encode (projection); energy is
    how much texture-like signal there is at all. Energy >> fidelity means the
    encoder replaced grain with its own pattern: mush."""
    den = float((dm * dm).sum()) or 1e-9
    return float((dp * dm).sum()) / den, float(np.sqrt((dp * dp).mean() / max((dm * dm).mean(), 1e-9)))


def ssim(a: Path, b: Path) -> float:
    _, err = run([FF, "-hide_banner", "-i", str(a), "-i", str(b), "-lavfi", "[0:v][1:v]ssim", "-f", "null", "-"])
    m = re.search(r"Y:([0-9.]+)", err.split("SSIM")[-1])
    return float(m.group(1)) if m else float("nan")


def blocky(p: Path) -> float:
    _, err = run([FF, "-hide_banner", "-i", str(p), "-vf", "blockdetect", "-f", "null", "-"])
    m = re.findall(r"block mean: ([0-9.]+)", err)
    return float(m[-1]) if m else float("nan")


def bench(work: Path, stills: Path, only: set | None = None) -> list[dict]:
    rows = []
    for fmt, (W, H), plat in (("v", (1080, 1920), "2.5M"), ("h", (1920, 1080), "8M")):
        src = work / f"{fmt}.y4m"
        base = {}
        for name, stages in recipes(W, H).items():
            if only and name not in only and name != "base":
                continue
            fc, lab = chain(stages)
            m = work / f"{name}_{fmt}_master.mp4"
            vf = ["-filter_complex", fc, "-map", f"[{lab}]"] if stages else ["-map", "0:v"]
            reps = 3 if name == "base" else 1
            ts = []
            for _ in range(reps):
                t, _ = run([FF, "-hide_banner", "-v", "error", "-y", "-i", str(src), *vf,
                            "-c:v", "h264_videotoolbox", "-b:v", "12M", "-profile:v", "high",
                            "-movflags", "+faststart", str(m)])
                ts.append(t)
            # the non-Mac export path: libx264 veryfast crf 18 -- a quality target, so size floats
            x = work / f"{name}_{fmt}_x264crf18.mp4"
            run([FF, "-hide_banner", "-v", "error", "-y", "-i", str(src), *vf, "-c:v", "libx264",
                 "-preset", "veryfast", "-crf", "18", str(x)])
            # the platform: capped-ABR libx264 from the uploaded master
            p = work / f"{name}_{fmt}_platform.mp4"
            _, log = run([FF, "-hide_banner", "-y", "-i", str(m), "-c:v", "libx264", "-preset", "medium",
                          "-b:v", plat, "-maxrate", plat, "-bufsize", f"{float(plat[:-1]) * 2}M",
                          "-profile:v", "high", str(p)])
            qp = [float(q) for q in re.findall(r"frame [IPB]:.*?Avg QP:\s*([0-9.]+)", log)]
            cnt = [int(c) for c in re.findall(r"frame [IPB]:(\d+)", log)]
            row = {"recipe": name, "fmt": f"{W}x{H}", "enc_s": min(ts),
                   "master_mbps": m.stat().st_size * 8 / 30 / 1e6,
                   "master_mb": m.stat().st_size / 1e6,
                   "x264crf18_mbps": x.stat().st_size * 8 / 30 / 1e6,
                   "platform_qp": sum(a * b for a, b in zip(qp, cnt)) / max(sum(cnt), 1),
                   "ssim_platform_vs_master": ssim(p, m),
                   "block_platform": blocky(p)}
            fm, fp = frames(m, W, H), frames(p, W, H)
            if name == "base":
                base = {"m": planes(fm, W, H), "p": planes(fp, W, H)}
                row["base_times"] = ts
            else:
                ym, um, vm = planes(fm, W, H)
                yp, up, vp = planes(fp, W, H)
                bm, bp = base["m"], base["p"]
                dm, dp = ym - bm[0], yp - bp[0]
                row["tex_luma_rms_master"] = float(np.sqrt((dm ** 2).mean()))
                row["hp_rms_master"] = float(np.sqrt((hp(dm) ** 2).mean()))
                row["hp_fidelity"], row["hp_energy"] = survival(hp(dm), hp(dp))
                row["full_fidelity"], row["full_energy"] = survival(dm, dp)
                cm = np.concatenate([(um - bm[1]).ravel(), (vm - bm[2]).ravel()])
                cp = np.concatenate([(up - bp[1]).ravel(), (vp - bp[2]).ravel()])
                row["chroma_rms_master"] = float(np.sqrt((cm ** 2).mean()))
                row["chroma_fidelity"], _ = survival(cm, cp)
            # stills: full master frame at t=15 s, and a 2x crop master|platform
            run([FF, "-v", "error", "-y", "-ss", "15", "-i", str(m), "-frames:v", "1",
                 str(stills / f"{name}_{W}x{H}.png")])
            cx, cy = (360, 700) if fmt == "v" else (1300, 330)
            crop = f"crop=320:320:{cx}:{cy},scale=640:640:flags=neighbor"
            run([FF, "-v", "error", "-y", "-ss", "15", "-i", str(m), "-ss", "15", "-i", str(p),
                 "-filter_complex", f"[0:v]{crop}[a];[1:v]{crop}[b];[a][b]hstack",
                 "-frames:v", "1", str(stills / f"{name}_{W}x{H}_master-vs-platform.png")])
            if name != "base":
                row["extra_s_per_min"] = (row["enc_s"] - rows_base(rows, fmt)["enc_s"]) * 2
            rows.append(row)
            print(json.dumps(row), flush=True)
    return rows


def rows_base(rows: list[dict], fmt: str) -> dict:
    W, H = (1080, 1920) if fmt == "v" else (1920, 1080)
    return next(r for r in rows if r["recipe"] == "base" and r["fmt"] == f"{W}x{H}")


if __name__ == "__main__":
    work = Path(sys.argv[1])
    stills = Path(__file__).parent / "stills"
    stills.mkdir(exist_ok=True)
    only = set(sys.argv[2].split(",")) if len(sys.argv) > 2 else None
    out = bench(work, stills, only)
    (work / ("results.json" if not only else "results_" + "_".join(sorted(only)) + ".json")).write_text(json.dumps(out, indent=1))

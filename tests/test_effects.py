"""Video effects on a shot (effects.py): each one renders, and moves the
picture the way it says, where it says, and nowhere else.

A textured, moving test card is exported plain and with each effect; every
check compares the two at a moment the effect should (or should not) show:

- flash / blur in: different at the start, the same once they have passed;
- zoom in / out: the middle of the frame grows at the end / start;
- shake / glitch: the picture is displaced from the plain one;
- grain / VHS: more frame-to-frame noise; VHS also draws scanlines;
- vignette / old film: darker corners; old film also turns warm;
- glow: brighter, softer; disco: the colour turns; strobe: blinks white;
- on the board: one undoable turn, kept through a cut, unknown names refused,
  Strength clamped.

    python tests/test_effects.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TMP = Path(tempfile.mkdtemp(prefix="vibecut-fx-"))
os.environ["VIBECUT_CACHE"] = str(TMP / "cache")
os.environ["VIBECUT_EXPORTS"] = str(TMP / "out")

from web.backend import board as bd  # noqa: E402
from web.backend import effects  # noqa: E402
from web.backend import export  # noqa: E402
from web.backend import timeline  # noqa: E402

failures: list[str] = []


def check(name: str, cond: bool, got: str = "") -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{': ' + got if got else ''}")
    if not cond:
        failures.append(name)


def ff(*args: str) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


def shot(cid: str) -> dict:
    return {"id": cid, "name": f"{cid}.MOV", "capture_time": None, "gps": None, "duration": 6.0,
            "shots": [{"index": 0, "start": 0.0, "end": 6.0, "thumb": "shot000.jpg", "best_t": 3.0,
                       "quality": 0.6, "aesthetic": None, "utility": False, "labels": [["x", 0.8]],
                       "faces": 0, "face_area": 0.0, "embedding": [1.0] + [0.0] * 7}]}


W, H = 320, 180


def frame(path: Path, t: float) -> np.ndarray:
    p = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(path), "-frames:v", "1",
                        "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True)
    return np.frombuffer(p.stdout, np.uint8).reshape(H, W, 3).astype(float)


def gray(x: np.ndarray) -> np.ndarray:
    return x.mean(axis=2)


def diff(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.abs(a - b).mean())


def sharp(x: np.ndarray) -> float:
    g = gray(x)
    return float(np.abs(np.diff(g, axis=1)).mean())


def centre_size(x: np.ndarray) -> float:
    """Width of the bright disc in the middle row: grows when the picture is pushed in."""
    row = gray(x)[H // 2]
    return float((row > 200).sum())


def disc_x(x: np.ndarray) -> float:
    """Where the white disc's middle is, across the frame."""
    row = gray(x)[H // 2]
    xs = np.nonzero(row > 200)[0]
    return float(xs.mean()) if len(xs) else 0.0


def main() -> int:
    A, B = TMP / "a.mov", TMP / "b.mov"
    # A: a checkerboard with a white disc in the middle, colour stripes on top, gently moving
    ff("-f", "lavfi", "-i",
       f"nullsrc=s={W}x{H}:r=30:d=6,geq="
       "r='if(lt(hypot(X-160,Y-90),30),250,if(lt(Y,20),220,90+60*mod(floor((X+T*10)/16)+floor(Y/16),2)))':"
       "g='if(lt(hypot(X-160,Y-90),30),250,if(lt(Y,20),60,90+60*mod(floor((X+T*10)/16)+floor(Y/16),2)))':"
       "b='if(lt(hypot(X-160,Y-90),30),250,if(lt(Y,20),60,90+60*mod(floor((X+T*10)/16)+floor(Y/16),2)))'",
       "-f", "lavfi", "-i", "sine=f=440:d=6:sample_rate=48000", "-c:v", "libx264", "-pix_fmt", "yuv420p",
       "-crf", "12", "-c:a", "pcm_s16le", "-shortest", str(A))
    ff("-f", "lavfi", "-i", f"color=c=gray:s={W}x{H}:r=30:d=6", "-f", "lavfi",
       "-i", "sine=f=880:d=6:sample_rate=48000", "-c:v", "libx264", "-pix_fmt", "yuv420p",
       "-c:a", "pcm_s16le", "-shortest", str(B))
    clips = {"A": {"id": "A", "path": str(A), "duration": 6.0, "width": W, "height": H},
             "B": {"id": "B", "path": str(B), "duration": 6.0, "width": W, "height": H}}
    cat = bd.Catalog.from_clips([shot("A"), shot("B")])
    option = {"key": "o", "name": "Two", "summary": "", "beats": [{"title": "All", "detail": "", "shots": [
        {"id": "A:0", "start": 1.0, "end": 4.0}, {"id": "B:0", "start": 1.0, "end": 3.0}]}]}
    mk = lambda d: {"options": [option]}  # noqa: E731
    s = bd.Session()
    s.add({"kind": "chat", "text": "go", "ops": [], "direction": {"text": "go"}}, cat, mk)
    s.add({"kind": "direct", "text": "pick", "ops": [{"op": "choose_option", "option": "o"}]}, cat, mk)

    def items():
        return timeline.layout(s.board)

    def fix(**kw):
        return s.add({"kind": "direct", "text": "fx", "ops": [{"op": "set_shot", "shot": "A:0", **kw}]}, cat, mk)

    print("on the board")
    t = fix(effect="shake")
    check("the shot carries its effect", items()[0].get("effect") == "shake", str(items()[0]))
    check("…the next shot doesn't", "effect" not in items()[1])
    check("the turn says so", any("Shake" in ln["text"] for ln in t.lines), str(t.lines))
    ta = fix(effect_amount=9)
    check("Strength is clamped to 200%", items()[0].get("effect_amount") == effects.AMOUNT[1], str(items()[0]))
    s.add({"kind": "direct", "text": "cut", "ops": [{"op": "split", "shot": "A:0", "at": 2.5}]}, cat, mk)
    it = items()
    check("a cut keeps the effect on both pieces", it[0].get("effect") == "shake" and it[1].get("effect") == "shake")
    s.toggle(s.turns[-1].id, cat, mk)
    s.toggle(ta.id, cat, mk)
    s.toggle(t.id, cat, mk)
    check("undo takes it off", "effect" not in items()[0])
    tb = fix(effect="sparkles_3d")
    check("an unknown effect is refused", "effect" not in items()[0] and any("sparkles_3d" in x for x in tb.skipped),
          str(tb.skipped))
    s.toggle(tb.id, cat, mk)
    t = fix(effect="vhs")
    t2 = fix(effect=None)
    check("No effect removes it, and its Strength", "effect" not in items()[0] and "effect_amount" not in items()[0],
          str(items()[0]))
    s.toggle(t2.id, cat, mk)
    s.toggle(t.id, cat, mk)

    print("export")
    renders: dict[str, Path] = {}

    def render(kind: str | None, amount: float = 1.0) -> Path:
        tt = fix(effect=kind, effect_amount=amount) if kind else None
        job = export.create(items(), clips, "t", None, want="wide")
        job.size = {"w": W, "h": H}
        out = TMP / f"{kind or 'plain'}-{amount}.mov"
        export._shot(job, job.items[0], out)
        if tt:
            s.toggle(tt.id, cat, mk)
        return out

    plain = render(None)
    for k in effects.KINDS:
        try:
            renders[k] = render(k)
            ok = True
        except Exception as e:  # noqa: BLE001
            ok = False
            print("   ", e)
        check(f"{effects.KINDS[k]} renders", ok)
    if len(renders) != len(effects.KINDS):
        print(f"\n{len(failures)} failed")
        return 1

    P = {t: frame(plain, t) for t in (0.05, 0.2, 1.0, 1.5, 2.9)}

    def at(k: str, t: float) -> np.ndarray:
        return frame(renders[k], t)

    print("timing")
    check("Flash: white at the cut", gray(at("flash", 0.03)).mean() > gray(P[0.05]).mean() + 60,
          f"{gray(at('flash', 0.03)).mean():.0f} vs {gray(P[0.05]).mean():.0f}")
    check("…gone by 1 s", diff(at("flash", 1.0), P[1.0]) < 3, f"{diff(at('flash', 1.0), P[1.0]):.1f}")
    check("Blur in: soft at the cut", sharp(at("blur_in", 0.05)) < 0.6 * sharp(P[0.05]),
          f"{sharp(at('blur_in', 0.05)):.1f} vs {sharp(P[0.05]):.1f}")
    check("…sharp by 1 s", diff(at("blur_in", 1.0), P[1.0]) < 3, f"{diff(at('blur_in', 1.0), P[1.0]):.1f}")
    zi0, zi1 = centre_size(at("zoom_in", 0.05)), centre_size(at("zoom_in", 2.9))
    check("Zoom in: the middle grows over the shot", zi1 > zi0 * 1.1, f"{zi0:.0f} -> {zi1:.0f} px")
    zo0, zo1 = centre_size(at("zoom_out", 0.05)), centre_size(at("zoom_out", 2.9))
    check("Zoom out: the middle shrinks over the shot", zo0 > zo1 * 1.1, f"{zo0:.0f} -> {zo1:.0f} px")
    pu = [centre_size(at("pulse", x)) for x in (0.02, 0.4)]
    check("Pulse: pushed in on the beat, back between", pu[0] > pu[1] + 2, f"{pu}")
    shakes = [diff(at("shake", x), P[x]) for x in (0.2, 1.0, 1.5)]
    check("Shake: the picture is moved off the plain one", min(shakes) > 3, f"{[round(x, 1) for x in shakes]}")
    strobe = [gray(frame(renders["strobe"], x / 30)).mean() for x in range(10)]
    check("Strobe: blinks white", max(strobe) - min(strobe) > 40, f"{min(strobe):.0f}..{max(strobe):.0f}")
    gl = [abs(disc_x(frame(renders["glitch"], x / 8 + 0.06)) - W / 2) for x in range(24)]
    check("Glitch: some moments jump sideways, some don't", max(gl) > 4 and min(gl) < 1.5,
          f"{min(gl):.1f}..{max(gl):.1f} px off centre")

    print("picture")
    noise = lambda x: float(np.abs(gray(x) - gray(P[1.0])).std())  # noqa: E731
    check("Film grain: noisier", noise(at("grain", 1.0)) > 2 * noise(frame(plain, 1.0)) + 1,
          f"{noise(at('grain', 1.0)):.1f}")
    v = gray(at("vhs", 1.0))
    rows = v[30:150].mean(axis=1)
    check("VHS: scanlines", float(np.abs(np.diff(rows)).mean()) > 1.5 * float(np.abs(np.diff(gray(P[1.0])[30:150].mean(axis=1))).mean()),
          f"{float(np.abs(np.diff(rows)).mean()):.1f}")
    corner = lambda x: float(gray(x)[:30, :40].mean() + gray(x)[-30:, -40:].mean()) / 2  # noqa: E731
    check("Vignette: darker corners", corner(at("vignette", 1.0)) < corner(P[1.0]) - 15,
          f"{corner(at('vignette', 1.0)):.0f} vs {corner(P[1.0]):.0f}")
    check("…the middle about the same", abs(gray(at("vignette", 1.0))[80:100, 140:180].mean() - gray(P[1.0])[80:100, 140:180].mean()) < 10)
    of = at("old_film", 1.0)[40:150]
    pl = P[1.0][40:150]
    warm = lambda x: float(x[..., 0].mean() - x[..., 2].mean())  # noqa: E731
    check("Old film: turns warm (sepia)", warm(of) > warm(pl) + 15, f"{warm(of):.0f} vs {warm(pl):.0f}")
    g = at("glow", 1.0)
    check("Glow: brighter and softer", gray(g).mean() > gray(P[1.0]).mean() + 10 and sharp(g) < sharp(P[1.0]),
          f"{gray(g).mean():.0f} vs {gray(P[1.0]).mean():.0f}")
    d0, d1 = at("disco", 0.05)[:20], at("disco", 1.5)[:20]
    check("Disco: the red stripe changes colour over time", diff(d0, d1) > 30, f"{diff(d0, d1):.0f}")

    print("strength")
    weak, strong = render("vignette", 0.5), render("vignette", 2.0)
    check("200% does more than 50%", corner(frame(strong, 1.0)) < corner(frame(weak, 1.0)) - 10,
          f"{corner(frame(weak, 1.0)):.0f} -> {corner(frame(strong, 1.0)):.0f}")

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

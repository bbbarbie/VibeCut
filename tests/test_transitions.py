"""Transitions the creator picks: does each one really happen at its cut?

1. On the board: `set_transition` on one join or every cut is one undoable
   turn, says what it did, refuses the last shot and unknown kinds, and is
   folded into the style export and preview both read (looks.picture).
2. Through the export (ffmpeg, ~20 s): two flat-coloured shots with footage
   past the cut. A plain cut jumps from one colour to the other between two
   frames; every blend has frames in between that are neither, centred on
   the timeline's cut, and the file stays exactly as long as the timeline.
   The blends must also differ from each other (a zoom is not a fade), and
   the light leak must be warmer than both shots in the middle. A shot not
   filmed long enough past the cut falls back to a cut and the export says so.

    python tests/test_transitions.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TMP = Path(tempfile.mkdtemp(prefix="vibecut-transitions-"))
os.environ["VIBECUT_CACHE"] = str(TMP / "cache")
os.environ["VIBECUT_EXPORTS"] = str(TMP / "out")

from web.backend import board as bd  # noqa: E402
from web.backend import export, looks, timeline, transitions  # noqa: E402

failures: list[str] = []
FPS = export.FPS


def check(name: str, cond: bool, got: str = "") -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{': ' + got if got else ''}")
    if not cond:
        failures.append(name)


def ff(*args: str) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


def shot(cid: str) -> dict:
    return {"id": cid, "name": f"{cid}.MOV", "capture_time": None, "gps": None, "duration": 8.0,
            "shots": [{"index": 0, "start": 0.0, "end": 8.0, "thumb": "shot000.jpg", "best_t": 4.0,
                       "quality": 0.6, "aesthetic": None, "utility": False, "labels": [["x", 0.8]],
                       "faces": 0, "face_area": 0.0, "embedding": [1.0] + [0.0] * 7}]}


def frames(path: str) -> np.ndarray:
    p = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vf", "scale=32:18", "-f", "rawvideo",
                        "-pix_fmt", "rgb24", "-"], capture_output=True, check=True)
    return np.frombuffer(p.stdout, np.uint8).reshape(-1, 18, 32, 3).astype(float)


def main() -> int:
    A, B, C = TMP / "a.mov", TMP / "b.mov", TMP / "c.mov"
    # still pictures with detail (a zoom of a flat colour is the same colour)
    for path, (r, g, b), f in ((A, (40, 70, 200), 440), (B, (60, 170, 70), 660), (C, (128, 128, 128), 880)):
        ff("-f", "lavfi", "-i", f"color=c=black:s=320x180:r=30:d=8,format=rgb24,"
           f"geq=r='{r}*(0.6+0.4*sin(X/9)*sin(Y/7))':g='{g}*(0.6+0.4*sin(X/9)*sin(Y/7))':b='{b}*(0.6+0.4*sin(X/9)*sin(Y/7))'",
           "-f", "lavfi",
           "-i", f"sine=f={f}:d=8:sample_rate=48000", "-c:v", "libx264", "-pix_fmt", "yuv420p",
           "-c:a", "pcm_s16le", "-shortest", str(path))
    clips = {c: {"id": c, "path": str(p), "duration": 8.0, "width": 320, "height": 180}
             for c, p in (("A", A), ("B", B), ("C", C))}
    cat = bd.Catalog.from_clips([shot("A"), shot("B"), shot("C")])
    # A then B with footage either side of their cut; C starts at the start of its file
    option = {"key": "o", "name": "Three", "summary": "", "beats": [{"title": "All", "detail": "", "shots": [
        {"id": "A:0", "start": 2.0, "end": 4.0}, {"id": "B:0", "start": 2.0, "end": 4.0},
        {"id": "C:0", "start": 0.0, "end": 2.0}]}]}
    mk = lambda d: {"options": [option]}  # noqa: E731
    s = bd.Session()
    s.add({"kind": "chat", "text": "go", "ops": [], "direction": {"text": "go"}}, cat, mk)
    s.add({"kind": "direct", "text": "pick", "ops": [{"op": "choose_option", "option": "o"}]}, cat, mk)

    def pick(**kw):
        return s.add({"kind": "direct", "text": "join", "ops": [{"op": "set_transition", **kw}]}, cat, mk)

    print("on the board")
    t1 = pick(shot="A:0", kind="zoom", dur=0.6)
    check("one join is recorded under the shot before it", s.board.get("picture_joins") == {"A:0": {"kind": "zoom", "dur": 0.6}},
          str(s.board.get("picture_joins")))
    check("the turn says so", any("zoom through" in ln["text"] for ln in t1.lines), str(t1.lines))
    pol = looks.picture(s.board, None)["transitions"]
    check("the style everything renders from carries it", pol["at"] == {"A:0": {"kind": "zoom", "dur": 0.6}}
          and pol["between"] == "cut", str(pol))
    s.toggle(t1.id, cat, mk)
    check("undo takes it away", not s.board.get("picture_joins") and not (looks.picture(s.board, None) or {}).get("transitions"))
    t2 = pick(all=True, kind="light_leak")
    check("every cut", s.board.get("picture_all") == {"kind": "light_leak", "dur": transitions.DUR_DEFAULT},
          str(s.board.get("picture_all")))
    check("…said in words", any("light leak" in ln["text"] for ln in t2.lines), str(t2.lines))
    pick(shot="B:0", kind="flash")
    t4 = pick(all=True, kind="dissolve")
    check("every cut again replaces the single picks", "picture_joins" not in s.board and s.board["picture_all"]["kind"] == "dissolve")
    pick(all=True, kind="auto")
    check("auto: back to the look", "picture_all" not in s.board and "picture_joins" not in s.board)
    del t4
    for bad, why in (({"shot": "C:0", "kind": "zoom"}, "the last shot"), ({"shot": "A:0", "kind": "spin"}, "an unknown kind")):
        t = pick(**bad)
        check(f"refuses {why}", bool(t.skipped) and "picture_joins" not in s.board, str(t.skipped))
        s.toggle(t.id, cat, mk)
    check("long joins are capped", (pick(shot="A:0", kind="blur", dur=9) and s.board["picture_joins"]["A:0"]["dur"]) == transitions.DUR_MAX)
    pick(shot="A:0", kind="auto")

    print("through the export")
    items = timeline.layout(s.board)
    cut = items[1]["seq_start"]

    def render(sty, name):
        job = export.create(items, clips, name, None, sty)
        export.start(job, [])
        while job.stage not in ("done", "error", "cancelled"):
            time.sleep(0.2)
        if job.stage != "done":
            raise RuntimeError(job.error)
        return frames(job.path), job

    plain, _ = render(None, "plain")
    total = int(round(items[-1]["seq_end"] * FPS))
    def between(fr: np.ndarray, whole: np.ndarray) -> np.ndarray:
        """Per frame: how far it is from every shot's own picture in that
        export, as a share of how far the first two are apart (0 = exactly one)."""
        pics = [whole[int(it["seq_start"] * FPS) + 12] for it in items]
        return np.min([np.abs(fr - p).mean((1, 2, 3)) for p in pics], axis=0) / np.abs(pics[0] - pics[1]).mean()

    k0 = int(cut * FPS)
    win = slice(k0 - 12, k0 + 12)
    check("a plain cut has no frame in between", between(plain[win], plain).max() < 0.08, f"{between(plain[win], plain).max():.3f}")
    mids = {}
    for kind in ("dissolve", "zoom", "slide_up", "blur", "light_leak"):
        s.add({"kind": "direct", "text": "j", "ops": [{"op": "set_transition", "shot": "A:0", "kind": kind, "dur": 0.6}]}, cat, mk)
        fr, job = render(looks.picture(s.board, None), kind)
        d = between(fr[win], fr)
        mixed = np.flatnonzero(d > 0.08)
        centre = (mixed.mean() + win.start) / FPS if len(mixed) else -1
        check(f"{kind}: frames in between at the cut", len(mixed) >= 6, f"{len(mixed)} frames")
        check(f"{kind}: centred on the timeline's cut", abs(centre - cut) < 0.07, f"{centre:.3f}s vs {cut:.3f}s")
        check(f"{kind}: exactly as long as the timeline", abs(len(fr) - total) <= 1, f"{len(fr)} vs {total} frames")
        check(f"{kind}: the second cut (no footage past it) stays a cut",
              between(fr[int(items[2]["seq_start"] * FPS) - 8:int(items[2]["seq_start"] * FPS) + 8], fr).max() < 0.08,
              f"{between(fr[int(items[2]['seq_start'] * FPS) - 8:int(items[2]['seq_start'] * FPS) + 8], fr).max():.3f}")
        mids[kind] = fr[k0]
        if kind == "light_leak":
            warm = lambda x: float(x[..., 0].mean() - x[..., 2].mean())  # noqa: E731
            check("light leak: warmer than either shot in the middle",
                  warm(fr[k0]) > max(warm(fr[k0 - 12]), warm(fr[k0 + 12])) + 20,
                  f"{warm(fr[k0]):.0f} vs {warm(fr[k0 - 12]):.0f} / {warm(fr[k0 + 12]):.0f}")
    names = list(mids)
    apart = min(np.abs(mids[x] - mids[y]).mean() for i, x in enumerate(names) for y in names[i + 1:])
    check("no two blends look the same at the cut", apart > 3, f"closest pair differs by {apart:.1f}/255")

    # every cut: the one with no footage past it says it fell back
    s.add({"kind": "direct", "text": "j", "ops": [{"op": "set_transition", "all": True, "kind": "slide_up"}]}, cat, mk)
    _, job = render(looks.picture(s.board, None), "all")
    check("a blend that can't fit becomes a cut, and the export says so", any("slide up" in n for n in job.notes), str(job.notes))

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

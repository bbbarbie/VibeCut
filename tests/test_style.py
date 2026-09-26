"""Does learning a style recover what was built into the reference?

Each fixture pair differs in exactly one respect -- how shots are joined,
how long they are held, where the cuts fall against a click track, the
grade, the frame -- and the learner has to separate them and recover the
magnitude that was built in. Then the look: fitting a LUT from a neutral
clip towards a graded one has to move the neutral clip's measured look
most of the way, and fitting a clip to itself has to change nothing.

    python tests/test_style.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cutgrammar import grade, media, style  # noqa: E402

SOURCES = [
    "color=c=crimson", "smptebars", "color=c=navy", "testsrc2",
    "color=c=goldenrod", "rgbtestsrc", "color=c=seagreen", "pal100bars",
]
SIZE = "320x180"
FPS = 30


def _ff(args: list[str]) -> None:
    p = subprocess.run(["ffmpeg", "-v", "error", "-y", *args], capture_output=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.decode()[-600:])


def build(path: str, lens: list[float], join: str = "cut", tdur: float = 0.6,
          audio: str | None = None, vf: str | None = None) -> None:
    """Shots of `lens` seconds from alternating sources, joined by `join`.

    For a soft join each shot is made `tdur` longer and the transition is
    centred on where the hard cut would have been, so the shot boundaries
    sit at the same times in every version.
    """
    ext = 0.0 if join == "cut" else tdur
    inputs, durs = [], []
    for i, L in enumerate(lens):
        src = SOURCES[i % len(SOURCES)]
        pre = ext / 2 if i > 0 else 0.0
        post = ext / 2 if i < len(lens) - 1 else 0.0
        durs.append(L + pre + post)
        inputs += ["-f", "lavfi", "-i", f"{src}{':' if '=' in src else '='}size={SIZE}:rate={FPS}:duration={durs[-1]:.3f}"]
    n = len(lens)
    if join == "cut" or n == 1:
        chain = "".join(f"[{i}:v]" for i in range(n)) + f"concat=n={n}:v=1:a=0[v0]"
    else:
        parts, prev, length = [], "[0:v]", durs[0]
        for i in range(1, n):
            out = "[v0]" if i == n - 1 else f"[x{i}]"
            parts.append(f"{prev}[{i}:v]xfade=transition={join}:duration={ext:.3f}:offset={length - ext:.3f}{out}")
            prev, length = out, length + durs[i] - ext
        chain = ";".join(parts)
    last = "[v0]"
    if vf:
        chain += f";[v0]{vf}[v1]"
        last = "[v1]"
    chain += f";{last}noise=alls=6:allf=t,format=yuv420p[v]"
    args = [*inputs]
    maps = ["-map", "[v]"]
    if audio:
        args += ["-f", "lavfi", "-i", audio]
        maps += ["-map", f"{n}:a", "-shortest"]
    _ff([*args, "-filter_complex", chain, *maps, "-c:v", "libx264", "-preset", "ultrafast",
         "-crf", "18", *(["-c:a", "aac"] if audio else []), path])


def learn(path: str) -> dict:
    m = media.load(path)
    return style.learn(m)


def main() -> int:
    failures: list[str] = []

    def check(name: str, cond: bool, got: str) -> None:
        print(f"  {'PASS' if cond else 'FAIL'}  {name}: {got}")
        if not cond:
            failures.append(name)

    lens = [2.0, 2.5, 1.8, 2.2, 3.0, 2.0, 2.4]
    with tempfile.TemporaryDirectory() as d:
        # --- transitions: same shots, three ways of joining them ----------
        print("transitions")
        got = {}
        for join in ("cut", "dissolve", "fadeblack", "fadewhite"):
            p = os.path.join(d, f"{join}.mp4")
            build(p, lens, join, tdur=0.6 if join != "fadewhite" else 0.3)
            got[join] = learn(p)["transitions"]
        c = got["cut"]["counts"]
        check("hard cuts are read as cuts", c["cut"] == 6 and c["dissolve"] + c["dip_black"] + c["flash"] == 0, str(c))
        c = got["dissolve"]["counts"]
        check("dissolves are read as dissolves", c["dissolve"] >= 5 and c["cut"] <= 1, str(c))
        dd = got["dissolve"]["dur"].get("dissolve", 0)
        check("  and their length is recovered (0.6 s)", abs(dd - 0.6) < 0.2, f"{dd:.2f}s")
        c = got["fadeblack"]["counts"]
        check("dips to black are read as dips", c["dip_black"] >= 5 and c["cut"] <= 1, str(c))
        c = got["fadewhite"]["counts"]
        check("white flashes are read as flashes", c["flash"] >= 4, str(c))
        check("the words say it", "dissolves" in " ".join(got["dissolve"]["words"])
              and "hard cuts only" in got["cut"]["words"], f"{got['dissolve']['words']} / {got['cut']['words']}")

        # A graded edit lifts its blacks: the dip bottoms out at a tinted
        # grey, not at black, and must still read as a dip.
        p = os.path.join(d, "graded_dips.mp4")
        build(p, lens, "fadeblack", tdur=0.6,
              vf="colorbalance=rs=-0.2:bs=0.25:rh=0.25:bh=-0.2,curves=all='0/0.08 1/0.95'")
        c = learn(p)["transitions"]["counts"]
        check("dips in a graded edit (lifted, teal blacks) are still dips", c["dip_black"] >= 5, str(c))

        # fade in from black / out to black at the ends
        p = os.path.join(d, "fades.mp4")
        build(p, lens[:3], vf="fade=t=in:st=0:d=1,fade=t=out:st=5.3:d=1")
        t = learn(p)["transitions"]
        check("opens from black and fades out", t["open"] and t["close"], f"open={t['open']} close={t['close']}")

        # --- pace: shot length recovered; an accelerating edit reads as one
        print("pace")
        for L in (0.8, 3.0):
            p = os.path.join(d, f"pace{L}.mp4")
            build(p, [L] * 10)
            pc = learn(p)["pace"]
            check(f"{L}s shots -> median {L}s", abs(pc["median_s"] - L) < 0.1, f"{pc['median_s']}s, {pc['words']}")
        p = os.path.join(d, "accel.mp4")
        build(p, [4, 3.5, 3, 2.5, 2, 1.6, 1.3, 1.1, 0.9, 0.8, 0.7, 0.6, 0.5, 0.5])
        acc = learn(p)["pace"]
        p = os.path.join(d, "even.mp4")
        build(p, [1.8] * 14)
        even = learn(p)["pace"]
        check("an accelerating edit trends faster", acc["trend"] < -0.5 and "speeds up towards the end" in acc["words"],
              f"trend {acc['trend']}, curve {acc['curve']}")
        check("an even edit doesn't", abs(even["trend"]) < 0.15, f"trend {even['trend']}")

        # --- beat: same shots, cut on a 120 BPM click vs a quarter-beat off
        print("beat")
        clicks = "aevalsrc='0.8*sin(2*PI*1200*t)*lt(mod(t\\,0.5)\\,0.03)':d=30:s=44100"
        on_lens = [1.0, 1.5, 1.0, 2.0, 1.0, 1.5, 1.0, 2.0, 1.5, 1.0, 2.0, 1.5]
        off_lens = [1.25] + on_lens[1:]
        res = {}
        for name, ls in (("on", on_lens), ("off", off_lens)):
            p = os.path.join(d, f"beat_{name}.mp4")
            build(p, ls, audio=clicks)
            res[name] = learn(p)["beat"]
        check("cuts on the click are on the beat", res["on"]["cuts_on_beat"] and res["on"]["on_grid"] > 0.8,
              f"grid {res['on']['on_grid']} lift {res['on']['lift']}")
        check("cuts between clicks are not", not res["off"]["cuts_on_beat"] and res["off"]["on_grid"] < 0.2,
              f"grid {res['off']['on_grid']} lift {res['off']['lift']}")
        check("tempo recovered", res["on"]["bpm"] is not None and abs(res["on"]["bpm"] - 120) < 2, str(res["on"]["bpm"]))

        # --- look: same shots, neutral vs a warm, lifted-black grade -------
        print("look")
        neutral = os.path.join(d, "neutral.mp4")
        warm = os.path.join(d, "warm.mp4")
        build(neutral, [3.0] * 6)
        build(warm, [3.0] * 6, vf="colorbalance=rm=0.25:bm=-0.25:rs=0.15:bs=-0.15,curves=all='0/0.12 1/1'")
        mn, mw = media.load(neutral), media.load(warm)
        ln, lw = style.learn(mn)["look"], style.learn(mw)["look"]
        check("the warm grade is warmer", lw["warmth"] - ln["warmth"] > 8, f"{ln['warmth']} -> {lw['warmth']}")
        check("and its blacks are lifted", lw["black"] - ln["black"] > 15, f"{ln['black']} -> {lw['black']}")
        check("the words say so", "warm" in lw["words"], str(lw["words"]))

        px_n, px_w = grade.pixels(mn.frames), grade.pixels(mw.frames)
        ref = grade.stats(px_w)
        lk = grade.Look(px_n, ref, strength=1.0)
        after = grade.stats(lk(px_n))
        moved_w = (after["warmth"] - ln["warmth"]) / (ref["warmth"] - ln["warmth"])
        moved_b = (after["black"] - ln["black"]) / (ref["black"] - ln["black"])
        check("the fitted LUT moves warmth most of the way", moved_w > 0.6, f"{moved_w:.0%}")
        check("and lifts the blacks most of the way", moved_b > 0.6, f"{moved_b:.0%}")
        lut = lk.lut()
        via_lut = grade.stats(grade.apply_lut(mn.frames[::10], lut).reshape(-1, 3).astype(np.float64))
        check("the baked LUT does what the function does", abs(via_lut["warmth"] - after["warmth"]) < 2.5,
              f"{via_lut['warmth']} vs {after['warmth']}")
        half = grade.stats(grade.Look(px_n, ref, strength=0.5)(px_n))
        check("half strength moves about half as far", 0.3 < (half["warmth"] - ln["warmth"]) / (after["warmth"] - ln["warmth"]) < 0.7,
              f"{half['warmth']}")
        same = grade.Look(px_n, grade.stats(px_n)).lut()
        g = np.linspace(0, 1, same.shape[0])
        ident = np.stack(np.meshgrid(g, g, g, indexing="ij"), axis=-1)
        err = float(np.abs(same - ident).max() * 255)
        check("fitting a clip to itself changes nothing", err < 3.0, f"max {err:.2f}/255")
        # content isn't grade: a blue-heavy reference must not paint everything blue
        blue = os.path.join(d, "blue.mp4")
        _ff(["-f", "lavfi", "-i", f"color=c=0x2060c0:size={SIZE}:rate={FPS}:duration=3",
             "-vf", "noise=alls=20:allf=t,format=yuv420p", "-c:v", "libx264", "-preset", "ultrafast", blue])
        px_b = grade.pixels(media.load(blue).frames)
        shift = (grade.Look(px_n, grade.stats(px_b))(px_n) - px_n).mean(axis=0)
        naive = px_b.mean(axis=0) - px_n.mean(axis=0)   # what histogram matching would move
        check("an all-blue reference moves blue far less than histogram matching would",
              abs(shift[2] - shift[0]) < 0.4 * abs(naive[2] - naive[0]),
              f"B-R shift {shift[2] - shift[0]:.1f} vs naive {naive[2] - naive[0]:.1f}")

        # --- frame: letterboxed 2.39 vs full frame -------------------------
        print("frame")
        lb = os.path.join(d, "letterbox.mp4")
        build(lb, [2.0] * 3, vf="scale=320:134,pad=320:180:0:23:black")
        fr = learn(lb)["frame"]
        full = learn(neutral)["frame"]
        check("letterbox recovered (2.39:1)", fr["letterbox"] and abs(fr["letterbox"] - 2.39) < 0.2, str(fr))
        check("full frame has no bars", full["letterbox"] is None, str(full))

        # --- real footage (optional): handheld clips, joined both ways ------
        # Synthetic sources hold still; real ones move during a dissolve,
        # and camera moves inside a shot look half like one. The thresholds
        # in style.py were set here. VIBECUT_REAL_CLIPS = a folder of clips.
        real = os.environ.get("VIBECUT_REAL_CLIPS")
        if real and os.path.isdir(real):
            print("real footage")
            raw = sorted(os.path.join(real, f) for f in os.listdir(real)
                         if f.lower().endswith((".mov", ".mp4")))[:8]
            small = []
            for i, r in enumerate(raw):
                o = os.path.join(d, f"real{i}.mp4")
                # clips shorter than 3 s hold their last frame, so every join is where it's meant to be
                _ff(["-i", r, "-vf", "scale=270:480:force_original_aspect_ratio=decrease,"
                     "pad=270:480:(ow-iw)/2:(oh-ih)/2,fps=30,tpad=stop_mode=clone:stop_duration=3,format=yuv420p",
                     "-t", "3", "-an",
                     "-c:v", "libx264", "-preset", "ultrafast", o])
                small.append(o)
            ins = [x for o in small for x in ("-i", o)]
            n = len(small)
            cut = os.path.join(d, "real_cut.mp4")
            _ff([*ins, "-filter_complex", "".join(f"[{i}:v]" for i in range(n)) + f"concat=n={n}:v=1[v]",
                 "-map", "[v]", "-c:v", "libx264", "-preset", "ultrafast", cut])
            parts, prev, length = [], "[0:v]", 3.0
            for i in range(1, n):
                out = "[v]" if i == n - 1 else f"[x{i}]"
                parts.append(f"{prev}[{i}:v]xfade=transition=dissolve:duration=0.5:offset={length - 0.5:.3f}{out}")
                prev, length = out, length + 2.5
            dis = os.path.join(d, "real_dissolve.mp4")
            _ff([*ins, "-filter_complex", ";".join(parts), "-map", "[v]", "-c:v", "libx264", "-preset", "ultrafast", dis])
            tc, td = learn(cut)["transitions"], learn(dis)["transitions"]
            check("real clips, hard cuts: no dissolve habit", "hard cuts only" in tc["words"], f"{tc['counts']}")
            check("real clips, dissolves: most found", td["counts"]["dissolve"] >= (n - 1) * 0.7
                  and "mostly dissolves" in td["words"], f"{td['counts']} of {n - 1}")

        # --- evidence: keyframe-only readings can't judge transitions ------
        print("evidence")
        s = style.learn(media.load_index(os.path.join(d, "dissolve.mp4")))
        check("a keyframe reading leaves transitions pending", s["transitions"].get("pending") == ["motion"],
              str(s["transitions"].get("words")))

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

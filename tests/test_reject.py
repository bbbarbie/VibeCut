"""Does reject throw away exactly the clips nobody would use -- and say why?

One fixture per failure, each otherwise like the good clip: lens cap, too
dark, blurred, a two-second mis-tap, a second take of the same view. Two
good clips of different things must survive, and two takes of someone
talking in the same place must be *flagged*, not dropped: they look the
same but may not say the same.

    python tests/test_reject.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cutgrammar import media, reject, signals  # noqa: E402

SCENE = ("color=c=0x2a3440:s=800x450:d={d}:r=30,drawgrid=w=18:h=18:t=3:c=0xe0e8f0@0.9[bg];"
         "color=c={col}:s=150x150:d={d}:r=30[box];[bg][box]overlay=x={x}:y=150[c];"
         "[c]crop=640:360:x='80+if({shake},78*sin(t*23),0)':y=45{post}")


def _clip(path: str, d: float = 10, col: str = "0xff8a1e", x: str = "325", shake: str = "0",
          post: str = "", speech: bool = False) -> str:
    args = ["-f", "lavfi", "-i", SCENE.format(d=d, col=col, x=x, shake=shake, post=post)]
    if speech:  # syllable-like bursts: voiced for ~0.3s, quiet for ~0.15s
        args += ["-f", "lavfi", "-i",
                 f"aevalsrc='0.4*sin(2*PI*180*t)*gt(sin(2*PI*2.2*t),-0.3)':d={d}:s=16000"]
    args += ["-c:v", "libx264", "-preset", "ultrafast", "-g", "15", "-pix_fmt", "yuv420p", "-shortest", path]
    p = subprocess.run(["ffmpeg", "-v", "error", "-y", *args], capture_output=True)
    if p.returncode:
        raise RuntimeError(p.stderr.decode()[:300])
    return path


def main() -> int:
    failures = []

    def check(name: str, cond: bool, got: str) -> None:
        print(f"  {'PASS' if cond else 'FAIL'}  {name}: {got}")
        if not cond:
            failures.append(name)

    with tempfile.TemporaryDirectory() as d:
        print("building fixtures...")
        clips = {
            "GOOD_A": _clip(f"{d}/a.mp4"),
            "GOOD_B": _clip(f"{d}/b.mp4", col="0x1ec8ff", x="120", post=",hue=h=90"),
            "SAME_AS_A": _clip(f"{d}/a2.mp4", post=",eq=brightness=-0.03"),
            "LENS_CAP": _clip(f"{d}/cap.mp4", post=",eq=brightness=-1"),
            "DARK": _clip(f"{d}/dark.mp4", post=",eq=brightness=-0.4:contrast=0.4"),
            "BLURRY": _clip(f"{d}/blur.mp4", post=",gblur=sigma=14"),
            "MISTAP": _clip(f"{d}/tap.mp4", d=1.8, x="900", shake="1"),
            "TALK_1": _clip(f"{d}/t1.mp4", x="200", speech=True),
            "TALK_2": _clip(f"{d}/t2.mp4", x="200", post=",eq=brightness=-0.02", speech=True),
        }
        cands = []
        for name, path in clips.items():
            sig = signals.from_media(media.load_index(path, audio=True))
            cands.append(reject.Candidate(id=name, name=name, sig=sig, embedding=np.asarray(sig.thumb),
                                          quality=float(np.mean(sig.quality))))
        # a lower-quality copy must be the one dropped
        next(c for c in cands if c.id == "SAME_AS_A").quality -= 0.05
        v = reject.reject_all(cands)

        expect = {"LENS_CAP": "lens-cap", "DARK": "dark", "BLURRY": "blurry", "MISTAP": "accident",
                  "SAME_AS_A": "duplicate"}
        for name, code in expect.items():
            check(f"{name} is rejected as {code}", v[name].rejected and v[name].code == code,
                  f"{v[name].code or 'kept'} — {v[name].zh}")
        # low-key is a style: a clearly visible subject on a dark ground stays
        stage = f"{d}/lowkey.mp4"   # a lit figure on a black stage, like a dance performance
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                        "color=c=0x050505:s=640x360:d=10:r=30[bg];color=c=0xf2c9a0:s=90x190:d=10:r=30[f];"
                        "[bg][f]overlay=x=275:y='95+6*sin(t*3)'", "-c:v", "libx264", "-preset", "ultrafast",
                        "-g", "15", "-pix_fmt", "yuv420p", stage], check=True, capture_output=True)
        lowkey = signals.from_media(media.load_index(stage, audio=False))
        lk = reject.judge(lowkey)
        check("a dark shot with a clear subject is kept (low-key, not a mistake)",
              not lk.rejected and np.mean(lowkey.luma) < reject.DARK_LUMA,
              f"luma {np.mean(lowkey.luma):.0f}, subject {np.mean(lowkey.subject):.2f} — {lk.zh or 'kept'}")
        for name in ("GOOD_A", "GOOD_B", "TALK_1", "TALK_2"):
            check(f"{name} is kept", not v[name].rejected, v[name].zh or "kept")
        check("every rejection says why, in plain words",
              all(x.zh and x.en for x in v.values() if x.rejected), "all have zh + en")
        check("the duplicate names the clip it copies", "GOOD_A" in v["SAME_AS_A"].zh, v["SAME_AS_A"].zh)
        flags = [f for f in v["TALK_1"].flags + v["TALK_2"].flags if f["code"] == "retake"]
        check("two talking takes that look alike are flagged, not dropped",
              len(flags) == 1 and not v["TALK_1"].rejected and not v["TALK_2"].rejected,
              flags[0]["zh"] if flags else "no flag")
        sim = reject._cos(next(c for c in cands if c.id == "GOOD_A").embedding,
                          next(c for c in cands if c.id == "GOOD_B").embedding)
        check("two different good clips are not near-duplicates", sim < reject.DUP_SIMILARITY, f"similarity {sim:.2f}")

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

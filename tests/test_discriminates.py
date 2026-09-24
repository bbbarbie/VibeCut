"""The test that matters: do the metrics tell a good edit from a bad one?

A measurement that only fires on bad footage proves nothing -- it has to
move in the right direction when the edit improves. These fixtures differ
in exactly one respect each, so a metric that shifts is responding to that
one thing and not to noise.

    python tests/test_discriminates.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cutgrammar import grammar, media, shots  # noqa: E402

# video cuts land at 3.0 / 5.0 / 7.5 / 11.5
CLIPS = [
    ("testsrc2=size=320x180:rate=30", 3.0, 300),
    ("color=c=crimson:size=320x180:rate=30", 2.0, 500),
    ("smptebars=size=320x180:rate=30", 2.5, 700),
    ("color=c=darkblue:size=320x180:rate=30", 4.0, 200),
    ("testsrc=size=320x180:rate=30", 2.0, 900),
]
J_OFFSET = 0.5  # seconds the sound arrives early in the good version


def _ff(args: list[str]) -> None:
    p = subprocess.run(["ffmpeg", "-v", "error", "-y", *args], capture_output=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.decode()[:400])


def build_fixtures(d: str) -> tuple[str, str]:
    """Two files with byte-identical picture and different audio timing."""
    parts = []
    for i, (src, dur, freq) in enumerate(CLIPS):
        out = os.path.join(d, f"c{i}.mp4")
        _ff(["-f", "lavfi", "-i", src,
             "-f", "lavfi", "-i", f"sine=frequency={freq}:duration={dur}",
             "-t", str(dur), "-c:v", "libx264", "-preset", "ultrafast",
             "-c:a", "aac", "-pix_fmt", "yuv420p", out])
        parts.append(out)

    lst = os.path.join(d, "list.txt")
    with open(lst, "w") as fh:
        for p in parts:
            fh.write(f"file '{p}'\n")

    hard = os.path.join(d, "hardsync.mp4")
    _ff(["-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", hard])

    # same tones, every change moved J_OFFSET earlier -> textbook J-cuts
    durs = [CLIPS[0][1] - J_OFFSET, *[c[1] for c in CLIPS[1:-1]],
            CLIPS[-1][1] + J_OFFSET]
    inputs, labels = [], ""
    for (_, _, freq), dur in zip(CLIPS, durs):
        inputs += ["-f", "lavfi", "-i", f"sine=frequency={freq}:duration={dur}"]
    labels = "".join(f"[{i}:a]" for i in range(len(CLIPS)))
    wav = os.path.join(d, "j.wav")
    _ff([*inputs, "-filter_complex",
         f"{labels}concat=n={len(CLIPS)}:v=0:a=1,loudnorm=I=-14[a]",
         "-map", "[a]", "-c:a", "pcm_s16le", wav])

    good = os.path.join(d, "jcut.mp4")
    _ff(["-i", hard, "-i", wav, "-map", "0:v", "-map", "1:a",
         "-c:v", "copy", "-c:a", "aac", "-shortest", good])
    return hard, good


def measure(path: str) -> dict:
    m = media.load(path)
    r = grammar.analyze(m, shots.detect(m))
    return {f.key: f for f in r.findings} | {"_n_shots": r.n_shots}


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        print("building fixtures...")
        hard, good = build_fixtures(d)
        bad_r, good_r = measure(hard), measure(good)

        failures = []

        def check(name: str, cond: bool, got: str) -> None:
            print(f"  {'PASS' if cond else 'FAIL'}  {name}: {got}")
            if not cond:
                failures.append(name)

        check("shot detection finds all 5 shots",
              bad_r["_n_shots"] == len(CLIPS),
              f"{bad_r['_n_shots']} shots")

        b, g = bad_r.get("jl_cuts"), good_r.get("jl_cuts")
        check("J/L metric is produced for both", b is not None and g is not None,
              f"hardsync={'yes' if b else 'no'} jcut={'yes' if g else 'no'}")

        if b and g:
            check("hard-synced cut is flagged", b.value > 0.7 and b.verdict == "bad",
                  f"{b.value:.0%} synced")
            check("J-cut version passes", g.value < 0.3 and g.verdict == "ok",
                  f"{g.value:.0%} synced")
            check("measured offset recovers the 0.5s we built in",
                  abs(g.extra["median_offset_s"] + J_OFFSET) < 0.15,
                  f"{g.extra['median_offset_s']:.2f}s")
            check("metric moved in the right direction", b.value - g.value > 0.5,
                  f"{b.value:.0%} -> {g.value:.0%}")

        bl, gl = bad_r.get("loudness"), good_r.get("loudness")
        if bl and gl:
            check("loudness normalisation is detected",
                  bl.verdict != "ok" and gl.verdict == "ok",
                  f"{bl.value:.1f} -> {gl.value:.1f} LUFS")

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

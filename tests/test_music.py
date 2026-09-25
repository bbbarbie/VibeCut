"""Does music matching follow energy *shape*, and only shape?

Fixtures: the same pink noise with opposite volume envelopes -- one rising,
one falling -- plus a copy of the rising one 20 dB quieter, and a storyboard
whose sections get busier as it goes. The rising track must rank first by a
margin no random curve gets near; the quiet copy must score the same as the
loud one; tempo must come back right on a click track and as None on noise.

    python tests/test_music.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cutgrammar import media, music  # noqa: E402

DUR = 120  # seconds of music; the edit below is 80s


def _ff(args: list[str]) -> None:
    p = subprocess.run(["ffmpeg", "-v", "error", "-y", *args], capture_output=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.decode()[:400])


def _noise(path: str, vol: str, dur: int = DUR) -> None:
    _ff(["-f", "lavfi", "-i", f"anoisesrc=color=pink:duration={dur}:seed=7",
         "-af", f"volume='{vol}':eval=frame", "-ar", "44100", path])


def _clicks(path: str, bpm: float, dur: int = 40) -> None:
    period = 60 / bpm
    _ff(["-f", "lavfi", "-i",
         f"aevalsrc='0.8*sin(2*PI*1200*t)*lt(mod(t\\,{period})\\,0.03)':d={dur}:s=44100", path])


# An edit that gets busier: long calm shots, then faster and more motion.
RISING_EDIT = [
    music.Section("Arrival", [8, 8, 8, 8], [2, 2, 3, 2]),
    music.Section("Market", [4] * 6, [8, 7, 9, 8, 8, 7]),
    music.Section("Festival", [2] * 12, [15] * 12),
]


def main() -> int:
    failures = []

    def check(name: str, cond: bool, got: str) -> None:
        print(f"  {'PASS' if cond else 'FAIL'}  {name}: {got}")
        if not cond:
            failures.append(name)

    with tempfile.TemporaryDirectory() as d:
        print("building fixtures...")
        lib = os.path.join(d, "music")
        os.makedirs(os.path.join(lib, "sub"))
        _noise(os.path.join(lib, "rising.m4a"), f"0.03+0.97*t/{DUR}")
        _noise(os.path.join(lib, "falling.mp3"), f"1-0.97*t/{DUR}")
        _noise(os.path.join(lib, "sub", "rising_quiet.flac"), f"0.1*(0.03+0.97*t/{DUR})")
        _noise(os.path.join(lib, "rising_short.wav"), "0.03+0.97*t/30", dur=30)

        t0 = time.time()
        tracks = music.LocalFolderSource(lib).list()
        first = time.time() - t0
        by = {os.path.basename(t.path): t for t in tracks}
        check("folder walk finds mp3/m4a/wav/flac, recursively", len(tracks) == 4, sorted(by))

        r = music.match(RISING_EDIT, tracks)
        names = [os.path.basename(s.track.path) for s in r["suggestions"]]
        scores = {os.path.basename(s.track.path): s.score for s in r["suggestions"]}
        check("rising track ranks first", names[0] in ("rising.m4a", "rising_quiet.flac"),
              " > ".join(f"{n} {scores[n]:+.2f}" for n in names))
        gap = scores["rising.m4a"] - scores["falling.mp3"]
        check("rising beats falling by a wide margin", gap > 1.0, f"gap {gap:.2f}")
        check("loudness doesn't matter, shape does",
              abs(scores["rising.m4a"] - scores["rising_quiet.flac"]) < 0.05,
              f"{scores['rising.m4a']:+.3f} vs quiet {scores['rising_quiet.flac']:+.3f}")
        check("tracks shorter than the edit are left out",
              r["too_short"] == 1 and "rising_short.wav" not in names,
              f"edit {r['edit_seconds']}s, {r['too_short']} too short")

        # Is the gap signal or noise? Null: 200 trendless energy curves
        # (smoothed noise, same length) -- tracks with no shape at all.
        rng = np.random.default_rng(0)

        def null(curves):
            ts = [music.Track(path=f"n{i}", duration=DUR, bpm=None, energy=c.astype(np.float32))
                  for i, c in enumerate(curves)]
            return sorted(s.score for s in music.match(RISING_EDIT, ts, top=len(ts))["suggestions"])

        def unit(x):
            return (x - x.min()) / (np.ptp(x) + 1e-9)
        flat_null = null([unit(music._smooth(rng.normal(size=DUR), 5)) for _ in range(200)])
        p95 = flat_null[int(0.95 * len(flat_null))]
        check("rising score clears the 95th percentile of shapeless tracks",
              scores["rising.m4a"] > p95 + 0.2, f"{scores['rising.m4a']:.2f} vs p95 {p95:.2f}")

        # Not a pass/fail: how finely can it rank *among* rising tracks?
        # Random walks trend, so many of them rise too.
        walks = null([unit(np.cumsum(rng.normal(size=DUR))) for _ in range(200)])
        beat = sum(w > scores["rising.m4a"] for w in walks)
        print(f"  INFO  {beat}/200 random-walk curves out-score the linear ramp "
              f"(p95 {walks[int(0.95 * len(walks))]:.2f}): with 3 sections the edit's shape "
              "is coarse, so ranking among broadly-rising tracks is weak")

        top = r["suggestions"][0]
        check("the reason is specific and names the busiest section",
              "Festival" in top.reason and "peaks" in top.reason, repr(top.reason))
        bottom = next(s for s in r["suggestions"] if s.track.path.endswith("falling.mp3"))
        check("a poor match gets no invented reason", bottom.reason == "", repr(bottom.reason))

        flat = music.match([music.Section("A", [5, 5], [3, 3]), music.Section("B", [5, 5], [3, 3])], tracks)
        check("a flat edit has no shape to match", flat["flat"] and not flat["suggestions"], str(flat["flat"]))

        # Cache: a second run reads features, decodes nothing.
        real = music.analyse
        music.analyse = lambda p: (_ for _ in ()).throw(AssertionError("decoded again"))
        t0 = time.time()
        again = music.LocalFolderSource(lib).list()
        second = time.time() - t0
        music.analyse = real
        check("second run is served from the cache", len(again) == 4 and second < first / 5,
              f"{first:.2f}s -> {second:.3f}s")

        # Tempo: right when the pulse is clear, None when there isn't one.
        for bpm in (120, 90, 150):
            p = os.path.join(d, f"click{bpm}.wav")
            _clicks(p, bpm)
            got, info = music.estimate_bpm(media.load_audio(p))
            check(f"click track at {bpm} BPM", got is not None and abs(got - bpm) < 1.5, str(got))
            # clicks start at t=0, so the grid must land on multiples of the period
            period = 60 / bpm
            ph = info.get("phase", -1) % period
            check(f"  beat phase at {bpm} BPM lands on the clicks", min(ph, period - ph) < 0.03, f"phase {ph:.3f}s")
        p = os.path.join(d, "noise.wav")
        _ff(["-f", "lavfi", "-i", "anoisesrc=color=white:duration=40:seed=3", p])
        got, info = music.estimate_bpm(media.load_audio(p))
        check("noise has no tempo", got is None, f"{got} {info}")
        got, info = music.estimate_bpm(media.load_audio(os.path.join(lib, "rising.m4a")))
        check("a swell of noise has no tempo", got is None, f"{got} {info}")

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

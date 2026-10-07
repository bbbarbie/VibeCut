"""Snap targets: the right moments, in the edit's time, sorted.

    python tests/test_timeline.py
"""

from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cutgrammar import music  # noqa: E402
from web.backend import timeline  # noqa: E402

BOARD = {"beats": [
    {"id": "t1", "title": "Morning", "shots": [
        {"id": "aaa:0", "start": 10.0, "end": 20.0},          # 10s taken from 10..20 of clip aaa
        {"key": "gap~x", "id": None, "gap": True, "start": 0.0, "end": 2.0},
    ]},
    {"id": "t2", "title": "Market", "shots": [
        {"id": "bbb:0", "start": 0.0, "end": 8.0},
    ]},
]}
CLIPS = {
    "aaa": {"marks": [
        {"t": 5.0, "kind": "quiet", "approx": 0.0},            # before the trimmed-in point: must vanish
        {"t": 13.5, "kind": "quiet", "approx": 0.0},           # -> edit 3.5
        {"t": 16.0, "kind": "motion_on", "approx": 0.5},       # -> edit 6.0
        {"t": 25.0, "kind": "sound", "approx": 0.0},           # after the out point: must vanish
    ]},
    "bbb": {"marks": [
        {"t": 0.01, "kind": "motion_on", "approx": 0.5},       # within a frame of the shot start: shot wins
        {"t": 4.0, "kind": "sound", "approx": 0.0},            # -> edit 16.0
    ]},
}


def main() -> int:
    failures = []

    def check(name: str, cond: bool, got: str) -> None:
        print(f"  {'PASS' if cond else 'FAIL'}  {name}: {got}")
        if not cond:
            failures.append(name)

    tl = timeline.build(BOARD, CLIPS, None)
    ts = tl["targets"]
    got = [(x["t"], x["type"]) for x in ts]
    check("targets are sorted", all(a["t"] <= b["t"] for a, b in zip(ts, ts[1:])), str(got))
    check("shot boundaries, gap start and end of edit are there",
          [(t, lbl) for t, lbl in ((x["t"], x["label"]) for x in ts if x["type"] == "shot")]
          == [(0.0, "shot 1 start"), (10.0, "gap start"), (12.0, "shot 2 start"), (20.0, "end of edit")],
          str([(x["t"], x["label"]) for x in ts if x["type"] == "shot"]))
    check("marks map from source time into the edit",
          (3.5, "silence") in got and (6.0, "motion") in got and (16.0, "silence") in got, str(got))
    check("marks outside the used part of a clip are dropped",
          all(not (x["t"] < 0 or x["t"] > 20) for x in ts) and len([g for g in got if g[1] != "shot"]) == 3,
          str(got))
    check("within a frame of a shot boundary, the boundary wins",
          [x for x in ts if abs(x["t"] - 12.0) < 0.05] == [{"t": 12.0, "type": "shot", "label": "shot 2 start"}],
          str([x for x in ts if abs(x["t"] - 12.0) < 0.05]))
    lbl = next(x["label"] for x in ts if x["t"] == 6.0)
    check("approximate targets say so", "±0.5s" in lbl, lbl)
    check("no music, no beat grid; no transcript, no words",
          not any(x["type"] in ("beat", "word") for x in ts) and tl["grid"] is None, "none")

    t = music.Track(path="x", duration=60, bpm=120.0, energy=np.zeros(60, np.float32), meta={"tempo": {"phase": 0.25}})
    beats = [x for x in timeline.build(BOARD, CLIPS, t)["targets"] if x["type"] == "beat"]
    check("a track with a tempo adds its beat grid", len(beats) >= 38 and beats[0]["t"] == 0.25
          and beats[0]["label"] == "bar 1 downbeat", f"{len(beats)} beats, first {beats[0]}")
    nobpm = music.Track(path="y", duration=60, bpm=None, energy=np.zeros(60, np.float32))
    check("a track without a reliable tempo adds nothing",
          not any(x["type"] == "beat" for x in timeline.build(BOARD, CLIPS, nobpm)["targets"]), "none")

    # The rough trim has no page of its own: a shot's ends are dragged in
    # Frames, as far as the whole shot as filmed, not just the trimmed window.
    filmed = {**CLIPS, "aaa": {**CLIPS["aaa"], "shots": [{"index": 0, "start": 0.0, "end": 31.5}]}}
    shot = timeline.build(BOARD, filmed, None)["items"][0]
    check("a shot can be dragged out to the whole shot as filmed",
          (shot["src_min"], shot["src_max"]) == (0.0, 31.5), str(shot))
    bare = timeline.build(BOARD, CLIPS, None)["items"]
    check("without the clip's shots, the ends stay where they are",
          (bare[2]["src_min"], bare[2]["src_max"]) == (0.0, 8.0) and "src_min" not in bare[1], str(bare))

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

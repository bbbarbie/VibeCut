"""Does borrowing a style actually give the edit that style?

Two halves.

1. On the storyboard (fast, no media): `apply_style` retimes shots towards
   the reference's pace *and its arc*, moves cuts onto the beat of a track,
   leaves voiceover parts alone, says honestly which shots were filmed too
   short, and is one undoable turn that replays exactly.

2. The round trip (ffmpeg, ~30 s): a reference with dissolves and a warm,
   lifted grade is learnt; an edit of *different* footage is exported with
   that style; the export is learnt in turn. It must read back as the
   reference's habits -- mostly dissolves, warmer, lifted blacks, bars --
   while every cut stays on the frame the timeline put it on. A metric that
   only fires proves nothing; this one has to survive a full render.

    python tests/test_restyle.py
"""

from __future__ import annotations

import copy
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TMP = Path(tempfile.mkdtemp(prefix="vibecut-restyle-"))
os.environ["VIBECUT_EXPORTS"] = str(TMP / "out")
os.environ.setdefault("VIBECUT_CACHE", str(TMP / "cache"))

from cutgrammar import grade, media, style  # noqa: E402
from web.backend import board as bd  # noqa: E402
from web.backend import export, restyle  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_board import CLIPS, OPTION, PROPOSALS  # noqa: E402
from test_style import build  # noqa: E402

failures: list[str] = []


def check(name: str, cond: bool, got: str) -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {name}: {got}")
    if not cond:
        failures.append(name)


def seq(board: dict) -> list[float]:
    out = []
    for bt in board["beats"]:
        for e in bt["shots"]:
            out.append(round(e["end"] - e["start"], 3))
    return out


def on_board() -> None:
    print("storyboard")
    cat = bd.Catalog.from_clips(CLIPS)
    s = bd.Session()
    s.add({"kind": "chat", "text": "a day in Tokyo", "ops": [], "direction": {"text": "a day in Tokyo"}},
          cat, lambda d: PROPOSALS)
    s.add({"kind": "direct", "text": "choose", "ops": [{"op": "choose_option", "option": "time"}]},
          cat, lambda d: PROPOSALS)
    before = copy.deepcopy(s.board)
    check("apply_style is never offered to the chat model", "apply_style" not in bd.LLM_OPS, str(bd.LLM_OPS))

    # A quick reference that speeds up: 2 s a shot on average, 3 s at the top, 1.2 s at the end.
    ref = {"pace": {"median_s": 2.0, "curve": [1.5, 1.25, 1.0, 0.8, 0.6]},
           "transitions": restyle.transition_policy({"share": {"cut": 0.3, "dissolve": 0.7, "dip_black": 0, "flash": 0},
                                                     "dur": {"dissolve": 0.6}, "open": True, "close": False})}
    op = {"op": "apply_style", "ref": "abc", "name": "Fast ref", "traits": ["pace", "transitions"], "style": ref}
    t = s.add({"kind": "direct", "text": "borrow", "ops": [op]}, cat, lambda d: PROPOSALS)
    lens = seq(s.board)
    check("the turn applied", not t.skipped, str(t.skipped))
    check("median shot moves to the reference's", abs(float(np.median(lens)) - 2.0) < 0.35,
          f"{np.median(seq(before)):.1f}s -> {np.median(lens):.2f}s")
    check("and follows its arc (long at the top, short at the end)", lens[0] > 2.6 and lens[-1] < 1.5,
          f"first {lens[0]}, last {lens[-1]}")
    check("the transition rule is stored for export", s.board["style"]["transitions"]["within"] == "dissolve",
          str(s.board["style"]["transitions"]))
    check("the diff says what was borrowed", any("Borrowed from “Fast ref”" in l["text"] for l in t.lines),
          " | ".join(l["text"] for l in t.lines[-3:]))
    # every retimed shot is still inside its source shot and centred on its best frame
    inside = all(cat.get(e["id"]).start - 1e-6 <= e["start"] and e["end"] <= cat.get(e["id"]).end + 1e-6
                 for bt in s.board["beats"] for e in bt["shots"])
    check("every shot stays inside what was filmed", inside, "")

    replay = copy.deepcopy(s.board)
    s.replay(cat, lambda d: PROPOSALS)
    check("replay is exact", s.board == replay, "")
    s.toggle(t.id, cat, lambda d: PROPOSALS)
    check("undo restores the board exactly", s.board == before, "")
    s.toggle(t.id, cat, lambda d: PROPOSALS)

    # longer than filmed: 12 s shots can't be held 30 s -- counted, not padded
    slow = {**op, "style": {"pace": {"median_s": 30.0, "curve": [1, 1, 1, 1, 1]}}, "traits": ["pace"]}
    t2 = s.add({"kind": "direct", "text": "slow", "ops": [slow]}, cat, lambda d: PROPOSALS)
    r = s.board["style"]["report"]
    check("shots filmed too short are counted, not padded", r["filmed_too_short"] == r["shots"]
          and max(seq(s.board)) <= 12.0 + 1e-6, str(r))
    check("  and the diff says so", any("weren't filmed longer" in l["text"] for l in t2.lines), "")
    s.toggle(t2.id, cat, lambda d: PROPOSALS)

    # on the beat: 120 BPM from t=0 -> every cut on a multiple of 0.5 s
    beat = {**op, "traits": ["pace", "beat"], "grid": {"bpm": 120.0, "phase": 0.0}}
    t3 = s.add({"kind": "direct", "text": "beat", "ops": [beat]}, cat, lambda d: PROPOSALS)
    cuts = np.cumsum(seq(s.board))[:-1]
    off = np.abs(cuts / 0.5 - np.round(cuts / 0.5)) * 0.5
    check("cuts land on the beat", float(off.max()) < 0.02 and s.board["style"]["report"]["on_beat"] >= len(cuts) - 1,
          f"worst {off.max():.3f}s, {s.board['style']['report']['on_beat']} snapped")
    s.toggle(t3.id, cat, lambda d: PROPOSALS)
    t4 = s.add({"kind": "direct", "text": "beat, no track", "ops": [{**op, "traits": ["beat"]}]}, cat, lambda d: PROPOSALS)
    check("cutting on the beat without a track is refused, not guessed", bool(t4.skipped), str(t4.skipped))

    # a voiceover part keeps its timing: the voice sets time there
    s2 = bd.Session()
    s2.add({"kind": "chat", "text": "a day in Tokyo", "ops": [], "direction": {"text": "a day in Tokyo"}},
           cat, lambda d: PROPOSALS)
    s2.add({"kind": "direct", "text": "choose", "ops": [{"op": "choose_option", "option": "time"}]},
           cat, lambda d: PROPOSALS)
    s2.board["beats"][1]["line"] = "We got to the market early."
    snap = copy.deepcopy(s2.board)
    b2, _ = bd.apply(snap, op, cat, PROPOSALS, new_id=lambda: "x")
    check("a voiceover part isn't retimed", b2["beats"][1]["shots"] == snap["beats"][1]["shots"]
          and b2["style"]["report"]["held_by_voice"] == 1, "")


def round_trip() -> None:
    print("round trip")
    d = TMP / "rt"
    d.mkdir(exist_ok=True)
    # The reference: 1 s shots, dissolves everywhere, warm with lifted blacks, letterboxed.
    ref_path = str(d / "ref.mp4")
    build(ref_path, [1.4] * 10, "dissolve", tdur=0.6,
          vf="colorbalance=rm=0.25:bm=-0.25:rs=0.15:bs=-0.15,curves=all='0/0.12 1/1',"
             "scale=320:134,pad=320:180:0:23:black")
    ref = style.learn(media.load(ref_path))
    check("reference reads as dissolves", "mostly dissolves" in ref["transitions"]["words"], str(ref["transitions"]["words"]))

    # The creator's footage: other sources, neutral grade, 10 s each.
    srcs = ["testsrc", "testsrc2", "smptehdbars", "rgbtestsrc", "yuvtestsrc", "pal75bars"]
    clips = {}
    for i, src in enumerate(srcs):
        p = d / f"clip{i}.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"{src}=size=320x180:rate=30", "-t", "10",
                        "-f", "lavfi", "-i", f"sine=frequency={300 + 100 * i}:duration=10",
                        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac",
                        "-shortest", str(p)], check=True)
        clips[f"c{i}"] = {"id": f"c{i}", "path": str(p), "width": 320, "height": 180, "duration": 10.0}
    # six 2 s shots from the middle of each clip, in two parts
    items, t = [], 0.0
    for i in range(6):
        items.append({"key": f"c{i}:0", "kind": "shot", "clip_id": f"c{i}", "src_start": 4.0, "src_end": 6.0,
                      "seq_start": round(t, 4), "seq_end": round(t + 2.0, 4), "n": i + 1,
                      "beat_id": "p1" if i < 3 else "p2"})
        t += 2.0
    # the third runs to the very end of its file: no handle past its cut
    items[2]["src_start"], items[2]["src_end"] = 8.0, 10.0

    def run(sty: dict | None, name: str) -> str:
        job = export.create(items, clips, name, None, sty)
        export.start(job, [])
        while job.stage not in ("done", "error", "cancelled"):
            time.sleep(0.2)
        if job.stage != "done":
            raise RuntimeError(job.error)
        return job.path, job

    plain, _ = run(None, "plain")
    # the look fitted the way reference.fit_look does it: on the creator's footage
    px = grade.pixels(np.concatenate([media.load(clips[c]["path"]).frames[::30] for c in clips]))
    lut = grade.Look(px, ref["look"], 1.0).lut()
    cube = str(d / "look.cube")
    grade.write_cube(lut, cube)
    sty = {"transitions": restyle.transition_policy(ref["transitions"]),
           "look": {"lut": cube, "strength": 1.0}, "letterbox": ref["frame"]["letterbox"], "name": "ref"}
    styled, job = run(sty, "styled")

    mp, ms = media.load(plain), media.load(styled)
    check("the export is exactly as long as the timeline", abs(ms.n_frames - mp.n_frames) <= 1,
          f"{ms.n_frames} vs {mp.n_frames} frames")
    got, base = style.learn(ms), style.learn(mp)
    check("the styled export reads back as dissolves", "mostly dissolves" in got["transitions"]["words"],
          f"{got['transitions']['counts']} (plain: {base['transitions']['counts']})")
    ts = [x["t"] for x in got["transitions"]["list"] if x["kind"] == "dissolve"]
    want = [it["seq_start"] for it in items[1:]]
    near = [min(abs(w - x) for x in ts) for w in want] if ts else [9.9]
    check("each dissolve is centred on its timeline cut", float(np.median(near)) < 0.1,
          f"median offset {np.median(near):.3f}s")
    check("the missing handle fell back to a cut, and said so", bool(job.notes), str(job.notes))
    lw, lb, lr = got["look"], base["look"], ref["look"]
    # This reference is warm partly by *content* (crimson, goldenrod); only
    # the grade should come across, and colour shifts are bounded so other
    # footage isn't painted with it. So: a clear move towards it, within the bound.
    dw = lw["warmth"] - lb["warmth"]
    check("warmth moved towards the reference, within the bound", 8 < dw <= 2 * grade.MAX_SHIFT + 2,
          f"{lb['warmth']} -> {lw['warmth']} (ref {lr['warmth']})")
    check("blacks lifted towards the reference", lw["black"] - lb["black"] > 0.5 * (lr["black"] - lb["black"]),
          f"{lb['black']} -> {lw['black']} (ref {lr['black']})")
    check("cinematic bars came through", got["frame"]["letterbox"] and abs(got["frame"]["letterbox"] - ref["frame"]["letterbox"]) < 0.25,
          str(got["frame"]))
    check("the plain export has none of it", "hard cuts only" in base["transitions"]["words"]
          and base["frame"]["letterbox"] is None, f"{base['transitions']['words']} {base['frame']}")


def main() -> int:
    on_board()
    round_trip()
    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

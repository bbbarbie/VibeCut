"""A day vlog is about the day: what the edit keeps from a shoot.

sarah (2026-10-14), after putting VibeCut's edit of her school day next to
her own: "a lot of material was left out, transitions, different locations,
it shouldn't all be about my face", and then "if the vlogger is talking [to]
the vlog audience the face can be in it a lot ... me and my friend sitting
there, it wasn't worth 14 seconds at all". Each rule here gets a pair of
fixtures that differ in exactly that respect:

- talk said to the lens keeps its sentence; the same talk turned to a friend
  (or, with no face direction read, two people chatting) is a 3 s glimpse,
  in the rough cut and at every pace;
- shortening an edit covers every stop of the day before any stop gets a
  second shot (and putting shots back starts with stops not yet shown);
- a short holds no moment longer than 3.5 s;
- a night shot with lights in it isn't left out for low exposure;
- cozy swipes between parts: the export slides one picture out and the next
  in (left half old, right half new on the cut frame), where a dissolve
  would blend them.

    python tests/test_day_picking.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

os.environ["VIBECUT_CACHE"] = tempfile.mkdtemp(prefix="vibecut-day-")
os.environ["VIBECUT_EXPORTS"] = os.path.join(os.environ["VIBECUT_CACHE"], "out")   # never her Movies folder
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from cutgrammar import trim  # noqa: E402
from cutgrammar.signals import ClipSignals  # noqa: E402
from web.backend import board as bd  # noqa: E402
from web.backend import brief, export, tempo, vision  # noqa: E402
from web.backend import storyboard as sb  # noqa: E402

N = 20


def signals(talking: bool = True) -> dict:
    return {"duration": float(N), "quality": [0.8] * N, "sharpness": [0.6] * N, "luma": [120.0] * N,
            "contrast": [0.5] * N, "motion": [2.0] * N, "subject": [0.8] * N, "edge": [0.0] * N,
            "speech": [0.9 if talking else 0.0] * N,
            "voiced": [[i + 0.05, i + 0.9] for i in range(N)] if talking else [], "thumb": [0.0] * 144}


def faces(people: float, facing: float) -> list[list[float]]:
    return [[1.0, 0.0, people, facing]] * N


def clip(cid: str, face_rows, talking: bool = True, when: str = "2026-10-12T12:46:00") -> dict:
    n = N + 1
    return {"id": cid, "name": f"{cid}.MOV", "duration": float(N), "capture_time": when, "gps": [40.808, -73.962],
            "signals": signals(talking), "faces": face_rows,
            "sound": {"voice": [0.9 if talking else 0.0] * n, "music": [0.0] * n},
            "shots": [{"index": 0, "start": 0.0, "end": float(N), "thumb": "t.jpg", "quality": 0.7, "best_t": 10.0,
                       "activity": 5.0, "labels": [], "faces": 1, "face_area": 0.08,
                       "embedding": [float(cid == k) for k in "abcdefgh"]}]}


def main() -> int:
    failures = []

    def check(name: str, cond: bool, got: str = "") -> None:
        print(f"  {'PASS' if cond else 'FAIL'}  {name}{': ' + got if got else ''}")
        if not cond:
            failures.append(name)

    print("talking to the audience vs chatting")
    sig = ClipSignals.from_json(signals())
    lens = np.asarray(faces(1, 1.0))
    chat = np.asarray(faces(2, 0.0))
    turned = np.asarray(faces(1, 0.0))
    two_blind = np.asarray(faces(2, -1.0))
    one_blind = np.asarray(faces(1, -1.0))
    check("one face looking into the lens while talking: said to the audience", trim.addressed(sig, lens) is True)
    check("turned to a friend while talking: overheard", trim.addressed(sig, chat) is False)
    check("alone but looking away the whole time: overheard", trim.addressed(sig, turned) is False)
    check("no direction read, two people talking: overheard", trim.addressed(sig, two_blind) is False)
    check("no direction read, one person: can't tell, nothing changes", trim.addressed(sig, one_blind) is None)
    check("old two-column face rows: can't tell", trim.addressed(sig, lens[:, :2]) is None)
    keep = trim.best_window(sig, None, lens)
    glimpse = trim.best_window(sig, None, chat)
    check("the rough cut keeps the talk to camera whole", keep.end - keep.start >= 15, f"{keep.start}-{keep.end}")
    check("and gives the chat a glimpse (her 14 s chat would be 3 s)",
          glimpse.end - glimpse.start <= trim.CHATTER_S + 0.2, f"{glimpse.start}-{glimpse.end}")

    clips = [clip("a", faces(1, 1.0)), clip("b", faces(2, 0.0))]
    shots = sb.shots_from_clips(clips)
    check("the pace leaves talk to camera alone, not the chat", tempo.talking(clips, shots) == {"a:0"},
          str(tempo.talking(clips, shots)))
    lens_track = [[r[0], r[1], 1.0, 1.0] for r in faces(1, 1.0)]
    talky = tempo.read([clip(c, lens_track) for c in "abcdef"])
    chatty = tempo.read([clip(c, faces(2, 0.0)) for c in "abcdef"])
    check("a shoot of talking to camera counts as talking, a shoot of chats doesn't",
          talky["facts"]["talking"] > 0.5 and chatty["facts"]["talking"] == 0.0,
          f"{talky['facts']['talking']} vs {chatty['facts']['talking']}")

    print("face direction from the boxes")
    track = vision.face_track([[[0.3, 0.3, 0.3, 0.3, 5.0]], [[0.3, 0.3, 0.3, 0.3, 60.0], [0.0, 0.3, 0.25, 0.25, 0.0]],
                               [[0.3, 0.3, 0.3, 0.3, 0.0], [0.9, 0.9, 0.02, 0.02, 0.0]], [[0.3, 0.3, 0.3, 0.3]]],
                              [0.2, 1.2, 2.2, 3.2], 4)
    check("looking in, turned away + a friend, a stranger far back, no direction",
          [r[2:] for r in track] == [[1.0, 1.0], [2.0, 0.0], [1.0, 1.0], [1.0, -1.0]], str(track))

    print("every stop of the day before a second shot of any")
    base = datetime(2026, 10, 12, 8, 30)

    def shot(i: int, minutes: int, gps, score: float, clip_id: str | None = None) -> sb.Shot:
        return sb.Shot(id=f"s{i}:0", clip_id=clip_id or f"s{i}", clip_name=f"s{i}", index=0, start=0.0, end=3.0,
                       thumb="", quality=score, aesthetic=None, utility=False, when=base + timedelta(minutes=minutes),
                       gps=gps, labels={}, faces=0, face_area=0.0, activity=5.0,
                       vec=np.eye(16, dtype=np.float32)[i % 16], order=i)
    here, there, far = (40.8075, -73.9626), (40.8100, -73.9600), (40.8200, -73.9500)
    # six good selfies in one spot, then three weaker shots of other stops
    day = [shot(i, i, here, 0.9) for i in range(6)] + \
          [shot(6, 90, there, 0.5), shot(7, 200, far, 0.45), shot(8, 400, here, 0.4)]
    where = brief.spots(day)
    check("stops: one spot, a walk away, further, and back hours later",
          len(set(where.values())) == 4 and len({where[s.id] for s in day[:6]}) == 1, str(where))

    def shaped(shots) -> list[str]:
        o = sb.Option("time", "As it happened", "time", "", [sb.Beat("Day", "", list(shots))])
        brief.shape([o], {"seconds": 15.0}, {})
        return [s.id for b in o.beats for s in b.shots]
    got = shaped(day)
    check("a 15 s edit keeps all three other stops and two of the selfies",
          {"s6:0", "s7:0", "s8:0"} <= set(got) and len(got) == 5, str(got))
    same = [shot(i, i, here, s.quality) for i, s in enumerate(day)]
    got_same = shaped(same)
    check("the same shots filmed in one stop: the weakest go, as before",
          not ({"s6:0", "s7:0", "s8:0"} & set(got_same)), str(got_same))

    print("putting shots back shows a new stop first")
    clips9 = []
    for s in day:
        clips9.append({"id": s.clip_id, "name": s.clip_name, "duration": 3.0,
                       "capture_time": s.when.isoformat(), "gps": list(s.gps),
                       "shots": [{"index": 0, "start": 0.0, "end": 3.0, "thumb": "t.jpg", "quality": s.quality,
                                  "best_t": 1.5, "labels": [], "embedding": list(map(float, s.vec))}]})
    cat = bd.Catalog.from_clips(clips9)
    board = {"beats": [{"id": "b1", "title": "Day", "shots": [{"id": "s0:0", "start": 0.0, "end": 3.0}]}]}
    pool = sb.shots_from_clips(clips9)
    ops, _ = brief.length_ops(board, cat, pool, 6.0, vision=False)
    added = [o["shot"] for o in ops if o["op"] == "add_shot"]
    check("one more shot: from a stop not shown yet, not another selfie", added and added[0] in {"s6:0", "s7:0"},
          str(added))

    print("a short holds no moment long")
    check("short: 3.5 s at most, whatever the pace", brief.cap_for({"format": "short", "pace": "calm"}) == 3.5
          and brief.cap_for({"seconds": 60.0}) == 3.5)
    check("a quick short stays quicker", brief.cap_for({"format": "short", "pace": "fast"}) == 2.5)
    check("a long vlog keeps the pace's own", brief.cap_for({"format": "tall", "seconds": 300.0, "pace": "calm"}) == 8.0)

    print("night shots with lights")

    def dim(i: int, hour: int, contrast: float) -> sb.Shot:
        s = shot(i, 0, here, 0.15)
        s.when, s.contrast = base.replace(hour=hour), contrast
        return s
    lit, murk, noon = dim(10, 20, 0.7), dim(11, 20, 0.1), dim(12, 12, 0.7)
    good = shot(9, 0, here, 0.8)
    keep_ids = {id(s) for s in sb.usable([lit, murk, noon, good])[0]}
    check("8:30 pm with lit windows stays; murk and a dim noon shot go",
          id(lit) in keep_ids and id(murk) not in keep_ids and id(noon) not in keep_ids)

    print("cozy swipes between parts")
    swipe_render(check)

    print(f"\n{'all passed' if not failures else f'{len(failures)} failed'}")
    return 1 if failures else 0


def swipe_render(check) -> None:
    d = Path(os.environ["VIBECUT_CACHE"]) / "swipe"
    d.mkdir(parents=True, exist_ok=True)
    clips = {}
    for cid, colour in (("r", "red"), ("b", "blue")):
        p = d / f"{cid}.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color={colour}:size=320x180:rate=30",
                        "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", "4",
                        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac",
                        "-shortest", str(p)], check=True)
        clips[cid] = {"id": cid, "path": str(p), "width": 320, "height": 180, "duration": 4.0}
    items = [{"key": "r:0", "kind": "shot", "clip_id": "r", "src_start": 1.0, "src_end": 3.0,
              "seq_start": 0.0, "seq_end": 2.0, "n": 1, "beat_id": "p1"},
             {"key": "b:0", "kind": "shot", "clip_id": "b", "src_start": 1.0, "src_end": 3.0,
              "seq_start": 2.0, "seq_end": 4.0, "n": 2, "beat_id": "p2"}]
    pol = {"between": "swipe", "within": "cut", "dur": 0.4, "open": False, "close": False}
    plan, _ = export.plan_transitions(export.spans(items), clips, {"transitions": pol})
    check("the plan marks the join a swipe, with a dissolve's handles", plan[0].get("swipe") and plan[0]["tail"] > 0
          and plan[1]["head"] > 0, str(plan))

    def render(sty: dict, name: str) -> str:
        job = export.create(items, clips, name, None, sty)
        export.start(job, [])
        while job.stage not in ("done", "error", "cancelled"):
            time.sleep(0.2)
        if job.stage != "done":
            raise RuntimeError(job.error)
        return job.path

    def at_cut(path: str) -> np.ndarray:
        info = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                               "stream=width,height", "-of", "csv=p=0", path], capture_output=True, text=True)
        w, h = (int(x) for x in info.stdout.strip().split(",")[:2])
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", "2.0", "-i", path, "-frames:v", "1", "-f", "rawvideo",
                              "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
        return np.frombuffer(raw[: w * h * 3], dtype=np.uint8).reshape(h, w, 3).astype(int)
    sw = at_cut(render({"transitions": pol}, "swipe"))
    dv = at_cut(render({"transitions": {**pol, "between": "dissolve"}}, "dissolve"))
    w = sw.shape[1]
    left, right = sw[:, : w // 4].mean(axis=(0, 1)), sw[:, -w // 4:].mean(axis=(0, 1))
    check("swipe on the cut frame: the old shot on the left, the new one on the right",
          left[0] > left[2] + 80 and right[2] > right[0] + 80, f"left {left.round()}, right {right.round()}")
    mid = dv[:, : w // 4].mean(axis=(0, 1))
    check("a dissolve on the same frame blends them instead", abs(mid[0] - mid[2]) < 80, f"{mid.round()}")


def test_day_picking() -> None:
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())

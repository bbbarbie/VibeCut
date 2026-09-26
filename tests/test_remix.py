"""Remix, piece by piece, without the web.

- The fingerprint takes what references agree on: one reference holding a
  single shot for eight seconds must not stretch ours.
- A drop is found where the music jumps, on the beat, and not in a flat track.
- Quantised windows are whole beats; the hook is at least two.
- Captions come only from times and labels the edit has.
- The export's duck really lowers the music inside the interval and not
  outside (ffmpeg, ~1 s).
- Caption frames: overlapping captions become one picture per segment and
  the schedule never overlaps itself (AppKit, compiles once).

    python tests/test_remix.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import wave
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from web.backend import export, remix, select as sel, storyboard as sb  # noqa: E402

failures: list[str] = []


def check(name: str, cond: bool, got: str) -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {name}: {got}")
    if not cond:
        failures.append(name)


def style(median=0.7, curve=None, first=1.4, bpm=120.0, dur=25.0) -> dict:
    return {"duration": dur, "pace": {"median_s": median, "curve": curve or [1, 1, 1, 1, 1], "first_s": first},
            "music": {"bpm": bpm, "arc": "builds", "energy": list(np.linspace(0, 1, 32))},
            "frame": {"vertical": True}}


def fingerprint() -> None:
    print("fingerprint")
    fp = remix.fingerprint([style(curve=[1, 1, 1, 8.3, 1]), style(curve=[1, 1, 0.9, 1, 1]), style(curve=[5.2, 0.7, 0.7, 1, 1])])
    check("one reference's held shot doesn't stretch our fourth", fp["curve"][3] <= 1.1, str(fp["curve"]))
    check("...nor its title hold our first fifth", fp["curve"][0] <= 1.1, str(fp["curve"]))
    fp2 = remix.fingerprint([style(bpm=104), style(bpm=133)])
    check("the tempo range spans the references with a margin", fp2["bpm"][0] < 104 and fp2["bpm"][1] > 133,
          str(fp2["bpm"]))
    fp3 = remix.fingerprint([style(dur=200.0)])
    check("a long reference is clipped to a short's length", fp3["duration"] <= remix.DEFAULT_LEN[1],
          str(fp3["duration"]))


def _wav(path: str, seconds: float, loud_from: float | None, sr: int = 16000, silent_until: float = 0.0) -> None:
    t = np.arange(int(seconds * sr)) / sr
    x = 0.05 * np.sin(2 * np.pi * 220 * t)
    if loud_from is not None:
        x[t >= loud_from] *= 8
    x[t < silent_until] = 0.0
    # a click every beat so the tempo is real
    period = 0.5
    for b in np.arange(0, seconds, period):
        i = int(b * sr)
        x[i:i + 40] += 0.5
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())


def drop() -> None:
    print("the drop")
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "a.wav")
        _wav(p, 40.0, loud_from=12.0)
        t = remix.find_drop(p, 120.0, 0.0, need_s=20.0, hook_s=1.5)
        check("found where the music jumps, on the grid", t is not None and abs(t - 12.0) < 0.26, str(t))
        q = os.path.join(d, "flat.wav")
        _wav(q, 40.0, loud_from=None)
        check("a flat track has no drop", remix.find_drop(q, 120.0, 0.0, 20.0, 1.5) is None, "None")
        r = os.path.join(d, "intro.wav")
        _wav(r, 40.0, loud_from=12.0, silent_until=4.0)
        t = remix.find_drop(r, 120.0, 0.0, 20.0, 1.5)
        check("silence before the intro is not a drop; the real jump is", t is not None and abs(t - 12.0) < 0.26, str(t))

    print("continuity")
    with tempfile.TemporaryDirectory() as d:
        sr = 16000
        t = np.arange(20 * sr) / sr
        bed = 0.5 * np.sin(2 * np.pi * 220 * t)                       # a filled pad
        plucks = bed * ((t % 1.0) < 0.15)                              # one short note a second, air between
        for name, x in (("bed", bed), ("plucks", plucks)):
            with wave.open(os.path.join(d, name + ".wav"), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(sr)
                w.writeframes((x * 32767).astype("<i2").tobytes())
        a, b = remix.continuity(os.path.join(d, "bed.wav")), remix.continuity(os.path.join(d, "plucks.wav"))
        check("a filled bed scores above plucks with air between them", a > 0.9 and b < 0.5, f"{a:.2f} vs {b:.2f}")

    print("vibe from the catalogue's words")
    from cutgrammar import music as mu

    def track(title, tags):
        return mu.Track(path=title, duration=100, bpm=120, energy=np.ones(100), title=title,
                        meta={"licence": {"title": title, "tags": tags}})
    a = remix.vibe(track("New pop song", ["nudisco", "action", "instrumental"]))
    b = remix.vibe(track("Dreams (Acoustic)", ["happy", "love", "male"]))
    check("a disco pop bed outranks an acoustic ballad at the same tempo", a > 0.6 and b < 0.4, f"{a:.2f} vs {b:.2f}")

    print("variety")
    fp = remix.fingerprint([style(median=0.7)])
    fp["pace_p"] = None
    ts = [0.7 * remix._spread(fp, k) for k in range(8)]
    check("shot lengths vary around the pace instead of marching", len(set(round(x, 2) for x in ts)) >= 3
          and min(ts) < 0.7 < max(ts), str([round(x, 2) for x in ts]))


def T(i: int) -> datetime:
    return datetime(2026, 9, 22, 8, 35) + timedelta(minutes=i)


def _pick(i: int, start: float, end: float, role: str = "hero", labels=None) -> sel.Pick:
    s = sb.Shot(id=f"c{i}:0", clip_id=f"c{i}", clip_name=f"IMG_{i}.MOV", index=0, start=0.0, end=10.0,
                thumb="", quality=0.8, aesthetic=0.2, utility=False, when=T(i), gps=None,
                labels=labels or {"people": 0.9}, faces=0, face_area=0.0, activity=0.5,
                vec=np.eye(4)[i % 4].astype(np.float32), order=i)
    return sel.Pick(s, role, start, end, 0.6, "")


def beats() -> None:
    print("whole beats")
    plan = sel.Plan(hook=[_pick(0, 2.0, 2.7, "hook")], sessions=[[_pick(1, 1.0, 1.9), _pick(2, 3.0, 3.6)]],
                    titles=["Morning"])
    clips = {p.shot.clip_id: {"duration": 10.0, "signals": {"subject": [0.3] * 11, "motion": [10.0] * 11}}
             for p in plan.picks}
    remix.quantise(plan, clips, 0.5)
    lens = [round(p.duration, 3) for p in plan.picks]
    check("every window is a whole number of beats", all(abs(x / 0.5 - round(x / 0.5)) < 1e-6 for x in lens), str(lens))
    check("the hook is held at least two beats", plan.hook[0].duration >= 1.0, str(plan.hook[0].duration))


def words() -> None:
    print("words on screen")
    plan = sel.Plan(hook=[_pick(0, 0.0, 1.5, "hook")],
                    sessions=[[_pick(1, 0.0, 1.0, labels={"cup": 0.7}), _pick(2, 0.0, 1.0)],
                              [_pick(3, 0.0, 1.0, labels={"laptop": 0.9})]],
                    titles=["Morning", "Afternoon"])
    caps = remix.captions(plan, None, None)
    kinds = [c["kind"] for c in caps]
    check("a title over the hook, a tag after it, words per scene", kinds == ["title", "tag", "scene", "scene"], str(kinds))
    check("the title's second line is the date the clips carry", caps[0]["sub"] == "Tuesday, September 22", caps[0]["sub"])
    scene = [c["text"] for c in caps if c["kind"] == "scene"]
    check("scene words are the clock and a phrase from a label the shot has",
          scene == ["8:36 a.m. · coffee run", "8:38 a.m. · work work work"], str(scene))
    check("the tag runs to the end and the title ends with the hook",
          caps[1]["end"] == plan.duration and caps[0]["end"] == 1.5, f"{caps[0]['end']} {caps[1]['end']}")
    caps2 = remix.captions(plan, "a day at columbia", "week one")
    check("the creator's own words replace the defaults", caps2[0]["text"] == "a day at columbia"
          and caps2[0]["sub"] == "week one" and caps2[1]["text"] == "a day at columbia", caps2[0]["text"])


def duck() -> None:
    print("the duck (ffmpeg)")
    expr = export._duck_expr([(1.0, 2.0, 0.2)])
    check("no ducks, no expression", export._duck_expr([]) == "", repr(export._duck_expr([])))
    p = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
                        "-af", f"volume='{expr}':eval=frame", "-f", "f32le", "-ac", "1", "-ar", "16000", "-"],
                       capture_output=True)
    x = np.frombuffer(p.stdout, dtype=np.float32)

    def rms(a, b):
        s = x[int(a * 16000):int(b * 16000)]
        return float(np.sqrt(np.mean(s * s)))

    inside, before, after = rms(1.3, 1.7), rms(0.2, 0.6), rms(2.4, 2.8)
    check("music is at the duck gain inside the interval and full outside",
          abs(inside / before - 0.2) < 0.03 and abs(after / before - 1) < 0.03,
          f"inside/outside = {inside / before:.2f}, after = {after / before:.2f}")
    mid = rms(0.9, 1.0)
    check("the edges ramp rather than step", 0.25 < mid / before < 0.95, f"{mid / before:.2f}")


def frames() -> None:
    print("caption frames (AppKit)")
    caps = [{"kind": "tag", "text": "a day in my life", "start": 1.0, "end": 4.0, "anim": "fade"},
            {"kind": "scene", "text": "8:35 a.m. · coffee run", "start": 1.0, "end": 2.5, "anim": "pop"}]
    with tempfile.TemporaryDirectory() as d:
        job = export.Job(id="t", items=[], clips={}, size={"w": 270, "h": 480}, total=5.0, name="t")
        export.WORK = Path(d)
        job.dir.mkdir(parents=True)
        (job.dir / "frames").mkdir()
        sched = remix.render_captions(caps, job.size, 30, job)
        ok = all(b["start"] >= a["end"] - 1e-9 for a, b in zip(sched, sched[1:]))
        check("the schedule never overlaps itself", ok and sched, f"{len(sched)} entries")
        check("it starts with the first caption and ends a frame before the last's cut",
              abs(sched[0]["start"] - 1.0) < 1e-6 and abs(sched[-1]["end"] - (4.0 - 1 / 30)) < 1e-3,
              f"{sched[0]['start']}–{sched[-1]['end']}")
        pngs = list((job.dir / "frames").glob("*.png"))
        check("one PNG per distinct picture, not per caption", len(pngs) == len(sched) and 8 <= len(pngs) <= 12,
              str(len(pngs)))


def main() -> int:
    fingerprint()
    drop()
    beats()
    words()
    duck()
    frames()
    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

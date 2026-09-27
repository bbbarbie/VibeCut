"""The sound across a cut: does each join do what it says, and only that?

Two clips, each a pure tone (440 Hz and 880 Hz), so which clip is sounding
at any instant can be measured exactly. The same two-shot edit is mixed
with one thing changed at a time:

- a hard cut vs the default micro-fade: the step at the join must shrink
  (a step is the click an amateur edit is heard by);
- a clean break vs a carried join between parts: the outgoing tone must
  keep sounding past the cut for CARRY_S (L cut), or the incoming tone
  must start CARRY_S early (J cut) -- and nowhere else;
- a shot filmed to the very end of its file: no footage to carry, so the
  join falls back to a cut and says so;
- music: at its gain, ducked where asked, and the export's sound is the
  preview's sound.

    python tests/test_audiomix.py
"""

from __future__ import annotations

import copy
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TMP = Path(tempfile.mkdtemp(prefix="vibecut-mix-"))
os.environ["VIBECUT_CACHE"] = str(TMP / "cache")
os.environ["VIBECUT_EXPORTS"] = str(TMP / "out")

from web.backend import audiomix as am  # noqa: E402
from web.backend import board as bd  # noqa: E402
from web.backend import export  # noqa: E402

SR = am.SR
failures: list[str] = []


def check(name: str, cond: bool, got: str = "") -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{': ' + got if got else ''}")
    if not cond:
        failures.append(name)


def ff(*args: str) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


def tone_clip(path: Path, freq: int, dur: float = 6.0) -> None:
    ff("-f", "lavfi", "-i", f"color=c=gray:s=320x180:r=30:d={dur}", "-f", "lavfi",
       "-i", f"sine=f={freq}:d={dur}:sample_rate=48000", "-c:v", "libx264", "-pix_fmt", "yuv420p",
       "-c:a", "pcm_s16le", "-shortest", str(path))


def energy(x: np.ndarray, freq: float, a: float, b: float) -> float:
    """Amplitude of one tone in [a, b) seconds (mono), by projection."""
    s = x[int(a * SR):int(b * SR)]
    if len(s) == 0:
        return 0.0
    t = np.arange(len(s)) / SR
    c, d = np.cos(2 * np.pi * freq * t), np.sin(2 * np.pi * freq * t)
    return float(2 * np.hypot((s * c).mean(), (s * d).mean()))


def items(a_range=(1.0, 3.0), b_range=(1.0, 3.0), same_part=False) -> list[dict]:
    la, lb = a_range[1] - a_range[0], b_range[1] - b_range[0]
    return [
        {"key": "A:0", "kind": "shot", "clip_id": "A", "src_start": a_range[0], "src_end": a_range[1],
         "seq_start": 0.0, "seq_end": la, "beat_id": "t1"},
        {"key": "B:0", "kind": "shot", "clip_id": "B", "src_start": b_range[0], "src_end": b_range[1],
         "seq_start": la, "seq_end": la + lb, "beat_id": "t1" if same_part else "t2"},
    ]


def main() -> int:
    A, B, M = TMP / "a.mov", TMP / "b.mov", TMP / "music.wav"
    tone_clip(A, 440)
    tone_clip(B, 880)
    ff("-f", "lavfi", "-i", "sine=f=220:d=20:sample_rate=48000", "-ac", "2", str(M))
    clips = {"A": {"id": "A", "path": str(A), "duration": 6.0, "width": 320, "height": 180},
             "B": {"id": "B", "path": str(B), "duration": 6.0, "width": 320, "height": 180}}

    print("length")
    it = items()
    buf, _ = am.render(it, clips)
    check("the mix is exactly the timeline's length", len(buf) == int(round(4.0 * SR)), f"{len(buf) / SR:.4f}s")

    print("the join itself (inside a part: a clean cut)")
    it = items(same_part=True)
    cut_at = int(2.0 * SR)
    micro, _ = am.render(it, clips)
    saved = am.MICRO_S
    am.MICRO_S = 0.0
    hard, _ = am.render(it, clips)
    am.MICRO_S = saved

    def step(x):
        w = x[cut_at - 48:cut_at + 48, 0]
        return float(np.abs(np.diff(w)).max())

    check("a hard join steps; the micro-fade takes the step out", step(micro) < 0.35 * step(hard),
          f"max sample jump {step(hard):.3f} -> {step(micro):.3f}")
    body = energy(micro[:, 0], 440, 0.2, 1.8) / energy(hard[:, 0], 440, 0.2, 1.8)
    check("…and leaves the rest of the shot alone", abs(body - 1) < 0.01, f"{body:.3f}")
    check("inside a part the default is a clean cut: no 440 after it",
          energy(micro[:, 0], 440, 2.05, 2.4) < 0.01, f"{energy(micro[:, 0], 440, 2.05, 2.4):.3f}")

    print("between parts: the sound carries (L cut), and only by CARRY_S")
    it = items()
    joins = am.joins_for(it)
    check("default between parts is carry_out", joins[0] == {"sound": "carry_out", "set": False}, str(joins))
    carried, notes = am.render(it, clips, joins=joins)
    clean, _ = am.render(it, clips, joins=am.joins_for(it, {"A:0": {"sound": "cut"}}))
    mono_c, mono_k = carried[:, 0], clean[:, 0]
    full = energy(mono_k, 440, 0.2, 1.8)     # the tone's own level
    after = energy(mono_c, 440, 2.05, 2.05 + am.CARRY_S * 0.6) / full
    check("the outgoing tone is still heard after the cut", after > 0.4, f"{after:.2f} of its level")
    check("…not with a clean break", energy(mono_k, 440, 2.05, 2.3) < 0.01, f"{energy(mono_k, 440, 2.05, 2.3):.3f}")
    gone = energy(mono_c, 440, 2.0 + am.CARRY_S + 0.02, 3.5)
    check("…and is gone once the carry is over", gone < 0.01, f"{gone:.3f}")
    # measured carry length: last 10 ms window where 440 is above a trace
    t = 2.0
    while energy(mono_c, 440, t, t + 0.01) > 0.05 * full and t < 3.5:
        t += 0.01
    check("the carry lasts CARRY_S (the magnitude built in)", abs((t - 2.0) - am.CARRY_S) < 0.06,
          f"{t - 2.0:.2f}s vs {am.CARRY_S}s")
    same = energy(mono_c, 440, 0.2, 1.8) / energy(mono_k, 440, 0.2, 1.8)
    check("before the cut the two mixes are the same", abs(same - 1) < 0.01, f"{same:.3f}")
    check("no picture changes: the mix length is untouched", len(carried) == len(clean))

    j, _ = am.render(it, clips, joins=am.joins_for(it, {"A:0": {"sound": "carry_in"}}))
    early = energy(j[:, 0], 880, 2.0 - am.CARRY_S * 0.6, 1.95) / full
    check("a J cut: the next tone starts before its picture", early > 0.4, f"{early:.2f} of its level")
    check("…which a clean break doesn't do", energy(mono_k, 880, 1.6, 1.95) < 0.01)

    print("no footage past the cut")
    it = items(a_range=(4.0, 6.0))    # A runs to the end of its file
    buf, notes = am.render(it, clips)
    check("the carry falls back to a cut", energy(buf[:, 0], 440, 2.05, 2.3) < 0.01)
    check("…and says so", any("became a cut" in n for n in notes), str(notes))
    check("…and the join reports it can't carry", not am.fits(it, clips, 0, "carry_out") and am.fits(items(), clips, 0, "carry_out"))

    print("music")
    it = items()
    base, _ = am.render(it, clips, joins=am.joins_for(it, {"A:0": {"sound": "cut"}}))
    music = {"path": str(M), "in": 0.0, "gain": am.MUSIC_GAIN, "fade_out": 0.0, "duck": [(0.5, 1.5, 0.2)]}
    mixed, _ = am.render(it, clips, joins=am.joins_for(it, {"A:0": {"sound": "cut"}}), music=music)
    bed = (mixed - base)[:, 0]
    lvl = energy(bed, 220, 2.2, 3.8)
    ref = energy(am.decode(str(M))[:, 0], 220, 2.2, 3.8)
    check("the bed sits at MUSIC_GAIN", abs(lvl / ref - am.MUSIC_GAIN) < 0.02, f"{lvl / ref:.3f} (want {am.MUSIC_GAIN})")
    ducked = energy(bed, 220, 0.8, 1.2) / ref
    check("…ducked where asked", abs(ducked - am.MUSIC_GAIN * 0.2) < 0.02, f"{ducked:.3f}")
    ts = (Path(__file__).resolve().parent.parent / "web/frontend/src/transport.ts").read_text()
    m = re.search(r"export const MUSIC_GAIN = ([0-9.]+)", ts)
    check("the preview's fallback music level is the export's", bool(m) and float(m.group(1)) == am.MUSIC_GAIN,
          m.group(1) if m else "not found")

    print("preview == export")
    it = items()
    sp = am.spec(it, clips, None, None, export.music_spec(str(M), None))
    prev = am.preview_file(sp, clips)
    import wave
    with wave.open(str(prev)) as w:
        pv = np.frombuffer(w.readframes(w.getnframes()), "<i2").reshape(-1, 2)[:, 0] / 32767
    job = export.create(it, clips, "mix test", str(M))
    export.start(job, [])
    while job.stage not in ("done", "error"):
        time.sleep(0.2)
    check("export finishes", job.stage == "done", job.error or job.stage)
    if job.stage == "done":
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", job.path, "-vn", "-f", "f32le", "-ac", "2", "-ar",
                              str(SR), "-"], capture_output=True, check=True).stdout
        ex = np.frombuffer(raw, np.float32).reshape(-1, 2)[:, 0]
        # Pure tones make sample alignment ambiguous; compare what is heard
        # instead -- each tone's level in every quarter second.
        prof = lambda x: np.array([[energy(x, f, a, a + 0.25) for f in (440, 880, 220)]  # noqa: E731
                                   for a in np.arange(0, 3.75, 0.25)])
        diff = float(np.abs(prof(ex) - prof(pv)).max())
        check("the exported sound is the preview's sound", diff < 0.005,
              f"largest level difference {diff:.4f} (tone level {energy(pv, 440, 0.2, 1.8):.3f})")
        carried = energy(ex, 440, 2.25, 2.5) / energy(ex, 440, 0.2, 1.8)
        check("…carry included", carried > 0.2, f"{carried:.2f} of its level after the cut")

    print("the join op")
    s = bd.Session()
    cat = bd.Catalog({}, {})
    snap = {"option": "t", "name": "n", "structure": "", "beats": [
        {"id": "t1", "title": "Morning", "detail": "", "shots": [{"id": "A:0", "start": 1.0, "end": 3.0}]},
        {"id": "t2", "title": "Market", "detail": "", "shots": [{"id": "B:0", "start": 1.0, "end": 3.0}]}]}
    mk = lambda d: None  # noqa: E731
    s.add({"kind": "direct", "text": "use", "ops": [{"op": "choose_option", "option": "t", "snapshot": snap}]}, cat, mk)
    t = s.add({"kind": "chat", "text": "clean break into the market",
               "ops": [{"op": "set_join", "shot": "A:0", "sound": "cut"}]}, cat, mk)
    check("set_join records the join on the board", s.board.get("joins") == {"A:0": {"sound": "cut"}}, str(s.board.get("joins")))
    check("…and the diff says so in words", t.lines and t.lines[0]["kind"] == "sound", str(t.lines))
    before = copy.deepcopy(s.board)
    bad = s.add({"kind": "direct", "text": "x", "ops": [{"op": "set_join", "shot": "B:0", "sound": "cut"}]}, cat, mk)
    check("the last shot has no join after it", bool(bad.skipped) and s.board == before, str(bad.skipped))
    s.toggle(t.id, cat, mk)
    check("undo takes the join back to automatic", not s.board.get("joins"), str(s.board.get("joins")))
    s.toggle(t.id, cat, mk)
    s.add({"kind": "direct", "text": "auto", "ops": [{"op": "set_join", "shot": "A:0", "sound": "default"}]}, cat, mk)
    check("'default' clears it", s.board.get("joins") == {}, str(s.board.get("joins")))
    s.add({"kind": "direct", "text": "music", "ops": [{"op": "set_music", "track": "x1", "in": 12.5, "gain": 0.85,
                                                        "bogus": 1}]}, cat, mk)
    check("set_music keeps only what the mix knows", s.board["music"] == {"track": "x1", "in": 12.5, "gain": 0.85},
          str(s.board["music"]))

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

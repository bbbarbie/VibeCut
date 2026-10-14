"""Extract audio: a shot's sound comes off onto its own strip.

Two clips, each a pure tone (440 Hz / 880 Hz), so which sound plays where
can be measured exactly. The same edit is mixed with one thing changed at
a time, and each change must move only what it says:

- extracted, untouched: the mix is the same as before (taking the sound off
  doesn't change what you hear until you change the strip);
- the strip moved later by 1 s: the 440 tone starts 1 s later, and the shot
  itself plays silent where it used to sound;
- volume 50%: the tone at half its level; muted: gone; deleted: gone, and
  the shot stays silent (as in every editor) until undone;
- the other shot is untouched throughout;
- a cut through a silenced shot doesn't bring its sound back;
- export hears what the preview hears (same strips through render).

    python tests/test_extract_audio.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TMP = Path(tempfile.mkdtemp(prefix="vibecut-extract-"))
os.environ["VIBECUT_CACHE"] = str(TMP / "cache")

from web.backend import audiomix as am  # noqa: E402
from web.backend import board as bd  # noqa: E402
from web.backend import timeline  # noqa: E402

SR = am.SR
failures: list[str] = []


def check(name: str, cond: bool, got: str = "") -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{': ' + got if got else ''}")
    if not cond:
        failures.append(name)


def tone_clip(path: Path, freq: int, dur: float = 6.0) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=gray:s=160x90:r=30:d={dur}",
                    "-f", "lavfi", "-i", f"sine=f={freq}:d={dur}:sample_rate=48000", "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", "-c:a", "pcm_s16le", "-shortest", str(path)], check=True)


def energy(x: np.ndarray, freq: float, a: float, b: float) -> float:
    s = x[int(a * SR):int(b * SR), 0]
    if len(s) == 0:
        return 0.0
    t = np.arange(len(s)) / SR
    return float(2 * np.hypot((s * np.cos(2 * np.pi * freq * t)).mean(), (s * np.sin(2 * np.pi * freq * t)).mean()))


def shot(cid: str) -> dict:
    return {"id": cid, "name": f"{cid}.MOV", "capture_time": None, "gps": None, "path": "", "duration": 6.0,
            "shots": [{"index": 0, "start": 0.0, "end": 6.0, "thumb": "shot000.jpg", "best_t": 3.0,
                       "quality": 0.6, "aesthetic": None, "utility": False, "labels": [["x", 0.8]],
                       "faces": 0, "face_area": 0.0, "embedding": [1.0] + [0.0] * 7}]}


def main() -> int:
    A, B = TMP / "a.mov", TMP / "b.mov"
    tone_clip(A, 440)
    tone_clip(B, 880)
    clips = {"A": {"id": "A", "path": str(A), "duration": 6.0}, "B": {"id": "B", "path": str(B), "duration": 6.0}}
    cat = bd.Catalog.from_clips([shot("A"), shot("B")])
    option = {"key": "o", "name": "Two", "summary": "", "beats": [{"title": "All", "detail": "", "shots": [
        {"id": "A:0", "start": 1.0, "end": 3.0}, {"id": "B:0", "start": 1.0, "end": 4.0}]}]}
    mk = lambda d: {"options": [option]}  # noqa: E731
    s = bd.Session()
    s.add({"kind": "chat", "text": "go", "ops": [], "direction": {"text": "go"}}, cat, mk)
    s.add({"kind": "direct", "text": "pick", "ops": [{"op": "choose_option", "option": "o"}]}, cat, mk)

    def mix():
        items = timeline.layout(s.board)
        buf, _ = am.render(items, clips, sound=am.strips_of(s.board))
        return buf

    before = mix()
    full = energy(before, 440, 0.2, 1.8)

    print("taking the sound off")
    t = s.add({"kind": "direct", "text": "extract", "ops": [{"op": "extract_audio", "shot": "A:0"}]}, cat, mk)
    strip = s.board["sound"]["strips"][0]
    check("one strip, where the shot is, its length", (strip["at"], strip["start"], strip["end"]) == (0.0, 1.0, 3.0),
          str(strip))
    same = mix()
    check("untouched, it sounds exactly as before", float(np.abs(same - before).max()) < 0.02,
          f"max diff {float(np.abs(same - before).max()):.4f}")
    check("the turn says what happened", any("own strip" in x["text"] for x in t.lines), str(t.lines))
    again = s.add({"kind": "direct", "text": "again", "ops": [{"op": "extract_audio", "shot": "A:0"}]}, cat, mk)
    check("twice is refused, not doubled", bool(again.skipped) and len(s.board["sound"]["strips"]) == 1,
          str(again.skipped))
    s.toggle(again.id, cat, mk)

    sid = strip["id"]

    print("moved 1 s later")
    mv = s.add({"kind": "direct", "text": "move", "ops": [{"op": "edit_audio", "audio": sid, "at": 1.0}]}, cat, mk)
    x = mix()
    check("silent where it used to start", energy(x, 440, 0.1, 0.9) < 0.01, f"{energy(x, 440, 0.1, 0.9):.3f}")
    late = energy(x, 440, 1.1, 2.9) / full
    check("…and sounding 1 s later at full level", abs(late - 1) < 0.03, f"{late:.3f}")
    check("…running over the next shot by 1 s", energy(x, 440, 2.1, 2.9) / full > 0.97,
          f"{energy(x, 440, 2.1, 2.9) / full:.3f}")
    check("the other shot is untouched", abs(energy(x, 880, 2.2, 4.8) - energy(before, 880, 2.2, 4.8)) < 0.01)
    s.toggle(mv.id, cat, mk)

    print("volume, mute, delete")
    v = s.add({"kind": "direct", "text": "vol", "ops": [{"op": "edit_audio", "audio": sid, "gain": 0.5}]}, cat, mk)
    half = energy(mix(), 440, 0.2, 1.8) / full
    check("50% is half the level (the magnitude built in)", abs(half - 0.5) < 0.02, f"{half:.3f}")
    s.add({"kind": "direct", "text": "loud", "ops": [{"op": "edit_audio", "audio": sid, "gain": 9}]}, cat, mk)
    check("louder stops at 200%", s.board["sound"]["strips"][0]["gain"] == bd.AUDIO_GAIN_MAX,
          str(s.board["sound"]["strips"][0]["gain"]))
    m = s.add({"kind": "direct", "text": "mute", "ops": [{"op": "edit_audio", "audio": sid, "mute": True}]}, cat, mk)
    check("muted is silent", energy(mix(), 440, 0.2, 1.8) < 0.01)
    check("…and the 880 shot still plays", energy(mix(), 880, 2.2, 4.8) > 0.9 * energy(before, 880, 2.2, 4.8))
    s.toggle(m.id, cat, mk)
    d = s.add({"kind": "direct", "text": "del", "ops": [{"op": "drop_audio", "audio": sid}]}, cat, mk)
    check("deleted: gone, the shot stays silent", energy(mix(), 440, 0.2, 1.8) < 0.01 and not s.board["sound"]["strips"])
    s.toggle(d.id, cat, mk)
    s.toggle(v.id, cat, mk)
    check("undo brings the strip back at its old level", s.board["sound"]["strips"][0]["gain"] != 0.5
          and len(s.board["sound"]["strips"]) == 1)
    s.toggle(t.id, cat, mk)
    check("undoing the extract puts the sound back under the shot", not (s.board.get("sound") or {}).get("off")
          and abs(energy(mix(), 440, 0.2, 1.8) / full - 1) < 0.02)
    s.toggle(t.id, cat, mk)

    print("a cut through a silenced shot")
    s.add({"kind": "direct", "text": "cut", "ops": [{"op": "split", "shot": "A:0", "at": 2.0}]}, cat, mk)
    s.add({"kind": "direct", "text": "mute", "ops": [{"op": "edit_audio", "audio": sid, "mute": True}]}, cat, mk)
    check("both pieces stay silent", energy(mix(), 440, 0.1, 1.9) < 0.01, f"{energy(mix(), 440, 0.1, 1.9):.3f}")
    lane = timeline.build(s.board, {}, None)["audio"]
    check("the timeline knows both pieces are silent and where the strip is",
          len(lane["off"]) == 2 and lane["strips"][0]["at"] == 0.0 and lane["strips"][0]["mute"], str(lane))

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

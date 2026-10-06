"""Music is not talking: a voice reading decides which loud seconds are words.

Two fixtures that differ in one respect -- the same loud audio (level-based
speech 0.8 every second), heard as a voice in one and as music in the other:
- the voice clip stays a talking clip and keeps everything usable;
- the music clip stops being one and is trimmed to a few seconds;
- a clip that talks for its first half keeps speech there only;
- voiced intervals where no voice is heard are dropped (cuts may land there).
Then, on macOS only, the real classifier: a spoken sentence (say) and a
synthesised tune, each put in a video, must read as voice and music.

    python tests/test_voice.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix="vibecut-voice-"))
os.environ["VIBECUT_CACHE"] = str(TMP / "cache")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cutgrammar import reject, trim  # noqa: E402
from cutgrammar.signals import VOICE_HI, ClipSignals, with_voice  # noqa: E402
from web.backend import indexer, sound  # noqa: E402

N = 30


def _loud() -> ClipSignals:
    q = [0.5] * N
    for i in range(12, 17):
        q[i] = 0.95
    return ClipSignals(duration=float(N), quality=q, sharpness=[0.8] * N, luma=[120.0] * N,
                       contrast=[0.8] * N, motion=[2.0] * N, subject=[0.8] * N, edge=[0.0] * N,
                       speech=[0.8] * N, voiced=[[i + 0.1, i + 0.9] for i in range(N)], thumb=[0.0] * 144)


def main() -> int:
    failures = []

    def check(name: str, cond: bool, got: str = "") -> None:
        print(f"  {'PASS' if cond else 'FAIL'}  {name}{': ' + got if got else ''}")
        if not cond:
            failures.append(name)

    raw = _loud()
    check("level alone: loud audio reads as talking", trim.is_talking(raw))
    voice = with_voice(raw, [0.9] * N)
    music = with_voice(raw, [0.03] * N)
    check("heard as a voice: still talking", trim.is_talking(voice))
    check("heard as music: not talking", not trim.is_talking(music))
    wv, wm = trim.best_window(voice), trim.best_window(music)
    check("the voice clip keeps everything usable", wv.end - wv.start >= 20, f"{wv.start}–{wv.end}")
    check("the music clip is trimmed to a few seconds", wm.end - wm.start <= 5, f"{wm.start}–{wm.end}")
    check("around its best seconds", 11 <= wm.start and wm.end <= 18, f"{wm.start}–{wm.end}")

    half = with_voice(raw, [0.9] * 15 + [0.02] * 15)
    check("talking only in the first half keeps speech there only",
          min(half.speech[:15]) > 0.7 and max(half.speech[15:]) == 0.0)
    check("voiced intervals without a voice are dropped",
          all(w[0] < 15 for w in half.voiced) and len(half.voiced) == 15, str(len(half.voiced)))
    check("no reading: nothing changes", with_voice(raw, []).speech == raw.speech)

    # per-second from half-overlapping ~1 s windows
    ws = [{"t": i * 0.5, "d": 1.0, "voice": 1.0 if i < 6 else 0.0} for i in range(12)]
    ps = sound.per_second(ws, 6, "voice")
    check("windows become one value per second", ps[:2] == [1.0, 1.0] and ps[-1] == 0.0, str(ps))

    # a cached reading is applied when a clip is loaded, once
    rec = {"id": "voice0000001", "signals": raw.to_json()}
    d = indexer.clip_dir(rec["id"])
    d.mkdir(parents=True, exist_ok=True)
    (d / "sound.json").write_text(json.dumps({"backend": "soundanalysis", "voice": [0.03] * N, "music": [0.9] * N}))
    sound.attach(rec)
    sound.attach(rec)
    check("a cached reading gates the loaded clip",
          not trim.is_talking(ClipSignals.from_json(rec["signals"])) and rec["sound"]["music"][0] == 0.9)

    # Every loud clip used to count as talking, and talking clips are never
    # thrown out -- which hid how strict the shake guess is. Handheld walking
    # footage now gets a warning at the gate, not a rejection.
    walk = with_voice(ClipSignals.from_json({**raw.to_json(), "motion": [14.0] * N}), [0.02] * N)
    v = reject.judge(walk)
    check("a handheld clip isn't thrown out on a shake guess", not v.rejected and v.flags
          and v.flags[0]["code"] == "shaky", f"{v.code or 'kept'}, flags {[f['code'] for f in v.flags]}")

    # -- the real classifier, macOS only --------------------------------------
    binary = sound.ensure_built()
    if binary is None:
        print(f"  SKIP  real classifier: {sound._failed}")
    else:
        aiff, talk_mov, tune_mov = TMP / "vo.aiff", TMP / "talk.mov", TMP / "tune.mov"
        subprocess.run(["say", "-o", str(aiff), "Hi everyone, welcome back to my channel. Today we are going "
                        "to the market, and then I will show you what I bought for dinner tonight."], check=True)
        gray = ["-f", "lavfi", "-i", "color=c=gray:s=320x180:r=30"]
        subprocess.run(["ffmpeg", "-v", "error", "-y", *gray, "-i", str(aiff), "-shortest", "-c:v", "libx264",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", str(talk_mov)], check=True)
        # a tune: a chord progression with a beat, loud the whole way
        tune = ("aevalsrc='0.25*sin(2*PI*(220+110*floor(mod(t,4)))*t)+0.2*sin(2*PI*(330+110*floor(mod(t,4)))*t)"
                "+0.2*sin(2*PI*(440+55*floor(mod(t,4)))*t)+0.3*sin(2*PI*60*t)*exp(-20*mod(t,0.5))':s=44100:d=8")
        subprocess.run(["ffmpeg", "-v", "error", "-y", *gray, "-f", "lavfi", "-i", tune, "-shortest",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(tune_mov)], check=True)
        heard = {}
        for name, mov in (("talk", talk_mov), ("tune", tune_mov)):
            ws = sound._classify(binary, str(mov)) or []
            heard[name] = (sum(w["voice"] for w in ws) / max(len(ws), 1), sum(w["music"] for w in ws) / max(len(ws), 1))
            print(f"        {name}: voice {heard[name][0]:.2f}, music {heard[name][1]:.2f} over {len(ws)} windows")
        check("a spoken sentence reads as a voice", heard["talk"][0] > 0.5, f"{heard['talk'][0]:.2f}")
        check("a tune doesn't", heard["tune"][0] < VOICE_HI, f"{heard['tune'][0]:.2f}")

    print(f"\n{'all passed' if not failures else f'{len(failures)} failed'}")
    return 1 if failures else 0


def test_voice() -> None:
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())

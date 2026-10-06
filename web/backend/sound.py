"""Bridge to the on-device sound classifier (sound/vibesound.swift).

Whether a loud second is a voice or a song is what decides how much of a
clip the rough cut keeps: a clip someone talks in keeps everything usable,
a clip with music under it gets trimmed to its best few seconds. The
level-based mask in features.speech_mask can't tell them apart; Apple's
built-in sound classifier can.

macOS only, compiled once into the cache like the Vision helper. The clip's
audio track is extracted to a temporary 16 kHz mono WAV (ffmpeg, audio only:
no picture is decoded) and classified on this Mac; nothing leaves it. The
per-second result is cached as sound.json next to the clip's index. Where
the helper can't run, nothing changes: the level-based mask is used, as
before.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from cutgrammar.signals import ClipSignals, with_voice

SRC = Path(__file__).parent / "sound" / "vibesound.swift"
WORKERS = 4
_lock = threading.Lock()
_binary: Path | None = None
_failed: str | None = None


def _target() -> Path:
    from .indexer import CACHE
    h = hashlib.sha1(SRC.read_bytes()).hexdigest()[:10]
    return CACHE / "bin" / f"vibesound-{h}"


def ensure_built() -> Path | None:
    global _binary, _failed
    with _lock:
        if _binary or _failed:
            return _binary
        if sys.platform != "darwin" or not shutil.which("swiftc") or not shutil.which("ffmpeg"):
            _failed = "not on macOS with swiftc and ffmpeg"
            return None
        target = _target()
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_suffix(".tmp")
            p = subprocess.run(["swiftc", "-O", str(SRC), "-o", str(tmp)], capture_output=True, text=True)
            if p.returncode != 0:
                _failed = p.stderr[-400:]
                print(f"[sound] build failed, keeping the level-based voice mask:\n{_failed}")
                return None
            os.replace(tmp, target)
        _binary = target
        return _binary


def status() -> str:
    return "ready" if _binary else ("unavailable" if _failed else "building")


def per_second(windows: list[dict], n: int, key: str) -> list[float]:
    """Windows of ~1 s overlapping by half -> one value per second: the mean
    of the windows centred inside it (the nearest one if none is)."""
    out = []
    for k in range(n):
        inside = [w[key] for w in windows if k <= w["t"] + w["d"] / 2 < k + 1]
        if not inside and windows:
            inside = [min(windows, key=lambda w: abs(w["t"] + w["d"] / 2 - (k + 0.5)))[key]]
        out.append(round(sum(inside) / len(inside), 3) if inside else 0.0)
    return out


def _classify(binary: Path, path: str) -> list[dict] | None:
    with tempfile.TemporaryDirectory() as d:
        wav = os.path.join(d, "a.wav")
        p = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", path, "-vn", "-ac", "1", "-ar", "16000", wav],
                           capture_output=True)
        if p.returncode or not os.path.exists(wav):
            return None
        p = subprocess.run([str(binary), wav], capture_output=True, text=True)
    for line in p.stdout.splitlines():
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        return None if r.get("error") and not r.get("windows") else r.get("windows", [])
    return None


def add_sound(recs: list[dict]) -> str:
    """Attach per-second voice / music / singing / laughter to each clip and
    gate its speech signal by the voice. Cached; returns the backend used."""
    from .indexer import clip_dir
    need = [r for r in recs if not (clip_dir(r["id"]) / "sound.json").exists() and r.get("path")]
    if need:
        binary = ensure_built()
        if binary is not None:
            def one(r: dict) -> None:
                if not os.path.isfile(r["path"]):
                    return
                ws = _classify(binary, r["path"])
                if ws is None:
                    return
                n = len(r["signals"]["quality"])
                s = {k: per_second(ws, n, k) for k in ("voice", "music", "singing", "laughter")} if ws else {}
                (clip_dir(r["id"]) / "sound.json").write_text(json.dumps({"backend": "soundanalysis", **s}))
            with ThreadPoolExecutor(max_workers=WORKERS) as ex:
                list(ex.map(one, need))
    used = "levels"
    for r in recs:
        if attach(r):
            used = "soundanalysis"
    return used


def attach(rec: dict) -> bool:
    """Gate a loaded clip's speech by its cached voice reading, in memory only."""
    from .indexer import clip_dir
    try:
        s = json.loads((clip_dir(rec["id"]) / "sound.json").read_text())
    except (OSError, ValueError):
        return False
    if rec.get("sound") is not None or not s.get("voice"):
        return bool(rec.get("sound"))
    rec["sound"] = s
    rec["signals"] = with_voice(ClipSignals.from_json(rec["signals"]), s["voice"]).to_json()
    return True

"""Decode a video into the small arrays every later stage works on.

Design rule: touch the pixels exactly once. Everything downstream
(shot detection, motion, grammar) runs on the tiny arrays produced here,
never on the original file. This is the "index once" principle from the
tech plan, at the scale of a single clip.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field

import numpy as np

# Frames are decoded at this size. Big enough for colour histograms and
# frame-difference motion, small enough that a 10-minute video fits in RAM.
FRAME_W, FRAME_H = 48, 27
AUDIO_SR = 16_000


@dataclass
class Media:
    path: str
    fps: float
    duration: float
    width: int
    height: int
    creation_time: str | None
    location: str | None
    # (n_frames, FRAME_H, FRAME_W, 3) uint8
    frames: np.ndarray
    # mono float32 at AUDIO_SR, empty if the file has no audio track
    audio: np.ndarray
    meta: dict = field(default_factory=dict)

    @property
    def n_frames(self) -> int:
        return len(self.frames)

    def t(self, frame_idx: int) -> float:
        """Frame index -> seconds."""
        return frame_idx / self.fps

    @property
    def has_audio(self) -> bool:
        return self.audio.size > 0


def _run(cmd: list[str]) -> bytes:
    p = subprocess.run(cmd, capture_output=True)
    if p.returncode != 0:
        raise RuntimeError(f"{cmd[0]} failed: {p.stderr.decode()[:500]}")
    return p.stdout


def probe(path: str) -> dict:
    """ffprobe metadata. Free information -- extract it before any ML."""
    raw = _run([
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", path,
    ])
    return json.loads(raw)


def _parse_fps(stream: dict) -> float:
    for key in ("avg_frame_rate", "r_frame_rate"):
        val = stream.get(key, "0/0")
        try:
            num, den = val.split("/")
            if float(den) > 0 and float(num) > 0:
                return float(num) / float(den)
        except (ValueError, ZeroDivisionError):
            continue
    return 30.0


def load(path: str, verbose: bool = False) -> Media:
    info = probe(path)

    vstreams = [s for s in info["streams"] if s.get("codec_type") == "video"]
    if not vstreams:
        raise ValueError(f"no video stream in {path}")
    v = vstreams[0]
    astreams = [s for s in info["streams"] if s.get("codec_type") == "audio"]

    fps = _parse_fps(v)
    duration = float(info["format"].get("duration", 0.0))
    tags = {**info["format"].get("tags", {}), **v.get("tags", {})}

    if verbose:
        print(f"  decoding {path} ({duration:.1f}s @ {fps:.2f}fps)")

    # --- video: native fps, tiny resolution -------------------------------
    raw = _run([
        "ffmpeg", "-v", "error", "-i", path,
        "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-vf", f"scale={FRAME_W}:{FRAME_H}",
        "-",
    ])
    stride = FRAME_W * FRAME_H * 3
    n = len(raw) // stride
    frames = np.frombuffer(raw[: n * stride], dtype=np.uint8)
    frames = frames.reshape(n, FRAME_H, FRAME_W, 3)

    # --- audio: mono 16k float ---------------------------------------------
    audio = np.zeros(0, dtype=np.float32)
    if astreams:
        araw = _run([
            "ffmpeg", "-v", "error", "-i", path,
            "-f", "f32le", "-ac", "1", "-ar", str(AUDIO_SR), "-",
        ])
        audio = np.frombuffer(araw, dtype=np.float32).copy()

    return Media(
        path=path,
        fps=fps,
        duration=duration or (n / fps),
        width=int(v.get("width", 0)),
        height=int(v.get("height", 0)),
        creation_time=tags.get("creation_time"),
        location=tags.get("location") or tags.get("com.apple.quicktime.location.ISO6709"),
        frames=frames,
        audio=audio,
        meta={"tags": tags, "codec": v.get("codec_name")},
    )


def loudness_lufs(path: str) -> float | None:
    """Integrated loudness via ffmpeg's EBU R128 meter.

    YouTube normalises to about -14 LUFS; anything far from that gets
    turned up or down on playback, which is where 'the audio feels off'
    usually comes from.
    """
    p = subprocess.run(
        ["ffmpeg", "-v", "info", "-i", path, "-af", "ebur128", "-f", "null", "-"],
        capture_output=True,
    )
    err = p.stderr.decode(errors="ignore")
    marker = "Integrated loudness:"
    if marker not in err:
        return None
    tail = err.split(marker)[-1]
    for line in tail.splitlines():
        if "LUFS" in line:
            try:
                return float(line.split()[-2])
            except (ValueError, IndexError):
                return None
    return None

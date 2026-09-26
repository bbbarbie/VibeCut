"""Export: the working storyboard, with its words on screen, as one video file.

Until now nothing was ever re-encoded -- the timeline played spans of the
original files. Export is the one place pixels are rendered, and it does it
in three steps so each stays simple and bounded:

1. **Shots.** Every span on the timeline becomes its own short file at the
   output size (scaled to fit, padded, 30 fps, audio as PCM so joining can't
   drift -- AAC's priming samples add up to an audible slip over dozens of
   joins). A gap is black and silent for its length. Lengths are counted in
   frames from the timeline's own layout, so a 60-shot edit ends on the same
   frame the timeline says it does.
2. **Join.** Stream copy, no re-encode.
3. **Finish.** Words on screen and music on top, encoded once.

Words on screen are drawn by the browser, not here: the same Canvas code that
draws the preview renders them to transparent PNG frames (only the frames
that change are sent -- a title holding still is one frame with a duration).
This ffmpeg build has no text renderer, and drawing them twice in two
languages would guarantee the export and the preview disagree. The frames
arrive as a schedule -- (frame, start, end) -- and become one ffconcat input
overlaid on the joined edit.

A borrowed style (restyle.py) is rendered here too, and only here: one
LUT over every shot, cinematic bars, and transitions. Dips, flashes and
fades happen inside a shot's own frames; a dissolve needs frames beyond
each cut (handles), so the two shots are rendered longer and overlapped,
which keeps every shot starting on the frame the timeline says. Where a
shot wasn't filmed long enough for handles, the dissolve falls back to a
cut and the export says how many did.

The original footage is only read. Output goes to ~/Movies/VibeCut.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from cutgrammar import media

from . import indexer
from . import timeline as tlm

FPS = tlm.FPS
OUT_DIR = Path(os.environ.get("VIBECUT_EXPORTS", str(Path.home() / "Movies" / "VibeCut")))
WORK = indexer.CACHE / "exports"
MUSIC_GAIN = 0.35   # music under the original sound, not over it
MAX_FRAMES = 20000  # overlay PNGs per export -- far above what titles need

_probe_cache: dict[str, dict] = {}


def _display(path: str) -> dict:
    """Display size (rotation applied, as ffmpeg's autorotate will) and audio."""
    if path not in _probe_cache:
        info = media.probe(path)
        v = next(s for s in info["streams"] if s.get("codec_type") == "video")
        w, h = int(v.get("width", 0)), int(v.get("height", 0))
        if media._rotation(v) in (90, 270):
            w, h = h, w
        _probe_cache[path] = {"w": w, "h": h,
                              "audio": any(s.get("codec_type") == "audio" for s in info["streams"])}
    return _probe_cache[path]


def frame_size(items: list[dict], clips: dict[str, dict]) -> dict:
    """1080p in the orientation most of the edit was filmed in."""
    portrait = landscape = 0.0
    for it in items:
        c = clips.get(it.get("clip_id") or "")
        if not c:
            continue
        w, h = c.get("width", 0), c.get("height", 0)
        try:
            d = _display(c["path"])
            w, h = d["w"], d["h"]
        except Exception:  # noqa: BLE001 -- a file gone missing shouldn't break the session
            pass
        if h > w:
            portrait += it["seq_end"] - it["seq_start"]
        else:
            landscape += it["seq_end"] - it["seq_start"]
    return {"w": 1080, "h": 1920} if portrait > landscape else {"w": 1920, "h": 1080}


def spans(items: list[dict]) -> list[dict]:
    """Timeline items -> frame-exact spans (cumulative rounding, no drift)."""
    out = []
    for it in items:
        f0, f1 = round(it["seq_start"] * FPS), round(it["seq_end"] * FPS)
        if f1 > f0:
            out.append({**it, "frames": f1 - f0})
    return out


# --------------------------------------------------------------------------
# jobs
# --------------------------------------------------------------------------

@dataclass
class Job:
    id: str
    items: list[dict]
    clips: dict[str, dict]
    size: dict
    total: float
    name: str
    music: str | None = None
    overlays: int = 0
    stage: str = "waiting"          # waiting | shots | joining | finishing | done | error | cancelled
    done: int = 0
    of: int = 0
    progress: float = 0.0
    error: str | None = None
    path: str | None = None
    started: float = field(default_factory=time.time)
    elapsed: float = 0.0
    schedule: list[dict] = field(default_factory=list)
    cancel: bool = False
    style: dict | None = None
    notes: list[str] = field(default_factory=list)
    # How the music sits under the picture (remix.py): where in the track to
    # start, how loud, where to duck under the original sound, and any sound
    # effects to drop in. None keeps the plain mix.
    mix: dict | None = None

    @property
    def dir(self) -> Path:
        return WORK / self.id

    def public(self) -> dict:
        return {"id": self.id, "stage": self.stage, "done": self.done, "of": self.of,
                "progress": round(self.progress, 3), "error": self.error,
                "file": Path(self.path).name if self.path else None, "path": self.path,
                "size": self.size, "total": round(self.total, 2), "overlays": self.overlays,
                "music": bool(self.music), "elapsed": round(self.elapsed, 1),
                "style": (self.style or {}).get("name"), "notes": self.notes}


JOBS: dict[str, Job] = {}


def _safe_name(s: str) -> str:
    s = re.sub(r"[^\w\s\-–·&]+", "", s, flags=re.UNICODE).strip()
    return re.sub(r"\s+", " ", s)[:60] or "VibeCut edit"


def create(items: list[dict], clips: dict[str, dict], name: str, music: str | None,
           style: dict | None = None, mix: dict | None = None) -> Job:
    sp = spans(items)
    if not sp:
        raise ValueError("the timeline is empty — choose a story first")
    for it in sp:
        if it["kind"] == "shot":
            c = clips.get(it["clip_id"])
            if not c or not os.path.isfile(c["path"]):
                raise ValueError(f"can't find the file for shot {it['n']} on disk any more")
    look = (style or {}).get("look")
    if look and not os.path.isfile(look.get("lut", "")):
        raise ValueError("the borrowed look's file is gone — apply the style again")
    job = Job(id=uuid.uuid4().hex[:10], items=sp, clips=clips, size=frame_size(sp, clips),
              total=sum(s["frames"] for s in sp) / FPS, name=_safe_name(name), music=music, style=style,
              mix=mix)
    job.dir.mkdir(parents=True, exist_ok=True)
    (job.dir / "frames").mkdir(exist_ok=True)
    JOBS[job.id] = job
    return job


def save_frame(job: Job, n: int, data: bytes) -> None:
    if job.stage != "waiting":
        raise ValueError("this export has already started")
    if not (0 <= n < MAX_FRAMES):
        raise ValueError("frame number out of range")
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("overlay frames must be PNG")
    (job.dir / "frames" / f"{n:05d}.png").write_bytes(data)


def start(job: Job, schedule: list[dict]) -> None:
    """schedule: [{frame: n | None, start, end}] covering where words are on screen."""
    if job.stage != "waiting":
        raise ValueError("this export has already started")
    clean = []
    for s in schedule:
        n = s.get("frame")
        a, z = float(s["start"]), float(s["end"])
        if z <= a:
            continue
        if n is not None and not (job.dir / "frames" / f"{int(n):05d}.png").exists():
            raise ValueError(f"overlay frame {n} was never uploaded")
        clean.append({"frame": None if n is None else int(n), "start": a, "end": z})
    clean.sort(key=lambda s: s["start"])
    job.schedule = clean
    job.overlays = len({s["frame"] for s in clean if s["frame"] is not None})
    job.stage = "shots"
    threading.Thread(target=_run, args=(job,), daemon=True).start()


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------

def _encoder() -> list[str]:
    if sys.platform == "darwin" and _has_encoder("h264_videotoolbox"):
        return ["-c:v", "h264_videotoolbox", "-b:v", "{rate}", "-profile:v", "high"]
    return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "{crf}"]


_encoders: str | None = None


def _has_encoder(name: str) -> bool:
    global _encoders
    if _encoders is None:
        try:
            _encoders = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"],
                                       capture_output=True, text=True).stdout
        except OSError:
            _encoders = ""
    return name in _encoders


def _venc(intermediate: bool, size: dict) -> list[str]:
    big = size["w"] * size["h"] >= 1920 * 1080
    rate = ("24M" if big else "12M") if intermediate else ("12M" if big else "6M")
    crf = "14" if intermediate else "18"
    return [x.replace("{rate}", rate).replace("{crf}", crf) for x in _encoder()]


def _ff(args: list[str], job: Job, total_s: float | None = None, base: float = 0.0, weight: float = 0.0) -> None:
    """Run ffmpeg; with total_s, report progress into job.progress."""
    cmd = ["ffmpeg", "-hide_banner", "-v", "error", "-y", "-nostdin"]
    if total_s:
        cmd += ["-progress", "pipe:1"]
    p = subprocess.Popen(cmd + args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if total_s and p.stdout:
        for line in p.stdout:
            if job.cancel:
                p.kill()
                break
            if line.startswith("out_time_us="):
                try:
                    t = int(line.split("=")[1]) / 1e6
                    job.progress = base + weight * min(1.0, t / total_s)
                except ValueError:
                    pass
    _, err = p.communicate()
    if job.cancel:
        raise InterruptedError
    if p.returncode != 0:
        raise RuntimeError((err or "").strip().splitlines()[-1] if err and err.strip() else "ffmpeg failed")


def _fit(size: dict, style: dict | None = None, fades: str = "") -> str:
    w, h = size["w"], size["h"]
    look = (style or {}).get("look")
    # The grade goes on the picture before padding, so bars stay black, and
    # after any fade, so a dip bottoms out at the grade's black -- a lifted
    # black stays lifted through a dip, as it does under a graded edit.
    grade = f"lut3d=file='{_esc(look['lut'])}':interp=tetrahedral," if look else ""
    chain = (f"scale={w}:{h}:force_original_aspect_ratio=decrease:flags=bicubic,{fades}{grade}"
             f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,fps={FPS}")
    bar = _bar(size, style)
    if bar:
        chain += f",drawbox=x=0:y=0:w={w}:h={bar}:color=black:t=fill,drawbox=x=0:y={h - bar}:w={w}:h={bar}:color=black:t=fill"
    return chain + ",format=yuv420p"


def _esc(path: str) -> str:
    """A path inside '...' in a filtergraph, where everything is literal but '."""
    if "'" in path:
        raise ValueError("the look file's path can't contain a quote")
    return path


def _bar(size: dict, style: dict | None) -> int:
    """Height of each cinematic bar, or 0. Only a horizontal frame gets them."""
    aspect = (style or {}).get("letterbox")
    w, h = size["w"], size["h"]
    if not aspect or h >= w or aspect <= w / h + 0.02:
        return 0
    return int(round((h - w / aspect) / 2 / 2)) * 2


# --------------------------------------------------------------------------
# transitions
# --------------------------------------------------------------------------

def plan_transitions(items: list[dict], clips: dict[str, dict], style: dict | None) -> tuple[list[dict], list[str]]:
    """Per item: handles (dissolves) and fades (dips, flashes, open, close).

    Returns (per-item dicts, notes). A boundary is "between parts" when the
    two shots belong to different beats of the storyboard.
    """
    per = [{"head": 0, "tail": 0, "fade_in": None, "fade_out": None} for _ in items]
    pol = (style or {}).get("transitions")
    notes: list[str] = []
    if not pol or not items:
        return per, notes
    half = max(1, int(round(pol.get("dur", 0.5) / 2 * FPS)))
    fell_back = 0
    for k in range(len(items) - 1):
        a, b = items[k], items[k + 1]
        kind = pol["between"] if a.get("beat_id") != b.get("beat_id") else pol["within"]
        if kind == "cut":
            continue
        n = min(half, a["frames"] // 2, b["frames"] // 2)
        if n < 1:
            continue
        if kind == "dissolve":
            if a["kind"] == "shot" and b["kind"] == "shot" and _room(a, clips, "tail", n) and _room(b, clips, "head", n):
                per[k]["tail"], per[k + 1]["head"] = n, n
                continue
            if a["kind"] == "shot" and b["kind"] == "shot":
                fell_back += 1
                continue
            kind = "dip_black"   # next to a gap (already black): fade the shot side
        color = "white" if kind == "flash" else "black"
        if a["kind"] == "shot":
            per[k]["fade_out"] = (n, color)
        if b["kind"] == "shot":
            per[k + 1]["fade_in"] = (n, color)
    if pol.get("open") and items[0]["kind"] == "shot" and not per[0]["fade_in"]:
        per[0]["fade_in"] = (min(FPS, items[0]["frames"] // 2), "black")
    if pol.get("close") and items[-1]["kind"] == "shot" and not per[-1]["fade_out"]:
        per[-1]["fade_out"] = (min(int(1.5 * FPS), items[-1]["frames"] // 2), "black")
    if fell_back:
        notes.append(f"{fell_back} dissolve{'s' * (fell_back != 1)} became a cut: the shot wasn't "
                     "filmed long enough past the cut to blend")
    return per, notes


def _room(it: dict, clips: dict[str, dict], side: str, n: int) -> bool:
    """Is there footage for n frames beyond this span's edge?"""
    c = clips.get(it.get("clip_id") or "")
    if not c:
        return False
    need = n / FPS
    if side == "head":
        return it["src_start"] - need >= 0
    return it["src_end"] + need <= float(c.get("duration") or 0) - 1 / FPS


def _shot(job: Job, it: dict, out: Path, tr: dict | None = None) -> None:
    tr = tr or {"head": 0, "tail": 0, "fade_in": None, "fade_out": None}
    n = it["frames"] + tr["head"] + tr["tail"]
    d = n / FPS
    size = job.size
    audio_out = ["-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2"]
    common = ["-frames:v", str(n), "-t", f"{d:.6f}", *_venc(True, size), *audio_out, str(out)]
    if it["kind"] == "gap":
        _ff(["-f", "lavfi", "-i", f"color=black:s={size['w']}x{size['h']}:r={FPS}",
             "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
             "-map", "0:v", "-map", "1:a", "-vf", "format=yuv420p", *common], job)
        return
    c = job.clips[it["clip_id"]]
    info = _display(c["path"])
    src = ["-ss", f"{it['src_start'] - tr['head'] / FPS:.4f}", "-t", f"{d + 0.5:.4f}", "-i", c["path"]]
    vfade, afade = "", ""
    if tr["fade_in"]:
        k, color = tr["fade_in"]
        vfade += f"fade=t=in:st=0:d={k / FPS:.4f}:color={color},"
        if color == "black":   # a dip takes the sound down with the picture; a flash doesn't
            afade += f",afade=t=in:st=0:d={k / FPS:.4f}"
    if tr["fade_out"]:
        k, color = tr["fade_out"]
        vfade += f"fade=t=out:st={d - k / FPS:.4f}:d={k / FPS:.4f}:color={color},"
        if color == "black":
            afade += f",afade=t=out:st={d - k / FPS:.4f}:d={k / FPS:.4f}"
    if info["audio"]:
        amap = ["-map", "0:a:0", "-af", f"aresample=48000,aformat=channel_layouts=stereo,apad{afade}"]
    else:
        src += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
        amap = ["-map", "1:a"]
    # A punch-in: a slow push into the frame over the shot, the short-form
    # editor's way of making a held shot feel like a new one. The picture is
    # already at the output size, so the push is a crop that grows.
    punch = ""
    if it.get("punch"):
        z = float(it["punch"]) if it["punch"] is not True else 0.08
        # positive pushes in over the shot; negative starts pushed in and settles back
        zexpr = f"1+{z:.3f}*in/{max(n, 1)}" if z > 0 else f"{1 - z:.3f}-{-z:.3f}*in/{max(n, 1)}"
        punch = (f",zoompan=z='{zexpr}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                 f":d=1:s={size['w']}x{size['h']}:fps={FPS},format=yuv420p")
    # A span that runs to the very end of its file can decode a frame or two
    # short; hold the last frame so every shot is exactly its frame count.
    args = [*src, "-map", "0:v:0", *amap, "-vf",
            _fit(size, job.style, vfade) + punch + ",tpad=stop_mode=clone:stop_duration=1", *common]
    hw = ["-hwaccel", "videotoolbox"] if sys.platform == "darwin" else []
    try:
        _ff(hw + args, job)
    except RuntimeError:
        if not hw:
            raise
        _ff(args, job)   # a codec the hardware decoder won't take


def _dissolve_runs(job: Job, segs: list[Path], plan: list[dict], seg_dir: Path) -> list[Path]:
    """Overlap each run of shots joined by dissolves into one segment.

    Each shot in a run was rendered with `tail` frames past its out point
    and `head` frames before its in point; overlapping by head + tail puts
    every cut back on its timeline frame, so the run is exactly as long
    as its shots.
    """
    out, k = [], 0
    while k < len(segs):
        j = k
        while j + 1 < len(segs) and plan[j]["tail"]:
            j += 1
        if j == k:
            out.append(segs[k])
            k += 1
            continue
        run = list(range(k, j + 1))
        lens = [job.items[i]["frames"] + plan[i]["head"] + plan[i]["tail"] for i in run]
        args, v, a, parts = [], "[v0]", "[a0]", []
        for n, i in enumerate(run):
            args += ["-i", str(segs[i])]
            parts.append(f"[{n}:v]settb=AVTB,setpts=PTS-STARTPTS[v{n}];[{n}:a]asetpts=PTS-STARTPTS[a{n}]")
        length = lens[0]
        for n in range(1, len(run)):
            ov = plan[run[n - 1]]["tail"] + plan[run[n]]["head"]
            parts.append(f"{v}[v{n}]xfade=transition=fade:duration={ov / FPS:.6f}:offset={(length - ov) / FPS:.6f}[x{n}]")
            parts.append(f"{a}[a{n}]acrossfade=d={ov / FPS:.6f}:c1=tri:c2=tri[y{n}]")
            v, a = f"[x{n}]", f"[y{n}]"
            length += lens[n] - ov
        dest = seg_dir / f"run{k:04d}.mov"
        _ff([*args, "-filter_complex", ";".join(parts), "-map", v, "-map", a,
             "-frames:v", str(length), *_venc(True, job.size),
             "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", str(dest)], job)
        out.append(dest)
        k = j + 1
    return out


def _overlay_input(job: Job) -> Path | None:
    """The schedule as an ffconcat of PNGs, transparent where nothing shows."""
    if not job.schedule:
        return None
    frames = job.dir / "frames"
    blank = frames / "blank.png"
    _blank_png(blank, job.size)
    lines = ["ffconcat version 1.0"]
    t = 0.0

    def entry(p: Path, dur: float) -> None:
        if dur > 1e-4:
            lines.append(f"file '{p.name}'")
            lines.append(f"duration {dur:.6f}")

    for s in job.schedule:
        a, z = max(s["start"], t), min(s["end"], job.total)
        if z <= a:
            continue
        entry(blank, a - t)
        entry(frames / f"{s['frame']:05d}.png" if s["frame"] is not None else blank, z - a)
        t = z
    entry(blank, job.total - t)
    lines.append(f"file '{blank.name}'")   # the last entry's duration needs a successor
    out = frames / "overlay.ffconcat"
    out.write_text("\n".join(lines) + "\n")
    return out


def _blank_png(path: Path, size: dict) -> None:
    """A fully transparent RGBA PNG, written without an image library."""
    import struct
    import zlib
    w, h = size["w"], size["h"]
    raw = (b"\x00" + b"\x00\x00\x00\x00" * w) * h

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))
    path.write_bytes(png)


DUCK_RAMP_S = 0.25   # attack/release of a duck; a step would be heard


def _duck_expr(ducks: list) -> str:
    """A volume expression: 1 outside the ducks, `gain` inside, ramped over DUCK_RAMP_S.

    Each duck is (start, end, gain) in sequence seconds. Overlaps take the
    quieter of the two.
    """
    terms = []
    for a, b, g in ducks:
        a, b, g = float(a), float(b), float(g)
        if b <= a or not 0 <= g < 1:
            continue
        # distance outside [a,b], clipped to the ramp -> 0 inside, 1 a ramp away.
        # The expression sits inside '...' in the filtergraph, so commas are literal.
        terms.append(f"({g:.3f}+{1 - g:.3f}*clip(max({a:.3f}-t,t-{b:.3f})/{DUCK_RAMP_S},0,1))")
    out = ""
    for t in terms:
        out = t if not out else f"min({out},{t})"
    return out


def _run(job: Job) -> None:
    t0 = time.time()
    try:
        seg_dir = job.dir / "shots"
        seg_dir.mkdir(exist_ok=True)
        job.of = len(job.items)
        plan, job.notes = plan_transitions(job.items, job.clips, job.style)
        segs = []
        for k, it in enumerate(job.items):
            if job.cancel:
                raise InterruptedError
            out = seg_dir / f"{k:04d}.mov"
            _shot(job, it, out, plan[k])
            segs.append(out)
            job.done = k + 1
            job.progress = 0.65 * (k + 1) / len(job.items)
            job.elapsed = time.time() - t0
        listing = [f"file '{p.name}'" for p in _dissolve_runs(job, segs, plan, seg_dir)]
        job.stage = "joining"
        (seg_dir / "list.ffconcat").write_text("ffconcat version 1.0\n" + "\n".join(listing) + "\n")
        joined = job.dir / "joined.mov"
        _ff(["-f", "concat", "-safe", "0", "-i", str(seg_dir / "list.ffconcat"), "-c", "copy", str(joined)], job)

        job.stage = "finishing"
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        dest = OUT_DIR / f"{job.name} {time.strftime('%Y-%m-%d %H.%M')}.mp4"
        k = 2
        while dest.exists():
            dest = OUT_DIR / f"{job.name} {time.strftime('%Y-%m-%d %H.%M')} ({k}).mp4"
            k += 1
        tmp = job.dir / "out.mp4"
        ov = _overlay_input(job)
        args = ["-i", str(joined)]
        filters, vmap, amap = [], "0:v", "0:a"
        if ov:
            args += ["-f", "concat", "-safe", "0", "-i", str(ov)]
            filters.append("[1:v]format=rgba[ov];[0:v][ov]overlay=0:0:eof_action=pass:format=auto,format=yuv420p[v]")
            vmap = "[v]"
        if job.music:
            mi = 2 if ov else 1
            mix = job.mix or {}
            if mix.get("in"):
                args += ["-ss", f"{float(mix['in']):.3f}"]
            args += ["-i", job.music]
            fade_d = float(mix.get("fade_out", 2.0))
            fade = max(0.0, job.total - fade_d)
            gain = float(mix.get("gain", MUSIC_GAIN))
            duck = _duck_expr(mix.get("duck") or [])
            chain = (f"[{mi}:a]aresample=48000,aformat=channel_layouts=stereo,volume={gain}"
                     + (f",volume='{duck}':eval=frame" if duck else "")
                     + f",afade=t=out:st={fade:.3f}:d={fade_d:.3f},apad[m]")
            filters.append(chain)
            mixers = ["[0:a]", "[m]"]
            if mix.get("original") is not None:
                # a music-led edit keeps the phone's own sound under the track, not level with it
                filters.append(f"[0:a]volume={float(mix['original']):.3f}[o]")
                mixers[0] = "[o]"
            for k, fx in enumerate(mix.get("sfx") or []):
                # a short sound at a cut: one input each, delayed into place
                fi = mi + 1 + k
                args += ["-i", fx["path"]]
                filters.append(f"[{fi}:a]aresample=48000,aformat=channel_layouts=stereo,"
                               f"volume={float(fx.get('gain', 0.5))},adelay={int(fx['at'] * 1000)}:all=1,"
                               f"apad=whole_dur={job.total:.3f}[fx{k}]")
                mixers.append(f"[fx{k}]")
            # loudnorm works (and would output) at 192 kHz; players expect 48 kHz AAC
            level = ",loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000" if mix.get("level") else ""
            filters.append(f"{''.join(mixers)}amix=inputs={len(mixers)}:duration=first:normalize=0{level}[a]")
            amap = "[a]"
        if filters:
            args += ["-filter_complex", ";".join(filters)]
        venc = _venc(False, job.size) if ov else ["-c:v", "copy"]
        args += ["-map", vmap, "-map", amap, *venc, "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                 "-t", f"{job.total:.6f}", "-movflags", "+faststart", str(tmp)]
        _ff(args, job, total_s=job.total, base=0.7, weight=0.3)
        shutil.move(str(tmp), dest)
        job.path = str(dest)
        job.progress = 1.0
        job.stage = "done"
        shutil.rmtree(job.dir, ignore_errors=True)   # intermediates only; the export is in OUT_DIR
    except InterruptedError:
        job.stage = "cancelled"
        shutil.rmtree(job.dir, ignore_errors=True)
    except Exception as e:  # noqa: BLE001 -- surfaced to the creator verbatim
        job.stage = "error"
        job.error = str(e)
    finally:
        job.elapsed = time.time() - t0

"""Reference videos: bring one in, learn its style, keep a small library.

A reference is a video the creator admires -- a file on this Mac, or a link
(fetched with yt-dlp, if it is installed). It is read once, the way every
clip is (48x27 frames + mono audio, cutgrammar.style), and what is kept is
the *measurements*: pace, transitions, beat, look, frame, music feel. Its
frames and sound never go into the creator's video; the export only ever
contains their own footage.

Downloaded files stay in the cache next to their style so a style can be
re-learnt when the learner improves; "Forget" deletes both.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import numpy as np

from cutgrammar import bestframe, grade, media, music
from cutgrammar import style as st

from . import indexer, restyle

ROOT = indexer.CACHE / "references"
LIMIT_S = 600.0            # a reference is learnt from at most its first 10 minutes
MAX_HEIGHT = 720           # plenty for 48x27; keeps downloads small
PREVIEW_SHOTS = 4
STATS_SHOTS = 40
STRENGTHS = {"subtle": 0.5, "full": 1.0}
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}


# --------------------------------------------------------------------------
# where things live
# --------------------------------------------------------------------------

def _rid(source: str) -> str:
    if is_url(source):
        key = source.strip()
    else:
        p = os.path.realpath(source)
        stt = os.stat(p)
        key = f"{p}|{stt.st_size}|{stt.st_mtime_ns}"
    return hashlib.sha1(f"{key}|{st.VERSION}".encode()).hexdigest()[:12]


def ref_dir(rid: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{12}", rid or ""):
        raise ValueError("no such reference")
    return ROOT / rid


def is_url(s: str) -> bool:
    u = urlparse(s.strip())
    return u.scheme in ("http", "https") and bool(u.netloc)


def ytdlp() -> str | None:
    return shutil.which("yt-dlp")


def load(rid: str) -> dict | None:
    d = ref_dir(rid)
    try:
        return {**json.loads((d / "meta.json").read_text()), "style": json.loads((d / "style.json").read_text())}
    except (OSError, ValueError):
        return None


def library() -> list[dict]:
    """Every style learnt so far, newest first -- a creator's own collection."""
    out = []
    if ROOT.exists():
        for d in ROOT.iterdir():
            r = load(d.name) if d.is_dir() else None
            if r:
                out.append(public(r))
    return sorted(out, key=lambda r: -r.get("learnt_at", 0))


def forget(rid: str) -> None:
    shutil.rmtree(ref_dir(rid), ignore_errors=True)


# --------------------------------------------------------------------------
# jobs: fetch (links only) -> read -> learn
# --------------------------------------------------------------------------

@dataclass
class Job:
    id: str
    source: str
    rid: str
    stage: str = "queued"      # fetching | reading | learning | done | error
    progress: float = 0.0
    error: str | None = None
    started: float = field(default_factory=time.time)

    def public(self) -> dict:
        r = load(self.rid) if self.stage == "done" else None
        return {"id": self.id, "stage": self.stage, "progress": round(self.progress, 3),
                "error": self.error, "rid": self.rid, "elapsed": round(time.time() - self.started, 1),
                "reference": public(r) if r else None}


JOBS: dict[str, Job] = {}


def start(source: str) -> Job:
    source = source.strip()
    if is_url(source):
        if not ytdlp():
            raise ValueError("Links need yt-dlp (brew install yt-dlp). Or save the video and drop the file.")
    else:
        source = os.path.expanduser(source)
        if not os.path.isfile(source):
            raise ValueError(f"can't find {source}")
        if Path(source).suffix.lower() not in VIDEO_EXT:
            raise ValueError("that isn't a video file (.mp4, .mov, .m4v, .webm, .mkv)")
    job = Job(id=uuid.uuid4().hex[:10], source=source, rid=_rid(source))
    JOBS[job.id] = job
    if load(job.rid):
        job.stage, job.progress = "done", 1.0   # learnt before: nothing to do
        return job
    threading.Thread(target=_run, args=(job,), daemon=True).start()
    return job


def _fetch(job: Job, d: Path) -> tuple[str, dict]:
    """Download a link with yt-dlp into d. Returns (file, info)."""
    job.stage = "fetching"
    cmd = [ytdlp() or "yt-dlp", "--no-playlist", "--newline", "--no-part", "--restrict-filenames",
           "-f", f"bv*[height<={MAX_HEIGHT}]+ba/b[height<={MAX_HEIGHT}]/bv*+ba/b",
           "--merge-output-format", "mp4", "--write-info-json",
           # only what will be learnt from
           "--download-sections", f"*0-{int(LIMIT_S)}",
           "-o", str(d / "source.%(ext)s"), "--", job.source]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    tail: list[str] = []
    for line in p.stdout or []:
        tail = (tail + [line.strip()])[-8:]
        m = re.search(r"\[download\]\s+([\d.]+)%", line)
        if m:
            job.progress = 0.5 * float(m.group(1)) / 100
    if p.wait() != 0:
        msg = next((t for t in reversed(tail) if "ERROR" in t), tail[-1] if tail else "download failed")
        raise RuntimeError(msg.replace("ERROR: ", "")[:300])
    files = [f for f in d.iterdir() if f.name.startswith("source.") and f.suffix.lower() in VIDEO_EXT]
    if not files:
        raise RuntimeError("the link didn't give a video file")
    try:
        info = json.loads((d / "source.info.json").read_text())
    except (OSError, ValueError):
        info = {}
    return str(files[0]), {"title": info.get("title"), "uploader": info.get("uploader") or info.get("channel"),
                           "url": info.get("webpage_url") or job.source}


def _run(job: Job) -> None:
    d = ROOT / job.rid
    tmp = ROOT / f".{job.rid}.{job.id}"
    try:
        tmp.mkdir(parents=True, exist_ok=True)
        if is_url(job.source):
            path, info = _fetch(job, tmp)
            path = str(d / Path(path).name)   # where it will live after the move
        else:
            path, info = job.source, {"title": Path(job.source).stem, "uploader": None, "url": None}
        job.stage, job.progress = "reading", max(job.progress, 0.5)
        m = media.load(str(tmp / Path(path).name) if is_url(job.source) else path, limit_s=LIMIT_S)
        job.stage, job.progress = "learning", 0.85
        style = st.learn(m)
        (tmp / "style.json").write_text(json.dumps(style))
        meta = {"rid": job.rid, "title": info.get("title") or "Reference", "uploader": info.get("uploader"),
                "url": info.get("url"), "path": path, "downloaded": is_url(job.source),
                "duration": round(m.duration, 2), "learnt_from_s": round(min(m.duration, LIMIT_S), 1),
                "learnt_at": time.time()}
        (tmp / "meta.json").write_text(json.dumps(meta))
        shutil.rmtree(d, ignore_errors=True)
        tmp.rename(d)
        job.stage, job.progress = "done", 1.0
    except Exception as e:  # noqa: BLE001 -- surfaced to the creator verbatim
        job.stage, job.error = "error", str(e)[:400]
        shutil.rmtree(tmp, ignore_errors=True)


# --------------------------------------------------------------------------
# the card: what can be borrowed, in words
# --------------------------------------------------------------------------

def public(r: dict) -> dict:
    s = r["style"]
    return {"rid": r["rid"], "title": r["title"], "uploader": r.get("uploader"), "url": r.get("url"),
            "downloaded": r.get("downloaded", False), "duration": r.get("duration"),
            "learnt_from_s": r.get("learnt_from_s"), "learnt_at": r.get("learnt_at"),
            "summary": st.summary(s)}


def card(rid: str, grid: dict | None, landscape: bool | None) -> dict:
    """Each trait: what the reference does, what applying it would do, and
    whether it can be applied to this edit right now (and if not, why)."""
    r = load(rid)
    if not r:
        raise ValueError("no such reference")
    s = r["style"]
    traits = []

    def add(key: str, title: str, words: list[str], how: str | None, why_not: str | None = None,
            on: bool = True, extra: dict | None = None) -> None:
        v = s.get(key) or {}
        pending = v.get("pending")
        traits.append({"key": key, "title": title, "words": words, "how": how,
                       "available": how is not None and not why_not and not pending,
                       "why_not": why_not or (f"Not measured — needs {', '.join(pending)}" if pending else None),
                       "on": on, "evidence": v.get("evidence", []), **(extra or {})})

    p = s.get("pace")
    if p:
        arc = ("quickening towards the end" if p["trend"] < -0.25
               else "slowing towards the end" if p["trend"] > 0.25 else "at an even pace")
        add("pace", "Pacing", p["words"],
            f"Hold each shot about {p['median_s']:.1f} s, {arc}, each centred on its best moment",
            extra={"numbers": {"median_s": p["median_s"], "per_min": p["per_min"], "curve": p["curve"]}})
    b = s.get("beat")
    if b is not None:
        why = None
        if not b.get("cuts_on_beat"):
            why = "The reference doesn't cut on the beat"
        elif not grid:
            why = "Put a track with a steady beat under the edit first (Music)"
        add("beat", "Cutting to the music", b["words"],
            "Move each cut to the nearest beat of your track" if b.get("cuts_on_beat") else None, why,
            on=bool(b.get("cuts_on_beat") and grid))
    tr = s.get("transitions")
    if tr:
        pol = restyle.transition_policy(tr)
        add("transitions", "Transitions", tr["words"], restyle.describe_policy(pol) + " — rendered in the export",
            on=pol["between"] != "cut" or pol["open"] or pol["close"],
            extra={"counts": tr["counts"]})
    lk = s.get("look")
    if lk:
        add("look", "Colour & mood", lk["words"],
            "One grade over your whole video, fitted to your footage — rendered in the export",
            extra={"numbers": {k: lk[k] for k in ("warmth", "tint", "sat", "black", "contrast", "median")}})
    fr = s.get("frame")
    if fr:
        how, why = None, None
        if fr.get("letterbox"):
            how = f"Add cinematic bars ({fr['letterbox']:.2f}:1) in the export"
            if landscape is False:
                why = "Your edit is vertical; bars are for a horizontal frame"
        add("frame", "Frame", fr["words"], how, why, on=bool(how and not why))
    mf = s.get("music")
    if mf:
        add("music", "Music feel", mf["words"], None,
            "Music isn't copied — pick one of your own tracks with the same feel (below)", on=False)
    return {"reference": public(r), "traits": traits}


# --------------------------------------------------------------------------
# music: the creator's own tracks closest in feel
# --------------------------------------------------------------------------

def music_matches(rid: str, tracks: list[music.Track], top: int = 3) -> list[dict]:
    """Rank the creator's tracks by the reference's energy arc and tempo.

    Shape as in music.match (z-normalised correlation), tempo as closeness
    on a log scale with half/double time counted as close -- a 70 BPM track
    feels like a 140 BPM one. Neither says the track is *good*.
    """
    r = load(rid)
    mf = (r or {}).get("style", {}).get("music")
    if not mf or not tracks:
        return []
    ref = np.asarray(mf["energy"], dtype=np.float64)
    scored = []
    for t in tracks:
        if not len(t.energy):
            continue
        shape = music.shape_score(t.energy.astype(np.float64), ref)
        tempo = None
        if mf.get("bpm") and t.bpm:
            ratio = abs(np.log2(t.bpm / mf["bpm"]))
            ratio = min(ratio, abs(ratio - 1))
            tempo = float(np.clip(1 - ratio / 0.25, 0, 1))
        score = shape if tempo is None else 0.6 * shape + 0.4 * tempo
        why = []
        if shape >= music.MIN_SHAPE_R:
            why.append(f"its energy {mf['arc'].replace('builds', 'builds too').replace('steady', 'stays steady')}")
        if tempo is not None and tempo > 0.5:
            why.append(f"{t.bpm:.0f} BPM, near the reference's {mf['bpm']:.0f}")
        scored.append({"id": t.id, "title": t.title, "bpm": t.bpm, "score": round(float(score), 3),
                       "reason": " · ".join(why), "audio": f"/api/music/audio/{t.id}"})
    scored.sort(key=lambda x: -x["score"])
    return scored[:top]


# --------------------------------------------------------------------------
# the look, fitted to this footage
# --------------------------------------------------------------------------

def _thumb_path(url: str) -> Path | None:
    m = re.fullmatch(r"/api/thumbs/([0-9a-f]+)/([\w.]+\.jpg)", url or "")
    return indexer.clip_dir(m.group(1)) / m.group(2) if m else None


def _read_jpeg(path: Path, w: int | None = None, h: int | None = None) -> np.ndarray | None:
    """A JPEG as (H, W, 3) uint8 via ffmpeg (numpy only here, no image lib)."""
    info = media.probe(str(path))
    v = next((s for s in info["streams"] if s.get("codec_type") == "video"), None)
    if not v:
        return None
    W, H = (w, h) if w else (int(v["width"]), int(v["height"]))
    p = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vf", f"scale={W}:{H}",
                        "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True)
    if p.returncode != 0 or len(p.stdout) < W * H * 3:
        return None
    return np.frombuffer(p.stdout[: W * H * 3], dtype=np.uint8).reshape(H, W, 3)


def _board_thumbs(board: dict, cat) -> list[Path]:
    seen, out = set(), []
    for bt in board.get("beats", []):
        for e in bt["shots"]:
            s = cat.shots.get(e.get("id") or "")
            p = _thumb_path(s.thumb) if s else None
            if p and p.exists() and p not in seen:
                seen.add(p)
                out.append(p)
    return out


def fit_look(rid: str, board: dict, cat, strength: str) -> dict:
    """Fit the reference's look to the shots on this board: write the LUT,
    and before/after stills of a few of them. Returns what the op records."""
    r = load(rid)
    if not r or not r["style"].get("look"):
        raise ValueError("this reference has no look to borrow")
    k = STRENGTHS.get(strength)
    if k is None:
        raise ValueError(f"strength must be one of {', '.join(STRENGTHS)}")
    thumbs = _board_thumbs(board, cat)
    if not thumbs:
        raise ValueError("choose a story first — the look is fitted to the shots in it")
    pick = [thumbs[i] for i in np.unique(np.linspace(0, len(thumbs) - 1, min(STATS_SHOTS, len(thumbs))).astype(int))]
    small = [x for x in (_read_jpeg(p, 48, 27) for p in pick) if x is not None]
    if not small:
        raise ValueError("couldn't read the shots' thumbnails")
    px = grade.pixels(np.stack(small))
    look = grade.Look(px, r["style"]["look"], k)
    sig = hashlib.sha1("|".join(str(p) for p in pick).encode()).hexdigest()[:8]
    d = ref_dir(rid)
    lut_path = d / f"look-{strength}-{sig}.cube"
    lut = look.lut()
    if not lut_path.exists():
        grade.write_cube(lut, str(lut_path), f"VibeCut · {r['title'][:40]}")
    previews = []
    for n, p in enumerate(pick[:: max(1, len(pick) // PREVIEW_SHOTS)][:PREVIEW_SHOTS]):
        name = f"prev-{sig}-{n}-{strength}.jpg"
        if not (d / name).exists():
            img = _read_jpeg(p)
            if img is None:
                continue
            bestframe.write_jpegs([grade.apply_lut(img, lut)], [str(d / name)], quality=4)
        previews.append({"before": "/api/thumbs/" + "/".join(p.parts[-2:]),
                         "after": f"/api/references/{rid}/files/{name}"})
    after = grade.stats(look(px))
    return {"lut": str(lut_path), "strength": k, "previews": previews,
            "look_words": grade.words(after),
            "numbers": {"yours": {x: grade.stats(px)[x] for x in ("warmth", "black", "sat")},
                        "after": {x: after[x] for x in ("warmth", "black", "sat")},
                        "reference": {x: r["style"]["look"][x] for x in ("warmth", "black", "sat")}}}


def file_path(rid: str, name: str) -> Path | None:
    if not re.fullmatch(r"prev-[0-9a-f]{8}-\d+-\w+\.jpg", name):
        return None
    p = ref_dir(rid) / name
    return p if p.exists() else None


def make_op(rid: str, traits: list[str], grid: dict | None, look: dict | None) -> dict:
    """Everything apply_style needs, decided now, so replay is exact."""
    r = load(rid)
    if not r:
        raise ValueError("no such reference")
    op = {"op": "apply_style", "ref": rid, "name": r["title"], "traits": list(traits),
          "style": restyle.snapshot(r["style"])}
    if "beat" in traits and grid:
        op["grid"] = grid
    if "look" in traits and look:
        op.update(lut=look["lut"], strength=look["strength"], look_words=look["look_words"])
    return op

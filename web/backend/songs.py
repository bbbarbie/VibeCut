"""The song under the edit: one picked for you, three more a tap away, or your own.

A vlogger shouldn't have to go shopping for music before they can watch
their edit. So the app picks a song the way an editor would start: by the
edit's tempo (quick / steady / calm, tempo.py), by how the song's energy
follows the edit's (cutgrammar.music), and by how the people who tagged the
song describe it. The pick is applied as one undoable turn that

  - starts the song on a beat, at the stretch whose shape fits the edit best,
  - makes every shot a whole number of beats, so the cuts land on the beat
    (talking shots only ever grow to the next beat, never into their words),
  - ducks the song wherever a voice is heard (sound.json, Apple's on-device
    classifier), worked out from the edit as it stands at mix time, so a
    later trim or reorder never leaves a duck in the wrong place.

Where the songs come from: the free music library (Openverse, CC0 / BY /
BY-SA only, so a credit line travels with the export), the creator's own
music folder if they set one, and any song they add here. Nothing is
bundled with the app. Every weight below is a prior, not calibrated.
"""

from __future__ import annotations

import re
import shutil
import threading
from pathlib import Path

import numpy as np

from cutgrammar import music as mu
from cutgrammar import openverse as ov
from cutgrammar.signals import VOICE_HI

from . import board as bd
from . import musiclib
from .audiomix import MUSIC_GAIN
from .indexer import CACHE

OWN_DIR = CACHE / "music" / "mine"
OWN_EXT = mu.AUDIO_EXT

# What to ask the library for, per tempo, and the song tempo each wants
# (beats a minute; half or double time counts too, a 60 BPM song cut on
# its eighths moves like 120). [prior]
MOODS = {
    "fast": ["upbeat pop", "feel good electronic pop", "indie dance pop", "summer pop"],
    "balanced": ["feel good indie pop", "upbeat acoustic", "happy indie folk", "lofi hip hop"],
    "calm": ["chill acoustic", "calm piano", "lofi chill", "peaceful ambient"],
}
TEMPO = {"fast": (110.0, 135.0), "balanced": (88.0, 115.0), "calm": (65.0, 95.0)}
PER_QUERY = 5

ORIGINAL_GAIN = 0.7    # the clips' own sound under a song: still there, a step back
DUCK_GAIN = 0.3        # the song under a voice, relative to its own level
DUCK_PAD_S = 0.3       # start before the first word, stay down a breath after
DUCK_JOIN_S = 1.0      # two voices this close are one duck, not a pump
FADE_OUT_S = 2.5


# --------------------------------------------------------------------------
# the pool: free library (per tempo, searched once), own folder, own songs
# --------------------------------------------------------------------------

STATE: dict = {"library": {}, "errors": {}, "own": None}
_lock = threading.Lock()


def _search(pace: str) -> None:
    try:
        tracks = ov.OpenverseSource(MOODS[pace], per_query=PER_QUERY).list()
        STATE["library"][pace] = [t for t in tracks if t.duration >= 30]
        if not tracks:
            STATE["errors"][pace] = "offline"
    except Exception as e:  # noqa: BLE001 -- offline, rate-limited: own songs still work
        STATE["library"][pace] = []
        STATE["errors"][pace] = str(e)[:200]


def status(pace: str) -> str:
    """searching | ready | offline. The first ask for a tempo starts the search."""
    with _lock:
        lib = STATE["library"].get(pace)
        if lib is None:
            STATE["library"][pace] = "searching"
            threading.Thread(target=_search, args=(pace,), daemon=True).start()
            return "searching"
    if lib == "searching":
        return "searching"
    return "offline" if not lib and STATE["errors"].get(pace) else "ready"


def own() -> list[mu.Track]:
    if STATE["own"] is None:
        STATE["own"] = mu.LocalFolderSource(str(OWN_DIR)).list() if OWN_DIR.is_dir() else []
        for t in STATE["own"]:
            t.meta = {**t.meta, "own": True}
    return STATE["own"]


def add_own(name: str, data_from) -> mu.Track:
    """Save a song the creator chose (a file object) and read its beat."""
    ext = Path(name).suffix.lower()
    if ext not in OWN_EXT:
        raise ValueError("That isn't a song file this app can read (mp3, m4a, wav or flac).")
    have = own()       # read the folder before the new file is in it
    OWN_DIR.mkdir(parents=True, exist_ok=True)
    stem = re.sub(r"[^\w\- ]+", "", Path(name).stem).strip()[:60] or "song"
    dest = OWN_DIR / f"{stem}{ext}"
    k = 2
    while dest.exists():
        dest = OWN_DIR / f"{stem} ({k}){ext}"
        k += 1
    with open(dest, "wb") as w:
        shutil.copyfileobj(data_from, w)
    try:
        t = mu.analyse(str(dest))
    except Exception as e:  # noqa: BLE001
        dest.unlink(missing_ok=True)
        raise ValueError("That file couldn't be read as a song.") from e
    t.title = t.title or stem
    t.meta = {**t.meta, "own": True}
    have.append(t)
    return t


def pool(pace: str) -> list[mu.Track]:
    lib = STATE["library"].get(pace)
    out = {t.id: t for t in (lib if isinstance(lib, list) else [])}
    for t in musiclib.STATE["tracks"] + own():
        out.setdefault(t.id, t)
    return list(out.values())


def find(track_id: str | None) -> mu.Track | None:
    if not track_id:
        return None
    for lib in STATE["library"].values():
        if isinstance(lib, list):
            for t in lib:
                if t.id == track_id:
                    return t
    return next((t for t in own() if t.id == track_id), None)


# --------------------------------------------------------------------------
# ranking: tempo, shape, what the song is said to be
# --------------------------------------------------------------------------

def tempo_fit(bpm: float | None, pace: str) -> float:
    """1 inside the tempo's range, falling off outside. A slow song also counts at
    double time (cut on its eighths it moves like a quick one); a quick song
    never counts as slow, it still sounds quick under calm shots."""
    if not bpm:
        return 0.2
    lo, hi = TEMPO.get(pace, TEMPO["balanced"])
    best = 0.0
    for b in (bpm, bpm * 2) if bpm < 90 else (bpm,):
        off = 0.0 if lo <= b <= hi else min(abs(np.log2(b / lo)), abs(np.log2(b / hi)))
        best = max(best, float(np.clip(1 - off / 0.25, 0, 1)))
    return best


def _words(t: mu.Track) -> str:
    rec = t.meta.get("licence") or {}
    return " ".join([rec.get("title", ""), t.title, *rec.get("tags", []), *rec.get("genres", [])]).lower()


DRIVING = ("pop", "dance", "disco", "electronic", "upbeat", "energetic", "funk", "groove", "house", "happy")
SLOW = ("acoustic", "ballad", "piano", "ambient", "peaceful", "relax", "chill", "calm", "lofi", "folk")


def lift(t: mu.Track) -> float:
    """0..1 from the song's own tags: driving words up, quiet words down."""
    w = _words(t)
    return float(np.clip(0.5 + 0.15 * sum(x in w for x in DRIVING) - 0.15 * sum(x in w for x in SLOW), 0, 1))


def best_start(t: mu.Track, curve: np.ndarray | None, length: float) -> float:
    """Where in the song the edit starts: the stretch whose energy follows the
    edit's, on a beat. A song shorter than the edit starts at its top."""
    room = t.duration - length
    start = 0.0
    if room > 4 and curve is not None and len(t.energy):
        n = max(1, int(np.ceil(length * mu.ENERGY_HZ)))
        # don't open in a fade-in's silence: the first 4 s are skipped when there's room
        cands = list(range(4 if room > 8 else 0, int(room) + 1, 4)) or [0]
        start = float(max(cands, key=lambda s: mu.shape_score(t.energy[s:s + n], curve)))
    ph = (t.meta.get("tempo") or {}).get("phase")
    if t.bpm and ph is not None:
        p = 60.0 / t.bpm
        start = ph + round((start - ph) / p) * p
        while start < 0:
            start += p
    return round(float(start), 3)


def _feel(t: mu.Track) -> str:
    if not t.bpm:
        return "A free-flowing song"
    return "A lively song" if t.bpm >= 110 or lift(t) > 0.65 else \
        "An easy-going song" if t.bpm >= 85 else "A slow, soft song"


def why(t: mu.Track) -> str:
    """One plain sentence a creator can read."""
    if t.meta.get("own"):
        base = "Your own song"
    elif t.meta.get("licence"):
        base = _feel(t)
    else:
        base = "From your music folder"
    beat = "the cuts land on its beat" if t.bpm and (t.meta.get("tempo") or {}).get("phase") is not None \
        else "it has no steady beat, so the cuts stay where they are"
    return f"{base}; {beat}."


def rank(board: dict, cat: bd.Catalog, pace: str, tracks: list[mu.Track]) -> list[mu.Track]:
    secs = musiclib.sections(board, cat)
    length = sum(s.duration for s in secs)
    curve, _ = mu.edit_curve(secs) if secs else (None, None)
    flat = curve is None or mu._z(mu._resample(curve)) is None
    want_lift = {"fast": 0.8, "balanced": 0.55, "calm": 0.25}.get(pace, 0.55)
    scored = []
    for t in tracks:
        if t.duration < length + 2 or not len(t.energy):
            continue
        n = max(1, int(np.ceil(length * mu.ENERGY_HZ)))
        shape = 0.0 if flat else max(0.0, max(mu.shape_score(t.energy[s:s + n], curve)
                                              for s in range(0, max(1, int(t.duration - length)), 4)))
        has_beat = bool(t.bpm) and (t.meta.get("tempo") or {}).get("phase") is not None
        score = (0.45 * tempo_fit(t.bpm, pace) + 0.25 * shape + 0.2 * (1 - abs(lift(t) - want_lift))
                 + 0.1 * has_beat)
        scored.append((score, t))
    scored.sort(key=lambda x: -x[0])
    return [t for _, t in scored]


# --------------------------------------------------------------------------
# applying: the bed, and every shot a whole number of beats
# --------------------------------------------------------------------------

def beat_ops(board: dict, cat: bd.Catalog, bpm: float, talk: set[str]) -> list[dict]:
    """trim ops that make each shot a whole number of beats.

    The song starts on a beat at the edit's first frame, so once every shot
    is whole beats long, every cut is on a beat. A shot moves its out-point
    by at most half a beat; a talking shot only grows (to the next beat, if
    it was filmed that long), so no word is cut short for the music."""
    p = 60.0 / bpm
    while p < 0.4:          # very quick songs: cut on every other beat
        p *= 2
    ops = []
    for beat in board["beats"]:
        for e in beat["shots"]:
            if bd.is_gap(e):
                continue
            d = e["end"] - e["start"]
            src = cat.get(e["id"])
            hi = src.end if src is not None else e["end"]
            if e["id"] in talk:
                n = int(np.ceil(d / p - 1e-6))
                if e["start"] + n * p > hi + 1e-6:
                    continue
            else:
                n = max(1, int(round(d / p)))
                if e["start"] + n * p > hi + 1e-6:
                    n = max(1, int(np.floor(d / p)))
            to = round(e["start"] + n * p, 3)
            if abs(to - e["end"]) >= bd.FRAME / 2:
                ops.append({"op": "trim", "shot": bd.key(e), "edge": "out", "to": to})
    return ops


def edit_length(board: dict) -> float:
    return sum(e["end"] - e["start"] for b in board["beats"] for e in b["shots"])


def use_ops(board: dict, cat: bd.Catalog, t: mu.Track | None, talk: set[str]) -> list[dict]:
    if t is None:
        return [{"op": "set_music", "track": None}]
    has_beat = bool(t.bpm) and (t.meta.get("tempo") or {}).get("phase") is not None
    trims = beat_ops(board, cat, float(t.bpm), talk) if has_beat else []
    after = board
    for op in trims:
        after, _ = bd.apply(after, op, cat, None, new_id=lambda: "")
    secs = musiclib.sections(after, cat)
    curve, _ = mu.edit_curve(secs) if secs else (None, None)
    start = best_start(t, curve, edit_length(after))
    bed = {"op": "set_music", "track": t.id, "in": start, "gain": MUSIC_GAIN, "original": ORIGINAL_GAIN,
           "level": True, "fade_out": FADE_OUT_S, "duck_speech": True}
    return trims + [bed]


def speech_ducks(items: list[dict], clips: dict) -> list[list[float]]:
    """[start, end, gain] in edit time wherever a voice is heard (sound.json, per second)."""
    spans: list[list[float]] = []
    for it in items:
        if it.get("kind") != "shot":
            continue
        voice = ((clips.get(it["clip_id"]) or {}).get("sound") or {}).get("voice") or []
        a, z = float(it["src_start"]), float(it["src_end"])
        for s in range(int(a), int(np.ceil(z))):
            if s < len(voice) and voice[s] >= VOICE_HI:
                t0 = it["seq_start"] + max(s, a) - a - DUCK_PAD_S
                t1 = it["seq_start"] + min(s + 1, z) - a + DUCK_PAD_S
                if spans and t0 - spans[-1][1] <= DUCK_JOIN_S:
                    spans[-1][1] = max(spans[-1][1], t1)
                else:
                    spans.append([max(0.0, t0), t1])
    return [[round(a, 3), round(b, 3), DUCK_GAIN] for a, b in spans]


def resolve(mix: dict | None, items: list[dict], clips: dict) -> dict | None:
    """The board's bed with its automatic ducks filled in from the edit as it is now."""
    if not mix or not mix.get("duck_speech"):
        return mix
    return {**mix, "duck": list(mix.get("duck") or []) + speech_ducks(items, clips)}


def credit(t: mu.Track | None) -> str | None:
    rec = (t.meta.get("licence") if t else None)
    return ov.credit(rec) if rec else None


def public(t: mu.Track, current: bool = False) -> dict:
    rec = t.meta.get("licence") or {}
    title = rec.get("title") or t.title or Path(t.path).stem
    return {"id": t.id, "title": title, "by": rec.get("creator") or "", "why": why(t),
            "own": bool(t.meta.get("own")), "seconds": round(t.duration, 1), "current": current,
            "audio": f"/api/music/audio/{t.id}"}

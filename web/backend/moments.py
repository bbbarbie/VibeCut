"""Which of the trim's best windows is the moment worth keeping.

trim.py can tell a sharp, steady second with something in it from a blurry
one; it can't tell the second someone laughs from the second before. So for
each shot it offers its top few windows (trim.candidates), and -- only when
there is a key -- Claude looks at a few frames from each and picks the one a
good editor would keep. Without a key, or if the answer doesn't come back,
the rules' own first choice stands, exactly as before.

What leaves the Mac: three small index frames (the ~1/s JPEGs already on
disk, 384 px wide) per option, nothing else of the clip -- no audio, no
file, no name. Answers are cached next to the clip's index, so a shot is
asked about once, not on every click at the gate. VIBECUT_MOMENTS=0 turns
it off.
"""

from __future__ import annotations

import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable

from cutgrammar.trim import Window

from . import indexer

FRAMES = 3          # per option: start, middle, end
INSET_S = 0.3       # the very first and last frame are often mid-cut; look just inside
WORKERS = 6

Ask = Callable[[list[dict]], tuple[int, str]]
_lock = threading.Lock()
_failed: set[str] = set()   # asked this run and it didn't answer: don't ask again until restart


def enabled() -> bool:
    from . import llm
    return os.environ.get("VIBECUT_MOMENTS", "1") != "0" and llm.available()


def _mmss(t: float) -> str:
    return f"{int(t // 60)}:{t % 60:04.1f}"


def _key(sid: str, cands: list[Window]) -> str:
    return sid + "|" + ";".join(f"{w.start:.2f}-{w.end:.2f}" for w in cands)


def _cache_path(cid: str) -> Path:
    return indexer.clip_dir(cid) / "moments.json"


def _read_cache(cid: str) -> dict:
    try:
        return json.loads(_cache_path(cid).read_text())
    except (OSError, ValueError):
        return {}


def frames(rec: dict, w: Window) -> list[Path]:
    """The index samples nearest the start, middle and end of a window."""
    s = rec.get("samples") or {}
    times, files = s.get("times") or [], s.get("files") or []
    if not times:
        return []
    inset = min(INSET_S, (w.end - w.start) / 4)
    want = [w.start + inset, (w.start + w.end) / 2, w.end - inset][:FRAMES]
    picked: list[int] = []
    for t in want:
        i = min(range(len(times)), key=lambda j: abs(times[j] - t))
        if i not in picked:
            picked.append(i)
    d = indexer.clip_dir(rec["id"])
    return [d / files[i] for i in picked]


def choose(jobs: list[tuple[dict, str, list[Window]]], ask: Ask | None = None) -> dict[str, tuple[int, str]]:
    """[(clip record, shot id, candidates)] -> {shot id: (index, why)}.

    Only shots Claude actually judged are in the answer; everything else
    keeps candidates[0]. Cached answers are returned without asking."""
    if ask is None:
        if not enabled():
            return {}
        from . import llm
        ask = llm.best_moment
    out: dict[str, tuple[int, str]] = {}
    todo: list[tuple[dict, str, list[Window], str]] = []
    caches: dict[str, dict] = {}
    for rec, sid, cands in jobs:
        if len(cands) < 2:
            continue
        k = _key(sid, cands)
        cache = caches.setdefault(rec["id"], _read_cache(rec["id"]))
        if k in cache:
            out[sid] = (int(cache[k]["best"]), cache[k].get("why", ""))
        elif k not in _failed:
            todo.append((rec, sid, cands, k))

    def one(job: tuple[dict, str, list[Window], str]) -> tuple[str, str, str, tuple[int, str] | None]:
        rec, sid, cands, k = job
        try:
            opts = []
            for w in cands:
                fs = frames(rec, w)
                if not fs:
                    return rec["id"], sid, k, None
                opts.append({"span": f"{_mmss(w.start)}–{_mmss(w.end)}, {w.end - w.start:.0f} s",
                             "frames": [f.read_bytes() for f in fs]})
            best, why = ask(opts)
            return rec["id"], sid, k, (best, why) if 0 <= best < len(cands) else None
        except Exception:  # noqa: BLE001 -- any failure means the rules' pick stands
            return rec["id"], sid, k, None

    if todo:
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            answers = list(ex.map(one, todo))
        with _lock:
            for cid, sid, k, ans in answers:
                if ans is None:
                    _failed.add(k)
                    continue
                out[sid] = ans
                cache = _read_cache(cid)
                cache[k] = {"best": ans[0], "why": ans[1]}
                try:
                    _cache_path(cid).write_text(json.dumps(cache))
                except OSError:
                    pass
    return out

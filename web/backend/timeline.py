"""The storyboard laid out in sequence time, plus the places a cut belongs.

Snap targets are what make the timeline precise without dragging: the
playhead is pulled to moments that already mean something -- a shot
boundary, where motion starts, where the talking stops, a beat of the
music -- instead of to whatever pixel the mouse landed on.

The list is sorted by time and the UI looks it up by binary search. Each
target has a type (which sets how strongly it pulls) and a label, because
snapping the user can't see reads as a bug.
"""

from __future__ import annotations

from typing import Callable

from cutgrammar import music

from . import board as bd

FPS = 30
FRAME = 1 / FPS
# Tie-break when two targets sit within a frame of each other.
PRIORITY = {"shot": 4, "silence": 3, "beat": 2, "motion": 1, "word": 3}


def layout(board: dict | None) -> list[dict]:
    items, t, n = [], 0.0, 0
    for b in (board or {}).get("beats", []):
        for e in b["shots"]:
            d = e["end"] - e["start"]
            gap = bd.is_gap(e)
            if not gap:
                n += 1
            items.append({
                "key": bd.key(e), "kind": "gap" if gap else "shot",
                "shot_id": e.get("id"), "clip_id": None if gap else e["id"].split(":")[0],
                "src_start": e["start"], "src_end": e["end"],
                "seq_start": round(t, 4), "seq_end": round(t + d, 4),
                "beat_id": b["id"], "beat_title": b["title"], "n": None if gap else n,
            })
            t += d
    return items


# --------------------------------------------------------------------------
# target sources -- each returns [{t, type, label}] in sequence time
# --------------------------------------------------------------------------

def shot_targets(items: list[dict], **_) -> list[dict]:
    out = []
    for it in items:
        label = "gap start" if it["kind"] == "gap" else f"shot {it['n']} start"
        out.append({"t": it["seq_start"], "type": "shot", "label": label})
    if items:
        out.append({"t": items[-1]["seq_end"], "type": "shot", "label": "end of edit"})
    return out


MARK_LABEL = {"motion_on": ("motion", "motion onset"), "motion_off": ("motion", "motion stops"),
              "quiet": ("silence", "silence starts"), "sound": ("silence", "sound returns")}


def mark_targets(items: list[dict], clips: dict[str, dict], **_) -> list[dict]:
    """Silence edges and motion onsets from the index, mapped into the edit."""
    out = []
    for it in items:
        if it["kind"] != "shot" or it["clip_id"] not in clips:
            continue
        for m in clips[it["clip_id"]].get("marks", []):
            if it["src_start"] + FRAME < m["t"] < it["src_end"] - FRAME:
                typ, what = MARK_LABEL[m["kind"]]
                approx = f" (±{m['approx']:.1f}s)" if m.get("approx", 0) >= 0.1 else ""
                out.append({"t": round(it["seq_start"] + m["t"] - it["src_start"], 4), "type": typ,
                            "label": f"{what} · shot {it['n']}{approx}"})
    return out


def beat_targets(items: list[dict], track: music.Track | None = None, **_) -> list[dict]:
    """The music's beat grid, if a track is in use and its tempo is reliable."""
    if track is None or not items:
        return []
    out = []
    for k, t in enumerate(music.beat_grid(track, items[-1]["seq_end"])):
        label = f"bar {k // 4 + 1} downbeat" if k % 4 == 0 else f"beat {k % 4 + 1} of 4 · bar {k // 4 + 1}"
        out.append({"t": t, "type": "beat", "label": label})
    return out


# Word boundaries belong here once there's a transcript (a source returning
# {"type": "word", "label": "after “amazing”"}). Transcription isn't built,
# so there is deliberately no word source -- not an empty stub pretending.
SOURCES: list[Callable[..., list[dict]]] = [shot_targets, mark_targets, beat_targets]


def targets(items: list[dict], clips: dict[str, dict], track: music.Track | None) -> list[dict]:
    raw = [x for src in SOURCES for x in src(items, clips=clips, track=track)]
    raw.sort(key=lambda x: (x["t"], -PRIORITY[x["type"]]))
    out: list[dict] = []
    for x in raw:  # within a frame of each other: keep the stronger one
        if out and x["t"] - out[-1]["t"] < FRAME / 2:
            if PRIORITY[x["type"]] > PRIORITY[out[-1]["type"]]:
                out[-1] = x
            continue
        out.append(x)
    return out


def build(board: dict | None, clips: dict[str, dict], track: music.Track | None) -> dict:
    items = layout(board)
    total = items[-1]["seq_end"] if items else 0.0
    grid = None
    if track is not None and track.bpm and (track.meta.get("tempo") or {}).get("phase") is not None:
        grid = {"bpm": track.bpm, "phase": track.meta["tempo"]["phase"]}
    return {"fps": FPS, "total": round(total, 4), "items": items,
            "targets": targets(items, clips, track), "grid": grid}

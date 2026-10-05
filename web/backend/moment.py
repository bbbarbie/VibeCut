"""The paused moment: what the creator is looking at when they stop the preview.

Pausing means something is wrong or should change (sarah, 2026-10-05). So the
chat that opens on pause is about that exact moment: the shot under the
playhead, where it sits in the edit and in its clip, how much of the clip it
uses, what's next to it, the words on screen, and the frame itself. The model
sees all of that with the creator's sentence and answers with operations on
the same storyboard as every other edit (board.py); nothing is applied until
the creator presses Apply, as one undoable turn.

Nothing here calls the model. `estimate` says what one message would cost
before it is sent.
"""

from __future__ import annotations

import base64
from pathlib import Path

from . import timeline

# Claude Opus 5 list prices, $ per million tokens (llm.MODEL); see llm.py.
PRICE_IN, PRICE_OUT = 5.0, 25.0
# What one answer costs to write, with its thinking: JSON ops + a sentence
# or two. A range, because thinking length varies. [prior]
OUT_TOKENS = (600, 2500)
CHARS_PER_TOKEN = 3.5


def _clock(t: float) -> str:
    return f"{int(t // 60)}:{t % 60:04.1f}"


def at(board: dict | None, cat, clips: dict[str, dict], overlays: list[dict], t: float) -> dict | None:
    """The moment under the playhead, or None when nothing is there."""
    items = timeline.layout(board)
    k = next((i for i, it in enumerate(items) if it["seq_start"] <= t < it["seq_end"]), None)
    if k is None and items and abs(t - items[-1]["seq_end"]) < 0.05:
        k = len(items) - 1
    if k is None:
        return None
    it = items[k]
    n = sum(1 for x in items[: k + 1] if x["kind"] == "shot")

    def brief(x: dict | None) -> dict | None:
        if not x:
            return None
        if x["kind"] == "gap":
            return {"key": x["key"], "gap": True, "length": round(x["seq_end"] - x["seq_start"], 2)}
        s = cat.shots.get(x["shot_id"])
        return {"key": x["key"], "clip": s.clip_name if s else x["clip_id"],
                "labels": sorted(s.labels, key=lambda l: -s.labels[l])[:5] if s else [],
                "length": round(x["seq_end"] - x["seq_start"], 2)}

    m = {"t": round(t, 3), "key": it["key"], "part": it["beat_title"], "n": n if it["kind"] == "shot" else None,
         "gap": it["kind"] == "gap", "in_shot": round(t - it["seq_start"], 2),
         "length": round(it["seq_end"] - it["seq_start"], 2),
         "before": brief(items[k - 1] if k else None), "after": brief(items[k + 1] if k + 1 < len(items) else None),
         "words": [{"id": o["id"], "kind": o["kind"], "text": o["text"], "sub": o.get("sub", ""),
                    "placed": bool(o.get("place"))}
                   for o in overlays if o["start"] <= t < o["shown_end"] and o["kind"] != "chapters"]}
    if it["kind"] == "shot":
        s = cat.shots.get(it["shot_id"])
        rec = clips.get(it["clip_id"]) or {}
        src = it["src_start"] + (t - it["seq_start"])
        m.update({"clip": s.clip_name if s else rec.get("name", it["clip_id"]), "clip_id": it["clip_id"],
                  "src_t": round(src, 2), "uses": [round(it["src_start"], 2), round(it["src_end"], 2)],
                  "clip_length": round(float(rec.get("duration") or 0), 2),
                  "labels": sorted(s.labels, key=lambda l: -s.labels[l])[:8] if s else [],
                  "faces": s.faces if s else 0, "frame": _frame(rec, src)})
    return m


def _frame(rec: dict, src: float) -> str | None:
    """The index sample nearest the paused time: what the creator sees, small."""
    smp = rec.get("samples") or {}
    times, files = smp.get("times") or [], smp.get("files") or []
    if not times or not files:
        return None
    from .indexer import clip_dir
    i = min(range(min(len(times), len(files))), key=lambda j: abs(times[j] - src))
    p = clip_dir(rec["id"]) / files[i]
    return str(p) if p.exists() else None


def header(m: dict) -> str:
    """'Shot 12 · 0:34 · IMG_4492' -- what the chat box is pinned to."""
    if m["gap"]:
        return f"Empty space · {_clock(m['t'])}"
    return f"Shot {m['n']} · {_clock(m['t'])} · {m['clip']}"


def describe(m: dict) -> str:
    """The moment as text for the model, next to the edit's state."""
    lines = [f"PAUSED AT {_clock(m['t'])} in the edit. The creator stopped here because something "
             f"should change at this moment; read their message as about this shot unless they say otherwise."]
    if m["gap"]:
        lines.append(f"Under the playhead: an empty space (entry {m['key']}), {m['length']} s long, in part “{m['part']}”.")
    else:
        lines.append(f"Under the playhead: shot {m['n']} (entry {m['key']}) in part “{m['part']}”, {m['in_shot']} s "
                     f"into it; it is {m['length']} s long and uses {m['uses'][0]}–{m['uses'][1]} s of "
                     f"{m['clip']} (clip {m['clip_length']} s); the paused frame is {m['src_t']} s into the clip.")
        if m["labels"]:
            lines.append(f"In the shot: {', '.join(m['labels'])}" + (f"; {m['faces']} face(s)" if m["faces"] else "") + ".")
    for side in ("before", "after"):
        x = m[side]
        if x:
            what = "an empty space" if x.get("gap") else f"{x['clip']} ({', '.join(x['labels'][:3]) or 'no labels'})"
            lines.append(f"{'Before' if side == 'before' else 'After'} it: entry {x['key']}, {what}, {x['length']} s.")
    if m["words"]:
        lines.append("On screen now: " + "; ".join(
            f"{w['kind']} {w['id']} “{w['text']}”" + (f" / “{w['sub']}”" if w["sub"] else "")
            + (" (placed by hand)" if w["placed"] else "") for w in m["words"]) + ".")
    else:
        lines.append("No words on screen at this moment.")
    if m.get("frame"):
        lines.append("The attached image is the paused frame.")
    return "\n".join(lines)


def image(m: dict) -> str | None:
    p = m.get("frame")
    if not p:
        return None
    try:
        return base64.b64encode(Path(p).read_bytes()).decode()
    except OSError:
        return None


def estimate(prompt_chars: int, with_image: bool) -> dict:
    """Dollars for one message: input from its size, output as a range."""
    tin = prompt_chars / CHARS_PER_TOKEN + (384 * 216 / 750 if with_image else 0)
    lo, hi = (tin * PRICE_IN + o * PRICE_OUT for o in OUT_TOKENS)
    return {"tokens_in": int(tin), "usd": [round(lo / 1e6, 3), round(hi / 1e6, 3)]}

"""The polish page's server side: one finished video, the creator pointing at it.

Open a finished edit (a file on this Mac), read it once (polish.probe: cuts,
movement, beat; on-device Vision for face boxes where it exists), then each
"click + sentence" becomes operations on the layers (polish.timeline), laid
out by polish.layout against the faces and the safe area. Nothing here edits
the storyboard, cuts footage, picks music or renders a file.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from polish import anchor as an
from polish import layout, parse, probe, recipe, snap, timeline

from . import indexer, llm, vision

router = APIRouter(prefix="/api/polish")
DIR = indexer.CACHE / "polish"
BOOK = recipe.Book(Path(os.environ.get("VIBECUT_RECIPES", str(DIR / "recipes.json"))))
VIDEO_EXT = {".mp4", ".mov", ".m4v"}
LOCK = threading.RLock()

# The one video being polished, and its layers.
P: dict = {"path": None, "probe": None, "faces": None, "job": "none", "error": None, "session": None}


def _default_recipe() -> recipe.Recipe:
    return BOOK.default() or recipe.Recipe(name="Default").check()


# --------------------------------------------------------------------------
# reading the video
# --------------------------------------------------------------------------

def _faces(path: str) -> list[dict] | None:
    """Face boxes per sampled second, top-left origin, or None where the
    on-device detector doesn't exist (the face rule then says 'not checked')."""
    hit = DIR / f"{probe.key(path)}.faces.json"
    if hit.exists():
        return json.loads(hit.read_text())
    if vision.ensure_built() is None:
        return None
    rec = indexer.index_clip(path)                      # the index's samples, decoded once
    d = indexer.clip_dir(rec["id"])
    files = [str(d / f) for f in rec["samples"]["files"]]
    found = vision.faces(files)
    out = []
    for t, f in zip(rec["samples"]["times"], files):
        # Vision's boxes have their origin bottom-left; layout's top-left
        out.append({"t": t, "boxes": [[b[0], round(1 - b[1] - b[3], 4), b[2], b[3]] for b in found.get(f, [])]})
    hit.write_text(json.dumps(out))
    return out


def faces_between(t0: float, t1: float) -> list[list[float]] | None:
    fs = P["faces"]
    if fs is None:
        return None
    return [b for s in fs if t0 - 0.5 <= s["t"] <= t1 + 0.5 for b in s["boxes"]]


def _placer(state: dict) -> dict:
    pr = P["probe"]
    if not pr:
        return {}
    W, H = pr["width"], pr["height"]
    return {c["id"]: layout.place(c["text"], recipe.from_dict(c["recipe"]), W, H,
                                  faces_between(c["t"], c["t"] + c["dur"]), c["scale"]).public(W, H)
            for c in state["captions"]}


def _analyse(path: str) -> None:
    try:
        pr = probe.analyse(path, DIR)
        faces = _faces(path)
        with LOCK:
            if P["path"] == path:
                P.update(probe=pr, faces=faces, job="ready")
    except Exception as e:  # noqa: BLE001 -- shown to the creator verbatim
        with LOCK:
            if P["path"] == path:
                P.update(job="error", error=str(e)[:300])


class OpenReq(BaseModel):
    path: str


@router.post("/open")
def open_video(req: OpenReq) -> dict:
    path = os.path.expanduser(req.path)
    if not os.path.isfile(path) or Path(path).suffix.lower() not in VIDEO_EXT:
        raise HTTPException(400, "Open a finished video: an .mp4 or .mov file on this Mac.")
    with LOCK:
        P.update(path=path, probe=None, faces=None, job="reading", error=None,
                 session=timeline.Session(placer=_placer))
    threading.Thread(target=_analyse, args=(path,), daemon=True).start()
    return state()


# --------------------------------------------------------------------------
# state
# --------------------------------------------------------------------------

@router.get("")
def state() -> dict:
    with LOCK:
        s = P["session"]
        pr = P["probe"]
        placed = _placer(s.state) if s and pr else {}
        return {
            "job": P["job"], "error": P["error"],
            "video": None if not P["path"] else {
                "name": Path(P["path"]).name, "url": "/api/polish/video",
                **({k: pr[k] for k in ("duration", "fps", "width", "height", "cuts", "bpm")} if pr else {})},
            "faces": P["faces"] is not None,
            "captions": [{**c, "place": placed.get(c["id"])} for c in (s.state["captions"] if s else [])],
            "effects": s.state["effects"] if s else [],
            "turns": [{"id": t.id, "said": t.said, "anchor": t.anchor, "reply": t.reply, "lines": t.lines,
                       "skipped": t.skipped, "undone": t.undone, "has_ops": bool(t.ops)} for t in (s.turns if s else [])],
            "recipe": _default_recipe().public(),
            "recipes": [r.public() for r in BOOK.load()],
            "system_fonts": list(recipe.SYSTEM_FAMILIES),
            "llm": llm.available(),
        }


@router.get("/video")
def video() -> FileResponse:
    if not P["path"]:
        raise HTTPException(404)
    return FileResponse(P["path"], media_type="video/mp4")


@router.get("/font")
def font(name: str) -> FileResponse:
    """A font file the creator pointed a recipe at -- only those, nothing else on disk."""
    hit = next((r for r in BOOK.load() if r.name == name and r.font_file), None)
    if hit is None or not os.path.isfile(hit.font_file):
        raise HTTPException(404)
    return FileResponse(hit.font_file)


# --------------------------------------------------------------------------
# the one interaction: here + a sentence
# --------------------------------------------------------------------------

class SayReq(BaseModel):
    t: float
    x: float
    y: float
    text: str


@router.post("/say")
def say(req: SayReq) -> dict:
    with LOCK:
        pr, s = P["probe"], P["session"]
        if not pr or not s:
            raise HTTPException(409, "Open a finished video first — it's still being read." if P["path"] else
                                "Open a finished video first.")
        a = an.make(req.t, req.x, req.y, pr["cuts"], pr["fps"], pr["duration"]).public()
        beats = snap.beats(pr["bpm"], pr["phase"], pr["duration"])
        rec = _default_recipe().public()
        out = parse.parse(req.text, a, s.state, rec, pr["onsets"], beats)
        if out.get("none") and llm.available():
            out = _ask_model(req.text, a, s.state, rec, pr, beats)
        if out.get("none"):
            raise HTTPException(409, "Here I can write words (“写上「…」”), add a boom, make words bigger or "
                                     "smaller, change or remove them, or put your recipe on them.")
        if out.get("ask"):
            raise HTTPException(409, out["ask"])
        if out.get("action") == "save_recipe":
            cap = next(c for c in s.state["captions"] if c["id"] == out["id"])
            saved = recipe.from_caption(cap, cap["recipe"]["name"] if cap["recipe"]["name"] != "Default" else "My captions")
            BOOK.save(saved)
            s.add(req.text, a, [], reply=f"Saved as your recipe “{saved.name}” — new words will use it.")
            return state()
        s.add(req.text, a, out["ops"], reply=out.get("reply", ""))
        return state()


@router.post("/turns/{tid}/toggle")
def toggle(tid: int) -> dict:
    with LOCK:
        if not P["session"]:
            raise HTTPException(409, "nothing open")
        P["session"].toggle(tid)
        return state()


class UseReq(BaseModel):
    name: str


@router.post("/recipe/use")
def recipe_use(req: UseReq) -> dict:
    try:
        BOOK.use(req.name)
    except recipe.RecipeError as e:
        raise HTTPException(400, str(e)) from e
    return state()


class EditReq(BaseModel):
    fields: dict


@router.post("/recipe/edit")
def recipe_edit(req: EditReq) -> dict:
    """Change the recipe new words use (e.g. point it at a font file on this
    Mac). Saved as a new version; captions already placed keep theirs until
    'use my recipe' is said on them."""
    cur = _default_recipe().public()
    try:
        r = recipe.from_dict({**cur, **req.fields, "saved": cur["saved"]})
    except (recipe.RecipeError, TypeError, ValueError) as e:
        raise HTTPException(400, str(e)) from e
    if r.name == "Default":
        r.name = "My captions"
    BOOK.save(r)
    return state()


# --------------------------------------------------------------------------
# a sentence no rule understood: ask the model for operations (key only)
# --------------------------------------------------------------------------

SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["reply", "ops"],
    "properties": {
        "reply": {"type": "string"},
        "ops": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["op", "id", "text", "scale"],
            "properties": {
                "op": {"type": "string", "enum": ["add_caption", "edit_caption", "drop_caption", "add_effect", "drop_effect"]},
                "id": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                "text": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                "scale": {"anyOf": [{"type": "number"}, {"type": "null"}]},
            }}},
    },
}
SYSTEM = """You turn one sentence a video creator says while pointing at a moment of their finished video into operations on its layers (words on screen and "boom" effects). The creator clicked at the time given as ANCHOR; "here", "this", "这里", "这段" mean that moment and the caption on screen there. Use only ids from LAYERS. Change only what was asked.
- add_caption {text}: words at the anchor, in the creator's recipe. Only words the creator said; never invent.
- edit_caption {id, text | scale}: new words, or size (scale 1.2 = bigger, 0.83 = smaller).
- drop_caption {id} / drop_effect {id}
- add_effect {}: a boom at the anchor.
If it isn't one of these, return no ops and say in `reply` what you can do. `reply` is one short sentence."""


def _ask_model(said: str, a: dict, st: dict, rec: dict, pr: dict, beats: list[float]) -> dict:
    import anthropic
    layers = "\n".join([f"caption {c['id']} {c['t']:.2f}-{c['t'] + c['dur']:.2f}s “{c['text']}”" for c in st["captions"]]
                       + [f"effect {e['id']} boom at {e['t']:.2f}s" for e in st["effects"]]) or "none"
    try:
        resp = llm.client().beta.messages.create(
            model=llm.MODEL, max_tokens=2000, betas=["server-side-fallback-2026-07-01"], fallbacks="default",
            system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": f"ANCHOR: {a['t']:.2f}s\nLAYERS:\n{layers}\n\nCREATOR: {said}"}],
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}})
        out = json.loads(next((b.text for b in resp.content if b.type == "text"), "{}"))
    except (anthropic.APIError, json.JSONDecodeError) as e:
        return {"ask": f"Couldn't read that sentence: {e}"}
    ops = []
    for o in out.get("ops", []):
        k = o.get("op")
        if k == "add_caption" and o.get("text"):
            ops.append({"op": k, "text": o["text"], "anchor": a, "recipe": rec})
        elif k == "edit_caption" and o.get("id"):
            ops.append({"op": k, "id": o["id"], **({"text": o["text"]} if o.get("text") else {}),
                        **({"scale": o["scale"]} if o.get("scale") else {})})
        elif k in ("drop_caption", "drop_effect") and o.get("id"):
            ops.append({"op": k, "id": o["id"]})
        elif k == "add_effect":
            t, why = snap.snap(a["t"], pr["onsets"], beats)
            ops.append({"op": k, "kind": "boom", "anchor": a, "t": t, "why": why})
    if not ops:
        return {"ask": out.get("reply") or "I didn't catch what to do here."}
    return {"ops": ops, "reply": out.get("reply", "")}

"""VibeCut local server. Footage never leaves this machine; with a key set,
the storyboard *text* goes to the chat model (see llm.py).

    python -m web.backend            # from the repo root; serves :8765
"""

from __future__ import annotations

import os
import threading
import uuid
from pathlib import Path
from urllib.parse import unquote

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import board as bd
from . import cut, indexer, llm, locate, musiclib, storyboard, timeline, vision, voiceover
from .preferences import PreferenceError, Preferences
from .workflow import Workflow, WorkflowError

@asynccontextmanager
async def lifespan(_: FastAPI):
    # Compiling the Vision helper takes ~30s the first time ever; do it now,
    # not when the first folder lands. Same for spinning up the workers.
    threading.Thread(target=vision.ensure_built, daemon=True).start()
    indexer.pool()
    if musiclib.load_setting() and os.path.isdir(musiclib.load_setting()):
        musiclib.set_folder(musiclib.load_setting())
    yield


app = FastAPI(title="VibeCut", docs_url="/api/docs", lifespan=lifespan)

# The one project: whatever has been dropped in this session, the working
# storyboard's turn log, and the shelf catalogue the ops resolve against.
CLIPS: dict[str, dict] = {}
VISION_USED = {"value": False}
SESSION = bd.Session()
CATALOG = {"cat": bd.Catalog({}, {})}
LOCK = threading.RLock()
# The rough cut (reject + trim) and where the edit stands relative to its gate.
PLAN: dict = {"plan": None}
WORKFLOW = Workflow()
# What the creator's edits have taught -- only what they confirmed.
PREFS = Preferences(indexer.CACHE / "preferences.json")


def _make_proposals(direction: dict) -> dict:
    lean = None if direction.get("keywords") else (direction.get("themes", []), direction.get("labels", []))
    return storyboard.build(list(CLIPS.values()), direction.get("text", ""),
                            vision=VISION_USED["value"], lean=lean, cut=cut.for_story(PLAN["plan"]),
                            voiceover=direction.get("voiceover"))


def _direction() -> dict | None:
    """The direction the proposals are currently built from."""
    for t in reversed(SESSION.turns):
        if t.direction is not None and not t.undone:
            return t.direction
    return None


def _lean_labels() -> set[str]:
    for t in reversed(SESSION.turns):
        if t.direction is not None and not t.undone:
            return set(t.direction.get("labels", []))
    return set()


def _session() -> dict:
    """Everything the UI renders: the board (enriched for display), the log, proposals."""
    cat = CATALOG["cat"]
    lean = _lean_labels()

    def shot(e: dict) -> dict:
        if bd.is_gap(e):
            return {**e, "key": bd.key(e), "clip_id": None, "thumb": "", "src_start": 0,
                    "src_end": e["end"], "lean": False}
        s = cat.shots.get(e["id"])
        return {**e, "key": bd.key(e), "clip_id": s.clip_id if s else e["id"].split(":")[0],
                "thumb": s.thumb if s else "", "src_start": s.start if s else e["start"],
                "src_end": s.end if s else e["end"],
                "lean": bool(s and lean and any(s.labels.get(l, 0) >= 0.2 for l in lean))}

    b = SESSION.board
    board = None if b is None else {
        **{k: b[k] for k in ("option", "name", "structure")},
        "beats": [{**bt, "shots": [shot(x) for x in bt["shots"]]} for bt in b["beats"]],
    }
    last = SESSION.last_active()
    ghosts = []
    if last and last.diff and not last.diff["replaced"]:
        # What the latest turn removed, so the board can show it struck through.
        prev = _board_before(last)
        for r in last.diff["beats"]["removed"]:
            old = next((x for x in (prev or {}).get("beats", []) if x["id"] == r["id"]), None)
            idx = [x["id"] for x in (prev or {}).get("beats", [])].index(r["id"]) if old else 0
            ghosts.append({"index": idx, "title": r["title"],
                           "thumbs": [cat.shots[x["id"]].thumb for x in (old or {}).get("shots", [])
                                      if x["id"] in cat.shots]})
    return {
        "board": board,
        "structure_note": _structure_note(b),
        "last": {"turn": last.id, "diff": last.diff, "ghosts": ghosts} if last else None,
        "turns": [{
            "id": t.id, "kind": t.kind, "text": t.text, "reply": t.reply, "question": t.question,
            "choices": t.choices, "lines": _with_thumbs(t.lines, cat), "skipped": t.skipped,
            "undone": t.undone, "at": t.at, "has_ops": bool(t.ops) or t.direction is not None,
            "direction": {k: t.direction[k] for k in ("themes",) if k in t.direction} if t.direction else None,
        } for t in SESSION.turns],
        "proposals": SESSION.proposals,
        "llm": llm.available(),
        "timeline": timeline.build(b, CLIPS, musiclib.current()),
        "workflow": WORKFLOW.public(),
        "cut": cut.summary(PLAN["plan"]) if PLAN["plan"] else None,
        "music": musiclib.current_public(),
        "preferences": PREFS.public(SESSION),
        "voiceover": _voiceover_public(),
    }


def _voiceover_public() -> dict | None:
    v = (_direction() or {}).get("voiceover")
    return None if not v else {"source": v["source"], "timing": v["timing"],
                               "lines": len(v["lines"]), "total": v["total"]}


def _board_before(turn: bd.Turn) -> dict | None:
    """Replay up to (not including) `turn` -- cheap, the log is short."""
    sub = bd.Session()
    sub.turns = [t for t in SESSION.turns if t.id < turn.id]
    sub.replay(CATALOG["cat"], _make_proposals)
    return sub.board


def _structure_note(b: dict | None) -> str | None:
    if not b:
        return None
    edits = sum(1 for t in SESSION.turns if not t.undone and t.ops
                and not any(o.get("op") == "choose_option" for o in t.ops))
    return b["structure"] + (f" Edited {edits}×." if edits else "")


def _with_thumbs(lines: list[dict], cat: bd.Catalog) -> list[dict]:
    out = []
    for l in lines:
        l = dict(l)
        if l.get("shot") and l["shot"] in cat.shots:
            l["thumb"] = cat.shots[l["shot"]].thumb
        out.append(l)
    return out


def _refresh_catalog() -> None:
    CATALOG["cat"] = bd.Catalog.from_clips(list(CLIPS.values()))
    SESSION.replay(CATALOG["cat"], _make_proposals)


def _public_clip(c: dict) -> dict:
    return {
        **{k: c[k] for k in ("id", "name", "duration", "width", "height", "capture_time",
                             "gps", "sampling", "index_seconds")},
        "video": f"/api/video/{c['id']}",
        "cut": _cut_of(c["id"]),
        "shots": [{
            "id": f"{c['id']}:{s['index']}", "index": s["index"], "start": s["start"],
            "end": s["end"], "best_t": s["best_t"], "quality": s["quality"],
            "aesthetic": s.get("aesthetic"), "labels": s.get("labels", [])[:4],
            "faces": s.get("faces", 0), "utility": s.get("utility"),
            "thumb": f"/api/thumbs/{c['id']}/{s['thumb']}",
        } for s in c["shots"]],
    }


def _cut_of(cid: str) -> dict | None:
    """What the rough cut decided about a clip: shown on the shelf, with its reason."""
    p = PLAN["plan"]
    d = p.clips.get(cid) if p else None
    if not d:
        return None
    return {"rejected": d["rejected"], "auto_rejected": d["auto_rejected"], "zh": d["zh"], "en": d["en"],
            "override": d["override"], "flags": d["flags"],
            "windows": {sid: s["use"] for sid, s in d["shots"].items()}}


def _project() -> dict:
    clips = sorted(CLIPS.values(), key=lambda c: (storyboard.parse_when(c.get("capture_time"))
                                                  or storyboard.datetime.max, c["name"]))
    return {"clips": [_public_clip(c) for c in clips], "vision": vision.status()}


# --------------------------------------------------------------------------
# import
# --------------------------------------------------------------------------

class LocateReq(BaseModel):
    files: list[dict]


@app.post("/api/locate")
def api_locate(req: LocateReq) -> dict:
    return locate.resolve(req.files, known=[c["path"] for c in CLIPS.values()])


UPLOADS = indexer.CACHE / "uploads"


@app.post("/api/upload")
async def api_upload(request: Request) -> dict:
    """Raw-body upload of one file the locator couldn't find on disk."""
    rel = unquote(request.headers.get("x-relpath", ""))
    batch = request.headers.get("x-batch", "default")
    name = Path(rel).name
    if Path(name).suffix.lower() not in indexer.VIDEO_EXT:
        raise HTTPException(400, "only .mp4 / .mov")
    d = UPLOADS / "".join(ch for ch in batch if ch.isalnum())[:32]
    d.mkdir(parents=True, exist_ok=True)
    dest = d / uuid.uuid4().hex[:8] / name  # keep the creator's file name
    dest.parent.mkdir()
    with open(dest, "wb") as fh:
        async for chunk in request.stream():
            fh.write(chunk)
    return {"path": str(dest)}


class ImportReq(BaseModel):
    paths: list[str] = []
    folder: str | None = None


@app.post("/api/import")
def api_import(req: ImportReq) -> dict:
    paths = list(req.paths)
    if req.folder:
        if not os.path.isdir(req.folder):
            raise HTTPException(400, f"not a folder: {req.folder}")
        paths += indexer.find_videos(req.folder)
    paths = [p for p in dict.fromkeys(paths)
             if os.path.isfile(p) and Path(p).suffix.lower() in indexer.VIDEO_EXT]
    if not paths:
        raise HTTPException(400, "no .mp4 or .mov files")
    # Adding to a session: only what isn't on the shelf already gets indexed.
    fresh = [p for p in paths if indexer.clip_id(p) not in CLIPS]

    def done(job: indexer.Job) -> None:
        with LOCK:
            for c in job.clips:
                CLIPS[c["id"]] = c
            VISION_USED["value"] = vision.status() == "ready"
            _refresh_catalog()
            # Stage 1 + 2: reject and trim, then stop at the gate for a person.
            PLAN["plan"] = cut.compute(CLIPS, PLAN["plan"])
            if WORKFLOW.state in ("intake", "indexing"):
                if WORKFLOW.state == "intake":
                    WORKFLOW.advance("indexing", f"{len(job.clips)} clips indexed")
                WORKFLOW.advance("rough-cut", "reject + trim computed")
                WORKFLOW.advance("cut-review", cut.summary(PLAN["plan"])["line_en"])
            elif job.clips:
                WORKFLOW.reopen("system", f"{len(job.clips)} new clip(s) to review")
            SESSION.replay(CATALOG["cat"], _make_proposals)

    return indexer.start(fresh, done, known=len(paths) - len(fresh)).public()


@app.get("/api/jobs/{job_id}")
def api_job(job_id: str) -> dict:
    job = indexer.JOBS.get(job_id)
    if not job:
        raise HTTPException(404)
    return job.public()


@app.get("/api/project")
def api_project() -> dict:
    return _project()


@app.delete("/api/project")
def api_clear() -> dict:
    global SESSION, WORKFLOW
    with LOCK:
        CLIPS.clear()
        SESSION = bd.Session()
        PREFS.new_project()
        WORKFLOW = Workflow()
        PLAN["plan"] = None
        _refresh_catalog()
    return _project()


# --------------------------------------------------------------------------
# storyboards
# --------------------------------------------------------------------------

class ChatReq(BaseModel):
    message: str


@app.get("/api/session")
def api_session() -> dict:
    with LOCK:
        return _session()


@app.post("/api/chat")
def api_chat(req: ChatReq) -> dict:
    """One conversational turn: message -> operations -> applied, diffed, undoable."""
    msg = req.message.strip()
    if not msg:
        raise HTTPException(400, "empty message")
    if not CLIPS:
        raise HTTPException(400, "drop some clips in first")
    if WORKFLOW.state not in ("story", "styling"):
        # The gate: nothing is built on the rough cut until a person has seen it.
        raise HTTPException(409, "Look over what was cut first — approve it, then we’ll build the story.")
    with LOCK:
        cat = CATALOG["cat"]
        try:
            out = (llm.interpret if llm.available() else llm.interpret_offline)(
                msg, cat, SESSION, PREFS.for_model())
        except llm.LLMError as e:
            raise HTTPException(502, str(e)) from e
        if out.get("error"):
            raise HTTPException(409, out["error"])
        direction = out.get("direction")
        if direction is not None:
            direction = {**direction, "text": msg}
            # A new description of the video keeps the voiceover it's told over.
            vo = (_direction() or {}).get("voiceover")
            if vo:
                direction["voiceover"] = vo
        SESSION.add({"kind": "chat", "text": msg, "ops": out.get("ops", []),
                     "reply": out.get("reply", ""), "question": out.get("question"),
                     "choices": out.get("choices", []) if out.get("question") else [],
                     "direction": direction}, cat, _make_proposals)
        return _session()


# --------------------------------------------------------------------------
# the creator's voiceover as the spine (opt-in)
# --------------------------------------------------------------------------

class VoiceoverReq(BaseModel):
    text: str


@app.post("/api/voiceover")
def api_voiceover(req: VoiceoverReq) -> dict:
    """Subtitles or a script -> a fourth proposal that follows it. Recorded
    as a turn, so Undo takes it away again."""
    if not CLIPS:
        raise HTTPException(400, "drop some clips in first")
    if WORKFLOW.state not in ("story", "styling"):
        raise HTTPException(409, "Look over what was cut first — approve it, then we’ll build the story.")
    script = voiceover.parse(req.text)
    if not script["lines"]:
        raise HTTPException(400, "no lines found — paste subtitles (.srt) or the script itself")
    with LOCK:
        cur = {k: v for k, v in (_direction() or {"text": ""}).items() if k != "voiceover"}
        what = "from subtitles" if script["timing"] == "estimated" else "timed from the words"
        SESSION.add({"kind": "direct", "text": f"Voiceover: {len(script['lines'])} lines, {what}",
                     "ops": [], "direction": {**cur, "voiceover": script}}, CATALOG["cat"], _make_proposals)
        return _session()


# --------------------------------------------------------------------------
# what edits teach: candidates, sorted only by the creator
# --------------------------------------------------------------------------

class ClassifyReq(BaseModel):
    turn: int
    klass: str
    rule: str = ""
    scope: str = ""
    counter: str = ""
    reason: str = ""


@app.post("/api/preferences/classify")
def api_pref_classify(req: ClassifyReq) -> dict:
    with LOCK:
        try:
            PREFS.classify(SESSION, req.turn, req.klass, "user", req.rule, req.scope, req.counter, req.reason)
        except PreferenceError as e:
            raise HTTPException(400, str(e)) from e
        return _session()


@app.post("/api/preferences/{rid}/{action}")
def api_pref_change(rid: str, action: str) -> dict:
    with LOCK:
        try:
            if action == "forget":
                PREFS.revoke(rid, "user")
            elif action == "narrow":
                PREFS.narrow(rid, "user")
            else:
                raise HTTPException(404)
        except PreferenceError as e:
            raise HTTPException(400, str(e)) from e
        return _session()


# --------------------------------------------------------------------------
# the rough cut and its gate
# --------------------------------------------------------------------------

@app.get("/api/cut")
def api_cut() -> dict:
    with LOCK:
        p = PLAN["plan"]
        return {"workflow": WORKFLOW.public(), "summary": cut.summary(p) if p else None,
                "clips": list(p.clips.values()) if p else []}


class OverrideReq(BaseModel):
    target: str          # clip id, or shot id "clip:index"
    action: str          # keep | reject | full | longer | shorter | auto


@app.post("/api/cut/override")
def api_cut_override(req: OverrideReq) -> dict:
    with LOCK:
        if not PLAN["plan"]:
            raise HTTPException(400, "nothing to override yet")
        try:
            PLAN["plan"] = cut.override(PLAN["plan"], req.target, req.action, CLIPS)
        except (ValueError, KeyError) as e:
            raise HTTPException(400, str(e)) from e
        WORKFLOW.revise("user", f"{req.action} {req.target}")
        SESSION.replay(CATALOG["cat"], _make_proposals)
    return api_cut()


@app.post("/api/cut/approve")
def api_cut_approve() -> dict:
    with LOCK:
        try:
            WORKFLOW.approve("user", cut.summary(PLAN["plan"])["line_en"] if PLAN["plan"] else "")
        except WorkflowError as e:
            raise HTTPException(409, str(e)) from e
        SESSION.replay(CATALOG["cat"], _make_proposals)
        return _session()


class OpsReq(BaseModel):
    ops: list[dict]
    label: str


@app.post("/api/ops")
def api_ops(req: OpsReq) -> dict:
    """Direct manipulation (Apply, timeline drag/delete) -- same log, same undo."""
    with LOCK:
        SESSION.add({"kind": "direct", "text": req.label, "ops": req.ops},
                    CATALOG["cat"], _make_proposals)
        return _session()


@app.post("/api/turns/{tid}/toggle")
def api_toggle(tid: int) -> dict:
    with LOCK:
        SESSION.toggle(tid, CATALOG["cat"], _make_proposals)
        return _session()


# --------------------------------------------------------------------------
# music: tracks from the creator's own folder that fit the storyboard's shape
# --------------------------------------------------------------------------

class MusicFolderReq(BaseModel):
    folder: str | None


@app.post("/api/music/folder")
def api_music_folder(req: MusicFolderReq) -> dict:
    try:
        return musiclib.set_folder(req.folder)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


class MusicUseReq(BaseModel):
    track_id: str | None


@app.post("/api/music/use")
def api_music_use(req: MusicUseReq) -> dict:
    """Put a track under the edit -- its beat grid becomes snap targets."""
    try:
        musiclib.use(req.track_id)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    with LOCK:
        return _session()


@app.get("/api/music/suggest")
def api_music_suggest() -> dict:
    with LOCK:
        return musiclib.suggest(SESSION.board, CATALOG["cat"])


@app.get("/api/music/audio/{track_id}")
def api_music_audio(track_id: str) -> FileResponse:
    p = musiclib.path_for(track_id)  # only files from the chosen folder
    if not p:
        raise HTTPException(404)
    return FileResponse(p)


# --------------------------------------------------------------------------
# local media -- only files that are in the index, nothing else on disk
# --------------------------------------------------------------------------

@app.get("/api/video/{clip_id}")
def api_video(clip_id: str) -> FileResponse:
    c = CLIPS.get(clip_id)
    if not c:
        raise HTTPException(404)
    # Chrome plays HEVC/H.264 .mov happily when told it's mp4.
    return FileResponse(c["path"], media_type="video/mp4")


@app.get("/api/thumbs/{clip_id}/{name}")
def api_thumb(clip_id: str, name: str) -> FileResponse:
    if clip_id not in CLIPS or "/" in name or not name.endswith(".jpg"):
        raise HTTPException(404)
    p = indexer.clip_dir(clip_id) / name
    if not p.exists():
        raise HTTPException(404)
    return FileResponse(p, media_type="image/jpeg",
                        headers={"Cache-Control": "public, max-age=31536000, immutable"})


DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if DIST.exists():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="ui")

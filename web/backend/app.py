"""VibeCut local server. Footage never leaves this machine; with a key set,
the storyboard *text* goes to the chat model (see llm.py).

    python -m web.backend            # from the repo root; serves :8765
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import unquote

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import board as bd
from . import projects as pj
from . import audiomix, brief, cut, export, looks, pitch, seams, smooth, indexer, llm, locate, musiclib, overlays, reference, remix, speech, storyboard, talk, timeline, vision, voiceover
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
    # The project that was open last time is open again, as it was left.
    last = pj.open_id()
    if last:
        try:
            _open_project(last)
        except pj.ProjectError:
            pj.set_open(None)
    yield


app = FastAPI(title="VibeCut", docs_url="/api/docs", lifespan=lifespan)

# The open project: whatever has been dropped into it, the working
# storyboard's turn log, and the shelf catalogue the ops resolve against.
# Everything here is rebuilt from the project's record (projects.py) and
# the per-file index cache; nothing lives only in memory.
PROJECT: dict = {"p": None}
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


def _open_project(pid: str) -> pj.Project:
    """Make `pid` the open project: its clips from the cache, its log
    replayed, its gate where it was left."""
    global SESSION, WORKFLOW
    pr = pj.load(pid)
    with LOCK:
        clips, missing = pj.restore_clips(pr)
        CLIPS.clear()
        CLIPS.update(clips)
        VISION_USED["value"] = vision.status() == "ready" and any(
            s.get("labels") for c in CLIPS.values() for s in c["shots"])
        SESSION = pj.restore_session(pr)
        WORKFLOW = pj.restore_workflow(pr)
        PREFS.new_project()
        pj.restore_prefs(pr, PREFS)
        old = cut.Plan(overrides=dict(pr.cut_overrides), targets=dict(pr.cut_targets),
                       windows=dict(pr.cut_windows))
        PLAN["plan"] = cut.compute(CLIPS, old) if CLIPS else None
        # A project whose files went missing since it was saved says so on
        # the footage screen; it never pretends they are there.
        if missing:
            pr.import_errors = missing + [e for e in pr.import_errors
                                          if e.get("path") not in {m["path"] for m in missing}]
        if not CLIPS and WORKFLOW.state != "intake":
            WORKFLOW = Workflow()
        PROJECT["p"] = pr
        _refresh_catalog()
    pj.set_open(pid)
    return pr


def _close_project() -> None:
    global SESSION, WORKFLOW
    with LOCK:
        PROJECT["p"] = None
        CLIPS.clear()
        SESSION = bd.Session()
        WORKFLOW = Workflow()
        PLAN["plan"] = None
        PREFS.new_project()
        _refresh_catalog()
    pj.set_open(None)


def _save() -> None:
    """The open project, as it stands, to disk. Cheap; called after every change."""
    pr = PROJECT["p"]
    if pr is None:
        return
    with LOCK:
        pj.capture(pr, CLIPS, SESSION, WORKFLOW, PLAN["plan"], PREFS)
    pj.save(pr)


def _meta() -> dict | None:
    pr = PROJECT["p"]
    return None if pr is None else pr.summary(CLIPS, SESSION.board)


def _capabilities() -> dict:
    """What this machine can do, so the UI says so instead of failing later."""
    return {
        "llm": llm.available(),
        "speech": sys.platform == "darwin" and shutil.which("swiftc") is not None,
        "vision": vision.status(),
        "links": reference.ytdlp() is not None,
        "music_folder": musiclib.STATE.get("folder"),
        "platform": sys.platform,
    }


# Mutating calls need an open project (the dashboard has none), and after
# they succeed the project is written to disk. Uploads, the finished-video
# tool and the reference library stand apart: they are not project state.
_NO_PROJECT_OK = ("/api/projects", "/api/upload", "/api/locate", "/api/polish", "/api/music/folder",
                  "/api/references")
_NOT_SAVED = ("/api/projects", "/api/upload", "/api/locate", "/api/polish", "/api/music/folder")


@app.middleware("http")
async def project_scope(request: Request, call_next):
    path = request.url.path
    mutating = request.method in ("POST", "DELETE", "PATCH", "PUT") and path.startswith("/api/")
    if mutating and PROJECT["p"] is None:
        if not path.startswith(_NO_PROJECT_OK) or path.endswith(("/apply", "/look")):
            return JSONResponse({"detail": "Open a project first."}, status_code=409)
    response = await call_next(request)
    if mutating and response.status_code < 400 and not path.startswith(_NOT_SAVED) \
            and "/frames/" not in path:
        _save()
    return response


def _make_proposals(direction: dict) -> dict:
    lean = None if direction.get("keywords") else (direction.get("themes", []), direction.get("labels", []))
    return storyboard.build(list(CLIPS.values()), direction.get("text", ""),
                            vision=VISION_USED["value"], lean=lean, cut=cut.for_story(PLAN["plan"]),
                            voiceover=direction.get("voiceover"), style=direction.get("style"))


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
        "style": b.get("style"),
        "beats": [{**bt, "shots": [shot(x) for x in bt["shots"]]} for bt in b["beats"]],
    }
    tl = timeline.build(b, CLIPS, _track())
    tl["frame"] = export.frame_size(tl["items"], CLIPS)
    last = SESSION.last_active()
    ghosts = []
    cuts = seams.check(tl["items"], CLIPS) if b else []
    review: list[dict] = []
    if last and last.diff and not last.diff["replaced"]:
        # What the latest turn removed, so the board can show it struck through.
        prev = _board_before(last)
        # A second look at the turn: did it make any cut rougher (or fix one)?
        review = seams.review(seams.check(timeline.build(prev, CLIPS, _track())["items"], CLIPS) if prev else [], cuts)
        for r in last.diff["beats"]["removed"]:
            old = next((x for x in (prev or {}).get("beats", []) if x["id"] == r["id"]), None)
            idx = [x["id"] for x in (prev or {}).get("beats", [])].index(r["id"]) if old else 0
            ghosts.append({"index": idx, "title": r["title"],
                           "thumbs": [cat.shots[x["id"]].thumb for x in (old or {}).get("shots", [])
                                      if x["id"] in cat.shots]})
    return {
        "board": board,
        "structure_note": _structure_note(b),
        "last": {"turn": last.id, "diff": last.diff, "ghosts": ghosts, "review": review} if last else None,
        "seams": cuts,
        "turns": [{
            "id": t.id, "kind": t.kind, "text": t.text, "reply": t.reply, "question": t.question,
            "choices": t.choices, "lines": _with_thumbs(t.lines, cat), "skipped": t.skipped,
            "undone": t.undone, "at": t.at, "has_ops": bool(t.ops) or t.direction is not None,
            "direction": {k: t.direction[k] for k in ("themes",) if k in t.direction} if t.direction else None,
        } for t in SESSION.turns],
        "proposals": SESSION.proposals,
        "llm": llm.available(),
        "timeline": tl,
        "overlays": _overlays_public(b, cat, tl),
        "workflow": WORKFLOW.public(),
        "cut": cut.summary(PLAN["plan"]) if PLAN["plan"] else None,
        "music": _music_public(),
        "mix": _mix_public(b, tl),
        "preferences": PREFS.public(SESSION),
        "voiceover": _voiceover_public(),
        "project": _meta(),
        "brief": PROJECT["p"].brief if PROJECT["p"] else None,
        "exports": list(PROJECT["p"].exports) if PROJECT["p"] else [],
        "import_errors": list(PROJECT["p"].import_errors) if PROJECT["p"] else [],
        "capabilities": _capabilities(),
    }


# --------------------------------------------------------------------------
# smoother cuts: asked for, one undoable turn (smooth.py)
# --------------------------------------------------------------------------

class SmoothReq(BaseModel):
    order: bool = True
    nudge: bool = True


@app.post("/api/smooth")
def api_smooth(req: SmoothReq) -> dict:
    with LOCK:
        if not SESSION.board:
            raise HTTPException(409, "Choose a story first — there are no cuts to smooth yet.")
        ops, said = smooth.propose(SESSION.board, CLIPS, CATALOG["cat"], order=req.order, nudge=req.nudge)
        if not ops:
            raise HTTPException(409, said)
        SESSION.add({"kind": "direct", "text": "Smoother cuts", "ops": ops, "reply": said},
                    CATALOG["cat"], _make_proposals)
        return _session()


# --------------------------------------------------------------------------
# the sound under the edit: the board's own music, and one mixed track
# --------------------------------------------------------------------------

def _track():
    """The track under the edit: the storyboard's (set_music -- undoable,
    replayed), else whatever the music card last put under it."""
    m = (SESSION.board or {}).get("music")
    if m is not None and "track" in m:
        return next((t for t in musiclib.STATE["tracks"] if t.id == m["track"]), None)
    return musiclib.current()


def _music_public() -> dict | None:
    t = _track()
    return None if t is None else {"id": t.id, "title": t.title, "duration": round(t.duration, 2),
                                   "bpm": t.bpm, "audio": f"/api/music/audio/{t.id}"}


# Specs of mixes the UI has been told about, by key; the file is rendered
# on first request, so a session poll never waits for audio.
MIXES: dict[str, dict] = {}


def _mix_spec(b: dict | None, items: list[dict]) -> dict | None:
    if not b or not items:
        return None
    t = _track()
    sp = export.spans(items)
    plan, _ = export.plan_transitions(sp, CLIPS, b.get("style"))
    music = export.music_spec(t.path if t else None, b.get("music"))
    return audiomix.spec(sp, CLIPS, b.get("joins"), plan, music)


def _mix_public(b: dict | None, tl: dict) -> dict | None:
    """What the preview plays: the same sound export will write."""
    sp = _mix_spec(b, tl["items"])
    if sp is None:
        return None
    k = audiomix.key_of(sp)
    MIXES[k] = sp
    while len(MIXES) > 64:   # only recent edits can still be asked for
        MIXES.pop(next(iter(MIXES)))
    joins = audiomix.joins_for(sp["items"], sp["joins"])
    # The picture side of the same plan export renders (plan_transitions):
    # per shot, frames of handle for a dissolve and any dip or flash, so the
    # player can show the join the file will have. Only non-trivial entries.
    trans = [{"key": it["key"], "head": p["head"], "tail": p["tail"],
              "fade_in": list(p["fade_in"]) if p["fade_in"] else None,
              "fade_out": list(p["fade_out"]) if p["fade_out"] else None}
             for it, p in zip(sp["items"], sp["transitions"] or [])
             if p["head"] or p["tail"] or p["fade_in"] or p["fade_out"]]
    size = tl.get("frame") or {"w": 1920, "h": 1080}
    bar = export._bar(size, (b or {}).get("style"))
    return {"key": k, "audio": f"/api/mix/{k}.wav", "transitions": trans,
            "bars": round(bar / size["h"], 4) if bar else 0.0,
            # `fits`: False where a carry was asked for but the shot wasn't
            # filmed long enough past the cut -- it plays as a clean break, and says so
            "joins": [{"after": it["key"], "at": sp["items"][i + 1]["seq_start"], **j,
                       "fits": audiomix.fits(sp["items"], CLIPS, i, j["sound"])}
                      for i, (it, j) in enumerate(zip(sp["items"], joins))]}


@app.get("/api/mix/{name}")
def api_mix(name: str) -> FileResponse:
    k = name.removesuffix(".wav")
    sp = MIXES.get(k)
    if sp is None:
        raise HTTPException(404, "that mix is out of date")
    try:
        path = audiomix.preview_file(sp, dict(CLIPS))
    except (OSError, subprocess.CalledProcessError) as e:
        raise HTTPException(500, f"couldn't mix the sound: {e}") from e
    return FileResponse(path, media_type="audio/wav",
                        headers={"Cache-Control": "public, max-age=31536000, immutable"})


def _overlays_public(b: dict | None, cat, tl: dict) -> dict:
    """Words on screen as both preview and export draw them: resolved times
    (on the beat, if the look says so), one style with the look's motion."""
    style = overlays.style_of(b)
    items = overlays.resolve(b)
    if (style.get("motion") or {}).get("beat_lock"):
        items = looks.beat_lock(items, tl.get("grid"), tl.get("total", 0.0))
    return {"items": items, "style": style, "findings": overlays.check(b, cat),
            "look": {"id": (b or {}).get("look"), "overrides": looks.overrides(b), "all": looks.public()}}


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
        # ~1 frame a second, for the rough cut's hover preview before the video seeks
        "samples": {"times": (c.get("samples") or {}).get("times", []),
                    "base": f"/api/samples/{c['id']}/"},
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
    return {"clips": [_public_clip(c) for c in clips], "vision": vision.status(), "project": _meta()}


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
    asked = list(dict.fromkeys(paths))
    paths = [p for p in asked if os.path.isfile(p) and Path(p).suffix.lower() in indexer.VIDEO_EXT]
    pr = PROJECT["p"]
    # A file that isn't there (moved since the project was saved, a bad
    # path) is reported on the footage screen, not dropped on the floor.
    gone = [{"path": p, "error": "no such file" if not os.path.isfile(p) else "only .mp4 / .mov"}
            for p in asked if p not in paths]
    if pr is not None and gone:
        with LOCK:
            pr.import_errors = [e for e in pr.import_errors if e.get("path") not in {g["path"] for g in gone}] + gone
    if not paths:
        raise HTTPException(400, "no .mp4 or .mov files" if not gone else gone[0]["error"] + ": " + Path(gone[0]["path"]).name)
    # Adding to a session: only what isn't on the shelf already gets indexed.
    fresh = [p for p in paths if indexer.clip_id(p) not in CLIPS]

    def done(job: indexer.Job) -> None:
        with LOCK:
            for c in job.clips:
                CLIPS[c["id"]] = c
            VISION_USED["value"] = vision.status() == "ready"
            _refresh_catalog()
            if pr is not None:
                # Files that couldn't be read stay listed (with a retry) until they can.
                tried = {p for p in paths}
                pr.import_errors = [e for e in pr.import_errors if e.get("path") not in tried] + list(job.errors)
            if not job.clips:
                return
            # Stage 1 + 2: reject and trim, then stop at the gate for a person.
            PLAN["plan"] = cut.compute(CLIPS, PLAN["plan"])
            if WORKFLOW.state in ("intake", "indexing"):
                if WORKFLOW.state == "intake":
                    WORKFLOW.advance("indexing", f"{len(job.clips)} clips indexed")
                WORKFLOW.advance("rough-cut", "reject + trim computed")
                WORKFLOW.advance("cut-review", cut.summary(PLAN["plan"])["line_en"])
            else:
                WORKFLOW.reopen("system", f"{len(job.clips)} new clip(s) to review")
            SESSION.replay(CATALOG["cat"], _make_proposals)
        if pr is not None and pr is PROJECT["p"]:
            _save()

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
    """Start the open project over: its footage, log and gate. The files
    on disk and their index are untouched."""
    global SESSION, WORKFLOW
    with LOCK:
        CLIPS.clear()
        SESSION = bd.Session()
        PREFS.new_project()
        WORKFLOW = Workflow()
        PLAN["plan"] = None
        if PROJECT["p"]:
            PROJECT["p"].brief = None
            PROJECT["p"].import_errors = []
        _refresh_catalog()
    return _project()


# --------------------------------------------------------------------------
# projects: the dashboard's list, and which one is open (projects.py)
# --------------------------------------------------------------------------

class ProjectReq(BaseModel):
    name: str = ""


class BriefReq(BaseModel):
    message: str | None = None
    style: dict | None = None
    said: str = ""


def _summaries() -> list[dict]:
    cur = PROJECT["p"]
    out = []
    for p in pj.list_all():
        if cur is not None and p.id == cur.id:
            out.append(cur.summary(CLIPS, SESSION.board))
        else:
            out.append(p.summary())
    return out


@app.get("/api/projects")
def api_projects() -> dict:
    return {"projects": _summaries(), "open": PROJECT["p"].id if PROJECT["p"] else None,
            "capabilities": _capabilities()}


@app.post("/api/projects")
def api_project_create(req: ProjectReq) -> dict:
    _save()
    pr = pj.create(req.name)
    _open_project(pr.id)
    return {"project": _meta(), "session": _session()}


@app.post("/api/projects/{pid}/open")
def api_project_open(pid: str) -> dict:
    if PROJECT["p"] is not None and PROJECT["p"].id == pid:
        return {"project": _meta(), "session": _session()}
    _save()
    try:
        _open_project(pid)
    except pj.ProjectError as e:
        raise HTTPException(404, str(e)) from e
    return {"project": _meta(), "session": _session()}


@app.post("/api/projects/close")
def api_project_close() -> dict:
    _save()
    _close_project()
    return {"projects": _summaries(), "open": None}


@app.patch("/api/projects/{pid}")
def api_project_rename(pid: str, req: ProjectReq) -> dict:
    name = req.name.strip()[:80]
    if not name:
        raise HTTPException(400, "give it a name")
    cur = PROJECT["p"]
    if cur is not None and cur.id == pid:
        cur.name = name
        _save()
        return {"project": _meta()}
    try:
        pr = pj.load(pid)
    except pj.ProjectError as e:
        raise HTTPException(404, str(e)) from e
    pr.name = name
    pj.save(pr)
    return {"project": pr.summary()}


@app.delete("/api/projects/{pid}")
def api_project_delete(pid: str) -> dict:
    """Removes the project record only -- never a clip, never an export."""
    if PROJECT["p"] is not None and PROJECT["p"].id == pid:
        _close_project()
    try:
        pj.delete(pid)
    except pj.ProjectError as e:
        raise HTTPException(404, str(e)) from e
    return {"projects": _summaries(), "open": PROJECT["p"].id if PROJECT["p"] else None}


@app.post("/api/project/brief")
def api_project_brief(req: BriefReq) -> dict:
    """The one-line description and style answers, kept on the project
    until the story is built (and after, as a record of what was asked)."""
    pr = PROJECT["p"]
    if pr is None:
        raise HTTPException(409, "Open a project first.")
    if req.message is None or not req.message.strip():
        pr.brief = None
    else:
        pr.brief = {"message": req.message.strip(), "style": brief.clean_style(req.style) or {},
                    "said": req.said, "at": time.time()}
    return _session()


# --------------------------------------------------------------------------
# storyboards
# --------------------------------------------------------------------------

class ChatReq(BaseModel):
    message: str
    # Answers to the style questions (brief.py), sent with the first description.
    style: dict | None = None


class QuestionsReq(BaseModel):
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
            # ...and the style answers, unless this message brings new ones.
            style = brief.clean_style(req.style) or (_direction() or {}).get("style")
            if style:
                direction["style"] = style
        SESSION.add({"kind": "chat", "text": msg, "ops": out.get("ops", []),
                     "reply": out.get("reply", ""), "question": out.get("question"),
                     "choices": out.get("choices", []) if out.get("question") else [],
                     "direction": direction}, cat, _make_proposals)
        return _session()


SUGGESTED: dict = {}     # clip ids -> suggestions, so a revisit doesn't ask again


@app.get("/api/brief/suggestions")
def api_brief_suggestions() -> dict:
    """Three one-line descriptions read from the footage, to click instead of typing."""
    with LOCK:
        clips = list(CLIPS.values())
    if not clips:
        return {"suggestions": [], "source": "none"}
    key = ",".join(sorted(c["id"] for c in clips))
    if key not in SUGGESTED:
        SUGGESTED.clear()
        SUGGESTED[key] = pitch.suggest(clips)
    return SUGGESTED[key]


@app.post("/api/brief/questions")
def api_brief_questions(req: QuestionsReq) -> dict:
    """The style questions asked once, after the first description."""
    with LOCK:
        shots, _ = storyboard.usable(storyboard.shots_from_clips(list(CLIPS.values())))
        qs = brief.fixed_questions(brief.theme_counts(shots))
    tailored = False
    if llm.available() and req.message.strip():
        try:
            extra = llm.tailor_questions(req.message.strip(), qs)
            qs += extra
            tailored = bool(extra)
        except llm.LLMError:
            pass  # the fixed questions are enough on their own
    return {"questions": qs, "tailored": tailored}


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
    action: str          # keep | reject | full | longer | shorter | set | auto
    start: float | None = None   # set: the creator's in and out points
    end: float | None = None


@app.post("/api/cut/override")
def api_cut_override(req: OverrideReq) -> dict:
    with LOCK:
        if not PLAN["plan"]:
            raise HTTPException(400, "nothing to override yet")
        try:
            PLAN["plan"] = cut.override(PLAN["plan"], req.target, req.action, CLIPS, req.start, req.end)
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
        if [o.get("op") for o in req.ops] == ["choose_option"]:
            _words_as_asked()
        return _session()


def _words_as_asked() -> None:
    """A story was just chosen: put on screen the words the style questions
    asked for, as their own turn so Undo takes only the words away."""
    b = SESSION.board
    d = _direction() or {}
    answer = (d.get("style") or {}).get("captions")
    if not b or b.get("overlays") or not d:
        return
    said = (d.get("text") or "").split("\n")[0].strip()
    ops, notes = brief.caption_ops(b, CATALOG["cat"], answer, said if len(said) <= 48 else None, said)
    if not ops:
        return
    n = sum(o["op"] == "add_overlay" for o in ops)
    reply = (f"Added {n} word overlay{'s' * (n != 1)}, as you asked at the start." if answer else
             f"Added {n} day-in-my-life caption{'s' * (n != 1)}: the time and what's happening. Click one to retype it.")
    if notes:
        reply += " " + " ".join(notes)
    SESSION.add({"kind": "direct", "text": "Words on screen, as you asked", "ops": ops, "reply": reply},
                CATALOG["cat"], _make_proposals)


@app.post("/api/turns/{tid}/toggle")
def api_toggle(tid: int) -> dict:
    with LOCK:
        SESSION.toggle(tid, CATALOG["cat"], _make_proposals)
        return _session()


# --------------------------------------------------------------------------
# talking-head mode (口播): transcribe on this Mac, cut pauses and retakes,
# a gate to review every cut, then a storyboard with subtitles
# --------------------------------------------------------------------------

TALK: dict = {"plan": None, "job": None}


class TalkReq(BaseModel):
    locale: str = "zh-CN"
    script: str = ""
    clips: list[str] | None = None


def _talk_clips(ids: list[str] | None) -> list[dict]:
    rejected, _ = cut.for_story(PLAN["plan"])
    pool = [c for c in CLIPS.values() if (c["id"] in ids if ids else c["id"] not in rejected)]
    return sorted(pool, key=lambda c: (storyboard.parse_when(c.get("capture_time")) or storyboard.datetime.max, c["name"]))


@app.post("/api/talk")
def api_talk(req: TalkReq) -> dict:
    if not CLIPS:
        raise HTTPException(400, "drop some clips in first")
    if req.locale not in speech.LOCALES:
        raise HTTPException(400, f"language must be one of {', '.join(speech.LOCALES)}")
    job = TALK["job"]
    if job and job["stage"] in ("transcribing", "reviewing"):
        raise HTTPException(409, "already transcribing")
    clips = _talk_clips(req.clips)
    job = {"stage": "transcribing", "done": 0, "total": len(clips), "current": "", "error": None, "silent": []}
    TALK["job"] = job

    def work() -> None:
        try:
            transcripts, levels, used = {}, {}, {}
            for c in clips:
                job["current"] = c["name"]
                try:
                    res = speech.transcribe(c, req.locale)
                except speech.SpeechError as e:
                    if "no sound" in str(e):
                        res = []
                    else:
                        raise
                if res:
                    transcripts[c["id"]] = res
                    levels[c["id"]] = talk.active(speech.audio(c))
                    used[c["id"]] = c
                else:
                    job["silent"].append(c["name"])
                job["done"] += 1
            if not transcripts:
                raise speech.SpeechError("No speech found in these clips — is the language right?")
            job["stage"] = "reviewing"
            agent = llm.review_talk if llm.available() else None
            plan = talk.build(transcripts, used, req.locale, levels, req.script, agent)
            with LOCK:
                TALK["plan"] = plan
            job["stage"] = "done"
        except Exception as e:  # noqa: BLE001 -- shown at the gate
            job["stage"], job["error"] = "error", str(e)

    threading.Thread(target=work, daemon=True).start()
    return {"job": job, "plan": None, "llm": llm.available()}


@app.get("/api/talk")
def api_talk_state() -> dict:
    with LOCK:
        p = TALK["plan"]
        return {"job": TALK["job"], "plan": talk.public(p) if p else None, "llm": llm.available()}


class TalkToggleReq(BaseModel):
    id: str


@app.post("/api/talk/toggle")
def api_talk_toggle(req: TalkToggleReq) -> dict:
    """Put a cut back, or take something out -- the creator's call at the gate."""
    with LOCK:
        if not TALK["plan"]:
            raise HTTPException(400, "nothing transcribed yet")
        try:
            talk.toggle(TALK["plan"], req.id)
        except KeyError as e:
            raise HTTPException(404, f"no item {req.id}") from e
        return {"job": TALK["job"], "plan": talk.public(TALK["plan"]), "llm": llm.available()}


class TalkApplyReq(BaseModel):
    captions: bool = True
    profile: dict = {}


@app.post("/api/talk/apply")
def api_talk_apply(req: TalkApplyReq) -> dict:
    """The reviewed cut becomes the working storyboard -- one turn, undoable."""
    with LOCK:
        p = TALK["plan"]
        if not p:
            raise HTTPException(400, "nothing transcribed yet")
        snap = talk.board(p, captions=req.captions, style=overlays.style_from_profile(req.profile) or None)
        if not snap["beats"]:
            raise HTTPException(409, "Everything was cut — put something back first.")
        s = talk.public(p)["summary"]
        SESSION.add({"kind": "direct", "text": "You used the talking-head cut",
                     "ops": [{"op": "choose_option", "option": "talk", "snapshot": snap}],
                     "reply": s["line_en"] + (" · subtitles added" if req.captions else "")},
                    CATALOG["cat"], _make_proposals)
        return _session()


# --------------------------------------------------------------------------
# words on screen: suggested from what the edit knows, then edited like shots
# --------------------------------------------------------------------------

class SuggestReq(BaseModel):
    profile: dict = {}
    title: str | None = None
    kinds: list[str] | None = None


@app.post("/api/overlays/suggest")
def api_overlays_suggest(req: SuggestReq) -> dict:
    """Fill in the overlays the edit is missing. One turn: Undo takes them all away."""
    with LOCK:
        b = SESSION.board
        if not b:
            raise HTTPException(409, "Choose a story first — titles hang off its parts and shots.")
        ops, notes = overlays.suggest(b, CATALOG["cat"], req.profile, req.title, req.kinds)
        style = overlays.style_from_profile(req.profile)
        if style and not b.get("overlay_style"):
            ops.insert(0, {"op": "overlay_style", **style, "source": "profile"})
        if not ops:
            raise HTTPException(409, "Nothing to add — " + (notes[0][0].lower() + notes[0][1:] if notes
                                                              else "every part already has its words."))
        n = sum(o["op"] == "add_overlay" for o in ops)
        reply = f"Added {n} overlay{'s' * (n != 1)} from what the edit already knows."
        if notes:
            reply += " " + " ".join(notes)
        SESSION.add({"kind": "direct", "text": "You asked for titles and labels", "ops": ops, "reply": reply},
                    CATALOG["cat"], _make_proposals)
        return _session()


# --------------------------------------------------------------------------
# export: the edit + its words on screen + music, as one file
# --------------------------------------------------------------------------

class ExportReq(BaseModel):
    music: bool = True


@app.post("/api/export")
def api_export(req: ExportReq) -> dict:
    """Create an export. The browser then uploads its overlay frames and starts it."""
    with LOCK:
        if not SESSION.board:
            raise HTTPException(409, "Choose a story first — there's nothing to export yet.")
        tl = timeline.build(SESSION.board, CLIPS, _track())
        track = _track() if req.music else None
        try:
            # Named after what the video says it is: its title, else the story.
            title = next((o["text"] for o in SESSION.board.get("overlays", []) if o["kind"] == "title"), None)
            job = export.create(tl["items"], dict(CLIPS), title or SESSION.board.get("name", ""),
                                track.path if track else None, SESSION.board.get("style"),
                                mix=SESSION.board.get("music"), joins=SESSION.board.get("joins"))
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        return job.public()


def _job(jid: str) -> export.Job:
    job = export.JOBS.get(jid)
    if not job:
        raise HTTPException(404, "no such export")
    return job


@app.post("/api/export/{jid}/frames/{n}")
async def api_export_frame(jid: str, n: int, request: Request) -> dict:
    job = _job(jid)
    try:
        export.save_frame(job, n, await request.body())
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {"ok": True}


class ExportStartReq(BaseModel):
    schedule: list[dict] = []


@app.post("/api/export/{jid}/start")
def api_export_start(jid: str, req: ExportStartReq) -> dict:
    job = _job(jid)
    try:
        export.start(job, req.schedule)
    except (ValueError, KeyError, TypeError) as e:
        raise HTTPException(400, str(e)) from e
    return job.public()


@app.get("/api/export/{jid}")
def api_export_status(jid: str) -> dict:
    job = _job(jid)
    pub = job.public()
    # A finished export is part of the project's record: the dashboard and
    # the Export stage list it, and it is how "done" is known after a restart.
    pr = PROJECT["p"]
    if pub["stage"] == "done" and pr is not None and not any(e.get("job") == jid for e in pr.exports):
        pr.exports.append({"job": jid, "file": pub["file"], "path": pub["path"], "at": time.time(),
                           "seconds": pub["total"], "size": pub["size"], "music": pub["music"],
                           "overlays": pub["overlays"], "bytes": os.path.getsize(pub["path"]) if pub["path"] and os.path.isfile(pub["path"]) else None})
        _save()
    return pub


@app.get("/api/exports/{n}/file")
def api_export_saved_file(n: int) -> FileResponse:
    """A past export of the open project, by its index in the list."""
    pr = PROJECT["p"]
    if pr is None or n < 0 or n >= len(pr.exports):
        raise HTTPException(404)
    path = pr.exports[n].get("path")
    if not path or not os.path.isfile(path):
        raise HTTPException(404, "that file is no longer where it was saved")
    return FileResponse(path, media_type="video/mp4", filename=Path(path).name)


@app.post("/api/export/{jid}/cancel")
def api_export_cancel(jid: str) -> dict:
    job = _job(jid)
    job.cancel = True
    if job.stage == "waiting":
        job.stage = "cancelled"
    return job.public()


@app.get("/api/export/{jid}/file")
def api_export_file(jid: str) -> FileResponse:
    job = _job(jid)
    if job.stage != "done" or not job.path or not os.path.isfile(job.path):
        raise HTTPException(404, "not finished")
    return FileResponse(job.path, media_type="video/mp4", filename=Path(job.path).name)


@app.post("/api/export/{jid}/reveal")
def api_export_reveal(jid: str) -> Response:
    job = _job(jid)
    if job.stage != "done" or not job.path:
        raise HTTPException(404, "not finished")
    if sys.platform == "darwin":
        subprocess.Popen(["open", "-R", job.path])
    return Response(status_code=204)


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
        if SESSION.board is not None:
            # On the board, so it's in the log: undoable, and a Remix's own
            # mix (in-point, levels) is replaced rather than silently kept.
            t = musiclib.current()
            SESSION.add({"kind": "direct", "text": f"Music: {t.title}" if t else "No music",
                         "ops": [{"op": "set_music", "track": req.track_id}]}, CATALOG["cat"], _make_proposals)
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
# borrow a feeling: learn a reference video's style, apply it as one turn
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# remix: reference reels + the shelf -> one finished short, then the board
# --------------------------------------------------------------------------

class RemixReq(BaseModel):
    refs: list[str]                 # links, or paths on this Mac
    title: str | None = None
    sub: str | None = None
    length: float | None = None
    name: str | None = None


@app.post("/api/remix")
def api_remix_start(req: RemixReq) -> dict:
    with LOCK:
        if not CLIPS:
            raise HTTPException(409, "Drop your clips in first — the remix is made from them.")
        refs = [r.strip() for r in req.refs if r.strip()]
        if not refs:
            raise HTTPException(400, "Paste at least one reference link.")
        clips = dict(CLIPS)
        cut_now = cut.for_story(PLAN["plan"]) if PLAN["plan"] else None

    def on_done(job: remix.Job) -> None:
        # the finished remix becomes the working storyboard, one undoable turn,
        # and its track joins the music list so the timeline knows the beat
        with LOCK:
            r = job.result or {}
            mx = r.get("music")
            if mx and not any(t.id == mx["track"].id for t in musiclib.STATE["tracks"]):
                musiclib.STATE["tracks"].append(mx["track"])
            if mx:
                musiclib.use(mx["track"].id)
            SESSION.add({"kind": "direct", "text": f"Remix in the style of {len(job.refs)} reference(s)",
                         "ops": remix.session_ops(r),
                         "reply": f"{r['plan'].duration:.0f} s, {len(r['plan'].picks)} shots" if r.get("plan") else ""},
                        CATALOG["cat"], _make_proposals)

    job = remix.start(refs, clips, cut_now, req.model_dump(), on_done)
    return job.public()


def _remix_job(jid: str) -> remix.Job:
    job = remix.JOBS.get(jid)
    if not job:
        raise HTTPException(404, "no such remix")
    return job


@app.get("/api/remix/{jid}")
def api_remix_status(jid: str) -> dict:
    return _remix_job(jid).public()


@app.get("/api/remix/{jid}/file")
def api_remix_file(jid: str) -> FileResponse:
    job = _remix_job(jid)
    if not job.result or not job.result.get("path"):
        raise HTTPException(409, "not finished yet")
    return FileResponse(job.result["path"], media_type="video/mp4", filename=Path(job.result["path"]).name)


@app.get("/api/remix/{jid}/credits")
def api_remix_credits(jid: str) -> FileResponse:
    job = _remix_job(jid)
    if not job.result or not job.result.get("credits"):
        raise HTTPException(409, "not finished yet")
    return FileResponse(job.result["credits"], media_type="text/plain", filename=Path(job.result["credits"]).name)


class RefReq(BaseModel):
    source: str             # a path on this Mac (from /api/locate or /api/upload), or a link


@app.post("/api/references")
def api_ref_start(req: RefReq) -> dict:
    try:
        return reference.start(req.source).public()
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.get("/api/references")
def api_ref_library() -> dict:
    return {"references": reference.library(), "links": reference.ytdlp() is not None}


@app.get("/api/references/jobs/{jid}")
def api_ref_job(jid: str) -> dict:
    job = reference.JOBS.get(jid)
    if not job:
        raise HTTPException(404, "no such job")
    return job.public()


def _grid() -> dict | None:
    return timeline.build(SESSION.board, CLIPS, _track()).get("grid")


@app.get("/api/references/{rid}")
def api_ref_card(rid: str) -> dict:
    with LOCK:
        b = SESSION.board
        landscape = None
        if b:
            fr = export.frame_size(timeline.layout(b), CLIPS)
            landscape = fr["w"] > fr["h"]
        try:
            out = reference.card(rid, _grid(), landscape)
        except ValueError as e:
            raise HTTPException(404, str(e)) from e
        out["music"] = reference.music_matches(rid, musiclib.STATE["tracks"])
        out["music_folder"] = musiclib.STATE["status"] == "ready"
        out["has_story"] = b is not None
        return out


class LookReq(BaseModel):
    strength: str = "full"


@app.post("/api/references/{rid}/look")
def api_ref_look(rid: str, req: LookReq) -> dict:
    """Fit the look to the shots in this story; before/after stills to judge it by."""
    with LOCK:
        if not SESSION.board:
            raise HTTPException(409, "Choose a story first — the look is fitted to its shots.")
        try:
            return reference.fit_look(rid, SESSION.board, CATALOG["cat"], req.strength)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e


class RefApplyReq(BaseModel):
    traits: list[str]
    strength: str = "full"


@app.post("/api/references/{rid}/apply")
def api_ref_apply(rid: str, req: RefApplyReq) -> dict:
    """One direct turn: the diff says what changed, Undo takes all of it back."""
    with LOCK:
        if not SESSION.board:
            raise HTTPException(409, "Choose a story first — a style is applied to an edit.")
        try:
            look = reference.fit_look(rid, SESSION.board, CATALOG["cat"], req.strength) if "look" in req.traits else None
            op = reference.make_op(rid, req.traits, _grid(), look)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        t = SESSION.add({"kind": "direct", "text": f"Borrow the feel of “{op['name']}”", "ops": [op]},
                        CATALOG["cat"], _make_proposals)
        if t.skipped:
            SESSION.turns.remove(t)
            SESSION.replay(CATALOG["cat"], _make_proposals)
            raise HTTPException(400, t.skipped[0])
        return _session()


@app.delete("/api/references/{rid}")
def api_ref_forget(rid: str) -> dict:
    try:
        reference.forget(rid)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    return api_ref_library()


@app.get("/api/references/{rid}/files/{name}")
def api_ref_file(rid: str, name: str) -> FileResponse:
    try:
        p = reference.file_path(rid, name)
    except ValueError:
        p = None
    if not p:
        raise HTTPException(404)
    return FileResponse(p, media_type="image/jpeg")


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


@app.get("/api/samples/{clip_id}/{i}")
def api_sample(clip_id: str, i: int) -> FileResponse:
    files = (CLIPS.get(clip_id) or {}).get("samples", {}).get("files", [])
    if not 0 <= i < len(files):
        raise HTTPException(404)
    p = indexer.clip_dir(clip_id) / files[i]
    if not p.exists():
        raise HTTPException(404)
    return FileResponse(p, media_type="image/jpeg",
                        headers={"Cache-Control": "public, max-age=31536000, immutable"})


# polish: a finished video, the creator pointing at it (polish_api.py)
from . import polish_api  # noqa: E402

app.include_router(polish_api.router)

DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if DIST.exists():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="ui")

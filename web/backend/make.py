"""The one pipeline: clips in, a finished video out, on the main path.

Why this exists (2026-10-17): the default path grouped clips by time, place
or subject, played them in filming order and asked for music afterwards --
a timeline, not a video -- while the engine that makes the video the
creator actually asked for (hero shots, a hook, cuts on the beat, music
with a drop, words that say something) lived only under "Build a short
from reference reels". This module makes that engine the default. Remix
becomes the case where references are given; without them the fingerprint
is a prior for the frame picked (PRIOR), so "Make my video" always means
the same thing: the strongest moments, in a shape, on a beat, with words.

What happens, as one undoable turn that lands when it's ready (a job, like
a Remix; the dialog shows where it is):

1. A **fingerprint**: the references' (remix.fingerprint) or the frame's
   prior -- shot length by pace, a hook, a length from the format.
2. The **moments** (remix.plan_shots -> select.choose, worth-ranked, judged
   by Claude from one frame each when there's a key).
3. **Music** (bed.candidates: own folder, Openverse, else the pack) picked
   for the edit's tempo and arc; every shot becomes whole beats; the track
   starts so its drop lands at the end of the hook.
4. The **board**, the **music**, the **look** and the **words** (a title,
   one line per stop) as ops. Levels follow the frame: a short rides on
   the music, a vlog keeps its own sound up front and ducks under talking.

Nothing is rendered here; the preview plays the board and export writes
the file. Every number in PRIOR is a guess until the creator says otherwise.
"""

from __future__ import annotations

import threading
import time
import uuid

from cutgrammar import music as mu

from . import audiomix, bed, oai, remix, select as sel, story, storyboard as sb, tempo, timeline

# Shot length and hook by frame and pace [prior]. A short is cut like the
# reels the creator brought on 2026-09-25 (0.7 s a shot, hook 1.4 s); a
# vlog breathes (2-3 s) but still opens on its strongest moment.
PRIOR = {
    "short": {"median": {"fast": 0.7, "balanced": 0.9, "calm": 1.2}, "hook_s": 1.5, "max_s": 60.0},
    "tall": {"median": {"fast": 1.8, "balanced": 2.5, "calm": 3.2}, "hook_s": 2.5, "max_s": None},
    "wide": {"median": {"fast": 1.8, "balanced": 2.5, "calm": 3.2}, "hook_s": 2.5, "max_s": None},
}
CURVE = [1.15, 1.0, 0.9, 0.9, 1.05]       # shots shorten through the middle, the ending breathes [prior]
SPREAD = (0.6, 1.5)                        # shot-to-shot variety around the median (p10 / p90 of the median)
# Levels by frame [prior]: a short rides on the music (Remix's levels); a
# vlog's own sounds stay up front (the bed's).
LEVELS = {"short": {"gain": remix.MUSIC_GAIN, "original": remix.ORIGINAL_GAIN},
          "tall": {"gain": audiomix.MUSIC_GAIN, "original": 1.0},
          "wide": {"gain": audiomix.MUSIC_GAIN, "original": 1.0}}
STAGES = {"choosing": "Choosing the moments…", "music": "Finding music and its drop…",
          "words": "Writing the words…", "done": "Done", "error": "Failed"}


def fingerprint(fmt: str, pace: str, seconds: float, styles: list[dict] | None = None) -> dict:
    """The shape the edit should take: the references' when there are any,
    else the frame's prior. `seconds` is the length the brief asked for."""
    fmt = fmt if fmt in PRIOR else "tall"
    pace = pace if pace in bed.PACE_BPM else "balanced"
    if styles:
        fp = remix.fingerprint(styles)
        if PRIOR[fmt]["max_s"]:
            fp["duration"] = round(min(fp["duration"], PRIOR[fmt]["max_s"]), 1)
        fp["refs_used"] = True
        return fp
    p = PRIOR[fmt]
    dur = float(seconds)
    if p["max_s"]:
        dur = min(dur, p["max_s"])
    med = p["median"][pace]
    return {"median_s": med, "curve": list(CURVE), "spread": SPREAD, "hook_s": p["hook_s"],
            "bpm": bed.PACE_BPM[pace], "arc": "builds", "energy": None,
            "duration": round(max(15.0, dur), 1), "vertical": fmt != "wide", "refs": 0, "refs_used": False}


def moments(clips: dict[str, dict], cut, fp: dict, judge=None) -> sel.Plan:
    return remix.plan_shots(clips, fp, length=fp["duration"], cut=cut, judge=judge)


def music(clips: dict[str, dict], plan: sel.Plan, fp: dict, pace: str, own: list[mu.Track] | None,
          progress=None, pool: list[mu.Track] | None = None) -> tuple[dict | None, str]:
    """A track for this plan, and the plan re-cut to its beat. `pool` stands
    in for bed.candidates in tests. Returns (pick, where it came from)."""
    source = "given"
    if pool is None:
        pool, source = bed.candidates(pace, own, progress)
    hook_s = sum(p.duration for p in plan.hook) or fp["hook_s"]
    mx = remix.pick_from(pool, fp, plan.duration + 4.0, hook_s)
    if mx:
        remix.quantise(plan, clips, mx["period"])
        hook_s = sum(p.duration for p in plan.hook) or hook_s
        mx["in"] = round(max(0.0, mx["drop"] - hook_s), 3)
    return mx, source


def ops(plan: sel.Plan, fp: dict, mx: dict | None, fmt: str, look: str | None, about: str,
        talking: set[str], name: str = "Your video", chapters: list[dict] | None = None) -> list[dict]:
    """Everything the turn applies: the board, the bed, the look, the words.
    `chapters` (story.py): the plan's chapters, which then carry the words --
    a designed title and a plain line under it each -- instead of a clock
    time per stop."""
    board = remix.board_of(plan, fp, name)
    board["option"] = "made"
    board["structure"] = ("Made from your clips in the style of your references — " if fp.get("refs_used")
                          else "Made from your clips — ") + remix.describe(fp)
    if chapters:
        board["structure"] = f"Told in {len(chapters)} chapters, each a setup, its steps and a payoff — " + remix.describe(fp)
    out: list[dict] = [{"op": "choose_option", "option": "made", "snapshot": board}]
    if mx:
        lv = LEVELS.get(fmt, LEVELS["tall"])
        m = {"op": "set_music", "track": mx["track"].id, "in": mx["in"], "gain": lv["gain"], "original": lv["original"],
             "level": True, "fade_out": min(3.0, max(1.5, 4 * mx["period"])), "duck": [], "sfx": []}
        if fmt != "short" and talking:
            m["duck"] = bed.ducks(board, talking)
        out.append(m)
    if look:
        out.append({"op": "set_look", "look": look})
    if chapters:
        return out + story.heading_ops(plan, chapters)
    title = (about or "").split(",")[0].strip()[:40] or None
    for c in remix.captions(plan, title, None):
        if c["kind"] == "title":
            out.append({"op": "add_overlay", "kind": "title", "text": c["text"], "sub": c.get("sub", ""),
                        "anchor": {"to": "edit"}, "at": 0.0, "dur": round(c["end"] - c["start"], 2), "anim": "rise"})
        elif c["kind"] == "scene":
            out.append({"op": "add_overlay", "kind": "part", "text": c["text"], "pos": "top", "size": "S",
                        "start": c["start"], "dur": round(c["end"] - c["start"], 2), "anim": "rise"})
    return out


def say(plan: sel.Plan, fp: dict, mx: dict | None, source: str, judged: bool, ai: dict | None = None) -> str:
    parts = [f"Made your video: {len(plan.picks)} moments, {plan.duration:.0f} s"
             + (", in the style of your references" if fp.get("refs_used") else "") + "."]
    if ai and ai.get("chapters"):
        parts.append(f"{ai['model']} planned it as {ai['chapters']} chapters (cost ${ai['cost']:.3f}).")
    elif ai and ai.get("error"):
        parts.append(f"The story plan didn't work ({ai['error']}), so the usual rules picked the moments."
                     + (f" That try cost ${ai['cost']:.3f}." if ai.get("cost") else ""))
    if mx:
        parts.append(f"Music: {mx['track'].title} ({mx['bpm']:.0f} BPM, from {source}); every cut sits on its beat.")
    else:
        parts.append("No track fit, so it plays with its own sound; Music in the rail finds one.")
    if judged:
        parts.append("Claude judged the moments from one frame each.")
    parts.append("Undo takes all of it back.")
    return " ".join(parts)


# --------------------------------------------------------------------------
# the job
# --------------------------------------------------------------------------

class Job:
    def __init__(self) -> None:
        self.id = uuid.uuid4().hex[:10]
        self.stage = "queued"
        self.line = ""
        self.done, self.total = 0, 0
        self.error: str | None = None
        self.started = time.time()
        self.result: dict | None = None

    def public(self) -> dict:
        return {"id": self.id, "stage": self.stage, "line": self.line or STAGES.get(self.stage, ""),
                "done": self.done, "total": self.total, "error": self.error,
                "elapsed": round(time.time() - self.started, 1)}


JOBS: dict[str, Job] = {}


def start(clips: dict[str, dict], cut, fmt: str, pace: str, look: str | None, about: str, seconds: float,
          own: list[mu.Track] | None, styles: list[dict] | None, judge, on_done, use_ai: bool = False) -> Job:
    """Run the pipeline in a thread; `on_done(job)` puts the ops on the session.
    Everything the thread needs is copied in now, so later edits can't move it."""
    job = Job()
    JOBS[job.id] = job

    def progress(done: int, total: int) -> None:
        job.done, job.total = done, total

    def run() -> None:
        try:
            job.stage = "choosing"
            fp = fingerprint(fmt, pace, seconds, styles)
            plan, chapters, ai = None, None, None
            if use_ai and oai.enabled() and not styles:
                # the story editor (story.py): only with the AI switch on and this edit's cost agreed
                job.line = "Planning the story…"
                try:
                    plan, chapters, _title, usage = story.plan(clips, cut, fmt, fp["duration"], about)
                    ai = {"model": usage.get("model"), "cost": usage.get("cost", 0.0), "chapters": len(chapters),
                          "tokens_in": usage.get("prompt_tokens"), "tokens_out": usage.get("completion_tokens")}
                except Exception as e:  # noqa: BLE001 -- the rules make the edit instead, and say so
                    paid = (getattr(e, "usage", None) or {}).get("cost", 0.0)
                    plan, chapters, ai = None, None, {"error": str(e)[:160], "cost": paid}
                job.line = ""
            if plan is None:
                plan = moments(clips, cut, fp, judge)
            if not plan.picks:
                raise ValueError("none of the clips had a moment worth keeping — add more footage")
            job.stage = "music"
            mx, source = music(clips, plan, fp, pace, own, progress)
            job.stage = "words"
            pool, _ = sb.usable(sb.shots_from_clips(list(clips.values()), cut))
            talking = tempo.talking(list(clips.values()), pool)
            judged = any(n.startswith("Claude judged") for n in plan.notes)
            job.result = {"ops": ops(plan, fp, mx, fmt, look, about, talking, chapters=chapters), "music": mx,
                          "fp": fp, "plan": plan, "ai": ai, "reply": say(plan, fp, mx, source, judged, ai)}
            job.stage = "done"
        except Exception as e:  # noqa: BLE001 -- the dialog shows it; nothing was changed
            job.stage, job.error = "error", str(e)[:300]
        finally:
            if on_done:
                on_done(job)

    threading.Thread(target=run, daemon=True).start()
    return job

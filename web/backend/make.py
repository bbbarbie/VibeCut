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

from . import audiomix, bed, remix, select as sel, storyboard as sb, tempo, timeline

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


def fingerprint(fmt: str, pace: str, seconds: float, styles: list[dict] | None = None,
                vibe: dict | None = None) -> dict:
    """The shape the edit should take: a chosen vibe's (vibes.py), else the
    references' when there are any, else the frame's prior. `seconds` is
    the length the brief asked for."""
    fmt = fmt if fmt in PRIOR else "tall"
    pace = pace if pace in bed.PACE_BPM else "balanced"
    if styles or vibe:
        fp = dict(vibe) if vibe else remix.fingerprint(styles)
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
    plan = remix.plan_shots(clips, fp, length=fp["duration"], cut=cut, judge=judge)
    # The hook is lifted out of its stop, not copied: a Remix played the hook
    # shot again in its place (sarah: never the same shot twice). A stop that
    # was only its hook is not lost: it opens the video.
    hooked = {p.shot.id for p in plan.hook}
    for sess in plan.sessions:
        sess[:] = [p for p in sess if p.shot.id not in hooked]
    return plan


END_BEATS = 2            # the last shot holds at least this many beats, so the end lands [prior]


def end_strong(plan: sel.Plan) -> bool:
    """A short lands on something: the last stop's strongest moment goes
    last. The hook is deliberate; before this the ending was whatever came
    last in the day (eval 2026-10-11: a day that winds down ended on its
    quietest footage). Only the last stop is reordered, and only if its
    strongest isn't already last. Returns whether anything moved."""
    if not plan.sessions or not plan.sessions[-1]:
        return False
    last = plan.sessions[-1]
    best = max(last, key=lambda p: p.score)
    if last[-1] is best:
        return False
    last.remove(best)
    last.append(best)
    best.why = (best.why + "; ends the video").strip("; ")
    return True


def end_beats(fp: dict, period: float) -> int:
    """How many beats the ending holds: the references' last shot in beats
    (1–4), else END_BEATS."""
    last = fp.get("last_s")
    if last:
        return int(min(4, max(1, round(float(last) / period))))
    return END_BEATS


def hold_ending(clips: dict[str, dict], plan: sel.Plan, period: float, beats: int = END_BEATS) -> None:
    """The last shot gets `beats` beats if it was filmed long enough."""
    if not plan.sessions or not plan.sessions[-1]:
        return
    p = plan.sessions[-1][-1]
    want = beats * period
    if p.duration + 1e-3 < want:
        p.start, p.end, p.short = sel.window(clips, p.shot, want)


def pace_of(fp: dict) -> str:
    """The cut's own tempo word, from the shots it was made of."""
    med = float(fp.get("median_s") or 2.0)
    return "fast" if med < 1.3 else "calm" if med > 3.0 else "balanced"


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
        hold_ending(clips, plan, mx["period"], end_beats(fp, mx["period"]))
        hook_s = sum(p.duration for p in plan.hook) or hook_s
        mx["in"] = round(max(0.0, mx["drop"] - hook_s), 3)
    return mx, source


def ops(plan: sel.Plan, fp: dict, mx: dict | None, fmt: str, look: str | None, about: str,
        talking: set[str], name: str = "Your video") -> list[dict]:
    """Everything the turn applies: the board, the bed, the look, the words."""
    ramp = ramp_hook(plan, mx, fmt)
    board = remix.board_of(plan, fp, name)
    board["option"] = "made"
    board["structure"] = ("Made from your clips in the style of your references — " if fp.get("refs_used")
                          else "Made from your clips — ") + remix.describe(fp)
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
    out.extend(punches(plan, mx))
    if ramp:
        hook_key, cut_at, second = ramp
        out.append({"op": "split", "shot": hook_key, "at": cut_at})
        out.append({"op": "set_shot", "shot": second, "speed": RAMP_SPEED})
        if look in FLASH_LOOKS:
            out.append({"op": "set_transition", "shot": second, "kind": "flash", "dur": FLASH_S})
    elif look in FLASH_LOOKS and plan.hook and mx:
        out.append({"op": "set_transition", "shot": plan.hook[-1].shot.id, "kind": "flash", "dur": FLASH_S})
    # the references' words: where they sit, how long they hold, whether a
    # reel that opens on its footage gets a title at all, caps or not
    text = fp.get("text")
    with_title, hold = True, None
    if text:
        if text["share"] < 0.05:
            return out                      # a wordless reel makes a wordless video
        style_op: dict = {"op": "overlay_style", "source": "reference"}
        if text.get("band") in ("bottom", "middle"):
            style_op["captions"] = text["band"]
        if text.get("upper"):
            style_op["template"] = "bold"
        if len(style_op) > 2:
            out.append(style_op)
        hold = text.get("hold_s")
        with_title = text.get("first_s") is None or text["first_s"] <= fp.get("hook_s", 1.5) + 0.5
    title = (about or "").split(",")[0].strip()[:40] or None
    for c in remix.captions(plan, title, None, hold_s=hold, with_title=with_title):
        if c["kind"] == "title":
            out.append({"op": "add_overlay", "kind": "title", "text": c["text"], "sub": c.get("sub", ""),
                        "anchor": {"to": "edit"}, "at": 0.0, "dur": round(c["end"] - c["start"], 2), "anim": "rise"})
        elif c["kind"] == "scene":
            out.append({"op": "add_overlay", "kind": "part", "text": c["text"], "pos": "top", "size": "S",
                        "start": c["start"], "dur": round(c["end"] - c["start"], 2), "anim": "rise"})
    return out


# Motion on the beat [priors]: the hook pushes in, the first shot after the
# drop hits (a harder push), every bar's first shot pushes a little,
# alternating in and out so nothing sits still. The reels the creator
# brought are built on this; before 2026-10-18 only text moved.
PUSH_HOOK, PUSH_HIT, PUSH_BAR = 0.08, 0.14, 0.05
BAR_BEATS = 4


def punches(plan: sel.Plan, mx: dict | None) -> list[dict]:
    """set_shot ops with a push per shot: the hook, the hit on the drop, the
    bars. With no beat known, only the hook and the first body shot move."""
    out: list[dict] = []
    seen: set[str] = set()

    def push(pick: sel.Pick, z: float) -> None:
        k = pick.shot.id
        if k in seen:
            return
        seen.add(k)
        out.append({"op": "set_shot", "shot": k, "punch": round(z, 3)})

    for h in plan.hook:
        push(h, PUSH_HOOK)
    body = [p for sess in plan.sessions for p in sess]
    if not body:
        return out
    push(body[0], PUSH_HIT)
    if mx:
        period, sign = mx["period"], 1
        t = body[0].duration
        for p in body[1:]:
            beat = t / period
            if abs(beat - round(beat / BAR_BEATS) * BAR_BEATS) < 0.26:   # this shot starts a bar
                push(p, sign * PUSH_BAR)
                sign = -sign
            t += p.duration
    return out


# Into the drop [priors]: the hook's last beat runs at RAMP_SPEED (two beats
# of footage in one), and for the loud looks a white flash sits on the cut.
# Both are the ops a person could do by hand (split, speed, a transition),
# so they show in History and undo like anything else.
RAMP_SPEED = 2.0
FLASH_LOOKS = ("hype", "playful")
FLASH_S = 0.2


def ramp_hook(plan: sel.Plan, mx: dict | None, fmt: str) -> tuple[str, float, str] | None:
    """Extend the hook by one beat of footage so its last beat can run at
    RAMP_SPEED without moving the drop. Returns (hook key, split at, second
    piece's key) or None when there's no beat, no hook, or no footage past it."""
    if not mx or not plan.hook or fmt != "short":
        return None
    p = plan.hook[-1]
    period = mx["period"]
    if p.duration < 2 * period - 1e-3 or p.end + period > p.shot.end + 1e-3:
        return None
    cut_at = round(p.end - period, 3)         # the last sequence beat starts here…
    p.end = round(p.end + period, 3)          # …and shows two beats of footage, at 2×
    return p.shot.id, cut_at, f"{p.shot.id}~{int(round(cut_at * 1000))}"


def say(plan: sel.Plan, fp: dict, mx: dict | None, source: str, judged: bool) -> str:
    parts = [f"Made your video: {len(plan.picks)} moments, {plan.duration:.0f} s"
             + (", in the style of your references" if fp.get("refs_used") else "") + "."]
    t = fp.get("text")
    if fp.get("refs_used") and t:
        parts.append("No words, like the reel." if t["share"] < 0.05 else
                     f"Words at the {t.get('band') or 'bottom'}, held about {t.get('hold_s') or 1.5:.1f} s, like the reel.")
    if mx:
        parts.append(f"Music: {mx['track'].title} ({mx['bpm']:.0f} BPM, from {source}); every cut sits on its beat, "
                     "the hook speeds into the drop, the picture pushes in on it and on every bar.")
    elif source.startswith("off"):
        parts.append("No music, as you had it last time; Music in the rail puts one under it.")
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
          own: list[mu.Track] | None, styles: list[dict] | None, judge, on_done, want_music: bool = True,
          register=None, vibe: dict | None = None) -> Job:
    """Run the pipeline in a thread; `on_done(job)` puts the ops on the session.
    Everything the thread needs is copied in now, so later edits can't move it.
    `register(job)` is called before the thread starts: a fast job (no music,
    few clips) can finish before the caller has even seen it."""
    job = Job()
    JOBS[job.id] = job
    if register:
        register(job)

    def progress(done: int, total: int) -> None:
        job.done, job.total = done, total

    def run() -> None:
        try:
            job.stage = "choosing"
            fp = fingerprint(fmt, pace, seconds, styles, vibe)
            plan = moments(clips, cut, fp, judge)
            if not plan.picks:
                raise ValueError("none of the clips had a moment worth keeping — add more footage")
            end_strong(plan)
            job.stage = "music"
            mx, source = (music(clips, plan, fp, pace, own, progress) if want_music
                          else (None, "off, as last time"))
            job.stage = "words"
            pool, _ = sb.usable(sb.shots_from_clips(list(clips.values()), cut))
            talking = tempo.talking(list(clips.values()), pool)
            judged = any(n.startswith("Claude judged") for n in plan.notes)
            job.result = {"ops": ops(plan, fp, mx, fmt, look, about, talking), "music": mx, "fp": fp,
                          "plan": plan, "reply": say(plan, fp, mx, source, judged)}
            job.stage = "done"
        except Exception as e:  # noqa: BLE001 -- the dialog shows it; nothing was changed
            job.stage, job.error = "error", str(e)[:300]
        finally:
            if on_done:
                on_done(job)

    threading.Thread(target=run, daemon=True).start()
    return job

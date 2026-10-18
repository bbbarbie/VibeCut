"""The story editor: a model that reads the shoot and plans the video.

Why this exists (sarah, 2026-10-18, comparing VibeCut with a London day
vlog she loves): that vlog is told in named chapters ("Morning Routine",
"OOTD", "Hit the stores"), each cut as a little story -- a quick setup, a
few short steps, one long payoff -- under a designed chapter title with a
plain line beneath it. VibeCut could not do this: on-device AI only
measures (labels, faces, sound), and hand-written rules pick one strong
moment per stop, each about as long as the next, with a clock time on it.
Nothing understood what was happening. "Is it just one action of taking
something, or a storytelling moment?" is a question about meaning, so a
model that can see the frames answers it.

What the model gets: up to MAX_CANDIDATES moments the rough cut kept (one
index frame each at low detail, plus what the device measured: time, stop,
labels, faces, talking, laughter, its worth). What it gives back: chapters
named by what happens, which moments each keeps, in what order, each with a
job (setup / step / payoff) and a length for that job, a subtitle line and a
title look per chapter. The rules still make the windows (the busiest
second), the beat grid and the music; the model never invents a frame or a
word the footage doesn't support.

One call per video. No answer, a bad answer, no key, or no yes to spending
it (oai.enabled): the rules' edit, exactly as before, and the reply says why.
Every number below is a prior.
"""

from __future__ import annotations

from . import oai, select as sel, storyboard as sb

MAX_CANDIDATES = 60          # frames sent; ~85 tokens each at low detail
# Seconds a shot holds for its job in a chapter, by frame [prior; the
# reference vlog: setups ~1-1.5 s, steps ~1-2 s, payoffs 3-4.5 s, a short
# cut about twice as fast].
ROLE_S = {
    "short": {"setup": (0.5, 1.2), "step": (0.6, 1.5), "payoff": (1.4, 3.0)},
    "tall": {"setup": (0.8, 1.6), "step": (1.0, 2.2), "payoff": (2.5, 4.5)},
    "wide": {"setup": (0.8, 1.6), "step": (1.0, 2.2), "payoff": (2.5, 4.5)},
}
HEADING_LOOKS = ("script", "spaced", "bold", "serif")
HEADING_S = 2.4              # how long a chapter title stays up [prior]
MAX_CHAPTERS = 8

SYSTEM = """You are the editor of a vlog. The creator filmed a day (or a trip) on their phone and wants it cut like the vlogs they love: told in short named chapters, each one a little story.

You get the moments that survived a rough cut, in filming order. Each has a number, what the phone measured (time, which stop of the day, image labels, faces, talking, laughter, a 0-1 worth score) and one frame. Decide the video:

- Chapters: group moments by what is happening, not just by place or hour ("Morning Routine", "Coffee Run", "OOTD", "Hit the Stores", "Night In"). 3 to 8 chapters, in the order they happened. A title is 1-3 words a creator would actually put on screen. The subtitle is one short plain line that says what happens or where ("matcha at Blank Street", "trying on everything"), lower case is fine; only name a place, shop or person if the frame or labels make it plain, never guess a brand.
- Inside a chapter, cut it like a sequence: one or two quick setup shots (arriving, the outside, a wide view), a few short steps (the actions: pouring, picking, walking in), and one payoff held longer (the reveal, the reaction, the finished thing, the view). A chapter can be only a payoff if there is nothing to build up.
- Choose what to leave out. Prefer moments where something happens, the day rather than the creator's face over and over, variety, and frames that look intended. Never keep two moments that look the same.
- Give each kept moment its job and its length in seconds, within the ranges you are given, and never longer than it was filmed. Make the total land near the target length.
- The hook: the one moment that should open the video before the first chapter, the most striking of the day (it may come from late in the day). It must not also appear in a chapter. Null if nothing stands out.
- Pick a title look per chapter: script (handwritten, soft), spaced (wide-spaced capitals in colour), bold (big heavy capitals), serif (elegant). Vary them a little, the way a creator would.
- video_title: 2-5 words naming the whole video."""

SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["video_title", "hook", "chapters"],
    "properties": {
        "video_title": {"type": "string"},
        "hook": {"type": ["integer", "null"]},
        "chapters": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["title", "subtitle", "look", "shots"],
            "properties": {
                "title": {"type": "string"},
                "subtitle": {"type": "string"},
                "look": {"type": "string", "enum": list(HEADING_LOOKS)},
                "shots": {"type": "array", "items": {
                    "type": "object", "additionalProperties": False,
                    "required": ["n", "role", "seconds"],
                    "properties": {"n": {"type": "integer"},
                                   "role": {"type": "string", "enum": ["setup", "step", "payoff"]},
                                   "seconds": {"type": "number"}}}},
            }}},
    },
}


class StoryError(Exception):
    pass


# --------------------------------------------------------------------------
# what the model sees
# --------------------------------------------------------------------------

def candidates(clips: dict[str, dict], cut) -> list[sb.Shot]:
    """The rough cut's usable moments, look-alikes collapsed, the strongest
    MAX_CANDIDATES by worth, back in filming order."""
    shots = sb.shots_from_clips(list(clips.values()), cut)
    shots, _ = sb.usable(shots)
    shots, _ = sel.dedupe([s for s in shots if not s.utility and s.duration >= sel.MIN_SHOT_S])
    if len(shots) > MAX_CANDIDATES:
        best = sorted(shots, key=lambda s: -(s.worth if s.worth is not None else s.score))[:MAX_CANDIDATES]
        keep = {s.id for s in best}
        shots = [s for s in shots if s.id in keep]
    return sorted(shots, key=lambda s: s.order)


def _clock(s: sb.Shot) -> str:
    if not s.when:
        return "time unknown"
    h = s.when.hour % 12 or 12
    return f"{s.when.strftime('%a')} {h}:{s.when.minute:02d} {'am' if s.when.hour < 12 else 'pm'}"


def describe(k: int, s: sb.Shot, stop: int, talking: bool) -> str:
    labels = ", ".join(n for n, v in sorted(s.labels.items(), key=lambda kv: -kv[1])[:4] if v >= 0.2) or "none"
    bits = [f"#{k}", _clock(s), f"stop {stop + 1}", f"{s.duration:.1f} s filmed", f"labels: {labels}"]
    if s.faces:
        bits.append(f"{s.faces} face{'s' * (s.faces != 1)}")
    if talking:
        bits.append("talking to camera")
    bits += [w for w in s.worth_why if "laugh" in w or "sing" in w or "new place" in w]
    if s.worth is not None:
        bits.append(f"worth {s.worth:.2f}")
    return " · ".join(bits)


def content(cands: list[sb.Shot], frames: list[bytes | None], stops: dict[str, int], talking: set[str],
            fmt: str, seconds: float, about: str) -> list[dict]:
    r = ROLE_S.get(fmt, ROLE_S["tall"])
    head = (f"Target length: about {seconds:.0f} s. Frame: {'vertical short' if fmt == 'short' else 'vertical vlog' if fmt == 'tall' else 'wide 16:9 vlog'}.\n"
            f"Seconds by job: setup {r['setup'][0]}-{r['setup'][1]}, step {r['step'][0]}-{r['step'][1]}, payoff {r['payoff'][0]}-{r['payoff'][1]}.\n"
            f"What the shoot looks like (guessed from it): {about or 'a day'}.\n"
            f"{len(cands)} moments follow, in filming order.")
    out: list[dict] = [{"type": "text", "text": head}]
    for k, (s, fr) in enumerate(zip(cands, frames), 1):
        out.append({"type": "text", "text": describe(k, s, stops.get(s.id, 0), s.id in talking)})
        if fr:
            out.append(oai.image(fr))
    return out


def estimate(n: int, model: str | None = None) -> float:
    """Dollars for one plan of `n` candidates, before it's made: ~85 tokens
    a frame, ~45 a line, the instructions, and an answer with its thinking
    [prior; the real cost is read from the reply's usage]."""
    p_in, _, p_out = oai.PRICES.get(model or oai.model(), oai.DEAREST)
    tokens_in = 900 + n * (85 + 45)
    tokens_out = 1200 + n * 25 + 3000
    return (tokens_in * p_in + tokens_out * p_out) / 1e6


# --------------------------------------------------------------------------
# the answer -> a plan
# --------------------------------------------------------------------------

def plan_from(answer: dict, cands: list[sb.Shot], clips: dict[str, dict], fmt: str) -> tuple[sel.Plan, list[dict], str]:
    """Check the answer against what was offered and make the plan: the hook
    first, then one session per chapter. -> (plan, chapters [{title,
    subtitle, look}], video title). Ids that weren't offered, repeats and
    lengths outside a job's range are corrected, never trusted."""
    roles = ROLE_S.get(fmt, ROLE_S["tall"])
    used: set[int] = set()

    def take(n) -> sb.Shot | None:
        if not isinstance(n, int) or not 1 <= n <= len(cands) or n in used:
            return None
        used.add(n)
        return cands[n - 1]

    def pick(s: sb.Shot, role: str, secs: float, sess: int) -> sel.Pick:
        lo, hi = roles.get(role, roles["step"])
        try:
            want = float(secs)
        except (TypeError, ValueError):
            want = (lo + hi) / 2
        want = min(max(want, lo), hi)
        a, b, short = sel.window(clips, s, want)
        # the beat grid (remix.quantise) holds payoffs on whole beats, the rest on half-beats
        return sel.Pick(s, "hero" if role == "payoff" else "filler", a, b, s.worth or s.score, role, sess, short)

    hook_shot = take(answer.get("hook"))
    hook = [pick(hook_shot, "payoff", roles["payoff"][0], 0)] if hook_shot else []
    if hook:
        hook[0].role = "hook"
    sessions, chapters = [], []
    for ch in (answer.get("chapters") or [])[:MAX_CHAPTERS]:
        if not isinstance(ch, dict):
            continue
        i = len(sessions)
        picks = []
        for sh in ch.get("shots") or []:
            if not isinstance(sh, dict):
                continue
            s = take(sh.get("n"))
            if s is not None:
                picks.append(pick(s, sh.get("role") if sh.get("role") in roles else "step", sh.get("seconds"), i))
        if not picks:
            continue
        sessions.append(picks)
        title = " ".join(str(ch.get("title") or "").split())[:40] or f"Part {i + 1}"
        chapters.append({"title": title, "subtitle": " ".join(str(ch.get("subtitle") or "").split())[:60],
                         "look": ch.get("look") if ch.get("look") in HEADING_LOOKS else "bold"})
    if not sessions:
        raise StoryError("the plan kept no moments")
    plan = sel.Plan(hook=hook, sessions=sessions, titles=[c["title"] for c in chapters])
    kept = sum(len(s) for s in sessions) + len(hook)
    plan.notes.append(f"Planned as {len(chapters)} chapters from {len(cands)} moments; kept {kept}.")
    return plan, chapters, " ".join(str(answer.get("video_title") or "").split())[:50]


def heading_ops(plan: sel.Plan, chapters: list[dict]) -> list[dict]:
    """A chapter title with its subtitle under it, at the start of each
    chapter (board beats r1.. as remix.board_of numbers them), held
    HEADING_S or the chapter's length if shorter."""
    out = []
    for i, (picks, ch) in enumerate(zip(plan.sessions, chapters), 1):
        span = sum(p.duration for p in picks)
        out.append({"op": "add_overlay", "kind": "heading", "text": ch["title"], "sub": ch["subtitle"],
                    "look": ch["look"], "beat": f"r{i}", "at": 0.0,
                    "dur": round(max(0.8, min(HEADING_S, span - 0.1)), 2)})
    return out


# --------------------------------------------------------------------------
# the call
# --------------------------------------------------------------------------

def plan(clips: dict[str, dict], cut, fmt: str, seconds: float, about: str, post=None):
    """-> (plan, chapters, video title, usage). Raises StoryError / oai.OAIError."""
    from . import brief, tempo
    cands = candidates(clips, cut)
    if len(cands) < 3:
        raise StoryError("too few moments to plan a story")
    frames = [sel._frame(clips, s) for s in cands]
    stops = brief.spots(cands)
    talking = tempo.talking(list(clips.values()), cands)
    answer, usage = oai.ask_json(SYSTEM, content(cands, frames, stops, talking, fmt, seconds, about),
                                 SCHEMA, "story_plan", post=post)
    p, chapters, title = plan_from(answer, cands, clips, fmt)
    return p, chapters, title, usage

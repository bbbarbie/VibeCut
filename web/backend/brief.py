"""A few style questions before the first edit, and what the answers do.

After the clips are in and the creator has said in one line what the video
is about, they get a short multiple-choice round -- how long, how it
should feel, how it opens, what it's mostly about -- the way an editor
would ask before touching anything. The fixed questions work without a
language model; with a key, Claude may add one or two questions tailored
to the description, whose answers only become part of the direction text.

Only questions whose answer changes the edit are asked. Length, pace and
opening reshape each proposal here (`shape`); focus becomes theme words
the storyboard already leans on. The targets below are guesses, like
every threshold in cutgrammar.
"""

from __future__ import annotations

import copy
from collections import Counter

# Rough target lengths. "long" keeps every usable shot.
LENGTH_S = {"short": 60.0, "medium": 180.0, "long": None}
# Longest a single shot may run at each pace, around its best frame.
PACE_CAP_S = {"calm": 8.0, "balanced": 5.0, "fast": 2.5}
MIN_SHOT_S = 1.5
# A short or fast edit shows each moment once: several shots of the same
# clip, or look-alikes (same cosine cut-off as remix's select.py), are one
# moment, and only its strongest shot stays. Longer, calmer edits keep them.
SIMILAR = 0.78
# Look-alikes only count as one moment when filmed close together, as
# retakes are (same window as cutgrammar.reject's duplicate rule): the same
# café in the morning and again at night is two moments, not a stutter.
RETAKE_WINDOW_S = 15 * 60
OPENINGS = ("hook", "start")
STYLE_KEYS = {"length": tuple(LENGTH_S), "pace": tuple(PACE_CAP_S), "opening": OPENINGS}

# Focus choices, each a storyboard theme (storyboard.THEMES).
FOCUS = [("people", "Me and the people I was with"), ("food", "Food and drinks"),
         ("city", "Streets and places"), ("nature", "Nature and outdoors"),
         ("night", "Evenings and nights"), ("sea", "Beach and water")]
MIN_FOCUS_SHOTS = 3


def fixed_questions(theme_counts: Counter | None = None) -> list[dict]:
    """The questions every creator gets. Focus lists only themes the
    footage actually has, so no answer points at nothing."""
    qs = [
        {"id": "length", "question": "How long should it be?", "multi": False, "choices": [
            {"key": "short", "label": "Short", "hint": "Under a minute, for Reels, TikTok or Shorts"},
            {"key": "medium", "label": "Medium", "hint": "About three minutes"},
            {"key": "long", "label": "Long", "hint": "Keep every good moment, a full vlog"}]},
        {"id": "pace", "question": "How should it feel?", "multi": False, "choices": [
            {"key": "calm", "label": "Slow and calm", "hint": "Let the shots breathe"},
            {"key": "balanced", "label": "Balanced", "hint": "A steady rhythm"},
            {"key": "fast", "label": "Fast and punchy", "hint": "Quick cuts, lots of energy"}]},
        {"id": "opening", "question": "How should it start?", "multi": False, "choices": [
            {"key": "hook", "label": "With the best moment", "hint": "A hook first, then the story"},
            {"key": "start", "label": "From the beginning", "hint": "In the order it happened"}]},
    ]
    counts = theme_counts or Counter()
    focus = [{"key": k, "label": label} for k, label in FOCUS if counts.get(k, 0) >= MIN_FOCUS_SHOTS]
    if len(focus) >= 2:
        qs.append({"id": "focus", "question": "What should it mostly be about?", "multi": True,
                   "hint": "Pick any, or none for a bit of everything", "choices": focus})
    return qs


def theme_counts(shots) -> Counter:
    """How many shots each focus theme would lean on."""
    from . import storyboard as sb
    c: Counter = Counter()
    for k, _ in FOCUS:
        d = sb.Direction(k, [k], [k], [], set(sb.THEMES[k]))
        c[k] = sum(sb.matches(s, d) for s in shots)
    return c


def clean_style(style: dict | None) -> dict | None:
    """Only the keys and values `shape` knows; anything else is dropped."""
    if not style:
        return None
    out = {k: style[k] for k, allowed in STYLE_KEYS.items() if style.get(k) in allowed}
    return out or None


def describe(style: dict | None) -> str:
    """A few plain words for the proposal summaries."""
    if not style:
        return ""
    bits = {"short": "short (about a minute)", "medium": "about three minutes", "long": "long"}
    words = []
    if style.get("length"):
        words.append(bits[style["length"]])
    if style.get("pace"):
        words.append({"calm": "calm", "balanced": "steady", "fast": "fast-cut"}[style["pace"]])
    s = ", ".join(words)
    if style.get("opening") == "hook":
        s = f"{s}, opening on the best moment" if s else "opening on the best moment"
    return s


def _window(s, cap: float, best: dict[str, float]) -> None:
    """Shorten a shot to `cap` seconds around its best frame."""
    if s.end - s.start <= cap:
        return
    c = best.get(s.id, (s.start + s.end) / 2)
    a = min(max(s.start, c - cap / 2), s.end - cap)
    s.start, s.end = round(a, 3), round(a + cap, 3)


def one_per_moment(shots: list, rank) -> list:
    """Keep the strongest shot of each moment, in story order."""
    keep: list = []
    for s in sorted(shots, key=rank, reverse=True):
        if not any(s.clip_id == k.clip_id or float(s.vec @ k.vec) >= SIMILAR for k in keep):
            keep.append(s)
    return [s for s in shots if s in keep]


def one_per_look(options: list) -> None:
    """Every proposal, whatever the answers: look-alike shots in one part --
    the same view filmed twice, a retake -- keep only their strongest. A
    viewer reads two near-identical shots in a row as a stutter, not a
    story, and it's the most common reason an auto-edit feels like a pile of
    clips. Different shots of one clip are left alone here (a walk filmed in
    one take is several moments); short and fast edits still collapse those
    too (`one_per_moment`). Only for proposals built with on-device Vision:
    the colour-histogram fallback calls far too much "alike"."""
    rank = lambda s: s.score + (0.15 if s.lean else 0.0)  # noqa: E731
    for o in options:
        dropped = 0
        for b in o.beats:
            keep: list = []
            for s in sorted(b.shots, key=rank, reverse=True):
                if not any(s.clip_id != k.clip_id and s.vec.shape == k.vec.shape
                           and float(s.vec @ k.vec) >= SIMILAR and _close(s, k) for k in keep):
                    keep.append(s)
            dropped += len(b.shots) - len(keep)
            b.shots = [s for s in b.shots if s in keep]
        o.beats = [b for b in o.beats if b.shots]
        if dropped:
            o.notes.append(f"Kept the best of each look-alike: {dropped} near-repeat shot"
                           f"{'s' * (dropped != 1)} left on the shelf.")


def _close(a, b) -> bool:
    if a.when is None or b.when is None:
        return True
    return abs((a.when - b.when).total_seconds()) <= RETAKE_WINDOW_S


def shape(options: list, style: dict | None, best: dict[str, float]) -> None:
    """Reshape storyboard.Option objects in place to the creator's answers.

    Order within the story is never changed except by the hook, which lifts
    the single strongest shot to the front. Short or fast edits keep one shot
    per moment (`one_per_moment`). Length is met by leaving out the
    weakest shots first, but every part keeps at least its best one.
    """
    from .storyboard import Beat

    style = clean_style(style)
    if not style:
        return
    rank = lambda s: s.score + (0.15 if s.lean else 0.0)  # noqa: E731
    for o in options:
        # Shots are shared between the proposals (and the voiceover one).
        for b in o.beats:
            b.shots = [copy.copy(s) for s in b.shots]
        cap = PACE_CAP_S.get(style.get("pace", ""))
        if cap:
            for b in o.beats:
                for s in b.shots:
                    _window(s, max(cap, MIN_SHOT_S), best)

        if style.get("length") == "short" or style.get("pace") == "fast":
            for b in o.beats:
                b.shots = one_per_moment(b.shots, rank)
        if style.get("opening") == "hook":
            everything = [s for b in o.beats for s in b.shots]
            if len(everything) > 1:
                top = max(everything, key=rank)
                for b in o.beats:
                    if top in b.shots:
                        b.shots.remove(top)
                o.beats = [b for b in o.beats if b.shots]
                o.beats.insert(0, Beat("Opening", "The strongest moment first, as a hook.", [top], top.lean))

        target = LENGTH_S.get(style.get("length", ""))
        if target:
            total = sum(s.end - s.start for b in o.beats for s in b.shots)
            # Drop the weakest shot that isn't the last one left in its part.
            while total > target:
                spare = [(rank(s), bi, s) for bi, b in enumerate(o.beats) if len(b.shots) > 1 for s in b.shots]
                if not spare:
                    break
                _, bi, s = min(spare, key=lambda t: t[0])
                o.beats[bi].shots.remove(s)
                total -= s.end - s.start
            # Still over: whole parts go, weakest first, never the opening.
            while total > target and len(o.beats) > 1:
                first = 1 if style.get("opening") == "hook" else 0
                pool = range(first, len(o.beats))
                if not pool:
                    break
                bi = min(pool, key=lambda i: max(rank(s) for s in o.beats[i].shots))
                total -= sum(s.end - s.start for s in o.beats[bi].shots)
                del o.beats[bi]

        said = describe(style)
        if said:
            o.summary = f"{o.summary} Shaped to your answers: {said}.".strip()

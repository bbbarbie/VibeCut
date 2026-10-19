"""The vlog grammar: scenes, the three-shot rule, stillness.

Why this exists (2026-10-19, after the creator watched a made video: "the
cut is too random, it's not those pretty vlogs on YouTube"). Laid out shot
by shot, her cut was 28 singles of 0.6–1.1 s, grouped by 45-minute gaps,
every one chosen on its own worth and none on what sat next to it. The
vlogs she means do three things ours didn't (design/research 01, 06, and
the editing-craft reading of 2026-10-19):

1. **Scenes, not sessions.** A scene is a place and an activity: a new
   one when the GPS moves on or twenty minutes pass (brief.spots), not
   when forty-five minutes do. Four to seven scenes for a 90-second vlog.
2. **The three-shot rule.** Inside a scene the shots run wide → medium →
   close: the place, the person doing the thing, the detail (the plate,
   the cup, the hands, the face). Two look-alikes never sit together.
   A scene ends on a detail or a face, not on a passing street.
3. **Stillness.** The longest holds go to the stillest shots -- a window,
   a cup, a view -- and a handheld walk gets a short one. Shots run 3–6 s
   (make.PRIOR for tall / wide), cut where the action ends.

What the index already knows is enough for all three: face area and face
count for shot size, labels for details, per-second motion for stillness,
GPS and capture time for scenes. Nothing new is read from the files.
Every threshold here is a prior until the creator says otherwise.
"""

from __future__ import annotations

import numpy as np

from . import brief, select as sel, storyboard as sb

CLOSE_FACE = 0.06        # a face this big is a close shot
MEDIUM_FACE = 0.015      # a face this big is a medium shot
DETAIL = {"plate", "tableware", "utensil", "cup", "drinking_glass", "fork", "spoon", "cookware", "food", "dessert",
          "beverage", "plant", "foliage", "flower", "book", "document", "laptop", "computer", "keyboard", "pen",
          "office_supplies", "consumer_electronics", "art", "decoration", "frame", "textile", "jewelry", "hat", "shoe",
          "eyeglasses", "raw_glass", "appliance", "machine"}
WIDE = {"outdoor", "sky", "blue_sky", "cloudy", "night_sky", "land", "structure", "road", "path", "crosswalk", "grass",
        "fence", "conveyance", "portal", "interior_room", "window", "door", "stairs", "crowd"}
LOOKALIKE = 0.78         # embedding cosine: the same view again
STILL, BUSY = 15.0, 40.0 # per-second motion (index units): rest, and walking with the phone
STILL_HOLD, BUSY_HOLD = 1.5, 0.7
MIN_HOLD_S, MAX_HOLD_S = 1.5, 7.0
MAX_SCENES = 7
MIN_PICK_S = 2.5         # a shot filmed shorter than this can't hold a vlog's pace
LENGTH_OK = 0.9          # a vlog this close to the length asked for is left alone
ASK_MORE_MAX = 1.6       # ...else more moments are asked for, at most this many times over


def shot_size(s) -> str:
    """wide / medium / close, from what the index knows of the frame."""
    fa = float(getattr(s, "face_area", 0.0) or 0.0)
    top = [k for k, _ in sorted((getattr(s, "labels", None) or {}).items(), key=lambda kv: -kv[1])[:4]]
    if fa >= CLOSE_FACE or any(t in DETAIL for t in top[:2]):
        return "close"
    if fa >= MEDIUM_FACE or (getattr(s, "faces", 0) or 0) > 0:
        return "medium"
    return "wide"


def _sim(a, b) -> float:
    va, vb = getattr(a, "vec", None), getattr(b, "vec", None)
    if va is None or vb is None or getattr(va, "size", 0) == 0 or va.size != vb.size:
        return 0.0
    return float(np.dot(va, vb))


def sequence(picks: list[sel.Pick]) -> list[sel.Pick]:
    """The three-shot order for one scene: wide, then medium, then close,
    each class in filming order; look-alikes kept apart; the scene ends on
    a close shot or a face when it has one."""
    if len(picks) <= 1:
        return list(picks)
    rank = {"wide": 0, "medium": 1, "close": 2}
    ordered = sorted(picks, key=lambda p: (rank[shot_size(p.shot)], p.shot.order))
    # keep look-alikes apart: a shot too like the one before it moves one place
    # on, once; when everything left looks the same there is nothing to do
    out: list[sel.Pick] = []
    pending = list(ordered)
    deferred: set[str] = set()
    while pending:
        nxt = pending.pop(0)
        if out and pending and nxt.shot.id not in deferred and _sim(out[-1].shot, nxt.shot) >= LOOKALIKE:
            deferred.add(nxt.shot.id)
            pending.insert(1, nxt)
            continue
        out.append(nxt)
    # end on a detail or a face
    last_close = next((i for i in range(len(out) - 1, -1, -1)
                       if shot_size(out[i].shot) == "close" or (getattr(out[i].shot, "faces", 0) or 0) > 0), None)
    if last_close is not None and last_close != len(out) - 1:
        out.append(out.pop(last_close))
    return out


def scenes(plan: sel.Plan) -> None:
    """Regroup the plan's picks into scenes in place: a stop of the day
    (brief.spots: a place, twenty minutes) is sequenced wide -> medium ->
    close on its own; stops are then folded, smallest neighbours first,
    into at most MAX_SCENES, and a folded scene keeps its stops in the
    order of the day -- breakfast never comes after the walk."""
    picks = [p for sess in plan.sessions for p in sess]
    if not picks:
        return
    where = brief.spots([p.shot for p in picks])
    groups: dict[int, list[sel.Pick]] = {}
    for p in picks:
        groups.setdefault(where.get(p.shot.id, 0), []).append(p)
    stops = [sequence(sorted(g, key=lambda p: p.shot.order)) for _, g in sorted(groups.items())]
    plan.sessions = sb._merge_smallest(stops, MAX_SCENES, key=None)
    plan.titles = titles(plan.sessions)
    for i, sess in enumerate(plan.sessions):
        for p in sess:
            p.session = i


def titles(sessions: list[list[sel.Pick]]) -> list[str]:
    """A part's name: the time of day, and the clock when a day has two
    afternoons ("Afternoon", "Afternoon, 3 pm"); never "Part 4"."""
    out: list[str] = []
    for i, g in enumerate(sessions):
        when = g[0].shot.when if g else None
        if not when:
            out.append(f"Scene {i + 1}")
            continue
        name = sb.part_of_day(when)
        if any(t == name or t.startswith(name + ",") for t in out):
            h = when.hour % 12 or 12
            name = f"{name}, {h}{':%02d' % when.minute if when.minute else ''} {'am' if when.hour < 12 else 'pm'}"
        out.append(name)
    return out


def stillness(s) -> float:
    """How much longer (or shorter) a shot may hold than the median: still
    frames rest, handheld walks don't."""
    a = float(getattr(s, "activity", 0.0) or 0.0)
    return STILL_HOLD if a < STILL else BUSY_HOLD if a > BUSY else 1.0


def breathe(plan: sel.Plan, clips: dict, fp: dict) -> dict:
    """Give every pick a hold: the vlog's median, the arc's curve for where
    it sits, times its stillness, clamped to MIN_HOLD_S..MAX_HOLD_S; cut in
    where the action is (select.window). Returns a small report."""
    seq = [p for sess in plan.sessions for p in sess]
    n = max(len(seq), 1)
    med = float(fp.get("median_s") or 4.0)
    curve = fp.get("curve") or [1.0] * 5
    held, short = 0, 0
    for k, p in enumerate(seq):
        pos = (k + 0.5) / n
        c = float(np.interp(pos * (len(curve) - 1), range(len(curve)), curve))
        want = float(np.clip(med * c * stillness(p.shot), MIN_HOLD_S, MAX_HOLD_S))
        p.start, p.end, p.short = sel.window(clips, p.shot, want)
        held += stillness(p.shot) > 1.0
        short += p.short
    return {"shots": len(seq), "still_held": held, "filmed_too_short": short, "median_s": med}


def describe(plan: sel.Plan) -> str:
    sizes = [[shot_size(p.shot) for p in sess] for sess in plan.sessions]
    return f"{len(plan.sessions)} scenes, " + "; ".join("→".join(x[0] for x in s) for s in sizes if s)

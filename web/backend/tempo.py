"""The edit's tempo and its starting story, read from the shoot itself.

No questions (sarah, 2026-10-07: "based on the material that i send you
you should be able to realize what kind of editing tempo we want"). A shoot
full of movement, music and short clips wants quick cuts; one of talking,
views and still moments wants room to breathe. Talking is never cut mid-
sentence at any pace: those shots keep their whole rough-trim window.

Which story to start from is read the same way: one day follows the clock,
several days around several places follow the places, a shoot that is
mostly one person on camera follows them.

Every threshold here is a prior, set on one real shoot, not calibrated.
"""

from __future__ import annotations

import statistics

from cutgrammar.signals import VOICE_HI

from . import storyboard as sb

# Mean picture change between keyframes (0-255 luma, indexer "activity"):
# at or above MOVING a shot is walking, riding, dancing; at or under STILL it
# is a view, a table, a face holding still. On her 42-clip shoot handheld
# walking clips read 35-50, two long calm views 4.7 and 6.2. [prior]
MOVING, STILL = 30.0, 10.0
# Share of the shots (moving / still) or of the kept seconds (talking /
# music) it takes to set the tempo. Shots, not seconds, for the picture: one
# long view shouldn't outvote thirty quick moments. [prior]
MOSTLY = 0.4
TALKY = 0.3
MUSIC = 0.3
# Clips this short or shorter (median) were filmed as quick glimpses. [prior]
GLIMPSE_S = 6.0
# A subject story only when one person is on camera this much of the time.
ON_CAMERA = 0.6
FACE_AREA = 0.04  # storyboard.by_subject's "on camera"
NAMES = {"fast": "Quick cuts", "balanced": "Steady cuts", "calm": "Calm cuts"}


def _secs(rec: dict, key: str, a: float, b: float) -> list[float]:
    vals = (rec.get("sound") or {}).get(key) or []
    return vals[int(a):max(int(a) + 1, int(b + 0.999))]


def talking(clips: list[dict], shots: list[sb.Shot]) -> set[str]:
    """Shots where someone is talking for most of the window."""
    by_id = {c["id"]: c for c in clips}
    out = set()
    for s in shots:
        v = _secs(by_id.get(s.clip_id, {}), "voice", s.start, s.end)
        if v and sum(v) / len(v) >= VOICE_HI:
            out.add(s.id)
    return out


def read(clips: list[dict], cut: tuple[set, dict] | None = None) -> dict:
    """{"pace": fast | balanced | calm, "why": one plain sentence}."""
    shots, _ = sb.usable(sb.shots_from_clips(clips, cut))
    total = sum(s.end - s.start for s in shots)
    if not shots or total <= 0:
        return {"pace": "balanced", "why": "There wasn't enough to read, so steady cuts."}
    share = lambda f: sum(1 for s in shots if f(s)) / len(shots)  # noqa: E731
    moving = share(lambda s: s.activity >= MOVING)
    still = share(lambda s: s.activity <= STILL)
    by_id = {c["id"]: c for c in clips}
    heard = [x for s in shots for x in _secs(by_id.get(s.clip_id, {}), "voice", s.start, s.end)]
    music = [x for s in shots for x in _secs(by_id.get(s.clip_id, {}), "music", s.start, s.end)]
    talk = sum(x >= VOICE_HI for x in heard) / len(heard) if heard else 0.0
    tune = sum(x >= VOICE_HI for x in music) / len(music) if music else 0.0
    kept = {s.clip_id for s in shots}
    glimpses = statistics.median(float(by_id[c].get("duration") or 0) for c in kept) <= GLIMPSE_S

    quick, slow = [], []
    if moving >= MOSTLY:
        quick.append("lots of movement")
    if tune >= MUSIC:
        quick.append("music playing")
    if glimpses:
        quick.append("short clips")
    if talk >= TALKY:
        slow.append("a lot of talking")
    if still >= MOSTLY:
        slow.append("calm, still shots")
    score = len(quick) - len(slow) - (talk >= TALKY)  # talking counts double
    pace = "fast" if score >= 2 else "calm" if score <= -1 else "balanced"
    why = {"fast": quick, "calm": slow, "balanced": quick + slow}[pace]
    if pace == "balanced" and quick and slow:
        said = f"mix {' and '.join(quick)} with {' and '.join(slow)}"
    elif why:
        said = "have " + " and ".join(why[:2])
    else:
        said = "have a bit of everything"
    return {"pace": pace, "why": f"{NAMES[pace]}: your clips {said}.",
            "facts": {"moving": round(moving, 2), "still": round(still, 2), "talking": round(talk, 2),
                      "music": round(tune, 2), "short_clips": glimpses}}


def pick_story(options: list[sb.Option], shots: list[sb.Shot]) -> tuple[str, str]:
    """(option key, why) for the story to start from."""
    have = {o.key: o for o in options}
    timed = [s for s in shots if s.when]
    days = len({s.when.date() for s in timed})
    total = sum(s.end - s.start for s in shots) or 1.0
    on_cam = sum(s.end - s.start for s in shots if s.face_area >= FACE_AREA) / total
    place = have.get("place")
    places = len({b.title.split(" again")[0].split(" — ")[0] for b in place.beats
                  if b.title.startswith("Place ")}) if place and not place.degraded else 0
    subject = have.get("subject")
    if subject and not subject.degraded and on_cam >= ON_CAMERA:
        return "subject", "It follows you on camera, since you're in most of the clips."
    if days > 1 and places >= 3:
        return "place", f"It follows the places, since you moved between {places} of them over {days} days."
    if days > 1:
        return "time", f"It follows the days in order ({days} of them)."
    return "time", "It follows your day in the order it happened."


def pace_ops(board: dict, cat, windows: dict, pace: str, talk: set[str]) -> list[dict]:
    """Every shot retimed to `pace`: its rough-trim window, at most the pace's
    longest shot around its best frame. Talking keeps its whole window."""
    from . import brief
    from .board import key, is_gap
    cap = brief.PACE_CAP_S[pace]
    ops = []
    for bt in board.get("beats", []):
        for e in bt["shots"]:
            if is_gap(e) or e["id"] not in cat.shots:
                continue
            src = cat.shots[e["id"]]
            a, b = windows.get(e["id"], (src.start, src.end))
            if e["id"] not in talk and b - a > cap:
                c = cat.best_t.get(e["id"], (a + b) / 2)
                a = min(max(a, c - cap / 2), b - cap)
                b = a + cap
            a, b = round(a, 3), round(b, 3)
            k = key(e)
            # widen first so the two trims never cross
            moves = [("in", a), ("out", b)] if a < e["end"] else [("out", b), ("in", a)]
            for edge, to in moves:
                if abs(to - e["start" if edge == "in" else "end"]) > 1e-3:
                    ops.append({"op": "trim", "shot": k, "edge": edge, "to": to})
    return ops

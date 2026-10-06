"""Three one-line descriptions of the video, read from the footage itself.

"What's this video about?" is the first thing the creator has to type, and
a blank box after dropping 40 clips is where people stall. The shoot already
says a lot -- how many days, morning to night or one evening, what the
on-device image labels keep seeing, whether people are in it, whether
someone talks to camera, where it was filmed -- so the suggestions are built
from that, and a click is enough.

Without a key the lines come from templates over those facts. With a key,
Claude phrases them from the same facts as *text* (counts, label words,
times, rounded coordinates) -- no frame and no audio leaves the Mac. The
creator's own words still win: the typed box stays.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime

import numpy as np

from cutgrammar import trim
from cutgrammar.signals import ClipSignals

from . import brief
from . import storyboard as sb

# focus theme -> how a creator would say it (brief.FOCUS keys)
SAY = {"food": "mostly the food", "people": "with friends", "city": "exploring the streets",
       "nature": "out in nature", "night": "into the night", "sea": "by the water"}
TITLE = {"food": "Eating my way through", "people": "Time with my people", "city": "City wandering",
         "nature": "Getting outside", "night": "A night out", "sea": "A beach day"}
TALKING_SHARE = 0.3     # this much talking-to-camera and it's a talking vlog [prior]
PEOPLE_SHARE = 0.25     # shots with a face, for "with friends" [prior]


def facts(clips: list[dict]) -> dict:
    """What the shoot says about itself, in plain values."""
    shots, _ = sb.usable(sb.shots_from_clips(clips))
    whens = sorted(w for w in (sb.parse_when(c.get("capture_time")) for c in clips) if w)
    days = sorted({w.date() for w in whens})
    counts = brief.theme_counts(shots) if shots else Counter()
    talking = 0
    for c in clips:
        if c.get("signals"):
            try:
                talking += trim.is_talking(ClipSignals.from_json(c["signals"]))
            except (TypeError, KeyError):
                pass
    gps = [tuple(c["gps"]) for c in clips if c.get("gps")]
    labels: Counter = Counter()
    for s in shots:
        for k, v in s.labels.items():
            if v >= 0.3:
                labels[k] += 1
    return {
        "clips": len(clips),
        "minutes": round(sum(float(c.get("duration") or 0) for c in clips) / 60, 1),
        "days": len(days),
        "weekend": bool(days) and all(d.weekday() >= 5 for d in days),
        "weekday": days[0].strftime("%A") if len(days) == 1 else None,
        "from": whens[0] if whens else None, "to": whens[-1] if whens else None,
        "themes": [k for k, n in counts.most_common() if n >= brief.MIN_FOCUS_SHOTS],
        "faces": (sum(s.faces > 0 for s in shots) / len(shots)) if shots else 0.0,
        "talking": talking / len(clips) if clips else 0.0,
        "labels": [k for k, _ in labels.most_common(12)],
        "where": (round(float(np.mean([g[0] for g in gps])), 2), round(float(np.mean([g[1] for g in gps])), 2))
                 if gps else None,
    }


def _span(f: dict) -> str:
    if f["days"] >= 2:
        return "A weekend away" if f["weekend"] and f["days"] <= 3 else f"{f['days']} days away"
    a, b = f["from"], f["to"]
    if a and b and a.hour < 12 and b.hour >= 17:
        return "A day in my life, morning to night"
    if a and a.hour >= 17:
        return "An evening out"
    return f"A {f['weekday']} in my life" if f["weekday"] else "A day in my life"


def offline(f: dict) -> list[str]:
    """Three different lines from the facts alone."""
    themes = [t for t in f["themes"] if t in SAY]
    if f["faces"] >= PEOPLE_SHARE and "people" not in themes:
        themes.append("people")
    span = _span(f)
    out = [f"{span}, {SAY[themes[0]]}" if themes else span]
    if len(themes) >= 2:
        out.append(f"{TITLE[themes[1]]}, {SAY[themes[0]]}")
    elif themes:
        out.append(TITLE[themes[0]])
    if f["talking"] >= TALKING_SHARE:
        out.append("Talking you through my day")
    elif f["days"] >= 2:
        out.append("Trip recap, the best bits")
    elif span.startswith("An evening"):
        out.append("Out after dark")
    else:
        out.append("Just a normal day")
    seen, uniq = set(), []
    for line in out + ["A little recap", "The best bits"]:
        if line.lower() not in seen:
            seen.add(line.lower())
            uniq.append(line)
    return uniq[:3]


def as_text(f: dict) -> str:
    """The facts as the only thing Claude is shown."""
    def t(w: datetime | None) -> str:
        return w.strftime("%a %-d %b, %-I:%M %p") if w else "unknown"
    return "\n".join([
        f"clips: {f['clips']} ({f['minutes']} min of footage)",
        f"days filmed: {f['days']}" + (" (a weekend)" if f["weekend"] else ""),
        f"first clip: {t(f['from'])}; last clip: {t(f['to'])}",
        f"what the picture shows most (on-device labels): {', '.join(f['labels']) or 'unknown'}",
        f"themes: {', '.join(f['themes']) or 'none clear'}",
        f"shots with a face: {round(f['faces'] * 100)}%",
        f"clips with someone talking: {round(f['talking'] * 100)}%",
        f"filmed around (lat, lon): {f['where'] if f['where'] else 'no location'}",
    ])


def guess(clips: list[dict]) -> str:
    """What the video is, read from the shoot alone, standing in for the
    description the creator no longer types (sarah, 2026-10-06: the question
    was a step she didn't need). The first template line: its span says day /
    evening / weekend / days away, which `brief.kind_of` reads for the length
    and the captions, and its theme words lean the story. Never the model."""
    return offline(facts(clips))[0] if clips else ""


def suggest(clips: list[dict], ask_model: bool | None = None) -> dict:
    """-> {"suggestions": [3 lines], "source": "claude" | "footage"}."""
    from . import llm
    f = facts(clips)
    if ask_model is None:
        ask_model = llm.available()
    if ask_model:
        try:
            lines = llm.suggest_briefs(as_text(f))
            if len(lines) >= 3:
                return {"suggestions": lines[:3], "source": "claude"}
        except llm.LLMError:
            pass
    return {"suggestions": offline(f), "source": "footage"}

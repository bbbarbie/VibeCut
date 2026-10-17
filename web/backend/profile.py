"""Your profile: who makes these videos and how they like them.

Asked once, after the first export (sarah, 2026-10-14): by then the creator
has seen what VibeCut does and has a reason to tell it more. One popup, the
email typed and everything else tapped: what they make (vlogs / lessons),
how fast they like the cuts, how shots join, how the captions look. Skip
means never asked again.

Kept on this Mac only ($VIBECUT_CACHE/profile.json). The email is the
profile's name: there is no account, no sign-in mail, no password, and the
email is never sent anywhere.

What it does: the answers are the starting point of the next video --
the pace (instead of the one read from the footage), the captions (said
words for lessons, what's happening for vlogs, or none), their style and
how they come in (overlays.TEMPLATES / ENTERS), the transition at every cut
(transitions.KINDS) and the look picked up front. They are put on as one
undoable turn when the story is chosen, like any pick in Frames. Then it
keeps up quietly: the pace, a look, a caption style or animation, a
transition used for every cut, or captions switched off, changed in Frames,
become the next video's start. Only once a profile exists; a skipped
profile learns nothing.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

from . import looks, overlays, transitions
from .indexer import CACHE

SCHEMA = "vibecut-profile/1"
PATH = CACHE / "profile.json"

# What they make. A lesson is captioned with what's said; a vlog with
# what's happening (brief.CAPTIONS "transcribe" / "describe").
KINDS = {"vlog": "Vlogs", "lesson": "Lessons and explainers"}
# Asked in the popup, or learnt from Frames (None = not said: the video's own)
FIELDS = {
    "kind": tuple(KINDS),
    "pace": ("fast", "balanced", "calm"),                    # tempo.NAMES
    "transition": tuple(transitions.KINDS),                  # every cut
    "captions": (*overlays.TEMPLATES, "none"),               # a caption style, or no captions
    "enter": tuple(overlays.ENTERS),                         # how captions come in (learnt only)
    "look": tuple(looks.all_looks()),                        # the up-front look (learnt only)
}
EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")


class ProfileError(ValueError):
    pass


def _blank() -> dict:
    return {"schema": SCHEMA, "email": None, **{k: None for k in FIELDS},
            "exports": 0, "asked": False, "at": None, "learned": []}


def load(path: Path | None = None) -> dict:
    """The saved profile; a missing or broken file is a blank one."""
    p = path or PATH
    out = _blank()
    try:
        raw = json.loads(p.read_text())
    except (OSError, ValueError):
        return out
    if not isinstance(raw, dict) or raw.get("schema") != SCHEMA:
        return out
    if isinstance(raw.get("email"), str) and EMAIL.match(raw["email"]):
        out["email"] = raw["email"]
    for k, allowed in FIELDS.items():
        if raw.get(k) in allowed:
            out[k] = raw[k]
    out["exports"] = int(raw["exports"]) if isinstance(raw.get("exports"), int) and raw["exports"] > 0 else 0
    out["asked"] = bool(raw.get("asked"))
    out["at"] = raw.get("at") if isinstance(raw.get("at"), (int, float)) else None
    out["learned"] = [x for x in raw.get("learned") or [] if isinstance(x, dict)][-20:]
    return out


def save(prof: dict, path: Path | None = None) -> dict:
    p = path or PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(prof, indent=1))
    tmp.replace(p)
    return prof


def exported(path: Path | None = None) -> dict:
    """One more video finished (any project)."""
    prof = load(path)
    prof["exports"] += 1
    return save(prof, path)


def should_ask(prof: dict) -> bool:
    """After the first export, once: not after a skip, not once made."""
    return prof["exports"] >= 1 and not prof["asked"] and not prof["email"]


def create(email: str, picks: dict, path: Path | None = None) -> dict:
    email = (email or "").strip()
    if not EMAIL.match(email):
        raise ProfileError("That doesn't look like an email address.")
    prof = load(path)
    prof["email"] = email
    for k, v in picks.items():
        if k not in FIELDS or (v is not None and v not in FIELDS[k]):
            raise ProfileError(f"{k} is one of {', '.join(FIELDS.get(k, ()))}")
        prof[k] = v
    prof["asked"], prof["at"] = True, time.time()
    return save(prof, path)


def skip(path: Path | None = None) -> dict:
    prof = load(path)
    prof["asked"] = True
    return save(prof, path)


def forget(path: Path | None = None) -> dict:
    """Delete the profile; the export count stays so it isn't asked again."""
    prof = load(path)
    return save({**_blank(), "exports": prof["exports"], "asked": True}, path)


def learn(field: str, value, why: str, path: Path | None = None) -> dict | None:
    """What was changed in Frames becomes the next video's start. Only for a
    profile that exists: a skipped one was a "no"."""
    prof = load(path)
    if not prof["email"] or field not in FIELDS or (value is not None and value not in FIELDS[field]):
        return None
    if prof[field] == value:
        return prof
    prof["learned"] = [*prof["learned"], {"field": field, "from": prof[field], "to": value, "why": why,
                                          "at": time.time()}][-20:]
    prof[field] = value
    return save(prof, path)


def defaults(prof: dict) -> dict:
    """What a new video starts from. Empty without a profile."""
    if not prof["email"]:
        return {}
    out = {k: prof[k] for k in ("pace", "look", "enter", "transition") if prof[k]}
    if prof["kind"]:
        out["captions"] = "transcribe" if prof["kind"] == "lesson" else "describe"
    if prof["captions"] == "none":
        out["captions"] = "none"
    elif prof["captions"]:
        out["template"] = prof["captions"]
    return out


def ops_for(board: dict | None, mine: dict) -> list[dict]:
    """The profile's captions and transition on a freshly chosen story."""
    if not board:
        return []
    ops: list[dict] = []
    if board.get("overlays") and (mine.get("template") or mine.get("enter")):
        ops.append({"op": "overlay_style", **{k: mine[k] for k in ("template", "enter") if mine.get(k)}})
    shots = sum(len(bt.get("shots") or []) for bt in board.get("beats") or [])
    if mine.get("transition") and shots > 1:
        ops.append({"op": "set_transition", "all": True, "kind": mine["transition"]})
    return ops


def learn_ops(ops: list[dict]) -> None:
    """Picks made by hand in Frames, in the order made."""
    for o in ops:
        kind = o.get("op")
        if kind == "set_look" and o.get("look"):
            learn("look", o["look"], "picked in Frames")
        elif kind == "overlay_style":
            for k, field in (("template", "captions"), ("enter", "enter")):
                if o.get(k):
                    learn(field, o[k], "picked in Frames")
        elif kind == "set_transition" and o.get("all") and o.get("kind") in transitions.KINDS:
            learn("transition", o["kind"], "used for every cut")


def public(prof: dict) -> dict:
    return {"email": prof["email"], **{k: prof[k] for k in FIELDS}, "exports": prof["exports"],
            "ask": should_ask(prof), "learned": prof["learned"][-5:]}

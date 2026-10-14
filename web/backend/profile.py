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
words for lessons, what's happening for vlogs, or none), the look the
captions come in and the joins between shots. Then it keeps up quietly:
changing the pace, the look or switching captions off in Frames moves the
profile to what was chosen, so the next video starts there. Only once a
profile exists; a skipped profile learns nothing.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

from .indexer import CACHE

SCHEMA = "vibecut-profile/1"
PATH = CACHE / "profile.json"

# What they make. A lesson is captioned with what's said; a vlog with
# what's happening (brief.CAPTIONS "transcribe" / "describe").
KINDS = {"vlog": "Vlogs", "lesson": "Lessons and explainers"}
# tempo.NAMES's keys
PACES = ("fast", "balanced", "calm")
# How one shot gives way to the next, as export.plan_transitions takes it.
# None = whatever the look does.
JOINS = {
    "cut": {"between": "cut", "within": "cut", "dur": 0.0, "open": False, "close": False},
    "soft": {"between": "dissolve", "within": "cut", "dur": 0.6, "open": True, "close": True},
    "dip": {"between": "dip_black", "within": "cut", "dur": 0.5, "open": True, "close": True},
    "flash": {"between": "flash", "within": "cut", "dur": 0.2, "open": False, "close": False},
}
# How the captions look: a look id (looks/*.json) whose words they are, or none.
CAPTIONS = {"bold": "hype", "clean": "clean", "cozy": "cozy", "quiet": "quiet", "playful": "playful", "none": None}
FIELDS = {"kind": tuple(KINDS), "pace": PACES, "joins": tuple(JOINS), "captions": tuple(CAPTIONS)}
EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")


class ProfileError(ValueError):
    pass


def _blank() -> dict:
    return {"schema": SCHEMA, "email": None, "kind": None, "pace": None, "joins": None, "captions": None,
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
    for k, allowed in FIELDS.items():
        v = picks.get(k)
        if v is not None and v not in allowed:
            raise ProfileError(f"{k} is one of {', '.join(allowed)}")
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


def captions_of(look_id: str | None) -> str | None:
    """The caption pick a look stands for."""
    return next((k for k, v in CAPTIONS.items() if v == look_id and v), None)


def joins_of(policy: dict | None) -> str | None:
    """The transitions pick a join policy stands for (by its between-parts join)."""
    between = (policy or {}).get("between")
    return next((k for k, v in JOINS.items() if v["between"] == between), None)


def defaults(prof: dict) -> dict:
    """What a new video starts from. Empty without a profile."""
    if not prof["email"]:
        return {}
    out: dict = {}
    if prof["pace"]:
        out["pace"] = prof["pace"]
    if prof["kind"]:
        out["captions"] = "transcribe" if prof["kind"] == "lesson" else "describe"
    if prof["captions"] == "none":
        out["captions"] = "none"
    elif prof["captions"]:
        out["look"] = CAPTIONS[prof["captions"]]
    if prof["joins"]:
        out["joins"] = prof["joins"]
    return out


def public(prof: dict) -> dict:
    return {"email": prof["email"], "kind": prof["kind"], "pace": prof["pace"], "joins": prof["joins"],
            "captions": prof["captions"], "exports": prof["exports"], "ask": should_ask(prof),
            "learned": prof["learned"][-5:]}

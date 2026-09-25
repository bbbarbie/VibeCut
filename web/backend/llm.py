"""Turn a chat message into storyboard operations -- never into a new storyboard.

The model reads a text rendering of the storyboard (beat ids, titles, shot
ids, durations, on-device labels) and answers with JSON constrained to a
schema: a one-line reply, at most one clarifying question, and a list of
operations for board.py to apply. It never sees pixels; what leaves the
machine is the storyboard text and the conversation.

Credentials: ANTHROPIC_API_KEY in the environment, or in web/.env.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from . import board as bd
from . import storyboard as sb

MODEL = "claude-opus-5"
ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


def _load_env() -> None:
    if os.environ.get("ANTHROPIC_API_KEY") or not ENV_FILE.exists():
        return
    for line in ENV_FILE.read_text().splitlines():
        k, _, v = line.strip().partition("=")
        if k and v and not k.startswith("#"):
            os.environ.setdefault(k.strip(), v.strip().strip("'\""))


_load_env()


def available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


_client = None


def client():
    global _client
    if _client is None:
        import anthropic
        _client = anthropic.Anthropic()
    return _client


SYSTEM = """You are the editing assistant inside VibeCut, a tool that helps a vlogger turn a shoot into a storyboard. You do not write prose edits and you never rebuild the storyboard: each user message becomes a short list of operations on the storyboard that exists now. Everything you don't touch stays exactly as it is — that is the whole point, so change only what the user asked for.

## What you see
Each user message comes with the current state:
- FOOTAGE: a summary of what was filmed (on-device image labels, dates, places).
- PROPOSALS: three storyboards built from the footage (keys: time, place, subject). They are suggestions; the user picks one with choose_option.
- STORYBOARD: the working storyboard — beats in order, each with an id (like t1, s3), a title, and its shots (id like 3f2a9c01be44:0, duration, time filmed, labels, quality 0–1, "cam" if the creator is talking to camera).
- SHELF: shots that are not in the storyboard, available to add or swap in.

Labels come from Apple's on-device classifier, so they are generic ("food", "structure", "people", "outdoor"). Map the user's words onto them sensibly: a "market section" is the beat whose title or shots are about food stalls, shops, crowds, produce; "the opening" is the first beat (or its first few shots); "the ending" is the last beat.

## Operations
Use only ids that appear in the state. Fields you don't need are null.
- choose_option {option}: start from one of the proposals. Only when the user picks one (or asks you to), or when they ask for an edit and no storyboard exists yet and one proposal clearly fits.
- move_beat {beat, to_index}: reorder a beat (0 = first).
- drop_beat {beat}: cut a whole section.
- drop_shot {shot}: cut one shot.
- swap_shot {shot, with_shot}: replace a shot with a shelf shot, keeping its slot and length. with_shot null = let VibeCut pick the best-made similar shelf shot.
- add_shot {shot, beat, to_index}: bring a shelf shot into a beat.
- move_shot {shot, beat, to_index}: move a shot within or between beats.
- retitle_beat {beat, title}
- set_pace {beat, direction: tighter|looser, amount: a_little|a_lot}: trims (or relaxes) every shot in the beat around its best moment. "Punchier", "too slow", "drags" → tighter. "Let it breathe", "too rushed" → looser. "A lot", "way", "much" → a_lot.
- open_with {shot} / end_with {shot}: make a specific shot the very first / very last. To open or end on a whole section, use move_beat instead.

## How to decide
- One user request → the smallest set of operations that does it. "Make the opening punchier and cut the market section" is exactly two operations: set_pace on the first beat, drop_beat on the market beat. Do not also reorder, retitle or tidy anything else.
- If the target is ambiguous (two beats could be "the market", or none looks like it), don't guess: ask one short question and return no operations.
- If the user describes the video itself rather than an edit (e.g. the first message, "it's a trip to Tokyo"), set `direction`: the themes to lean into, mapped to labels that exist in FOOTAGE. VibeCut then rebuilds the three proposals — this never touches the working storyboard.
- If that description is too vague to know what to lean into, and the footage has clearly different threads (e.g. lots of food and lots of people), ask exactly one question offering two or three concrete choices grounded in the footage ("Is this more about the food or the people you were with?"), put those choices in `choices`, and set nothing else. Don't ask when the footage only supports one reading or the user already said.
- Never ask more than one question at a time. Never ask when the request is clear.
- `reply` is one short sentence saying what you did (or empty if you asked a question). No lists, no restating the whole storyboard."""


def _nullable(schema: dict) -> dict:
    return {"anyOf": [schema, {"type": "null"}]}


SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["reply", "question", "choices", "direction", "ops"],
    "properties": {
        "reply": {"type": "string"},
        "question": _nullable({"type": "string"}),
        "choices": {"type": "array", "items": {"type": "string"}},
        "direction": _nullable({
            "type": "object", "additionalProperties": False,
            "required": ["themes", "labels"],
            "properties": {
                "themes": {"type": "array", "items": {"type": "string"},
                           "description": "Short names shown to the user, e.g. ['food']"},
                "labels": {"type": "array", "items": {"type": "string"},
                           "description": "Label identifiers from FOOTAGE that count as a match"},
            },
        }),
        "ops": {
            "type": "array",
            "items": {
                "type": "object", "additionalProperties": False,
                "required": ["op", "option", "beat", "shot", "with_shot", "to_index",
                             "title", "direction", "amount"],
                "properties": {
                    "op": {"type": "string", "enum": list(bd.LLM_OPS)},
                    "option": _nullable({"type": "string", "enum": ["time", "place", "subject"]}),
                    "beat": _nullable({"type": "string"}),
                    "shot": _nullable({"type": "string"}),
                    "with_shot": _nullable({"type": "string"}),
                    "to_index": _nullable({"type": "integer"}),
                    "title": _nullable({"type": "string"}),
                    "direction": _nullable({"type": "string", "enum": ["tighter", "looser"]}),
                    "amount": _nullable({"type": "string", "enum": ["a_little", "a_lot"]}),
                },
            },
        },
    },
}


# --------------------------------------------------------------------------
# state as text
# --------------------------------------------------------------------------

def _mmss(s: float) -> str:
    return f"{int(s // 60)}:{int(s % 60):02d}"


def _shot_line(cat: bd.Catalog, sid: str, start: float | None = None, end: float | None = None,
               key: str | None = None) -> str:
    s = cat.shots.get(sid)
    if s is None:
        return f"{key or sid} (missing)"
    d = (end - start) if start is not None else s.duration
    labels = ",".join(l for l, _ in sorted(s.labels.items(), key=lambda kv: -kv[1])[:4])
    when = s.when.strftime("%a %-I:%M%p").lower() if s.when else "undated"
    cam = " cam" if s.face_area >= 0.04 else ""
    return f"{key or sid} {d:.1f}s {when} q{s.score:.2f}{cam} [{labels}]"


def render_state(cat: bd.Catalog, session: bd.Session) -> str:
    shots = list(cat.shots.values())
    counts: dict[str, int] = {}
    for s in shots:
        for l, v in s.labels.items():
            if v >= 0.3:
                counts[l] = counts.get(l, 0) + 1
    days = sorted({s.when.date() for s in shots if s.when})
    places = len({s.gps for s in shots if s.gps})
    top = ", ".join(f"{l}×{n}" for l, n in sorted(counts.items(), key=lambda kv: -kv[1])[:30])
    out = [f"FOOTAGE: {len(shots)} shots, {len(days)} filming day(s), {places} distinct GPS points, "
           f"{sum(s.face_area >= 0.04 for s in shots)} talking-to-camera shots.",
           f"Labels: {top or 'none (Vision unavailable)'}", ""]

    if session.proposals:
        out.append("PROPOSALS:")
        for o in session.proposals["options"]:
            beats = " | ".join(f"{b['title']} ({len(b['shots'])})" for b in o["beats"])
            out.append(f"- {o['key']}: {o['name']} — {o['summary']} Beats: {beats}")
        out.append("")

    b = session.board
    used = set()
    if b:
        total = sum(s["end"] - s["start"] for bt in b["beats"] for s in bt["shots"])
        out.append(f"STORYBOARD (from '{b['name']}', {_mmss(total)} total):")
        for i, bt in enumerate(b["beats"]):
            d = sum(s["end"] - s["start"] for s in bt["shots"])
            out.append(f"beat {bt['id']} #{i + 1} \"{bt['title']}\" — {len(bt['shots'])} shots, {_mmss(d)}")
            for s in bt["shots"]:
                if bd.is_gap(s):
                    out.append(f"  {bd.key(s)} (gap, {s['end'] - s['start']:.1f}s of black)")
                    continue
                used.add(s["id"])
                out.append("  " + _shot_line(cat, s["id"], s["start"], s["end"], key=bd.key(s)))
    else:
        out.append("STORYBOARD: none yet — the user hasn't chosen a proposal.")
    out.append("")

    shelf = sorted((s for s in shots if s.id not in used and not s.utility), key=lambda s: -s.score)
    out.append(f"SHELF ({len(shelf)} shots not in the storyboard, best first):")
    out += ["  " + _shot_line(cat, s.id) for s in shelf[:150]]
    return "\n".join(out)


def _history(session: bd.Session, limit: int = 12) -> list[dict]:
    msgs = []
    for t in [t for t in session.turns if t.kind == "chat"][-limit:]:
        msgs.append({"role": "user", "content": t.text})
        said = t.question or t.reply or "Done."
        done = "; ".join(l["text"] for l in t.lines) if t.lines else "no change"
        state = " (the user later undid this)" if t.undone else ""
        msgs.append({"role": "assistant", "content": f"{said}\n[applied: {done}{state}]"})
    return msgs


# --------------------------------------------------------------------------
# the call
# --------------------------------------------------------------------------

class LLMError(Exception):
    pass


def interpret(message: str, cat: bd.Catalog, session: bd.Session) -> dict:
    """-> {"reply", "question", "choices", "direction", "ops"}"""
    import anthropic

    messages = _history(session) + [{
        "role": "user",
        "content": f"{render_state(cat, session)}\n\nUSER: {message}",
    }]
    try:
        resp = client().beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
            messages=messages,
            output_config={"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}},
        )
    except anthropic.AuthenticationError as e:
        raise LLMError("The Anthropic key was rejected — check ANTHROPIC_API_KEY in web/.env.") from e
    except anthropic.RateLimitError as e:
        raise LLMError("Rate-limited by the Anthropic API — try again in a moment.") from e
    except anthropic.APIStatusError as e:
        raise LLMError(f"Anthropic API error {e.status_code}: {e.message}") from e
    except anthropic.APIConnectionError as e:
        raise LLMError("Couldn't reach the Anthropic API — check the connection.") from e

    if resp.stop_reason == "refusal":
        raise LLMError("The model declined that request.")
    if resp.stop_reason == "max_tokens":
        raise LLMError("The model's answer was cut off; try a shorter request.")
    text = next((b.text for b in resp.content if b.type == "text"), "")
    try:
        out = json.loads(text)
    except json.JSONDecodeError as e:
        raise LLMError("The model's answer wasn't valid JSON.") from e
    out.setdefault("choices", [])
    out["ops"] = [op for op in out.get("ops") or [] if isinstance(op, dict)]
    return out


def interpret_offline(message: str, cat: bd.Catalog, session: bd.Session) -> dict:
    """No key: the first message still works (keyword lean), edits need the model."""
    if session.board is None:
        d = sb.read_direction(message, list(cat.shots.values()))
        return {"reply": "", "question": None, "choices": [], "ops": [],
                "direction": {"themes": d.themes, "labels": sorted(d.labels), "keywords": True}}
    return {"reply": "", "question": None, "choices": [], "direction": None, "ops": [],
            "error": "Editing by chat needs the language model: add ANTHROPIC_API_KEY=… to "
                     "web/.env and restart the server. Timeline edits, Apply and Undo still work."}

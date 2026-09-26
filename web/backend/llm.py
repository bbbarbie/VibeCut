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
from . import overlays as ov
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
- PROPOSALS: three storyboards built from the footage (keys: time, place, subject). They are suggestions; the user picks one with choose_option. If the creator gave a voiceover there is a fourth, key voice: one beat per spoken line, titled with the line. Its gaps are lines nothing on the shelf shows; they are deliberate — don't fill one with an unrelated shot unless the user asks, and then prefer a shot that shows what the line says.
- CREATOR RULES (only if the creator has confirmed any): preferences they asked to keep. Follow them where they apply; the current message wins if it says otherwise. Never invent a rule from one edit.
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

Words on screen (OVERLAYS in the state). They hang off a beat or a shot and move with it; one font and colour for the whole video is set elsewhere, so never try to change fonts per overlay.
- add_overlay {kind, text, sub, beat | shot}: kind is title (big opening words), part (a part/place label, sub = small line above it), name (a person's name tag, sub = handle or role), caption (a spoken line or short remark), date, end (end card). Give beat or shot to say where it goes; both null = the start of the video (for end: the last seconds). Only write words the user gave you or that are already in the storyboard (beat titles). Never invent names, places or quotes — ask instead.
- edit_overlay {overlay, text, sub, kind: null}: change the words of an existing overlay (id from OVERLAYS). Give beat or shot to move it there.
- drop_overlay {overlay}

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
                             "title", "direction", "amount", "overlay", "kind", "text", "sub"],
                "properties": {
                    "op": {"type": "string", "enum": list(bd.LLM_OPS)},
                    "option": _nullable({"type": "string", "enum": ["time", "place", "subject", "voice"]}),
                    "beat": _nullable({"type": "string"}),
                    "shot": _nullable({"type": "string"}),
                    "with_shot": _nullable({"type": "string"}),
                    "to_index": _nullable({"type": "integer"}),
                    "title": _nullable({"type": "string"}),
                    "direction": _nullable({"type": "string", "enum": ["tighter", "looser"]}),
                    "amount": _nullable({"type": "string", "enum": ["a_little", "a_lot"]}),
                    "overlay": _nullable({"type": "string"}),
                    "kind": _nullable({"type": "string", "enum": ["title", "part", "name", "caption", "date", "end"]}),
                    "text": _nullable({"type": "string"}),
                    "sub": _nullable({"type": "string"}),
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


def render_state(cat: bd.Catalog, session: bd.Session, rules: str = "") -> str:
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
        items = ov.resolve(b)
        if items:
            where = {bt["id"]: bt["title"] for bt in b["beats"]}
            out.append("")
            out.append(f"OVERLAYS ({len(items)}, one style: {ov.style_of(b)['font']}):")
            for o in items:
                a = o["anchor"]
                on = {"edit": "the video", "end": "the end", "beat": f"beat {a.get('id')} “{where.get(a.get('id'), '')}”",
                      "shot": f"shot {a.get('id')}"}[a["to"]]
                sub = f" / {o['sub']}" if o.get("sub") else ""
                out.append(f"  {o['id']} {o['kind']} “{o['text']}{sub}” on {on}, {_mmss(o['start'])}–{_mmss(o['end'])}")
    else:
        out.append("STORYBOARD: none yet — the user hasn't chosen a proposal.")
    out.append("")

    shelf = sorted((s for s in shots if s.id not in used and not s.utility), key=lambda s: -s.score)
    out.append(f"SHELF ({len(shelf)} shots not in the storyboard, best first):")
    out += ["  " + _shot_line(cat, s.id) for s in shelf[:150]]
    if rules:
        out += ["", rules]
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


def interpret(message: str, cat: bd.Catalog, session: bd.Session, rules: str = "") -> dict:
    """-> {"reply", "question", "choices", "direction", "ops"}. `rules` are the
    creator's confirmed preferences (preferences.py), never candidates."""
    import anthropic

    messages = _history(session) + [{
        "role": "user",
        "content": f"{render_state(cat, session, rules)}\n\nUSER: {message}",
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
    out["ops"] = [_overlay_op(op) for op in out.get("ops") or [] if isinstance(op, dict)]
    return out


def _overlay_op(op: dict) -> dict:
    """The schema's flat fields -> what overlays.py expects."""
    if op.get("op") == "edit_overlay":
        for k in ("beat", "shot"):
            if op.get(k):
                op["anchor"], op["at"] = {"to": k, "id": op.pop(k)}, 0.3
        op.pop("kind", None)
        for k in ("text", "sub"):
            if op.get(k) is None:
                op.pop(k, None)
    return op


def interpret_offline(message: str, cat: bd.Catalog, session: bd.Session, rules: str = "") -> dict:
    """No key: the first message still works (keyword lean), edits need the model."""
    if session.board is None:
        d = sb.read_direction(message, list(cat.shots.values()))
        return {"reply": "", "question": None, "choices": [], "ops": [],
                "direction": {"themes": d.themes, "labels": sorted(d.labels), "keywords": True}}
    return {"reply": "", "question": None, "choices": [], "direction": None, "ops": [],
            "error": "Editing by chat needs the language model: add ANTHROPIC_API_KEY=… to "
                     "web/.env and restart the server. Timeline edits, Apply and Undo still work."}


# --------------------------------------------------------------------------
# talking-head mode: which sentences to cut (talk.py)
# --------------------------------------------------------------------------

TALK_SYSTEM = """You review the transcript of a creator talking to camera (口播), sentence by sentence, and decide which sentences a careful editor would cut. You only see text; timing and pauses are handled elsewhere.

Cut:
- retake: a sentence the speaker says again shortly after (usually better). Cut the EARLIER take, keep the last complete one.
- false_start: a sentence started and abandoned ("So the first thing — actually, let me start with…").
- mistake: a sentence that is immediately corrected ("…it's 30 — sorry, 40 minutes").
- off_script: only when a SCRIPT is given and the sentence is clearly an aside that isn't part of what they meant to record ("wait, is this recording?", "let me try that again").
- filler: a sentence that is nothing but filler.

Never cut a sentence just because it's informal, a joke, or not in the script but on topic. When unsure, keep it. The creator reviews every cut, so give a short note in English saying why (e.g. "Same as sentence 7 — keeping the later take").

Each sentence has an id, its text, its length in seconds, `rule` (what VibeCut's simple rules suggested: retake / script_retake / stumble / filler, or null) and, with a script, the script line it matched. You may agree or disagree with the rules. `reply` is one short English sentence summarising what you cut."""

TALK_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["reply", "drops"],
    "properties": {
        "reply": {"type": "string"},
        "drops": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["id", "reason", "note"],
            "properties": {
                "id": {"type": "string"},
                "reason": {"type": "string", "enum": ["retake", "false_start", "mistake", "off_script", "filler"]},
                "note": {"type": "string"},
            }}},
    },
}


def review_talk(sentences: list[dict], script: list[str]) -> dict:
    """-> {"reply", "drops": [{id, reason, note}]}. Only text leaves the machine."""
    import anthropic

    body = "SENTENCES:\n" + "\n".join(
        f"{s['id']} ({s['seconds']}s{', rule: ' + s['rule'] if s.get('rule') else ''}"
        f"{', script line ' + str(s['script_line']) if s.get('script_line') else ''}): {s['text']}" for s in sentences)
    if script:
        body = "SCRIPT:\n" + "\n".join(f"{k + 1}. {ln}" for k, ln in enumerate(script)) + "\n\n" + body
    try:
        resp = client().messages.create(
            model=MODEL, max_tokens=16000,
            system=[{"type": "text", "text": TALK_SYSTEM, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": body}],
            output_config={"effort": "medium", "format": {"type": "json_schema", "schema": TALK_SCHEMA}},
        )
    except anthropic.APIError as e:
        raise LLMError(str(e)) from e
    text = next((b.text for b in resp.content if b.type == "text"), "")
    return json.loads(text)

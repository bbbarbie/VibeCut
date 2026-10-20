"""AI Edit sets how the captions look, the way the Captions tab does.

sarah (2026-10-20) asked the chat to "change all captions to lower case,
style's own font with contrasting colours with the background", and it said
it couldn't set fonts or colours. Since then the chat has the Captions tab's
controls (word art, font, colour or automatic, outline, shadow, background,
boldness, animation, where captions sit) and can move or size one caption,
every caption or every title. No network: the course key's reply is played
by a stand-in.

What must hold: an answer changes only what was asked ("keep" leaves the
rest, so a strict schema that asks for every field can't reset any); own /
soft / auto go back to the word art's own and the automatic colour; numbers
are kept inside the tab's sliders; every caption at once is one edit per
caption, never their words or timing, and reads as one line; it is one
undoable turn, its diff computed, not reported; the paused-moment box
proposes the same; and the schema stays valid for strict structured output
(no ranges, every field required, nothing extra).

    python tests/test_chat_captions.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

if __name__ == "__main__":
    os.environ["VIBECUT_CACHE"] = tempfile.mkdtemp(prefix="vibecut-chat-captions-")
os.environ["VIBECUT_EXPORTS"] = os.path.join(os.environ["VIBECUT_CACHE"], "out")
os.environ.setdefault("VIBECUT_BED", "0")
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["OPENAI_API_KEY"] = ""
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.test_board import CLIPS, PROPOSALS, session  # noqa: E402
from web.backend import app as A  # noqa: E402
from web.backend import board as bd  # noqa: E402
from web.backend import defaults, llm, oai, timeline  # noqa: E402
from web.backend import overlays as ov  # noqa: E402
from web.backend import projects as pj  # noqa: E402

oai.ENV_FILE = llm.ENV_FILE = Path(os.environ["VIBECUT_CACHE"]) / "no.env"

failures: list[str] = []


def check(name: str, cond: bool, got: str = "") -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{': ' + got if got else ''}")
    if not cond:
        failures.append(name)


KEEP_SET = {"set": "keep", "color": "#000000"}


def captions(**kw) -> dict:
    """caption_style's fields as a strict answer gives them: all of them, "keep" where not asked."""
    c = {"word_art": "keep", "font": "keep", "colour": "keep",
         "outline": {**KEEP_SET, "width": 0}, "shadow": {**KEEP_SET, "strength": 0, "softness": 0, "distance": 0},
         "background": {**KEEP_SET, "opacity": 0, "round": 0}, "boldness": {"set": "keep", "amount": 0},
         "animation": "keep", "position": "keep"}
    return {**c, **kw}


def placement(**kw) -> dict:
    return {"mode": "keep", "x": 0, "y": 0, "scale": 0, "size": "keep", "title_look": "keep", **kw}


def op(**kw) -> dict:
    fields = llm.SCHEMA["properties"]["ops"]["items"]["required"]
    return {k: kw.get(k) for k in fields}


def answer(ops: list[dict], reply: str = "Done.") -> dict:
    return {"model": "gpt-6.1-sol", "usage": {"prompt_tokens": 6000, "completion_tokens": 400},
            "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(
                {"reply": reply, "question": None, "choices": [], "direction": None, "ops": ops})}}]}


def strict_problems(node, path="$") -> list[str]:
    """What OpenAI's strict mode or Claude's structured outputs would refuse."""
    out = []
    if isinstance(node, dict):
        for bad in ("minimum", "maximum", "minLength", "maxLength", "pattern", "format", "minItems"):
            if bad in node:
                out.append(f"{path} has {bad}")
        if node.get("type") == "object":
            props = node.get("properties") or {}
            if node.get("additionalProperties") is not False:
                out.append(f"{path} allows extra fields")
            if sorted(node.get("required") or []) != sorted(props):
                out.append(f"{path} doesn't require every field")
        for k, v in node.items():
            out += strict_problems(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            out += strict_problems(v, f"{path}[{i}]")
    return out


def style() -> dict:
    return A.SESSION.board.get("overlay_style") or {}


def kinds(*ks: str) -> list[dict]:
    return [o for o in A.SESSION.board.get("overlays") or [] if o["kind"] in ks]


def main() -> int:
    s, cat = session()
    A.SESSION = s
    A.CATALOG["cat"] = cat
    A.CLIPS.clear()
    A.CLIPS.update({c["id"]: c for c in CLIPS})
    A._make_proposals = lambda d: PROPOSALS
    A._session = lambda: {}
    A._save = lambda: None
    A.WORKFLOW.state = "story"
    A.PROJECT["p"] = pj.Project(id="chat-captions", name="Chat")
    beats = [b["id"] for b in s.board["beats"]]
    shots = [x for b in s.board["beats"] for x in b["shots"]]
    # a made video's words: a chapter title, an opening title, stop labels and captions
    words = [{"op": "add_overlay", "kind": "heading", "text": "MORNING", "sub": "slow start", "beat": beats[0]},
             {"op": "add_overlay", "kind": "title", "text": "Tokyo", "beat": beats[0]},
             {"op": "add_overlay", "kind": "part", "text": "Columbia University, morning", "beat": beats[0]},
             {"op": "add_overlay", "kind": "part", "text": "Shibuya, night", "beat": beats[-1]}]
    words += [{"op": "add_overlay", "kind": "caption", "text": t, "shot": bd.key(x)}
              for t, x in zip(["This Matcha Is So Good", "Walk To Class", "Why Is It So Cold"], shots)]
    s.add({"kind": "direct", "text": "words", "ops": words}, cat, lambda d: PROPOSALS)
    s.add({"kind": "direct", "text": "picked by hand",
           "ops": [{"op": "overlay_style", "template": "bold", "text_color": "#ff0000"}]}, cat, lambda d: PROPOSALS)
    check("the fixture has its words", len(kinds("caption")) == 3 and len(kinds("part")) == 2
          and len(kinds("heading")) == 1, str(s.turns[-2].skipped))

    sent: list[dict] = []
    replies: list[dict] = []

    def stand_in(url, body, headers):
        sent.append(body)
        return replies.pop(0)
    real_post = oai._post
    oai._post = stand_in
    os.environ["OPENAI_API_KEY"] = "sk-test"
    oai.switch(True)

    def chat(message: str, ops: list[dict]):
        replies.append(answer(ops))
        A.api_chat(A.ChatReq(message=message, ai_ok=A.api_chat_estimate()["usd"][1]))
        return A.SESSION.turns[-1]

    try:
        print("the schema and the instructions")
        probs = strict_problems(llm.SCHEMA)
        check("valid for strict structured output: no ranges, every field required, nothing extra",
              not probs, "; ".join(probs[:4]))
        unions = json.dumps(llm.SCHEMA).count('"anyOf"')
        check("at most 16 nullable fields, Claude's limit for structured outputs", unions <= 16, str(unions))
        items = llm.SCHEMA["properties"]["ops"]["items"]
        check("caption_style is an op, with placement and captions fields",
              "caption_style" in items["properties"]["op"]["enum"]
              and {"placement", "captions"} <= set(items["required"]))
        names = [*ov.TEMPLATES, *ov.TYPEFACES, *ov.ENTERS, "soft", "all_captions", "all_titles"]
        check("the instructions name every word art, font and animation, and all captions / titles",
              all(n in llm.SYSTEM for n in names), str([n for n in names if n not in llm.SYSTEM]))
        check("and where in the app the rest is done",
              all(w in llm.SYSTEM for w in ("under Effects", "under Edit", "Music in the left rail", "Audio")))
        state = llm.render_state(cat, A.SESSION)
        line = next((l for l in state.splitlines() if l.startswith("CAPTION STYLE")), "")
        check("the state says how the captions look now", "word_art bold" in line and "colour #ff0000" in line
              and "font own" in line and "outline own" in line, line)
        check("and where each caption sits", "usual spot, size M" in state and "title look spaced" in state)

        print("her message: lowercase, the style's own font, colours that stand out")
        A.SESSION.add({"kind": "direct", "text": "a font", "ops": [{"op": "overlay_style", "typeface": "anton"}]},
                      cat, lambda d: PROPOSALS)
        before = json.dumps(style(), sort_keys=True)
        lowered = [op(op="edit_overlay", overlay=o["id"], text=o["text"].lower()) for o in kinds("caption")]
        t = chat("change all captions to lower case style's own font with contrasting colours",
                 [op(op="caption_style", captions=captions(font="own", colour="auto")), *lowered])
        st = style()
        check("one undoable chat turn", t.kind == "chat" and not t.skipped, str(t.skipped))
        check("the style's own font, the automatic colour", st.get("typeface", "x") is None
              and st.get("text_color", "x") is None, json.dumps(st))
        check("what wasn't asked stays (the word art)", st.get("template") == "bold")
        check("the words are lowercase", all(o["text"] == o["text"].lower() for o in kinds("caption")))
        said = [l["text"] for l in t.lines]
        check("the diff says so, computed", "Caption font: back to the look's own" in said
              and "Caption colour: automatic" in said, json.dumps(said))
        A.SESSION.toggle(t.id, cat, lambda d: PROPOSALS)
        check("Undo brings the font, colour and words back", json.dumps(style(), sort_keys=True) == before
              and kinds("caption")[0]["text"] == "This Matcha Is So Good")
        A.SESSION.toggle(t.id, cat, lambda d: PROPOSALS)

        print("everything in the Captions tab")
        t = chat("white outline, montserrat, word by word, in the middle",
                 [op(op="caption_style", option="unused", amount="unused", captions=captions(
                     font="Montserrat", animation="word", position="center",
                     outline={"set": "on", "color": "#FFF", "width": 0.12}))])
        st = style()
        check("font, animation, position", st.get("typeface") == "montserrat" and st.get("enter") == "word"
              and st.get("captions") == "center", json.dumps(st))
        check("an outline in white (#FFF read as #ffffff)", st.get("outline") == {"color": "#ffffff", "width": 0.12})
        said = [l["text"] for l in t.lines]
        check("each named in the diff", "Caption font: Montserrat" in said and "Captions come in: Word by word" in said
              and any("outline" in x for x in said), json.dumps(said))
        check("an entrance asked for in words is remembered like one picked in the tab",
              defaults.get().get("caption_enter") == "word", json.dumps(defaults.get()))

        t = chat("soft shadow, pink box, bolder",
                 [op(op="caption_style", captions=captions(
                     shadow={"set": "on", "color": "#000000", "strength": 70, "softness": -1, "distance": 5},
                     background={"set": "on", "color": "pink", "opacity": 0.9, "round": 0.9},
                     boldness={"set": "on", "amount": 1}))])
        st = style()
        check("a shadow: 70 read as 70%, a bad softness the tab's own, 5 as 5%",
              st.get("shadow") == {"color": "#000000", "opacity": 0.7, "blur": 0.4, "dist": 0.05}, json.dumps(st.get("shadow")))
        check("a pink background, roundness kept inside its slider",
              st.get("backdrop") == {"color": "#ff6fae", "opacity": 0.9, "round": 0.5}, json.dumps(st.get("backdrop")))
        check("bolder, up to the tab's heaviest", st.get("thick") == ov.THICK_MAX)
        check("the outline from before is still there", st.get("outline") == {"color": "#ffffff", "width": 0.12})

        t = chat("no shadow, the word art's own background, sparkly letters",
                 [op(op="caption_style", captions=captions(
                     colour="sparkly", shadow={"set": "none", "color": "", "strength": 0, "softness": 0, "distance": 0},
                     background={"set": "own", "color": "", "opacity": 0, "round": 0}))])
        st = style()
        check("none switches the shadow off, keeping its other numbers",
              st.get("shadow") == {"color": "#000000", "opacity": 0.0, "blur": 0.4, "dist": 0.05}, json.dumps(st.get("shadow")))
        check("own = the word art's own", "backdrop" in st and st["backdrop"] is None)
        check("a colour that isn't one changes nothing", st.get("text_color") is None and not t.skipped)

        t = chat("back to the soft captions", [op(op="caption_style", captions=captions(word_art="soft"))])
        check("soft = no template", style().get("template", "x") is None
              and "Captions: Soft" in [l["text"] for l in t.lines])
        n = len(A.SESSION.turns)
        t = chat("hmm", [op(op="caption_style", captions=captions())])
        check("all keep: no op at all, nothing skipped", len(A.SESSION.turns) == n + 1 and t.ops == [] and not t.skipped)

        t = chat("tighten the first part a lot", [op(op="set_pace", beat=beats[0], direction="tighter",
                                                     amount="a_lot", option="unused")])
        check("unused means not given; the rest of the op still works", not t.skipped and t.ops
              and t.ops[0].get("amount") == "a_lot" and "option" not in t.ops[0], str(t.skipped))
        A.SESSION.toggle(t.id, cat, lambda d: PROPOSALS)

        print("moving and sizing")
        t = chat("put every caption near the top, bigger",
                 [op(op="edit_overlay", overlay="all_captions", text="ignored", beat=beats[-1],
                     placement=placement(mode="set", x=0.5, y=0.2, scale=0, size="l"))])
        small = kinds("caption", "part")
        check("every caption and stop label placed, at its own scale", all(
            o.get("place") == {"x": 0.5, "y": 0.2, "scale": 1.0} and o["size"] == "L" for o in small),
            json.dumps([o.get("place") for o in small]))
        check("their words and timing are their own", kinds("caption")[0]["text"] == "this matcha is so good"
              and all(o["anchor"]["id"] != beats[-1] or o["kind"] == "part" for o in kinds("caption")))
        check("titles left alone", all(o.get("place") is None for o in kinds("heading", "title")))
        said = [l["text"] for l in t.lines]
        check("one turn of five edits, read as one line", len(t.ops) == 5
              and said == ["Changed the place of 5 captions"], json.dumps(said))

        cap = kinds("caption")[0]
        t = chat("that one back where it was", [op(op="edit_overlay", overlay=cap["id"],
                                                    placement=placement(mode="usual"))])
        check("usual = back to its spot", kinds("caption")[0].get("place") is None
              and kinds("caption")[1].get("place") is not None)
        t = chat("bigger, 4x", [op(op="edit_overlay", overlay=cap["id"],
                                   placement=placement(mode="set", x=1.4, y=-2, scale=4))])
        check("kept on the frame and inside the size limits", kinds("caption")[0].get("place")
              == {"x": 1.0, "y": 0.5, "scale": ov.SCALE_MAX}, json.dumps(kinds("caption")[0].get("place")))

        t = chat("script chapter titles", [op(op="edit_overlay", overlay="all_titles",
                                              placement=placement(title_look="script"))])
        check("the chapter title takes the look; the plain title has none to take",
              kinds("heading")[0]["look"] == "script" and "look" not in kinds("title")[0] and not t.skipped,
              str(t.skipped))
        check("said as a change of style", any(l["text"].startswith("Changed the style of the chapter title")
                                               for l in t.lines), json.dumps([l["text"] for l in t.lines]))

        print("the paused box proposes the same")
        at = timeline.layout(A.SESSION.board)[0]["seq_start"] + 0.3
        info = A.api_moment(A.MomentReq(t=at))
        replies.append(answer([op(op="edit_overlay", overlay="all_captions", placement=placement(size="S")),
                               op(op="caption_style", captions=captions(font="caveat"))]))
        n = len(A.SESSION.turns)
        out = A.api_moment_chat(A.MomentReq(t=at, message="smaller, handwriting", ai_ok=info["estimate"]["usd"][1]))
        check("one edit per caption and the overlay_style op, nothing applied yet",
              [o["op"] for o in out["ops"]] == ["edit_overlay"] * 5 + ["overlay_style"]
              and out["ops"][-1].get("typeface") == "caveat" and len(A.SESSION.turns) == n, json.dumps(out["ops"])[:300])
        check("its preview is computed", out["preview"] and out["preview"]["lines"], json.dumps(out["preview"]))
    finally:
        oai._post = real_post
        oai.switch(False)
        os.environ["OPENAI_API_KEY"] = ""

    print(f"\n{'all passed' if not failures else f'{len(failures)} failed: ' + ', '.join(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

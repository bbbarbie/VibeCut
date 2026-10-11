"""The captions answer must change what's on screen -- and only that way.

Same story, answers that differ in one respect: "No captions" adds nothing;
"Describe" gives a title and per-moment captions (time, place, what's in
the shot); "Transcribe" subtitles what's said where a voice is heard; the
look question picks the look. Every word comes from the footage or the
description, and one Undo takes the words away without touching the cut.

    python tests/test_captions_answer.py
"""

from __future__ import annotations

import os
import re
import sys
import tempfile
from datetime import timedelta

os.environ["VIBECUT_CACHE"] = tempfile.mkdtemp(prefix="vibecut-captions-")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.test_board import PROPOSALS, session  # noqa: E402
from web.backend import brief  # noqa: E402
from web.backend import overlays as ov  # noqa: E402

mk = lambda d: PROPOSALS  # noqa: E731


def main() -> int:
    failures = []

    def check(name: str, cond: bool, got: str = "") -> None:
        print(f"  {'PASS' if cond else 'FAIL'}  {name}{': ' + got if got else ''}")
        if not cond:
            failures.append(name)

    def words(answer):
        s, cat = session()
        cut = [[x["id"] for x in b["shots"]] for b in s.board["beats"]]
        ops, notes = brief.caption_ops(s.board, cat, answer, "A day in Tokyo")
        t = s.add({"kind": "direct", "text": "words", "ops": ops}, cat, mk) if ops else None
        return s, cat, t, cut, notes

    s, *_ = words("none")
    check("no captions: nothing added", not s.board.get("overlays") and not s.board.get("look"))
    s, *_ = words(None)
    check("no answer: nothing added", not s.board.get("overlays"))

    print("describe")
    s, cat, t, cut, _ = words("describe")
    kinds = [o["kind"] for o in s.board["overlays"]]
    check("describe: no opening title (the video opens on the footage)", "title" not in kinds, str(kinds))
    check("describe: captions with the time", kinds.count("caption") >= 3, str(kinds))
    check("describe: the cozy look unless asked otherwise", ov.style_of(s.board).get("look") == "cozy")
    check("the words draw in preview and export", len(ov.resolve(s.board)) == len(s.board["overlays"]))
    s.toggle(t.id, cat, mk)
    check("one undo takes the words away", not s.board.get("overlays") and not s.board.get("look"))
    check("and leaves the cut as it was", [[x["id"] for x in b["shots"]] for b in s.board["beats"]] == cut)

    s, cat = session()
    ops, _ = brief.caption_ops(s.board, cat, "describe", "A day in Tokyo", look="bold")
    check("the look question picks the look: bold is hype", ops[0] == {"op": "set_look", "look": "hype"})
    old, _ = brief.caption_ops(s.board, cat, "key", "A day in Tokyo")
    check("an answer saved before the change still works (key -> describe, quiet)",
          old[0] == {"op": "set_look", "look": "quiet"} and any(o.get("kind") == "caption" for o in old))

    print("describe: the place")
    from web.backend import places
    for i, sh in enumerate(cat.shots.values()):
        sh.gps = (35.6595, 139.7005) if i % 2 == 0 else (35.7148, 139.7967)
    found = places.lookup([sh.gps for sh in cat.shots.values()], ask=lambda ks: [
        {"at": k, "area": "Shibuya" if k.startswith("35.66") else "Asakusa", "city": "Tokyo"} for k in ks])
    check("coordinates become a neighbourhood name, one lookup per ~100 m",
          sorted(places.short_name(r) for r in found.values()) == ["Asakusa", "Shibuya"], str(found))
    again = places.lookup([sh.gps for sh in cat.shots.values()], ask=lambda ks: 1 / 0)
    check("and are cached: no second lookup", again == found)
    ops, _ = brief.caption_ops(s.board, cat, "describe", "A day in Tokyo", places=found)
    subs = [o.get("sub") for o in ops if o.get("kind") == "caption" and o.get("sub")]
    check("a caption names the place where a new one starts", subs and set(subs) <= {"Shibuya", "Asakusa"}, str(subs))
    check("never a street address: a place, area or city", places.short_name({"name": "1-2-3 Dogenzaka"}) is None)
    nogps, _ = brief.caption_ops(s.board, cat, "describe", "A day in Tokyo", places={})
    check("no place found: captions go without it", not any(o.get("sub") for o in nogps))

    print("transcribe")
    from web.backend import subtitles
    s, cat = session()
    clips = {sh.clip_id: {"id": sh.clip_id, "name": sh.clip_name, "sound": {"voice": [0.9] * 10}}
             for sh in cat.shots.values()}
    quiet_clip = next(iter(clips))
    clips[quiet_clip]["sound"] = {"voice": [0.0] * 10, "music": [0.9] * 10}
    asked = []

    def hear(rec, loc):
        asked.append((rec["id"], loc))
        out = []
        for sh in cat.shots.values():
            if sh.clip_id == rec["id"]:
                t0 = sh.start + 0.4
                out.append({"text": "this is so good", "words": [
                    {"t": w, "s": round(t0 + 0.3 * k, 2), "e": round(t0 + 0.3 * k + 0.25, 2)}
                    for k, w in enumerate(["this", "is", "so", "good"])]})
        return out
    ops, notes = subtitles.caption_ops(s.board, cat, clips, "A day in Tokyo", transcribe=hear)
    check("transcribe: what's said becomes captions", ops and all(o["text"] == "this is so good" for o in ops),
          str([o["text"] for o in ops][:3]))
    check("timed to the words, inside the shot", all(0.3 <= o["at"] <= 0.5 and o["dur"] >= subtitles.MIN_DUR for o in ops),
          str([(o["at"], o["dur"]) for o in ops][:3]))
    check("clips where no voice is heard aren't transcribed", quiet_clip not in {a for a, _ in asked})
    check("each clip is transcribed once", len(asked) == len(set(asked)))
    check("the language follows the description", {loc for _, loc in asked} == {"en-US"}
          and subtitles.locale_for("东京的一天") == "zh-CN")
    words_ = [{"t": w, "s": i * 0.3, "e": i * 0.3 + 0.2, "n": 0} for i, w in enumerate("one two three".split())] + \
             [{"t": "four", "s": 3.0, "e": 3.2, "n": 0}]
    check("a pause starts a new line", [len(x) for x in subtitles.lines(words_, False)] == [3, 1])

    from web.backend import speech

    def broken(rec, loc):
        raise speech.SpeechError("Transcribing needs macOS 26 or later with the Xcode command-line tools.")
    ops, notes = subtitles.caption_ops(s.board, cat, clips, "", transcribe=broken)
    check("no recogniser: no subtitles, and it says why", not ops and notes and "macOS" in notes[0], str(notes))
    # Through the brief there is no hook: on a Mac that has the recogniser the
    # fixture clips (no files behind them) must not reach it.
    real_transcribe, speech.transcribe = speech.transcribe, broken
    try:
        full, _ = brief.caption_ops(s.board, cat, "transcribe", "A day in Tokyo", clips=clips)
    finally:
        speech.transcribe = real_transcribe
    check("transcribe through the brief: the clean look and a title, or nothing when it can't hear",
          full == [] or full[0] == {"op": "set_look", "look": "clean"})

    print("day in my life")
    from web.backend import daylog
    s, cat, t, cut, notes = words("day")   # saved before the change: describe, cozy
    caps = [o for o in s.board["overlays"] if o["kind"] == "caption"]
    check("day: a caption per moment the day moves on", len(caps) >= 3, str([o["text"] for o in caps]))
    check("day: each starts with the clock", all(re.match(r"\d{1,2}:\d\d (am|pm)", o["text"]) for o in caps),
          str([o["text"] for o in caps]))
    first = s.board["beats"][0]["shots"][0]
    sh = cat.shots[first["id"]]
    want = daylog.clock(sh.when + timedelta(seconds=first["start"] - sh.start))
    check("day: the time is the recording time of that shot", caps[0]["text"].startswith(want), f"{caps[0]['text']} vs {want}")
    check("day: what's happening comes from the labels",
          any(o["text"].endswith("· eating out") for o in caps) and any(o["text"].endswith("· market") for o in caps),
          str([o["text"] for o in caps]))
    check("day: the cozy look", ov.style_of(s.board).get("look") == "cozy")
    check("day: captions are ordinary overlays, retypable by hand",
          all(set(ov.EDITABLE) >= {"text"} for _ in caps))
    s.toggle(t.id, cat, mk)
    check("day: one undo takes them away", not s.board.get("overlays"))

    check("the most specific label speaks", daylog.phrase({"food": 0.9, "sushi": 0.6}) == "sushi time")
    check("an unsure label stays quiet", daylog.phrase({"coffee": 0.1}) is None)
    check("unknown labels give the time alone", daylog.phrase({"structure": 0.9}) is None)

    s, cat = session()
    auto, _ = brief.caption_ops(s.board, cat, None, None, "A day in my life in Tokyo")
    check("a day-in-my-life description gets these captions by default",
          any(o.get("kind") == "caption" for o in auto) and auto[0] == {"op": "set_look", "look": "cozy"})
    off, _ = brief.caption_ops(s.board, cat, "none", None, "A day in my life in Tokyo")
    check("but 'No captions' still means none", off == [])
    plain, _ = brief.caption_ops(s.board, cat, None, None, "trip to Tokyo")
    check("other descriptions get nothing unasked", plain == [])

    from web.backend import llm
    real = llm.day_phrases
    llm.day_phrases = lambda items, about="": ["slow start", "", "temple hopping", "dinner with friends"][:len(items)]
    ops, _ = daylog.caption_ops(s.board, cat, "A day in my life", ask_model=True)
    check("with a key, Claude's phrase replaces the table's",
          [o["text"].split(" · ")[-1] for o in ops] == ["slow start", "market", "temple hopping", "dinner with friends"],
          str([o["text"] for o in ops]))

    def fail(items, about=""):
        raise llm.LLMError("down")
    llm.day_phrases = fail
    ops, _ = daylog.caption_ops(s.board, cat, "", ask_model=True)
    check("and if Claude can't be reached, the table's phrases stand", ops[0]["text"].endswith("slow morning"))
    llm.day_phrases = real

    for sh in cat.shots.values():
        sh.when = None
    ops, notes = daylog.caption_ops(s.board, cat, ask_model=False)
    check("no recording times: no invented clock, and it says so", ops == [] and "recording time" in notes[0])

    check("the question is asked", "captions" in [q["id"] for q in brief.fixed_questions()])
    check("the answer survives cleaning", brief.clean_style({"captions": "bold"}) == {"captions": "bold"})
    check("a made-up answer doesn't", brief.clean_style({"captions": "neon"}) is None)

    print(f"\n{'all passed' if not failures else f'{len(failures)} failed'}")
    return 1 if failures else 0


def test_captions_answer() -> None:
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())

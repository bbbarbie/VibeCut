"""Talking-head cut (口播精剪): does each rule fire on the fault it's for, and
only on it?

Transcripts are built by hand (as the on-device recogniser returns them:
Chinese one character per timed word), so this runs without a speech
model. Each rule is shown on two fixtures that differ in one respect:

- a sentence said again -> the earlier take goes; a *different* sentence
  in the same place stays;
- a pause longer than a breath is cut down to one; a short one isn't;
- "我觉得我觉得" loses one "我觉得"; "谢谢" is not a stumble;
- with a script, of two takes of one line the more complete one stays,
  even when it came first -- without the script nothing is guessed;
- a pause folded into a character's timing is found from the audio level;
- the result is a storyboard whose subtitles never overlap and whose
  length is exactly what was kept.

    python tests/test_talk.py
"""

from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web.backend import board as bd  # noqa: E402
from web.backend import overlays as ov  # noqa: E402
from web.backend import talk  # noqa: E402

CHAR = 0.25


def said(lines: list[tuple[str, float]]) -> list[dict]:
    """[(text, start)] -> recogniser results, one timed word per CJK character."""
    out = []
    for text, t0 in lines:
        words, t = [], t0
        for ch in text:
            if ch in talk.PUNCT:
                continue
            words.append({"t": ch, "s": round(t, 3), "e": round(t + CHAR, 3)})
            t += CHAR
        out.append({"text": text, "start": t0, "end": t, "words": words})
    return out


def clip(cid="c1", dur=30.0) -> dict:
    return {"id": cid, "name": f"{cid}.MOV", "duration": dur,
            "shots": [{"index": 0, "start": 0.0, "end": dur}]}


def plan(lines, script="", levels=None, agent=None):
    c = clip()
    return talk.build({"c1": said(lines)}, {"c1": c}, "zh-CN", levels, script, agent)


def sentence(p, text):
    return next(s for s in p.sents if s.text.startswith(text))


def kept_text(p) -> str:
    return "".join(p.toks[i].t for sp in talk.spans(p) for i in sp["toks"])


BASE = [("大家好今天聊剪辑。", 0.0),          # 0.0–2.0
        ("第二步是删掉重复。", 3.5),          # 3.5–5.5   (said again next)
        ("第二步是删掉重复的句子。", 5.8),    # 5.8–8.55
        ("我觉得我觉得这样很好。", 9.55),     # 9.55–12.05
        ("嗯最后配上字幕。", 12.5)]           # 12.5–14.25


def main() -> int:
    failures = []

    def check(name: str, cond: bool, got: str) -> None:
        print(f"  {'PASS' if cond else 'FAIL'}  {name}: {got}")
        if not cond:
            failures.append(name)

    p = plan(BASE)
    s2, s3 = sentence(p, "第二步是删掉重复。"[:8]), sentence(p, "第二步是删掉重复的")
    check("a sentence said again: the earlier take goes, the last stays",
          s2.auto == "retake" and not s3.auto, f"{s2.auto} / {s3.auto}")
    other = plan([BASE[0], ("第三步是加上音乐。", 3.5), *BASE[2:]])
    check("…a different sentence in the same place stays",
          not any(s.auto for s in other.sents if s.text.startswith("第三步")), "kept")

    check("a stumble loses the repeat, keeps the sentence", "我觉得这样很好" in kept_text(p)
          and "我觉得我觉得" not in kept_text(p), kept_text(p)[-16:])
    thanks = plan([("谢谢大家的支持。", 0.0)])
    check("…'谢谢' is a word, not a stumble", kept_text(thanks) == "谢谢大家的支持", kept_text(thanks))
    check("a filler sound goes", "嗯" not in kept_text(p) and "最后配上字幕" in kept_text(p), kept_text(p)[-8:])

    # Pauses: 1.5 s after the first sentence is cut to a breath; 0.3 s isn't touched.
    sp = talk.spans(p)
    first = sp[0]
    check("a 1.5 s pause is cut down to a breath",
          abs(first["end"] - (2.0 + talk.TAIL)) < 1e-6 and abs(sp[1]["start"] - (5.8 - talk.LEAD)) < 1e-6,
          f"span ends {first['end']}, next starts {sp[1]['start']}")
    pub = talk.public(p)
    pauses = [it for it in pub["items"] if it["kind"] == "pause"]
    check("…a 0.3 s gap is not a pause", all(it["len"] >= talk.MIN_PAUSE for it in pauses)
          and not any(abs(it["len"] - 0.3) < 0.01 for it in pauses), str([it["len"] for it in pauses]))

    # The creator overrides at the gate.
    before = sum(x["end"] - x["start"] for x in talk.spans(p))
    talk.toggle(p, s2.id)
    after = sum(x["end"] - x["start"] for x in talk.spans(p))
    check("putting a retake back puts its seconds back", abs(after - before - 2.0) < 0.3 and "第二步是删掉重复第二步" in kept_text(p),
          f"{before:.2f}s -> {after:.2f}s")
    talk.toggle(p, s2.id)
    # Keep a 1.0 s pause whole: the two sentences become one piece.
    two = plan([("今天天气很好。", 0.0), ("我们出去走走。", 2.75)])   # 0–1.5, gap 1.25, 2.75–4.25
    pid = next(it["id"] for it in talk.public(two)["items"] if it["kind"] == "pause")
    n0 = len(talk.spans(two))
    talk.toggle(two, pid)
    n1 = [(x["start"], x["end"]) for x in talk.spans(two)]
    check("keeping a pause keeps all of it (no cut there)", n0 == 2 and len(n1) == 1 and n1[0][1] - n1[0][0] > 4.2,
          f"{n0} pieces -> {n1}")

    # Script: of two takes of one line, the more complete stays even if it came first.
    takes = [("第二步是删掉重复的句子。", 0.0), ("第二步是删掉。", 3.5)]
    script = "大家好。第二步是删掉重复的句子。最后配上字幕。"
    ws = plan(takes, script)
    wo = plan(takes)
    check("with a script, the more complete take stays even when it came first",
          ws.sents[0].auto is None and ws.sents[1].auto == "script_retake", f"{ws.sents[0].auto} / {ws.sents[1].auto}")
    check("…without the script nothing is guessed", not any(s.auto for s in wo.sents), "both kept")
    check("script lines never said are listed", [u["text"] for u in talk.public(ws)["unsaid"]] == ["大家好。", "最后配上字幕。"],
          str([u["text"] for u in talk.public(ws)["unsaid"]]))

    # A pause folded into a character: '今' 1.0–3.0 but only loud 1.0–1.2.
    folded = [{"text": "我今天到了。", "start": 0.0, "end": 3.75, "words": [
        {"t": "我", "s": 0.75, "e": 1.0}, {"t": "今", "s": 1.0, "e": 3.0}, {"t": "天", "s": 3.0, "e": 3.25},
        {"t": "到", "s": 3.25, "e": 3.5}, {"t": "了", "s": 3.5, "e": 3.75}]}]
    lv = np.zeros(400, bool)
    lv[75:120] = True
    lv[300:375] = True
    c = clip()
    pl = talk.build({"c1": folded}, {"c1": c}, "zh-CN", {"c1": lv})
    pn = talk.build({"c1": folded}, {"c1": c}, "zh-CN", None)
    check("a pause hidden inside a character's timing is found from the level",
          len(talk.spans(pl)) == 2 and len(talk.spans(pn)) == 1,
          f"{len(talk.spans(pl))} pieces with level, {len(talk.spans(pn))} without")

    # The agent's judgement replaces the rules' at sentence level (can keep a rule's retake).
    p2 = plan(BASE, agent=lambda sents, lines: {"reply": "ok", "drops": [
        {"id": next(x["id"] for x in sents if x["text"].startswith("我觉得")), "reason": "mistake", "note": "说错了"}]})
    check("the model's call replaces the rules' (keeps the retake, cuts what it flagged)",
          p2.source == "agent" and not sentence(p2, "第二步是删掉重复。"[:8]).auto
          and sentence(p2, "我觉得").auto == "mistake", f"{p2.source}")
    broken = plan(BASE, agent=lambda s, l: (_ for _ in ()).throw(RuntimeError("offline")))
    check("…and if it can't be reached, the rules stand", broken.source == "rules"
          and sentence(broken, "第二步是删掉重复。"[:8]).auto == "retake" and "offline" in broken.agent_note, broken.agent_note[:40])

    # The gate shows every word: the parts of a sentence (kept, cut, pauses between) spell it out.
    gappy = plan([("大家好", 0.0), ("欢迎回到我的频道。", 1.25)])   # a 0.5 s pause inside one result
    gappy = talk.build({"c1": [{"text": "大家好欢迎回到我的频道。", "start": 0.0, "end": 3.0, "words":
        said([("大家好", 0.0)])[0]["words"] + said([("欢迎回到我的频道", 1.25)])[0]["words"]}]}, {"c1": clip()}, "zh-CN")
    shown = [it for it in talk.public(gappy)["items"] if it["kind"] == "sentence"]
    spelled = "".join(p["text"] for it in shown for p in it["parts"] if p["kind"] == "words")
    check("the review spells out every word, pauses between", spelled == "大家好欢迎回到我的频道"
          and any(p["kind"] == "pause" for it in shown for p in it["parts"]), spelled)

    # Subtitles break between words, even when a bigger gap falls inside one.
    words = said([("然后我们去了中央公园拍了很多照片", 0.0)])[0]["words"]
    for w in words[words.index(next(x for x in words if x["t"] == "公")):]:
        w["s"] += 0.2; w["e"] += 0.2              # the biggest gap: inside 中央|公园
    res = [{"text": "然后我们去了中央公园拍了很多照片", "start": 0.0, "end": 4.2, "words": words,
            "segs": ["然后", "我们", "去", "了", "中央公园", "拍", "了", "很多", "照片"]}]
    seg = talk.build({"c1": res}, {"c1": clip()}, "zh-CN")
    lines = [o["text"] for o in talk.board(seg)["overlays"]]
    check("a long subtitle breaks between words, not inside 中央公园, and evenly", len(lines) == 2 and
          min(len(l) for l in lines) >= 5 and
          not any(l.endswith("中央") for l in lines) and "".join(lines) == "然后我们去了中央公园拍了很多照片", " / ".join(lines))

    # A pause timed a character early (拍 | 了) doesn't split the word 拍了.
    early = [dict(w) for w in said([("我们拍了很多照片", 0.0)])[0]["words"]]
    for w in early[3:]:
        w["s"] += 0.6; w["e"] += 0.6              # the pause lands between 拍 and 了
    res = [{"text": "我们拍了很多照片", "start": 0.0, "end": 2.6, "words": early, "segs": ["我们", "拍", "了", "很多", "照片"]}]
    lines = [o["text"] for o in talk.board(talk.build({"c1": res}, {"c1": clip()}, "zh-CN"))["overlays"]]
    check("a pause timed mid-word moves the word to the next subtitle (no line starts with 了)", lines == ["我们", "拍了很多照片"], " / ".join(lines))

    # Storyboard + subtitles.
    p = plan(BASE)
    snap = talk.board(p)
    cat = bd.Catalog.from_clips([{**clip(), "capture_time": None, "gps": None,
                                  "shots": [{"index": 0, "start": 0.0, "end": 30.0, "thumb": "shot000.jpg", "best_t": 1.0,
                                             "quality": 0.5, "labels": [], "faces": 1, "face_area": 0.1}]}])
    s = bd.Session()
    t = s.add({"kind": "direct", "text": "talk", "ops": [{"op": "choose_option", "option": "talk", "snapshot": snap}]},
              cat, lambda d: None)
    total = sum(e["end"] - e["start"] for b in s.board["beats"] for e in b["shots"])
    kept = sum(x["end"] - x["start"] for x in talk.spans(p))
    caps = ov.resolve(s.board)
    check("it becomes a storyboard exactly as long as what was kept", not t.skipped and abs(total - kept) < 1e-6,
          f"{total:.2f}s")
    check("subtitles never overlap and stay inside the edit",
          all(a["end"] <= b["start"] + 1e-6 for a, b in zip(caps, caps[1:])) and caps[-1]["end"] <= total + 0.2,
          f"{len(caps)} lines")
    check("subtitles say what was kept, not what was cut",
          "".join(c["text"] for c in caps) == kept_text(p) and not any(f["rule"] == "read_time" for f in ov.check(s.board)),
          " / ".join(c["text"] for c in caps))

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

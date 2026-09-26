"""Talking-head mode (口播): cut by what was said, then caption it.

Opt-in, like the voiceover: VibeCut's default path still needs no
transcript. When the creator talks to camera, what they *said* is the spine,
and the tells of an amateur talking-head edit are all in the speech:

- **Dead air (气口).** Every pause longer than a breath makes the video feel
  slow. A pause over MIN_PAUSE is cut down to a breath (LEAD + TAIL), not to
  nothing -- zero-gap jump cuts sound breathless.
- **Retakes (重说).** People say a sentence, fumble, and say it again. The
  earlier take goes; the *last* one stays, because that's the one the
  speaker meant. With the creator's script, takes of the same script line
  compete and the most complete one stays.
- **Stumbles (卡顿) and fillers (语气词).** "我觉得我觉得", "I I think",
  嗯/呃/um/uh inside a sentence.

Every removal is a proposal with a reason, shown struck through at a gate;
the creator can put any of it back. Rules run with no model; with a key the
chat model reads the sentences (and the script) and its judgement replaces
the rules' at sentence level -- it can keep what a rule dropped. The model
only ever sees text, never audio.

Timing comes from the on-device recogniser (speech.py). Chinese is timed
per character and a pause is often folded into the character before it
('今' 1.56–3.96 s), so every word is first shrunk to where the audio is
actually loud. Pauses are found on that refined timing.

The result is a storyboard like any other -- parts, shots, undo, export --
with subtitles as caption overlays anchored to the pieces they're spoken in.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np

HOP = 0.01
MIN_PAUSE = 0.45        # a gap longer than a breath is dead air
LEAD = 0.12             # kept before speech resumes after a cut pause
TAIL = 0.15             # kept after speech stops before a cut pause
PARA_PAUSE = 1.6        # a pause this long starts a new part
PART_MAX_SENTENCES = 5
SENTENCE_PAUSE = 0.7    # a gap this long ends a sentence even without punctuation
CAPTION_CJK = 14        # characters per subtitle line
CAPTION_LATIN = 38
FILLERS = {"嗯", "呃", "额", "um", "uh", "erm", "hmm", "uhm"}
# Chinese subtitling rule: a line never starts with a particle.
NO_LINE_START = {"了", "的", "着", "过", "吗", "呢", "吧", "啊", "呀", "嘛", "么", "得", "地", "哦", "啦"}
PUNCT = "，。！？、；：,.!?;:…—\"'“”‘’（）()《》「」 "

REASONS = {
    "retake": ("重说", "said again", "The earlier take — the same sentence is said again right after."),
    "script_retake": ("重说", "said again", "Another take of the same script line is more complete."),
    "stumble": ("卡顿", "stumble", "Repeated words or a false start."),
    "filler": ("语气词", "filler", "A filler sound."),
    "off_script": ("不在稿子里", "not in your script", "Doesn't match any line of your script."),
    "false_start": ("说一半", "false start", "Started, then abandoned."),
    "mistake": ("说错", "misspoken", "Corrected right after."),
    "agent": ("建议删", "suggested", "Suggested by the editing model."),
}


def _is_cjk(s: str) -> bool:
    return any("㐀" <= ch <= "鿿" or "぀" <= ch <= "ヿ" for ch in s)


def norm(s: str) -> str:
    return "".join(ch for ch in s.lower() if ch not in PUNCT and not ch.isspace())


def _bigrams(s: str) -> set[str]:
    return {s[i:i + 2] for i in range(len(s) - 1)} or ({s} if s else set())


def containment(a: str, b: str) -> float:
    """How much of a's text is found in b (0..1), on character bigrams."""
    A, B = _bigrams(norm(a)), _bigrams(norm(b))
    return len(A & B) / len(A) if A else 0.0


# --------------------------------------------------------------------------
# audio level -> refined word timing
# --------------------------------------------------------------------------

def active(samples: np.ndarray, sr: int = 16000) -> np.ndarray:
    """Per-10 ms 'someone is making sound' from level, relative to this clip."""
    n = int(sr * HOP)
    k = len(samples) // n
    if k == 0:
        return np.zeros(0, bool)
    frames = samples[:k * n].reshape(k, n)
    db = 20 * np.log10(np.sqrt((frames ** 2).mean(axis=1)) + 1e-6)
    floor, top = np.percentile(db, 10), np.percentile(db, 95)
    return db > floor + 0.35 * (top - floor)


def refine(words: list[dict], act: np.ndarray) -> list[dict]:
    """Shrink each word to its main burst of sound.

    A pause is folded into a word's timing either side -- before '第' (the
    silence belongs to its start) or after '今' -- and the previous word's
    tail often bleeds into the front of the range. So: split the word's
    range into loud runs (bridging gaps under 0.15 s) and keep the longest.
    """
    bridge = int(0.15 / HOP)
    out = []
    for w in words:
        a = int(w["s"] / HOP)
        z = max(a + 1, int(np.ceil(w["e"] / HOP)))
        seg = act[a:z] if a < len(act) else np.zeros(0, bool)
        s, e = w["s"], w["e"]
        idx = np.flatnonzero(seg)
        if idx.size:
            runs, start, prev = [], idx[0], idx[0]
            for k in idx[1:]:
                if k - prev > bridge:
                    runs.append((start, prev))
                    start = k
                prev = k
            runs.append((start, prev))
            r0, r1 = max(runs, key=lambda r: r[1] - r[0])
            s = max(w["s"], (a + r0) * HOP)
            e = min(w["e"], (a + r1 + 1) * HOP)
            if e - s < 0.04:
                s, e = w["s"], w["e"]
        out.append({**w, "s": round(float(s), 3), "e": round(float(e), 3)})
    return out


# --------------------------------------------------------------------------
# tokens and sentences
# --------------------------------------------------------------------------

@dataclass
class Token:
    clip: str
    t: str
    s: float
    e: float
    brk: int = 0            # before it: 2 = sentence end (。？! or a result boundary), 1 = comma
    sentence: str = ""
    ws: bool = True          # starts a word (Chinese: from NLTokenizer segments)
    drop: str | None = None  # reason code when a rule removes it


def tokens_of(clip_id: str, results: list[dict], act: np.ndarray | None) -> list[Token]:
    toks: list[Token] = []
    for r in results:
        # Punctuation comes back as timed runs of its own (' ，', '。'): it
        # marks a break before the next word, it isn't a word.
        words = [w for w in r["words"] if norm(w["t"])]
        marks = {}
        pending = 2
        for w in r["words"]:
            if not norm(w["t"]):
                pending = max(pending, 2 if any(ch in "。！？.!?…" for ch in w["t"]) else 1)
            else:
                marks[id(w)] = pending
                pending = 0
        brks = [marks[id(w)] for w in words]
        starts = _word_starts([norm(w["t"]) for w in words], r.get("segs"))
        if act is not None and act.size:
            words = refine(words, act)
        text, pos = r.get("text", ""), 0
        for k, w in enumerate(words):
            t = w["t"].strip()
            i = text.find(t, pos)
            skipped = text[pos:i] if i >= 0 else ""
            if i >= 0:
                pos = i + len(t)
            brk = max(brks[k], 2 if any(ch in "。！？.!?…" for ch in skipped) else
                      1 if any(ch in "，、；：,;:" for ch in skipped) else 0)
            toks.append(Token(clip_id, t, w["s"], w["e"], brk=brk, ws=starts[k]))
    toks.sort(key=lambda x: x.s)
    return toks


def _word_starts(units: list[str], segs: list[str] | None) -> list[bool]:
    """Which timed units begin a word, given the text's word segments."""
    if not segs:
        return [True] * len(units)
    bounds, pos = set(), 0
    for sgm in segs:
        n = len(norm(sgm))
        if n:
            if norm(sgm) not in NO_LINE_START:
                bounds.add(pos)
            pos += n
    out, pos = [], 0
    for u in units:
        out.append(pos in bounds)
        pos += len(u)
    return out


def sentences_of(toks: list[Token]) -> list[list[int]]:
    out: list[list[int]] = []
    for i, t in enumerate(toks):
        prev = toks[i - 1] if i else None
        new = prev is None or t.clip != prev.clip or t.brk == 2 or t.s - prev.e >= SENTENCE_PAUSE
        if new:
            out.append([])
        out[-1].append(i)
    return out


def text_of(toks: list[Token], idx: list[int]) -> str:
    s = ""
    for i in idx:
        t = toks[i].t
        if s and not _is_cjk(t) and not _is_cjk(s[-1]) and t not in PUNCT:
            s += " "
        s += t
    return s


# --------------------------------------------------------------------------
# rules
# --------------------------------------------------------------------------

def mark_fillers(toks: list[Token]) -> None:
    for t in toks:
        if norm(t.t) in FILLERS:
            t.drop = "filler"


def mark_stumbles(toks: list[Token], idx: list[int]) -> None:
    """Immediate repeats ("我觉得我觉得", "I I think") and restarts at a
    clause start ("我也觉得我也挺好" -> keep "我也挺好")."""
    u = [norm(toks[i].t) for i in idx]
    n = len(u)
    p = 0
    while p < n:
        hit = None
        cjk = _is_cjk(toks[idx[p]].t)
        for k in range(min(6, n // 2), 0, -1):
            if cjk and k < 2:
                break
            unit = u[p:p + k]
            if len(set("".join(unit))) <= 1:          # 哈哈 / 谢谢 are words, not stumbles
                continue
            at_clause = p == 0 or toks[idx[p]].brk > 0 or toks[idx[p]].s - toks[idx[p - 1]].e > 0.25 \
                or toks[idx[p - 1]].drop == "stumble"
            for q in range(p + k, min(n - k + 1, p + k + (3 if at_clause else 0) + 1)):
                if u[q:q + k] == unit:
                    hit = q
                    break
            if hit is not None:
                break
        if hit is not None:
            for j in range(p, hit):
                toks[idx[j]].drop = toks[idx[j]].drop or "stumble"
            p = hit
        else:
            p += 1


@dataclass
class Sentence:
    id: str
    clip: str
    idx: list[int]
    text: str
    start: float
    end: float
    auto: str | None = None          # reason code if a rule/agent drops it
    flag: str | None = None          # suggestion only (e.g. off-script), not dropped
    note: str = ""
    script_line: int | None = None


def mark_retakes(sents: list[Sentence], toks: list[Token]) -> None:
    """Said again within the next two sentences: the earlier take goes.

    The recogniser doesn't always end a sentence where the speaker did, so
    the take may be only the *end* of a sentence ("…剪掉。第二步是删掉重复的
    句子" then "第二步是删掉重复的句子"): then just that tail goes. Matching is
    on character pairs, so a misheard character (剧子/句子) still matches."""
    for i, a in enumerate(sents):
        if a.auto:
            continue
        for b in sents[i + 1:i + 3]:
            if b.clip != a.clip:
                break
            nb = norm(b.text)
            if len(nb) < 4:
                continue
            best, best_k = 0.0, 0
            for k in range(len(a.idx), 0, -1):
                tail = text_of(toks, a.idx[-k:])
                if len(norm(tail)) < max(4, int(0.6 * len(nb))):
                    break
                c = containment(tail, b.text)
                if c > best + 0.02:
                    best, best_k = c, k
            head = norm(a.text)[:max(3, len(norm(a.text)) // 2)]
            # A tail that leaves only a word or two in front (often misheard:
            # 第二步/第二部) is the whole sentence said again.
            whole = best_k >= len(a.idx) - 3 or (nb.startswith(head) and len(norm(a.text)) <= len(nb) + 2)
            if best >= 0.6 and whole:
                a.auto = "retake"
                a.note = f"said again as “{b.text[:24]}{'…' if len(b.text) > 24 else ''}”"
                break
            if best >= 0.6 and best_k:
                for j in a.idx[-best_k:]:
                    toks[j].drop = "retake"
                break


def split_script(script: str) -> list[str]:
    parts = re.split(r"(?<=[。！？!?；;])|\n+|(?<=\.)\s+", script or "")
    return [p.strip() for p in parts if p and norm(p)]


def match_script(sents: list[Sentence], lines: list[str]) -> list[int]:
    """Map sentences to script lines; among consecutive takes of one line keep
    the most complete (ties: the last). Returns script lines never said."""
    if not lines:
        return []
    for s in sents:
        if s.auto:
            continue
        scores = [containment(s.text, ln) for ln in lines]
        best = int(np.argmax(scores))
        if scores[best] >= 0.5:
            s.script_line = best
        elif len(norm(s.text)) >= 6 and scores[best] < 0.25:
            s.flag = "off_script"
    i = 0
    live = [s for s in sents if not s.auto]
    while i < len(live):
        j = i
        while j + 1 < len(live) and live[j + 1].script_line is not None and live[j + 1].script_line == live[i].script_line:
            j += 1
        if live[i].script_line is not None and j > i:
            group = live[i:j + 1]
            ln = lines[live[i].script_line]
            best = max(range(len(group)), key=lambda k: (round(containment(ln, group[k].text), 2), k))
            for k, s in enumerate(group):
                if k != best:
                    s.auto = "script_retake"
                    s.note = f"script line {s.script_line + 1}: another take is more complete"
        i = j + 1
    said = {s.script_line for s in sents if s.script_line is not None and not s.auto}
    return [k for k in range(len(lines)) if k not in said]


# --------------------------------------------------------------------------
# the plan
# --------------------------------------------------------------------------

@dataclass
class Plan:
    locale: str
    toks: list[Token]
    sents: list[Sentence]
    clips: dict[str, dict]
    script: list[str] = field(default_factory=list)
    unsaid: list[int] = field(default_factory=list)
    source: str = "rules"
    agent_note: str = ""
    overrides: dict[str, bool] = field(default_factory=dict)   # item id -> removed?

    # -- decisions -----------------------------------------------------------
    def removed(self, item: str, auto: bool) -> bool:
        return self.overrides.get(item, auto)

    def sentence_dropped(self, s: Sentence) -> bool:
        return self.removed(s.id, bool(s.auto))

    def token_dropped(self, i: int) -> bool:
        t = self.toks[i]
        s = self._sent[t.sentence]
        if self.sentence_dropped(s):
            return True
        return bool(t.drop) and self.removed(self._run_id(i), True)

    def _run_id(self, i: int) -> str:
        """Consecutive tokens removed for one reason form one toggleable run."""
        j = i
        while j > 0 and self.toks[j - 1].drop == self.toks[i].drop and self.toks[j - 1].sentence == self.toks[i].sentence:
            j -= 1
        return f"{self.toks[i].sentence}/w{j}"

    def pause_id(self, i: int) -> str:
        return f"p:{self.toks[i].clip}:{i}"

    def pause_cut(self, i: int) -> bool:
        """The gap after token i is a cut pause."""
        return self.removed(self.pause_id(i), True)

    def __post_init__(self):
        self._sent = {s.id: s for s in self.sents}


def build(transcripts: dict[str, list[dict]], clips: dict[str, dict], locale: str,
          levels: dict[str, np.ndarray] | None = None, script: str = "", agent=None) -> Plan:
    """transcripts: clip id -> speech.transcribe() output, in playing order."""
    toks: list[Token] = []
    for cid, res in transcripts.items():
        toks += tokens_of(cid, res, (levels or {}).get(cid))
    mark_fillers(toks)
    sents: list[Sentence] = []
    for k, idx in enumerate(sentences_of(toks)):
        sid = f"s{k + 1}"
        for i in idx:
            toks[i].sentence = sid
        mark_stumbles(toks, idx)
        sents.append(Sentence(sid, toks[idx[0]].clip, idx, text_of(toks, idx), toks[idx[0]].s, toks[idx[-1]].e))
    # a sentence that is nothing but fillers/stumbles goes whole
    for s in sents:
        if all(toks[i].drop for i in s.idx):
            s.auto = toks[s.idx[0]].drop
    mark_retakes(sents, toks)
    lines = split_script(script)
    unsaid = match_script(sents, lines)
    plan = Plan(locale, toks, sents, clips, lines, unsaid)
    if agent is not None:
        try:
            verdict = agent([{"id": s.id, "text": s.text, "seconds": round(s.end - s.start, 1),
                              "rule": s.auto, "script_line": None if s.script_line is None else s.script_line + 1}
                             for s in sents], lines)
            by = {s.id: s for s in sents}
            for s in sents:        # the model's judgement replaces the rules' at sentence level
                if s.auto in ("retake", "script_retake"):
                    s.auto = None
            for d in verdict.get("drops", []):
                s = by.get(d.get("id"))
                if s:
                    s.auto = d.get("reason") if d.get("reason") in REASONS else "agent"
                    s.note = (d.get("note") or "").strip()[:120]
            plan.source = "agent"
            plan.agent_note = (verdict.get("reply") or "").strip()
        except Exception as e:  # noqa: BLE001 -- the rules still stand
            plan.agent_note = f"The editing model couldn't be reached ({e}); these are the rules' suggestions."
    return plan


def toggle(plan: Plan, item: str) -> None:
    auto = _auto_of(plan, item)
    cur = plan.removed(item, auto)
    if (not cur) == auto:
        plan.overrides.pop(item, None)
    else:
        plan.overrides[item] = not cur


def _auto_of(plan: Plan, item: str) -> bool:
    if item.startswith("p:"):
        return True
    if "/w" in item:
        return True
    s = plan._sent.get(item)
    if s is None:
        raise KeyError(item)
    return bool(s.auto)


# --------------------------------------------------------------------------
# kept spans -> storyboard + captions
# --------------------------------------------------------------------------

def spans(plan: Plan) -> list[dict]:
    """Source spans to keep, in order: {clip, start, end, toks: [i...]}."""
    T = plan.toks
    out: list[dict] = []
    prev = None
    for i, t in enumerate(T):
        if plan.token_dropped(i):
            continue
        joined = (prev is not None and T[prev].clip == t.clip and prev == i - 1
                  and (t.s - T[prev].e < MIN_PAUSE or not plan.pause_cut(prev)))
        if joined:
            out[-1]["end"] = float(t.e)
            out[-1]["toks"].append(i)
        else:
            if out:
                last = out[-1]["toks"][-1]
                nxt = T[last + 1].s if last + 1 < len(T) and T[last + 1].clip == T[last].clip else T[last].e + TAIL
                out[-1]["end"] = min(T[last].e + TAIL, max(T[last].e, nxt))
            before = T[i - 1].e if i > 0 and T[i - 1].clip == t.clip else 0.0
            out.append({"clip": t.clip, "start": max(before, t.s - LEAD, 0.0), "end": t.e, "toks": [i]})
        prev = i
    if out:
        last = out[-1]["toks"][-1]
        dur = plan.clips.get(T[last].clip, {}).get("duration", T[last].e + TAIL)
        out[-1]["end"] = min(T[last].e + TAIL, dur)
    for sp in out:
        sp["start"], sp["end"] = round(float(sp["start"]), 3), round(float(sp["end"]), 3)
    return [sp for sp in out if sp["end"] - sp["start"] >= 0.1]


def _shot_for(clip: dict, t: float) -> str:
    for s in clip.get("shots", []):
        if s["start"] - 1e-3 <= t < s["end"]:
            return f"{clip['id']}:{s['index']}"
    s = min(clip.get("shots", [{"index": 0, "start": 0}]), key=lambda s: abs(s["start"] - t))
    return f"{clip['id']}:{s['index']}"


def board(plan: Plan, captions: bool = True, style: dict | None = None) -> dict:
    T = plan.toks
    sp = spans(plan)
    beats: list[dict] = []
    seq, t = [], 0.0
    last_sent = None
    for k, s in enumerate(sp):
        first = T[s["toks"][0]]
        gap_before = first.s - T[s["toks"][0] - 1].e if s["toks"][0] > 0 else 99
        cur = beats[-1] if beats else None
        new = (cur is None or cur["_clip"] != s["clip"] or gap_before >= PARA_PAUSE
               or (first.sentence != last_sent and len(cur["_sents"]) >= PART_MAX_SENTENCES))
        if new:
            text = plan._sent[first.sentence].text
            beats.append({"id": f"k{len(beats) + 1}", "title": text[:18] + ("…" if len(text) > 18 else ""),
                          "detail": "", "shots": [], "_clip": s["clip"], "_sents": []})
            cur = beats[-1]
        for i in s["toks"]:
            if T[i].sentence not in cur["_sents"]:
                cur["_sents"].append(T[i].sentence)
        last_sent = T[s["toks"][-1]].sentence
        sid = _shot_for(plan.clips[s["clip"]], s["start"])
        key = f"{sid}~t{int(round(s['start'] * 1000))}"
        cur["shots"].append({"key": key, "id": sid, "start": s["start"], "end": s["end"]})
        seq.append({**s, "key": key, "seq": t})
        t += s["end"] - s["start"]
    for b in beats:
        n = len(b["_sents"])
        b["detail"] = f"{n} sentence{'s' * (n != 1)}"
        del b["_clip"], b["_sents"]
    out = {"option": "talk", "name": "Talking-head cut",
           "structure": "Cut by what you said: pauses shortened to a breath, retakes and stumbles taken out.",
           "beats": beats}
    if captions and seq:
        out["overlays"] = caption_overlays(plan, seq)
        out["overlay_style"] = {"font": "Clean", "color": "#ffffff", "accent": "#b9d9eb", "captions": "bottom",
                                "backing": "shadow", **(style or {})}
    return out


def caption_overlays(plan: Plan, seq: list[dict]) -> list[dict]:
    """Subtitle lines from the kept words, timed on the cut edit."""
    T = plan.toks
    where: dict[int, dict] = {}
    for s in seq:
        for i in s["toks"]:
            where[i] = s

    def to_seq(i: int, edge: str) -> float:
        s = where[i]
        v = T[i].s if edge == "s" else T[i].e
        return s["seq"] + min(max(v, s["start"]), s["end"]) - s["start"]

    lines: list[list[int]] = []
    kept = [i for s in seq for i in s["toks"]]
    for i in kept:
        cur = lines[-1] if lines else None
        if cur:
            p = cur[-1]
            hard = (T[i].sentence != T[p].sentence or T[i].brk > 0 or T[i].clip != T[p].clip
                    or T[i].s - T[p].e >= MIN_PAUSE)
            if not hard:
                cur.append(i)
                text = text_of(T, cur)
                limit = CAPTION_CJK if _is_cjk(text) else CAPTION_LATIN
                if len(norm(text)) > limit:
                    # Too long: break where the speaker left the biggest gap
                    # (Chinese has no spaces; a gap is the best word boundary).
                    lo = max(1, len(cur) // 2)
                    cands = [k for k in range(lo, len(cur)) if T[cur[k]].ws] or \
                        [k for k in range(1, len(cur)) if T[cur[k]].ws] or list(range(lo, len(cur)))
                    # the speaker's biggest gap; on a tie, the most even split
                    j = max(cands, key=lambda k: (round(T[cur[k]].s - T[cur[k - 1]].e, 2),
                                                  -abs(len(norm(text_of(T, cur[:k]))) - len(norm(text)) / 2)))
                    lines[-1], rest = cur[:j], cur[j:]
                    lines.append(rest)
                continue
            # A pause the recogniser timed a character off ('拍 | 了很多照片'):
            # never start a line mid-word -- move the word's start down with it.
            if not T[i].ws and T[i].sentence == T[p].sentence and T[i].clip == T[p].clip:
                k = len(cur) - 1
                while k > 0 and not T[cur[k]].ws:
                    k -= 1
                if 0 < k and len(cur) - k <= 2:
                    lines[-1], moved = cur[:k], cur[k:]
                    lines.append(moved + [i])
                    continue
        lines.append([i])
    out = []   # size L: vertical talking-head subtitles read big
    for n, ln in enumerate(lines):
        a = to_seq(ln[0], "s")
        z = to_seq(ln[-1], "e") + 0.1
        nxt = to_seq(lines[n + 1][0], "s") if n + 1 < len(lines) else None
        if nxt is not None:
            z = min(max(z, a + 0.8), nxt)   # at least 0.8 s, never over the next line
        text = text_of(T, ln).strip(PUNCT.replace("？", "").replace("！", "").replace("?", "").replace("!", ""))
        if not text:
            continue
        s = where[ln[0]]
        out.append({"id": f"cap{n + 1}", "kind": "caption", "text": text[:140], "sub": "", "pos": "bottom",
                    "size": "L", "anim": "none", "dur": round(float(max(0.3, z - a)), 3),
                    "anchor": {"to": "shot", "id": s["key"]}, "at": round(float(a - s["seq"]), 3), "speech": True})
    return out


# --------------------------------------------------------------------------
# what the gate shows
# --------------------------------------------------------------------------

def public(plan: Plan) -> dict:
    T = plan.toks
    items = []
    removed = {"pause": [0, 0.0], "retake": [0, 0.0], "stumble": [0, 0.0], "filler": [0, 0.0], "other": [0, 0.0]}

    def bucket(code: str) -> str:
        return "retake" if code in ("retake", "script_retake") else code if code in removed else "other"

    prev_sent_last = None
    for s in plan.sents:
        # the pause before this sentence, if any
        f = s.idx[0]
        if prev_sent_last is not None and T[f].clip == T[prev_sent_last].clip:
            gap = T[f].s - T[prev_sent_last].e
            if gap >= MIN_PAUSE:
                cut = plan.pause_cut(prev_sent_last)
                items.append({"kind": "pause", "id": plan.pause_id(prev_sent_last), "len": round(gap, 2),
                              "cut": cut, "keeps": round(min(gap, LEAD + TAIL), 2)})
                if cut:
                    removed["pause"][0] += 1
                    removed["pause"][1] += gap - min(gap, LEAD + TAIL)
        dropped = plan.sentence_dropped(s)
        parts = []
        run: dict | None = None
        for j, i in enumerate(s.idx):
            t = T[i]
            if j and t.s - T[s.idx[j - 1]].e >= MIN_PAUSE:
                pid = plan.pause_id(s.idx[j - 1])
                cut = plan.pause_cut(s.idx[j - 1])
                gap = t.s - T[s.idx[j - 1]].e
                parts.append({"kind": "pause", "id": pid, "len": round(gap, 2), "cut": cut})
                run = None
                if cut and not dropped:
                    removed["pause"][0] += 1
                    removed["pause"][1] += gap - min(gap, LEAD + TAIL)
            code = t.drop
            rid = plan._run_id(i) if code else None
            if run and run.get("id") == rid and run["kind"] == "words":
                run["text"] = text_of(T, run["_idx"] + [i])
                run["_idx"].append(i)
                continue
            gone = bool(code) and plan.removed(rid, True)
            run = {"kind": "words", "id": rid, "_idx": [i], "text": t.t, "removed": gone, "code": code,
                   "zh": REASONS[code][0] if code else "", "en": REASONS[code][1] if code else ""}
            parts.append(run)
        for p in parts:
            if p["kind"] == "words" and p["removed"] and not dropped:
                removed[bucket(p["code"])][0] += 1
                removed[bucket(p["code"])][1] += sum(T[i].e - T[i].s for i in p["_idx"])
            p.pop("_idx", None)
        code = s.auto or s.flag
        if dropped:
            removed[bucket(s.auto or "other")][0] += 1
            removed[bucket(s.auto or "other")][1] += s.end - s.start
        items.append({"kind": "sentence", "id": s.id, "clip": s.clip, "clip_name": plan.clips[s.clip]["name"],
                      "start": s.start, "end": s.end, "text": s.text, "removed": dropped,
                      "auto": bool(s.auto), "override": s.id in plan.overrides, "code": code,
                      "zh": REASONS[code][0] if code in REASONS else "", "en": REASONS[code][1] if code in REASONS else "",
                      "why": s.note or (REASONS[code][2] if code in REASONS else ""), "flag": s.flag,
                      "script_line": None if s.script_line is None else s.script_line + 1, "parts": parts})
        prev_sent_last = s.idx[-1]
    sp = spans(plan)
    raw = sum(c.get("duration", 0.0) for cid, c in plan.clips.items() if any(t.clip == cid for t in T))
    cut = sum(x["end"] - x["start"] for x in sp)
    mm = lambda x: f"{int(x // 60)}:{int(round(x % 60)):02d}" if x % 60 < 59.5 else f"{int(x // 60) + 1}:00"  # noqa: E731
    return {
        "locale": plan.locale, "source": plan.source, "agent_note": plan.agent_note,
        "clips": [{"id": cid, "name": c["name"]} for cid, c in plan.clips.items() if any(t.clip == cid for t in T)],
        "items": items,
        "script": plan.script, "unsaid": [{"line": k + 1, "text": plan.script[k]} for k in plan.unsaid],
        "summary": {
            "raw": round(raw, 1), "cut": round(cut, 1), "sentences": len(plan.sents),
            "removed": {k: {"n": v[0], "seconds": round(v[1], 1)} for k, v in removed.items()},
            "line_en": f"{mm(raw)} → {mm(cut)}: " + (" · ".join(
                f"{n} {word}{'s' * (n != 1)} {verb}" for n, word, verb in (
                    (removed["pause"][0], "pause", "shortened"), (removed["retake"][0], "retake", "removed"),
                    (removed["stumble"][0], "stumble", "removed"), (removed["filler"][0], "filler", "removed"))
                if n) or "nothing to cut"),
        },
    }

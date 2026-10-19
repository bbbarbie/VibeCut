"""The AI checks its own edit: one look at the whole cut, then the fixes.

Why this exists (sarah, 2026-10-18: "lets do AI checks own edit"): the
story editor (story.py) plans a video from one frame per moment, moment by
moment. It never sees the finished timeline, so it can keep two shots of the
same table twenty seconds apart, or let a chapter run on. An editor checks a
cut by looking at it whole, so this does the same: a contact sheet -- one
still from the middle of every shot, in playing order, numbered, coloured
by chapter -- goes to the model with the list of shots, and it answers with
what's wrong and the few changes that fix it.

What other tools do (research of 2026-10-18 on oh-my-cassette, ffmpeg-skill,
ai-video-editing-skill, FireRed-OpenStoryline): the contact sheet is the
convention (one still per shot at the middle of the range the timeline
uses, numbered tiles), but there it is shown to a person, or checked for
layout only. None has a model look at its own cut for story faults, so the
review below is written from scratch, with their guardrails: one round,
never a loop; dedup keeps most of the shots (OpenStoryline keeps > 80%);
nothing is claimed about pictures that weren't looked at.

The fixes are ordinary board ops (drop a shot, trim its end, move it), so
they land as one undoable turn of their own, after "Made your video" or
when the creator asks for a check. Shortening keeps the music's beat when
there is one. Every number here is a prior.
"""

from __future__ import annotations

import hashlib
import math
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from . import indexer, moment, oai, timeline

TILES = 16               # shots per sheet
MAX_SHEETS = 6           # 96 shots; more and the rest are listed but not pictured (and said so)
TILE = {"vertical": (180, 320), "wide": (320, 180)}     # (w, h) of one still
COLS = {"vertical": 8, "wide": 4}
STRIP_H, PAD = 26, 6     # the label under each still, the gap between cells
BG = (12, 12, 12)
HOOK_RGB = (105, 105, 105)
CHAPTER_RGB = [(204, 62, 58), (46, 112, 196), (36, 140, 82), (196, 122, 22),
               (132, 74, 186), (18, 140, 150), (196, 62, 132), (120, 96, 60)]
LOOKALIKE = 0.78         # feature-print cosine worth naming to the model (select's look-alike line)
MAX_HINTS = 12
MIN_S = 0.6              # the shortest a shot may be shortened to
MAX_DROP = 0.25          # never drop more than this share of the shots...
FEW = 5                  # ...and none at all from an edit this small
ISSUES = ("repeat", "drags", "back_and_forth", "opening", "ending", "other")

SYSTEM = """You are the supervising editor checking a finished cut of a phone vlog before the creator sees it. Another editor made it; you are seeing it whole for the first time.

You get contact sheets: one still from the middle of every shot, in the order they play, left to right then top to bottom. Under each still is its number and how many seconds it stays on screen. The colour of that strip is its chapter; grey is the opening hook. The stills are the filmed pictures, without the captions, colour grade or transitions the video adds. You also get the list of shots with what the phone measured.

Look for what makes a cut feel amateur or slow, in this order:
1. repeat: two shots a viewer would read as the same shot twice (same place, same framing, same action), anywhere in the video, not only side by side. A wide shot then a close one of the same thing is coverage, not a repeat. Keep the better one (sharper, better framed, more happening, or the one its chapter needs) and drop the other.
2. drags: a chapter that holds longer than what happens in it, several steps of the same action in a row, or a long shot where nothing changes. Tighten it by dropping the weakest step or shortening a long shot. A payoff (the reveal, the reaction, the view) may hold; setups and steps should be quick. Each chapter should feel like a little story: a quick setup, a few steps, a payoff.
3. back_and_forth: the video leaves a place or an action and comes back to it later (A, B, A) when those shots could sit together. Move the stray shot to its group.
4. opening: the first shot must stop the scroll. If it is weak and a clearly stronger shot exists that no chapter needs as its payoff, move that one to open.
5. ending: the last shot should land (a payoff, a view, a sign-off), not trail off. Fix it with a move or a drop only when that clearly helps.

Rules:
- Fix only what is clearly wrong. A cut that holds up gets no fixes, and you say so.
- The changes you can make: drop a shot; shorten a shot to a number of seconds (at least 0.6, and shorter than it is now); move a shot to play just before another shot.
- Never drop more than a quarter of the shots. Never drop a shot where someone talks to the camera unless it repeats another shot.
- The pictures decide, not the list. The phone's look-alike scores over-call shots with similar colours and miss the same scene in different light.
- summary: one or two plain sentences to the creator saying what you changed and why, or that the cut holds up. No editing jargon, no shot numbers.
- Each issue: its kind, the shot numbers, and a short note in plain words. Each fix names the issue kind it answers."""

SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["summary", "issues", "fixes"],
    "properties": {
        "summary": {"type": "string"},
        "issues": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["kind", "shots", "note"],
            "properties": {"kind": {"type": "string", "enum": list(ISSUES)},
                           "shots": {"type": "array", "items": {"type": "integer"}},
                           "note": {"type": "string"}}}},
        "fixes": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["do", "shot", "seconds", "before", "because"],
            "properties": {"do": {"type": "string", "enum": ["drop", "shorten", "move"]},
                           "shot": {"type": "integer"},
                           "seconds": {"type": ["number", "null"]},
                           "before": {"type": ["integer", "null"]},
                           "because": {"type": "string", "enum": list(ISSUES)}}}},
    },
}


class CheckError(Exception):
    pass


# --------------------------------------------------------------------------
# the contact sheet
# --------------------------------------------------------------------------

# Shot numbers and seconds under each still. ffmpeg here has no drawtext,
# so the few glyphs a label needs are drawn from a 5x7 bitmap.
_GLYPHS = {
    "0": (".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."),
    "1": ("..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."),
    "2": (".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"),
    "3": ("#####", "...#.", "..#..", "...#.", "....#", "#...#", ".###."),
    "4": ("...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."),
    "5": ("#####", "#....", "####.", "....#", "....#", "#...#", ".###."),
    "6": ("..##.", ".#...", "#....", "####.", "#...#", "#...#", ".###."),
    "7": ("#####", "....#", "...#.", "..#..", ".#...", ".#...", ".#..."),
    "8": (".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."),
    "9": (".###.", "#...#", "#...#", ".####", "....#", "...#.", ".##.."),
    ".": (".....", ".....", ".....", ".....", ".....", ".##..", ".##.."),
    "s": (".....", ".....", ".####", "#....", ".###.", "....#", "####."),
    "#": (".#.#.", ".#.#.", "#####", ".#.#.", "#####", ".#.#.", ".#.#."),
}


def _glyph(ch: str) -> np.ndarray:
    rows = _GLYPHS.get(ch)
    if rows is None:
        return np.zeros((7, 5), bool)
    return np.array([[c == "#" for c in row] for row in rows])


def _text(img: np.ndarray, s: str, x: int, y: int, scale: int, rgb=(255, 255, 255)) -> None:
    for ch in s:
        g = np.kron(_glyph(ch), np.ones((scale, scale), bool))
        h, w = g.shape
        if x + w > img.shape[1] or y + h > img.shape[0]:
            return
        img[y:y + h, x:x + w][g] = rgb
        x += 6 * scale


def _text_w(s: str, scale: int) -> int:
    return len(s) * 6 * scale - scale


def _decode(paths: list[str | None], w: int, h: int) -> tuple[np.ndarray, set[int]]:
    """Each still fitted into a w x h cell (bars, as a fit frame shows it),
    one ffmpeg call for the lot. -> (stills, indices with no picture, whose
    cells stay dark)."""
    out = np.zeros((len(paths), h, w, 3), np.uint8)
    out[:] = (26, 28, 34)
    have = [(i, p) for i, p in enumerate(paths) if p and Path(p).exists()]
    if have:
        got = _run_decode([p for _, p in have], w, h)
        if got is None and len(have) > 1:      # one unreadable file spoils the batch: one at a time
            got = [(_run_decode([p], w, h) or [None])[0] for _, p in have]
        for (i, _), fr in zip(have, got or []):
            if fr is not None:
                out[i] = fr
        done = {i for (i, _), fr in zip(have, got or []) if fr is not None}
    else:
        done = set()
    return out, set(range(len(paths))) - done


def _run_decode(paths: list[str], w: int, h: int) -> list[np.ndarray] | None:
    fit = f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=0x07080b,setsar=1,format=rgb24"
    cmd = ["ffmpeg", "-v", "error"]
    for p in paths:
        cmd += ["-i", p]
    graph = ";".join(f"[{k}:v]{fit}[v{k}]" for k in range(len(paths)))
    graph += ";" + "".join(f"[v{k}]" for k in range(len(paths))) + f"concat=n={len(paths)}:v=1:a=0[o]"
    # every still is one frame at time 0: passthrough, or the output frame rate drops most of them
    cmd += ["-filter_complex", graph, "-map", "[o]", "-fps_mode", "passthrough", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        return None
    frames = np.frombuffer(p.stdout, np.uint8)
    if p.returncode != 0 or len(frames) != len(paths) * w * h * 3:
        return None
    return list(frames.reshape(len(paths), h, w, 3))


def _jpeg(img: np.ndarray) -> bytes:
    h, w = img.shape[:2]
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "sheet.jpg"
        p = subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
                            "-i", "-", "-frames:v", "1", "-q:v", "3", str(f)],
                           input=np.ascontiguousarray(img).tobytes(), capture_output=True, timeout=60)
        if p.returncode != 0 or not f.exists():
            raise CheckError("couldn't draw the contact sheet: " + p.stderr.decode(errors="ignore")[:200])
        return f.read_bytes()


def shots_of(board: dict | None) -> list[dict]:
    """The edit's shots in playing order (gaps left out), numbered as the
    timeline numbers them."""
    return [it for it in timeline.layout(board) if it["kind"] == "shot"]


def chapters_of(board: dict | None) -> list[dict]:
    """Each part of the edit: its id, title, the heading's line under it."""
    heads = {o["anchor"].get("id"): o for o in (board or {}).get("overlays", [])
             if o.get("kind") == "heading" and o.get("anchor", {}).get("to") == "beat"}
    return [{"id": b["id"], "title": b["title"], "sub": (heads.get(b["id"]) or {}).get("sub", ""),
             "hook": b["id"] == "r0" or b["title"] == "Hook"}
            for b in (board or {}).get("beats", []) if any(not e.get("gap") for e in b["shots"])]


def _colours(chapters: list[dict]) -> dict[str, tuple]:
    out, k = {}, 0
    for c in chapters:
        if c["hook"]:
            out[c["id"]] = HOOK_RGB
        else:
            out[c["id"]] = CHAPTER_RGB[k % len(CHAPTER_RGB)]
            k += 1
    return out


def stills_of(items: list[dict], clips: dict[str, dict]) -> list[str | None]:
    """The index sample nearest the middle of the seconds each shot uses
    (the convention: one still per shot, mid-range, so no tile is a black
    lead-in). None where the clip has no samples."""
    return [moment._frame(clips[it["clip_id"]], (it["src_start"] + it["src_end"]) / 2)
            if it["clip_id"] in clips else None for it in items]


def sheets(items: list[dict], paths: list[str | None], fmt: str, chapters: list[dict]) -> tuple[list[bytes], set[int]]:
    """Contact sheets of the edit: TILES stills each, numbered, a coloured
    strip per chapter. -> (JPEG bytes per sheet, numbers of the shots with
    no picture)."""
    shape = "wide" if fmt == "wide" else "vertical"
    w, h = TILE[shape]
    cols = COLS[shape]
    colour = _colours(chapters)
    out, dark = [], set()
    for first in range(0, min(len(items), TILES * MAX_SHEETS), TILES):
        page = items[first:first + TILES]
        stills, none = _decode(paths[first:first + TILES], w, h)
        dark |= {page[j]["n"] for j in none}
        rows = math.ceil(len(page) / cols)
        ncols = min(cols, len(page)) if rows == 1 else cols
        img = np.zeros((PAD + rows * (h + STRIP_H + PAD), PAD + ncols * (w + PAD), 3), np.uint8)
        img[:] = BG
        for j, it in enumerate(page):
            r, c = divmod(j, cols)
            x, y = PAD + c * (w + PAD), PAD + r * (h + STRIP_H + PAD)
            img[y:y + h, x:x + w] = stills[j]
            img[y + h:y + h + STRIP_H, x:x + w] = colour.get(it["beat_id"], HOOK_RGB)
            _text(img, f"#{it['n']}", x + 6, y + h + 3, 3)
            secs = f"{it['seq_end'] - it['seq_start']:.1f}s"
            _text(img, secs, x + w - 6 - _text_w(secs, 3), y + h + 3, 3)
        out.append(_jpeg(img))
    return out, dark


def save(sheet_bytes: list[bytes]) -> list[str]:
    """Keep the sheets so the creator can see what the AI looked at. -> names."""
    d = indexer.CACHE / "checks"
    d.mkdir(parents=True, exist_ok=True)
    names = []
    for b in sheet_bytes:
        name = hashlib.sha1(b).hexdigest()[:16] + ".jpg"
        (d / name).write_bytes(b)
        names.append(name)
    return names


def sheet_path(name: str) -> Path | None:
    if len(name) != 20 or not name.endswith(".jpg") or any(c not in "0123456789abcdef" for c in name[:16]):
        return None
    p = indexer.CACHE / "checks" / name
    return p if p.exists() else None


# --------------------------------------------------------------------------
# the list that goes with it
# --------------------------------------------------------------------------

def _clock(s) -> str:
    if not s.when:
        return ""
    h = s.when.hour % 12 or 12
    return f"{s.when.strftime('%a')} {h}:{s.when.minute:02d} {'am' if s.when.hour < 12 else 'pm'}"


def _mmss(t: float) -> str:
    return f"{int(t // 60)}:{int(t % 60):02d}"


def hints(items: list[dict], cat) -> list[str]:
    """What the phone measured that points at a repeat: feature prints that
    look alike, and the same seconds of one clip used twice."""
    out: list[tuple[float, str]] = []
    for i, a in enumerate(items):
        sa = cat.shots.get(a["shot_id"])
        for b in items[i + 1:]:
            if a["clip_id"] == b["clip_id"] and a["src_start"] < b["src_end"] and b["src_start"] < a["src_end"]:
                out.append((2.0, f"#{a['n']} and #{b['n']} use the same seconds of {sa.clip_name if sa else a['clip_id']}"))
                continue
            sb_ = cat.shots.get(b["shot_id"])
            if sa is None or sb_ is None or sa.vec.shape != sb_.vec.shape or not sa.vec.size:
                continue
            cos = float(sa.vec @ sb_.vec)
            if cos >= LOOKALIKE and a["shot_id"] != b["shot_id"]:
                out.append((cos, f"#{a['n']} and #{b['n']} look alike to the phone ({cos:.2f})"))
    out.sort(key=lambda x: -x[0])
    return [s for _, s in out[:MAX_HINTS]]


def legend(items: list[dict], chapters: list[dict], cat, talking: set[str], fmt: str,
           target_s: float | None, bpm: float | None, missing: set[int] = frozenset()) -> str:
    total = items[-1]["seq_end"] if items else 0.0
    frame = {"short": "vertical short", "tall": "vertical vlog", "wide": "wide 16:9 vlog"}.get(fmt, "vertical vlog")
    head = f"The cut: {len(items)} shots, {total:.1f} s, {frame}."
    if target_s:
        head += f" It was asked to be about {target_s:.0f} s."
    if bpm:
        head += f" Music at {bpm:.0f} BPM; the cuts sit on its beat."
    pictured = min(len(items), TILES * MAX_SHEETS)
    lines = [head, f"{math.ceil(pictured / TILES)} contact sheet(s), {TILES} shots each."]
    if pictured < len(items):
        lines.append(f"Shots #{pictured + 1}-#{len(items)} are listed but not pictured.")
    lines.append("Chapters:")
    by_ch: dict[str, list[dict]] = {}
    for it in items:
        by_ch.setdefault(it["beat_id"], []).append(it)
    for c in chapters:
        its = by_ch.get(c["id"]) or []
        if not its:
            continue
        secs = its[-1]["seq_end"] - its[0]["seq_start"]
        name = "Hook (grey)" if c["hook"] else f"“{c['title']}”" + (f" ({c['sub']})" if c["sub"] else "")
        span = f"#{its[0]['n']}" + (f"-#{its[-1]['n']}" if len(its) > 1 else "")
        lines.append(f"- {name}: {span}, {len(its)} shot{'s' * (len(its) != 1)}, {secs:.1f} s"
                     + (f" ({100 * secs / total:.0f}% of the video)" if total else ""))
    lines.append("Shots (number · chapter · on screen · filmed · clip @ where in it · filmed at · what the phone saw):")
    title = {c["id"]: ("Hook" if c["hook"] else c["title"]) for c in chapters}
    for it in items:
        s = cat.shots.get(it["shot_id"])
        on = it["seq_end"] - it["seq_start"]
        bits = [f"#{it['n']}", title.get(it["beat_id"], it["beat_title"]), f"{on:.1f} s on screen"]
        if s is not None:
            bits.append(f"of {s.duration:.1f} s filmed")
            bits.append(f"{s.clip_name} @ {_mmss(it['src_start'])}")
            if _clock(s):
                bits.append(_clock(s))
            labels = [n for n, v in sorted(s.labels.items(), key=lambda kv: -kv[1])[:4] if v >= 0.2]
            bits.append("labels: " + (", ".join(labels) or "none"))
            if s.faces:
                bits.append(f"{s.faces} face{'s' * (s.faces != 1)}")
        if it["shot_id"] in talking:
            bits.append("someone talks to the camera")
        if (it.get("speed") or 1.0) != 1.0:
            bits.append(f"plays at {it['speed']}x")
        if it["n"] in missing:
            bits.append("no picture (its tile is dark)")
        lines.append(" · ".join(bits))
    found = hints(items, cat)
    if found:
        lines.append("The phone's measurements (they over-call and miss; your eyes decide):")
        lines += [f"- {h}" for h in found]
    return "\n".join(lines)


def estimate(n: int, model: str | None = None) -> float:
    """Dollars for one check of an edit of `n` shots, before it's sent:
    ~1500 tokens a sheet at high detail, ~50 a listed shot, the
    instructions, and an answer with its thinking [prior; the real cost is
    read from the reply's usage]."""
    p_in, _, p_out = oai.PRICES.get(model or oai.model(), oai.DEAREST)
    n = max(1, n)
    tokens_in = 1100 + n * 50 + math.ceil(min(n, TILES * MAX_SHEETS) / TILES) * 1500
    tokens_out = 600 + n * 15 + 2500
    return (tokens_in * p_in + tokens_out * p_out) / 1e6


# --------------------------------------------------------------------------
# the answer -> ops
# --------------------------------------------------------------------------

def fixes_to_ops(answer: dict, items: list[dict], talking: set[str], period: float | None = None) -> tuple[list[dict], list[str]]:
    """The model's fixes as board ops, checked against the edit: numbers
    that aren't shots, a second fix to one shot, a drop past the limit, a
    talking shot dropped for anything but a repeat, a "shorten" that
    lengthens -- each left out, and said. Shortening keeps whole half-beats
    when the music's beat is known. -> (ops, what was left out)."""
    by_n = {it["n"]: it for it in items}
    allowed = 0 if len(items) <= FEW else int(len(items) * MAX_DROP)
    touched: set[int] = set()
    moves, trims, drops, left = [], [], [], []
    for f in answer.get("fixes") or []:
        if not isinstance(f, dict):
            continue
        n, do = f.get("shot"), f.get("do")
        it = by_n.get(n) if isinstance(n, int) else None
        if it is None or n in touched:
            continue
        if do == "drop":
            if it["shot_id"] in talking and f.get("because") != "repeat":
                left.append(f"Kept shot {n}: someone talks to the camera there.")
                continue
            if len(drops) >= allowed:
                left.append(f"Kept shot {n}: dropping more would cut too much of the edit.")
                continue
            drops.append({"op": "drop_shot", "shot": it["key"]})
        elif do == "shorten":
            now = it["seq_end"] - it["seq_start"]
            try:
                want = float(f.get("seconds"))
            except (TypeError, ValueError):
                continue
            want = max(MIN_S, want)
            if period:
                unit = period / 2
                k = max(math.ceil(MIN_S / unit - 1e-6), round(want / unit))
                while k * unit > now - 0.05 and k > 1:
                    k -= 1
                want = k * unit
            if want > now - 0.1:
                continue
            speed = float(it.get("speed") or 1.0)
            trims.append({"op": "trim", "shot": it["key"], "edge": "out",
                          "to": round(it["src_start"] + want * speed, 3)})
        elif do == "move":
            to = by_n.get(f.get("before")) if isinstance(f.get("before"), int) else None
            if to is None or to["n"] == n or to["n"] == n + 1:
                continue
            moves.append({"op": "move_shot", "shot": it["key"], "beat": to["beat_id"], "before": to["key"]})
        else:
            continue
        touched.add(n)
    if len(drops) >= len(items):
        drops = drops[:-1]
    # a move must not point at a shot that's being dropped
    gone = {d["shot"] for d in drops}
    moves = [m for m in moves if m["before"] not in gone]
    return moves + trims + drops, left


def reply(answer: dict, ops: list[dict], left: list[str], n: int, cost: float | None) -> str:
    said = " ".join(str(answer.get("summary") or "").split())[:400]
    out = [f"I looked over all {n} shots of the finished cut. " + (said or ("It holds up, so I changed nothing." if not ops else ""))]
    unfixed = [i for i in answer.get("issues") or [] if isinstance(i, dict) and i.get("note")]
    if not ops and unfixed:
        out.append("Worth a look: " + "; ".join(" ".join(str(i["note"]).split())[:120] for i in unfixed[:3]) + ".")
    out += left[:3]
    return " ".join(x for x in out if x).strip()


# --------------------------------------------------------------------------
# the call
# --------------------------------------------------------------------------

def review(board: dict | None, cat, clips: dict[str, dict], fmt: str, target_s: float | None = None,
           period: float | None = None, post=None) -> dict:
    """Look at the cut and answer with fixes. -> {ops, reply, summary,
    issues, sheets (names), usage}. Raises CheckError / oai.OAIError (with
    what a paid answer cost on `.usage`)."""
    from . import tempo
    items = shots_of(board)
    if len(items) < 3:
        raise CheckError("there are too few shots to check")
    chapters = chapters_of(board)
    pics, missing = sheets(items, stills_of(items, clips), fmt, chapters)
    if len(missing) > len(items) / 2:
        # never claim to have looked at pictures it didn't have
        raise CheckError("most of the shots have no picture to look at")
    shots = [cat.shots[it["shot_id"]] for it in items if it["shot_id"] in cat.shots]
    talking = tempo.talking(list(clips.values()), shots)
    text = legend(items, chapters, cat, talking, fmt, target_s, 60.0 / period if period else None, missing)
    content = [{"type": "text", "text": text}] + [oai.image(p, detail="high") for p in pics]
    answer, usage = oai.ask_json(SYSTEM, content, SCHEMA, "edit_check", max_tokens=8000, post=post)
    ops, left = fixes_to_ops(answer, items, talking, period)
    return {"ops": ops, "reply": reply(answer, ops, left, len(items), usage.get("cost")),
            "summary": answer.get("summary", ""), "issues": answer.get("issues") or [],
            "sheets": save(pics), "usage": usage, "shots": len(items)}

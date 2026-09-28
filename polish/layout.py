"""Where a caption's words go, and the rules they may not break.

Three hard rules, each a tell of an amateur caption the creator shouldn't
have to catch by eye:

- **Words never sit on a face.** A face is what the viewer is looking at;
  text over it hides the one thing the shot is for. The caption's box is
  checked against every face in the frame over the caption's whole time on
  screen. On a conflict it moves -- above the face, then below it, then to
  the top of the frame -- and says where and why. It never silently stays.
- **Words stay inside the safe area.** The platforms' buttons, captions and
  progress bars cover the edges (more on vertical video, bottom and right).
- **No orphan.** A last line with a single character (Chinese) or a single
  word looks like a mistake; the line above gives it company.

The browser draws exactly the lines, size and box computed here, scaling
down only if its real font measures wider, so the rules are checked once,
in one place, and tested here. Text is measured by a model of the glyphs
(CJK one em, Latin about half) -- close, and on the wide side on purpose.

The face rule is only as good as the face boxes: on a machine without the
on-device detector there are none, and the check says "not checked"
(evidence: pending), never "no faces".
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from cutgrammar import evidence
from cutgrammar.grammar import BAD, OK, WARN, Finding, gate

LINE_H = 1.25          # line height, in ems
FACE_PAD = 0.02        # keep this much of the frame between words and a face
GAP = 0.02             # between a face and words placed beside it
MIN_SHRINK = 0.7       # a caption may shrink to 70% of its recipe size to fit its lines

CJK = re.compile(r"[぀-ヿ㐀-鿿가-힯豈-﫿＀-￯]")
PUNCT_AFTER = "，。！？、；：,.!?;:」』）)”’"


def safe(W: float, H: float, margin: float) -> dict:
    """The safe area in pixels: the platforms' own margins (as overlayDraw
    uses for every other overlay), never less than the recipe's margin."""
    portrait = H > W
    return {"l": W * max(0.07, margin), "r": W * max(0.14 if portrait else 0.07, margin),
            "t": H * max(0.09 if portrait else 0.08, margin), "b": H * max(0.2 if portrait else 0.09, margin)}


def char_em(ch: str, weight: int) -> float:
    if CJK.match(ch):
        w = 1.0
    elif ch == " ":
        w = 0.3
    elif ch in "il.,:;'!|":
        w = 0.3
    elif ch in "mwMW@":
        w = 0.9
    elif ch.isupper() or ch.isdigit():
        w = 0.66
    else:
        w = 0.56
    return w * (1.06 if weight >= 600 else 1.0)


def width(text: str, px: float, weight: int, stroke_em: float = 0.0) -> float:
    return sum(char_em(c, weight) for c in text) * px + stroke_em * px


def tokens(text: str) -> list[str]:
    """Breakable pieces: a CJK character (with punctuation stuck to it), or a word with its space."""
    out: list[str] = []
    for m in re.finditer(r"[぀-ヿ㐀-鿿가-힯豈-﫿＀-￯]|[^\s぀-ヿ㐀-鿿가-힯豈-﫿＀-￯]+\s*|\s+", text):
        tok = m.group(0)
        if out and tok and tok[0] in PUNCT_AFTER:
            out[-1] += tok        # never start a line with closing punctuation
        else:
            out.append(tok)
    return [t for t in out if t]


def _visible(tok: str) -> int:
    return len(tok.strip())


def orphan(line: str) -> bool:
    """A last line that is one character, or one word."""
    s = line.strip()
    if not s:
        return False
    if CJK.search(s):
        return len(re.sub(r"[\s" + re.escape(PUNCT_AFTER) + "]", "", s)) <= 1
    return len(s.split()) <= 1 and len(s) <= 12


def break_lines(text: str, max_w: float, px: float, weight: int, stroke_em: float) -> list[str]:
    toks = tokens(text)
    lines: list[list[str]] = [[]]
    for tok in toks:
        cur = "".join(lines[-1] + [tok]).rstrip()
        if lines[-1] and width(cur, px, weight, stroke_em) > max_w:
            lines.append([tok.lstrip()])
        else:
            lines[-1].append(tok)
    # an orphan takes company from the line above, if that line can spare it
    if len(lines) > 1 and orphan("".join(lines[-1])):
        prev = lines[-2]
        while prev and orphan("".join(lines[-1])) and len(prev) > 2:
            lines[-1].insert(0, prev.pop())
    return ["".join(l).strip() for l in lines if "".join(l).strip()]


# --------------------------------------------------------------------------
# faces and boxes (all boxes x, y, w, h in pixels, origin top-left)
# --------------------------------------------------------------------------

def faces_px(faces: list[list[float]], W: float, H: float) -> list[tuple[float, float, float, float]]:
    """Normalised [x, y, w, h] (top-left) -> padded pixel boxes."""
    p = FACE_PAD
    return [((f[0] - p) * W, (f[1] - p) * H, (f[2] + 2 * p) * W, (f[3] + 2 * p) * H) for f in faces]


def overlap(a, b) -> float:
    """Area of intersection of two boxes."""
    w = min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0])
    h = min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])
    return max(0.0, w) * max(0.0, h)


def inside(box, s: dict, W: float, H: float, eps: float = 0.5) -> bool:
    return (box[0] >= s["l"] - eps and box[1] >= s["t"] - eps
            and box[0] + box[2] <= W - s["r"] + eps and box[1] + box[3] <= H - s["b"] + eps)


@dataclass
class Placement:
    lines: list[str]
    px: float                        # text size in pixels
    box: tuple[float, float, float, float]
    position: str                    # where it ended up: the recipe's, or where it moved to
    moved: str | None = None         # why it moved, in words, or None
    findings: list[Finding] = field(default_factory=list)

    def public(self, W: float, H: float) -> dict:
        x, y, w, h = self.box
        return {"lines": self.lines, "size": round(self.px / H, 5),
                "box": [round(x / W, 5), round(y / H, 5), round(w / W, 5), round(h / H, 5)],
                "position": self.position, "moved": self.moved,
                "checks": [{"key": f.key, "label": f.label, "value": f.value, "unit": f.unit,
                            "verdict": f.verdict, "detail": f.detail} for f in self.findings]}


def place(text: str, recipe, W: float, H: float, faces: list[list[float]] | None,
          scale: float = 1.0, speaker: list[float] | None = None) -> Placement:
    """Lay out one caption.

    `faces`: every face box seen while the caption is on screen (normalised,
    top-left), or None when faces couldn't be looked for. `speaker`: the box
    to follow for position "follow_speaker" (else the largest face).
    """
    s = safe(W, H, recipe.margin)
    room_w = W - s["l"] - s["r"]
    base = recipe.size * min(W, H) * scale
    stroke = recipe.stroke_width if recipe.stroke_color else 0.0

    # size: the recipe's, shrunk only as far as needed to fit max_lines in the safe width
    px, lines = base, break_lines(text, room_w, base, recipe.weight, stroke)
    while len(lines) > recipe.max_lines and px > base * MIN_SHRINK:
        px *= 0.92
        lines = break_lines(text, room_w, px, recipe.weight, stroke)
    bw = min(room_w, max(width(l, px, recipe.weight, stroke) for l in lines))
    bh = len(lines) * px * LINE_H
    cx = W / 2

    def at(position: str, fx=None) -> tuple[float, float, float, float] | None:
        if position == "lower_third":
            y = H - s["b"] - bh
        elif position == "center":
            y = (H - bh) / 2
        elif position == "top":
            y = s["t"]
        elif position == "above" and fx:
            y = fx[1] - GAP * H - bh
        elif position == "below" and fx:
            y = fx[1] + fx[3] + GAP * H
        else:
            return None
        x = cx - bw / 2
        if fx and position in ("above", "below"):
            x = min(max(fx[0] + fx[2] / 2 - bw / 2, s["l"]), W - s["r"] - bw)
        return (x, y, bw, bh)

    fboxes = faces_px(faces or [], W, H)
    hits = lambda b: sum(overlap(b, f) for f in fboxes)  # noqa: E731

    want = recipe.position
    if want == "follow_speaker":
        spk = faces_px([speaker], W, H)[0] if speaker else (max(fboxes, key=lambda f: f[2] * f[3]) if fboxes else None)
        first = at("below", spk) if spk else at("lower_third")
        if first and spk and not inside(first, s, W, H):
            first = at("above", spk)
        first = first or at("lower_third")
        name = "under the speaker" if spk else "lower_third"
    else:
        first, name = at(want), want

    box, where, moved = first, name, None
    if fboxes and hits(first) > 0:
        worst = max(fboxes, key=lambda f: overlap(first, f))
        tries = [("above the face", at("above", worst)), ("below the face", at("below", worst)),
                 ("top of the frame", at("top")), ("lower third", at("lower_third")), ("centre", at("center"))]
        ok = [(n, b) for n, b in tries if b and inside(b, s, W, H) and hits(b) == 0]
        if ok:
            where, box = ok[0]
            moved = f"moved {where} — it would have covered a face"
        else:
            moved = "couldn't find room clear of every face — it overlaps one; move it or shorten it"

    fs: list[Finding] = []
    area = hits(box) / max(1.0, box[2] * box[3])
    fs.append(Finding("caption_face", "Covers a face", round(area, 3), "fraction",
                      BAD if area > 0 else OK,
                      "The words sit on a face." if area > 0 else "Clear of every face.",
                      evidence=[evidence.STILL]))
    ins = inside(box, s, W, H)
    fs.append(Finding("caption_safe", "Inside the safe area", 1.0 if ins else 0.0, "", OK if ins else BAD,
                      "Inside the safe area." if ins else "Part of the words falls where the app's buttons are.",
                      evidence=[evidence.META]))
    orph = orphan(lines[-1]) and len(lines) > 1
    fs.append(Finding("caption_orphan", "Lonely last line", float(orph), "", WARN if orph else OK,
                      "The last line is one character or word." if orph else "No lonely last line.",
                      evidence=[evidence.META]))
    if px < base - 1e-6:
        fs.append(Finding("caption_shrunk", "Smaller to fit", round(px / base, 2), "×", WARN,
                          f"Set at {px / base:.0%} of the recipe's size to fit {recipe.max_lines} line(s).",
                          evidence=[evidence.META]))
    have = {evidence.META} | ({evidence.STILL} if faces is not None else set())
    gate(fs, have)
    return Placement(lines=lines, px=px, box=box, position=where, moved=moved, findings=fs)

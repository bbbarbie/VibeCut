"""polish: the click becomes a place, and the words obey the frame.

The discrimination pairs (CLAUDE.md: a check that only fires proves nothing):

- A clip with a face in the lower third vs the same clip with the face at
  the top. A "lower third" caption must move off the face in the first,
  stay in the lower third in the second, and be inside the safe area in
  both -- checked on the box the browser will draw, not on "a caption
  exists".
- A line break that would leave one character alone vs one that wouldn't.
- An effect clicked 0.3 s before a movement vs in a still stretch: it
  starts on the movement in the first, where clicked in the second.
- A finished video with a movement starting at a known frame vs one that
  never moves: the onset is found to the frame, and nothing is invented.

    python tests/test_polish.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from polish import anchor as an  # noqa: E402
from polish import layout, parse, probe, recipe, snap, timeline  # noqa: E402

failures: list[str] = []
TMP = Path(tempfile.mkdtemp(prefix="vibecut-polish-"))


def check(name: str, cond: bool, got: str = "") -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{': ' + got if got else ''}")
    if not cond:
        failures.append(name)


def ff(*args: str) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


W, H = 1080, 1920          # a vertical finished edit
LOWER = recipe.Recipe(name="Mine", position="lower_third", size=0.06).check()


def face_clip(path: Path, face: tuple[float, float, float, float]) -> None:
    """A clip with a skin-coloured 'face' block where `face` (normalised x, y, w, h) says."""
    x, y, w, h = face
    ff("-f", "lavfi", "-i", f"color=c=0x303a48:s={W // 4}x{H // 4}:r=30:d=2",
       "-vf", f"drawbox=x={int(x * W / 4)}:y={int(y * H / 4)}:w={int(w * W / 4)}:h={int(h * H / 4)}:color=0xe0ac90:t=fill",
       "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path))


def main() -> int:
    print("words never sit on a face")
    low_face = (0.30, 0.66, 0.40, 0.22)     # a face in the lower third
    top_face = (0.30, 0.10, 0.40, 0.22)     # the same face, at the top
    for name, face in (("low", low_face), ("top", top_face)):
        face_clip(TMP / f"{name}.mp4", face)
    probed = {n: probe.analyse(str(TMP / f"{n}.mp4")) for n in ("low", "top")}
    check("the fixture clips are the frame the caption is laid out on",
          all(p["width"] * 4 == W and p["height"] * 4 == H for p in probed.values()),
          str({n: (p["width"], p["height"]) for n, p in probed.items()}))
    s = layout.safe(W, H, LOWER.margin)
    text = "东京第一天"
    a = layout.place(text, LOWER, W, H, [list(low_face)])
    b = layout.place(text, LOWER, W, H, [list(top_face)])
    fa = layout.faces_px([list(low_face)], W, H)[0]
    check("a lower-third caption over a lower-third face moves", a.moved is not None and a.position != "lower_third",
          f"{a.position}: {a.moved}")
    check("…off the face (on the box that will be drawn)", layout.overlap(a.box, fa) == 0,
          f"box {tuple(round(v) for v in a.box)} vs face {tuple(round(v) for v in fa)}")
    check("…and is still inside the safe area", layout.inside(a.box, s, W, H), str(tuple(round(v) for v in a.box)))
    check("…and says it moved", "face" in (a.moved or ""), a.moved or "")
    check("the same caption with the face at the top stays in the lower third",
          b.moved is None and b.position == "lower_third" and layout.inside(b.box, s, W, H), f"{b.position}")
    check("…with its bottom on the safe line", abs(b.box[1] + b.box[3] - (H - s["b"])) < 1, f"{b.box[1] + b.box[3]:.0f}")
    fc = {f.key: f for f in a.findings}
    check("the checks carry their numbers", fc["caption_face"].value == 0 and fc["caption_face"].verdict == "ok"
          and fc["caption_safe"].verdict == "ok")
    none = layout.place(text, LOWER, W, H, None)
    check("no face detector here: the face check says 'not checked', not 'clear'",
          {f.key: f for f in none.findings}["caption_face"].verdict == "pending")

    print("…through the whole path: click, sentence, layers")
    sess = timeline.Session(placer=lambda st: {c["id"]: layout.place(c["text"], recipe.from_dict(c["recipe"]), W, H,
                                                                        [list(low_face)], c["scale"]).public(W, H)
                                               for c in st["captions"]})
    anc = an.make(21.0, 0.5, 0.8, [0.0, 12.0, 30.0], 30.0, 60.0).public()
    out = parse.parse("这里写上「东京第一天」", anc, sess.state, LOWER.public(), [], [])
    t = sess.add("这里写上「东京第一天」", anc, out["ops"])
    check("one sentence, one caption, in the recipe", len(sess.state["captions"]) == 1
          and sess.state["captions"][0]["recipe"]["name"] == "Mine" and sess.state["captions"][0]["t"] == 21.0)
    check("the turn says it moved off a face", "would have covered a face" in t.lines[0]["text"], t.lines[0]["text"])

    print("no orphan on the last line")
    lone = "我们终于到了东京塔下面啦"
    px = 100.0
    greedy_w = layout.width(lone[:-1], px, 700) + 1       # room for all but the last character
    lines = layout.break_lines(lone, greedy_w, px, 700, 0.0)
    check("the last character doesn't stand alone", len(lines) == 2 and len(lines[-1]) >= 2, str(lines))
    wide = layout.break_lines(lone, layout.width(lone, px, 700) + 1, px, 700, 0.0)
    check("a line that fits isn't broken", wide == [lone], str(wide))
    check("an English widow gets company", not layout.orphan(layout.break_lines(
        "we finally made it to tokyo", layout.width("we finally made it to", 60, 700) + 1, 60, 700, 0)[-1]))

    print("inside the safe area, however big")
    huge = recipe.Recipe(size=0.2, max_lines=2).check()
    long = "今天从早上六点一直走到晚上十一点，脚都快断了但是真的很开心"
    p = layout.place(long, huge, W, H, [])
    check("a big recipe on long words shrinks to fit, inside the safe area",
          layout.inside(p.box, layout.safe(W, H, huge.margin), W, H) and any(f.key == "caption_shrunk" for f in p.findings),
          f"{len(p.lines)} lines at {p.px:.0f}px")

    print("an effect starts on movement or the beat")
    onsets, beats = [21.3], snap.beats(120.0, 0.1, 60)
    t1, why1 = snap.snap(21.0, onsets, beats)
    t2, why2 = snap.snap(40.02, onsets, beats)
    t3, why3 = snap.snap(40.3, onsets, [])
    check("clicked 0.3 s before a movement: starts on it", t1 == 21.3 and "movement" in why1, f"{t1} {why1}")
    check("no movement near: the beat", t2 == 40.1 and "beat" in why2, f"{t2} {why2}")
    check("neither: where clicked, and says so", t3 == 40.3 and "clicked" in why3, why3)
    boom = parse.parse("这里加个 boom", an.make(21.0, 0.5, 0.5, [0.0], 30, 60).public(), timeline.empty(), None, onsets, [])
    check("'这里加个 boom' is one snapped effect", boom["ops"][0]["op"] == "add_effect" and boom["ops"][0]["t"] == 21.3)

    print("reading the finished video")
    mover = TMP / "mover.mp4"
    # still for 1.5 s, then someone walks through (a big bright block, from frame 45), cut at 3.0 s
    ff("-f", "lavfi", "-i", "color=c=0x404040:s=320x180:r=30:d=3", "-f", "lavfi", "-i", "color=c=white:s=90x120:r=30:d=3",
       "-filter_complex", "[0][1]overlay=x='if(lt(t,1.5),10,10+(t-1.5)*140)':y=30", "-c:v", "libx264", "-pix_fmt", "yuv420p",
       str(TMP / "m1.mp4"))
    ff("-f", "lavfi", "-i", "color=c=0x806020:s=320x180:r=30:d=2", "-c:v", "libx264", "-pix_fmt", "yuv420p",
       str(TMP / "m2.mp4"))
    (TMP / "l.txt").write_text(f"file '{TMP / 'm1.mp4'}'\nfile '{TMP / 'm2.mp4'}'\n")
    ff("-f", "concat", "-safe", "0", "-i", str(TMP / "l.txt"), "-c", "copy", str(mover))
    pm = probe.analyse(str(mover))
    check("the cut is found", any(abs(c - 3.0) < 0.05 for c in pm["cuts"]), str(pm["cuts"]))
    check("the movement starts on its frame (1.5 s = frame 45)", any(abs(o - 1.5) <= 1 / 30 + 1e-6 for o in pm["onsets"]),
          str(pm["onsets"]))
    check("…and the cut itself isn't a 'movement'", not any(abs(o - 3.0) < 0.2 for o in pm["onsets"]), str(pm["onsets"]))
    still = probe.analyse(str(TMP / "m2.mp4"))
    check("a still shot has no onsets", still["onsets"] == [], str(still["onsets"]))
    check("no steady pulse: no beat claimed", pm["bpm"] is None)

    print("the anchor is exact")
    a1 = an.make(21.017, 0.25, 1.4, [0.0, 12.0, 30.0], 30.0, 60.0)
    check("time lands on a frame, position inside the picture, the right shot",
          (a1.frame, a1.t, a1.y, a1.shot) == (630, 21.0, 1.0, 1), str(a1))

    print("sentences")
    st = sess.state
    cid = st["captions"][0]["id"]
    at = an.make(22.0, 0.5, 0.8, [0.0], 30, 60).public()
    cases = [("这段字大一点", "edit_caption"), ("make it bigger", "edit_caption"), ("删掉这条字幕", "drop_caption"),
             ("改成「东京第二天」", "edit_caption"), ('write "Day one"', "add_caption"), ("写上 东京塔", "add_caption")]
    for said, op in cases:
        r = parse.parse(said, at, st, LOWER.public(), [], [])
        check(f"'{said}' -> {op}", r.get("ops") and r["ops"][0]["op"] == op and (op == "add_caption" or r["ops"][0]["id"] == cid),
              str(r))
    far = an.make(50.0, 0.5, 0.5, [0.0], 30, 60).public()
    check("'bigger' with nothing there asks, never guesses", "ask" in parse.parse("这段字大一点", far, st, None, [], []))
    check("the words themselves are kept", parse.parse("写上「东京第一天」", at, st, LOWER.public(), [], [])["ops"][0]["text"] == "东京第一天")

    print("recipes")
    book = recipe.Book(TMP / "recipes.json")
    tuned = dict(sess.state["captions"][0])
    tuned["scale"] = 1.2
    r = recipe.from_caption(tuned, "Travel")
    book.save(r)
    check("saving a tuned caption keeps its size as tuned", abs(book.default().size - 0.072) < 1e-6, str(book.default().size))
    book.save(recipe.Recipe(name="Other").check())
    book.use("Travel")
    check("'use my recipe' puts it first", book.default().name == "Travel")
    bad = TMP / "font.txt"
    bad.write_text("x")
    for kw, why in (({"family": "Some Web Font"}, "not a system font"), ({"font_file": str(bad)}, "not a font file"),
                    ({"font_file": str(TMP / 'missing.otf')}, "missing file")):
        try:
            recipe.Recipe(**kw).check()
            check(f"refuses a font that's {why}", False)
        except recipe.RecipeError:
            check(f"refuses a font that's {why}", True)
    real = TMP / "Mine.otf"
    real.write_bytes(b"OTTO")
    check("a font file on the creator's disk is accepted", recipe.Recipe(family="Mine", font_file=str(real)).check().font_file == str(real.resolve()))

    print("undo")
    s2 = timeline.Session()
    t1 = s2.add("a", anc, [{"op": "add_caption", "text": "一", "anchor": anc, "recipe": LOWER.public()}])
    s2.add("b", anc, [{"op": "edit_caption", "id": s2.state["captions"][0]["id"], "scale": 1.2}])
    s2.toggle(t1.id)
    check("undoing the caption skips the edit that needed it", not s2.state["captions"] and s2.turns[1].skipped)
    s2.toggle(t1.id)
    check("redo brings both back, exactly", s2.state["captions"][0]["scale"] == 1.2)

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

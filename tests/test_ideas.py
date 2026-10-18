"""A reel teaches its ideas, not only its rhythm: words, opening, ending.

- text_style: synthetic word events -> share, where, how long, caps, first.
- The Mac's Vision really reads words: a frame drawn with "COFFEE RUN" by
  the caption renderer comes back with those words and a bottom-band box.
  (Skipped with a note where Vision isn't here.)
- opening / ending on a synthetic reference: the last shot's length is the
  one built in; a long still ending reads as still.
- The fingerprint carries them; Make puts words where the reel put them,
  holds them as long, drops the title for a wordless reel, and holds the
  ending as many beats as the reel's last shot.

    python tests/test_ideas.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("VIBECUT_CACHE", tempfile.mkdtemp(prefix="vibecut-ideas-"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

failures: list[str] = []


def check(name: str, cond: bool, got: str = "") -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{': ' + got if got else ''}")
    if not cond:
        failures.append(name)


def main() -> int:
    from cutgrammar import media, style as st
    from web.backend import make, remix, vision

    print("words on screen, from events")
    ev = []
    for i in range(40):                       # 20 s at 2 fps
        t = i / 2
        items = []
        if 1.0 <= t < 4.0 or 10.0 <= t < 13.0:
            items = [{"text": "COFFEE RUN", "box": [0.2, 0.12, 0.6, 0.06], "conf": 0.9}]
        ev.append({"t": t, "items": items})
    w = st.text_style(ev, 20.0)
    check("share, first, band, hold, caps", w["share"] == 0.3 and w["first_s"] == 1.0 and w["band"] == "bottom"
          and abs(w["hold_s"] - 3.0) < 0.6 and w["upper"] == 1.0 and w["cards"] == 2, json.dumps({k: w[k] for k in ("share", "first_s", "band", "hold_s", "upper", "cards")}))
    check("no words at all is said plainly", st.text_style([{"t": 0, "items": []}, {"t": 0.5, "items": []}], 1.0)["share"] == 0.0)
    check("nothing sampled: nothing learnt", st.text_style([], 1.0) is None)

    print("the Mac's Vision reads a frame")
    if vision.ensure_built() is None:
        print("  SKIP  no Vision helper here")
    else:
        d = Path(tempfile.mkdtemp(prefix="vibecut-ocr-"))
        exe = remix.text_tool()
        png = d / "f.png"
        subprocess.run([str(exe), str(png), "540", "960", json.dumps({"lines": [{"text": "COFFEE RUN", "size": 56, "weight": "bold", "y": 780}]})], check=True)
        jpg = d / "f.jpg"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(png), "-vf", "format=yuv420p", "-q:v", "3", str(jpg)], check=True)
        found = vision.text([str(jpg)]).get(str(jpg), [])
        texts = " ".join(i["text"] for i in found).upper()
        check("the words come back", "COFFEE" in texts, texts[:60] or "(nothing)")
        box = found[0]["box"] if found else None
        check("…in the bottom band (origin bottom-left)", bool(box) and (box[1] + box[3] / 2) < 0.33, str(box))

    print("opening and ending, from a synthetic reel")
    from tests.test_style import build
    d2 = Path(tempfile.mkdtemp(prefix="vibecut-ideas-ref-"))
    ref = str(d2 / "ref.mp4")
    build(ref, [0.8, 0.8, 1.0, 0.8, 0.9, 1.0, 4.0])      # quick, then a long last shot
    learnt = st.learn(media.load(ref))
    e, o = learnt["ending"], learnt["opening"]
    check("the last shot's length is the one built in", abs(e["last_s"] - 4.0) < 0.35, str(e["last_s"]))
    check("the first cut is where it was built", abs(o["first_cut_s"] - 0.8) < 0.3, str(o["first_cut_s"]))
    check("words are 'not checked' when no text was read", learnt["words"].get("pending") == ["vision"])
    check("the summary has the new lines", any(l.startswith("ending") for l in st.summary(learnt)) and any(l.startswith("words") for l in st.summary(learnt)))

    print("into the fingerprint and the video")
    styles = [{**learnt, "words": w, "music": {"bpm": 120, "arc": "builds"}}]
    fp = remix.fingerprint(styles)
    check("the fingerprint carries the words and the ending", fp["text"]["band"] == "bottom" and fp["text"]["upper"] and fp["last_s"] == 4.0 and abs(fp["text"]["hold_s"] - 3.0) < 0.6, json.dumps({"text": fp["text"], "last_s": fp["last_s"]}))
    check("the ending holds as many beats as the reel's last shot (capped)", make.end_beats(fp, 0.5) == 4 and make.end_beats({"last_s": 1.1}, 0.5) == 2 and make.end_beats({}, 0.5) == make.END_BEATS)
    from types import SimpleNamespace
    from web.backend import select as sel
    from datetime import datetime
    def pick(sid, score, dur=1.0):
        when = datetime(2026, 9, 22, 8, 35)      # a stop's line is its clock (and a label, when one says something)
        return sel.Pick(SimpleNamespace(id=sid, start=0.0, end=dur, clip_id="c", when=when, labels={}, clip_name="c"), "hero", 0.0, dur, score, "", 0)
    plan = sel.Plan(hook=[pick("h", 0.9, 1.5)], sessions=[[pick("a", 0.5, 2.0), pick("b", 0.8, 2.0)], [pick("c", 0.6, 2.0)]], titles=["Morning", "Noon"])
    fp2 = make.fingerprint("short", "fast", 60.0, styles)
    ops = make.ops(plan, fp2, None, "short", "hype", "A day", set())
    styled = [o for o in ops if o["op"] == "overlay_style"]
    parts = [o for o in ops if o.get("kind") == "part"]
    check("captions go where the reel's words were, in caps", styled and styled[0].get("captions") == "bottom" and styled[0].get("template") == "bold", json.dumps(styled))
    check("…and hold about as long", parts and all(abs(o["dur"] - 3.0) < 0.6 or o["dur"] <= 2.0 for o in parts), str([o["dur"] for o in parts]))
    check("a title, because the reel's words start at the top", any(o.get("kind") == "title" for o in ops))
    silent = [{**learnt, "words": {"share": 0.0, "band": None, "hold_s": None, "upper": None, "first_s": None}, "music": {"bpm": 120, "arc": "builds"}}]
    ops2 = make.ops(plan, make.fingerprint("short", "fast", 60.0, silent), None, "short", "hype", "A day", set())
    check("a wordless reel makes a wordless video", not any(o.get("op") == "add_overlay" for o in ops2), str([o["op"] for o in ops2]))

    print()
    if failures:
        print(f"{len(failures)} failed: {failures}")
        return 1
    print("all passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

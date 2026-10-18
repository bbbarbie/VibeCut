"""Caption templates and entrances on the board.

A template (the Style tab) and an entrance (the Animation tab) dress every
caption in the video: one undoable turn each, said in words, refused when
unknown, kept when the look changes (they were picked by hand), and put
back to the look's own with None. The drawing itself is overlayDraw.ts
(tested in overlayTemplates.test.ts).

    python tests/test_caption_templates.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("VIBECUT_CACHE", str(Path(tempfile.mkdtemp(prefix="vibecut-tpl-")) / "cache"))

from web.backend import board as bd  # noqa: E402
from web.backend import overlays  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_transitions import shot  # noqa: E402

failures: list[str] = []


def check(name: str, cond: bool, got: str = "") -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{': ' + got if got else ''}")
    if not cond:
        failures.append(name)


def main() -> int:
    cat = bd.Catalog.from_clips([shot("A"), shot("B")])
    option = {"key": "o", "name": "Two", "summary": "", "beats": [{"title": "All", "detail": "", "shots": [
        {"id": "A:0", "start": 2.0, "end": 4.0}, {"id": "B:0", "start": 2.0, "end": 4.0}]}]}
    mk = lambda d: {"options": [option]}  # noqa: E731
    s = bd.Session()
    s.add({"kind": "chat", "text": "go", "ops": [], "direction": {"text": "go"}}, cat, mk)
    s.add({"kind": "direct", "text": "pick", "ops": [{"op": "choose_option", "option": "o"}]}, cat, mk)
    s.add({"kind": "direct", "text": "look", "ops": [{"op": "set_look", "look": "cozy"}]}, cat, mk)

    def do(**kw):
        return s.add({"kind": "direct", "text": "style", "ops": [{"op": "overlay_style", **kw}]}, cat, mk)

    t = do(template="outlined")
    st = overlays.style_of(s.board)
    check("the template is the video's caption style", st.get("template") == "outlined", str(st.get("template")))
    check("…said in words", any("Outlined" in ln["text"] for ln in t.lines), str(t.lines))
    e = do(enter="stamp")
    check("an entrance too", overlays.style_of(s.board).get("enter") == "stamp")
    check("…said in words", any("Stamp" in ln["text"] for ln in e.lines), str(e.lines))
    s.add({"kind": "direct", "text": "look", "ops": [{"op": "set_look", "look": "hype"}]}, cat, mk)
    st = overlays.style_of(s.board)
    check("a new look keeps what was picked by hand", st.get("template") == "outlined" and st.get("enter") == "stamp"
          and st.get("look") == "hype", str(st))
    s.toggle(e.id, cat, mk)
    check("undo takes the entrance away", not overlays.style_of(s.board).get("enter"))
    back = do(template=None)
    check("None: back to the look's own", not overlays.style_of(s.board).get("template"), str(back.lines))
    for bad in ({"template": "comic-sans"}, {"enter": "explode"}):
        t = do(**bad)
        check(f"refuses {bad}", bool(t.skipped), str(t.skipped))
    c = do(text_color="#FFD84D")
    check("a picked caption colour is the video's", overlays.style_of(s.board).get("text_color") == "#ffd84d", str(c.lines))
    s.add({"kind": "direct", "text": "look", "ops": [{"op": "set_look", "look": "hype"}]}, cat, mk)
    check("a new look keeps the picked colour", overlays.style_of(s.board).get("text_color") == "#ffd84d")
    do(text_color=None)
    check("None: back to automatic", not overlays.style_of(s.board).get("text_color"))
    check("refuses a colour that isn't one", bool(do(text_color="yellow").skipped))
    f = do(typeface="bebas-neue")
    check("a picked font is the video's, said in words", overlays.style_of(s.board).get("typeface") == "bebas-neue"
          and any("Bebas Neue" in ln["text"] for ln in f.lines), str(f.lines))
    s.add({"kind": "direct", "text": "look", "ops": [{"op": "set_look", "look": "cozy"}]}, cat, mk)
    check("a new look keeps the picked font", overlays.style_of(s.board).get("typeface") == "bebas-neue")
    do(typeface=None)
    check("None: back to the style's own font", not overlays.style_of(s.board).get("typeface"))
    check("refuses a font that isn't shipped", bool(do(typeface="comic-sans").skipped))
    d = do(outline={"color": "#FF0000", "width": 0.2}, shadow={"color": "#000000", "opacity": 0.5, "blur": 0.4, "dist": 0.1})
    st = overlays.style_of(s.board)
    check("outline and shadow are the video's, said in words", st.get("outline") == {"color": "#ff0000", "width": 0.2}
          and st.get("shadow", {}).get("opacity") == 0.5 and any("outline and shadow" in ln["text"] for ln in d.lines), str(d.lines))
    do(backdrop={"color": "#000000", "opacity": 0.8, "round": 0.25}, thick=0.06)
    check("background and boldness kept", overlays.style_of(s.board).get("backdrop", {}).get("opacity") == 0.8
          and overlays.style_of(s.board).get("thick") == 0.06)
    s.add({"kind": "direct", "text": "look", "ops": [{"op": "set_look", "look": "hype"}]}, cat, mk)
    check("a new look keeps them", overlays.style_of(s.board).get("outline", {}).get("width") == 0.2)
    do(outline=None, shadow=None, backdrop=None, thick=None)
    check("None: back to the style's own", not any(overlays.style_of(s.board).get(k) for k in ("outline", "shadow", "backdrop", "thick")))
    for bad in ({"outline": {"color": "#000000", "width": 2}}, {"shadow": {"color": "red", "opacity": 1, "blur": 0, "dist": 0}},
                {"backdrop": {"color": "#000000", "opacity": 0.5}}, {"thick": 1}):
        check(f"refuses {bad}", bool(do(**bad).skipped))
    check("every template has a name", set(overlays.TEMPLATES) == {"outlined", "bold", "label", "highlight", "handwritten",
                                                                     "tape", "pop", "quiet", "neon", "glow", "gradient",
                                                                     "extrude", "retro"})
    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

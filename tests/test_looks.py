"""A look changes the words' whole surface -- and never a choice made by hand.

- Every look is a complete, dated record the renderer can draw.
- Two boards that differ only in one hand-set field (the font) must, after
  the same set_look, differ only in that field: the look fills in the rest,
  the hand-set font survives and is reported, and "use the look's" resets
  exactly it. Undo takes the look back off.
- Beat lock moves a word onto the beat only when it was already close, and
  keeps its length; far-off words stay where they were.

    python tests/test_looks.py
"""

from __future__ import annotations

import os
import re
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web.backend import board as bd  # noqa: E402
from web.backend import llm, looks, overlays  # noqa: E402

failures: list[str] = []


def check(name: str, cond: bool, got: str = "") -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{': ' + got if got else ''}")
    if not cond:
        failures.append(name)


HEX = re.compile(r"^#[0-9a-f]{6}$")
SNAP = {"option": "t", "name": "n", "structure": "", "beats": [
    {"id": "t1", "title": "Morning", "detail": "", "shots": [{"id": "a:0", "start": 0.0, "end": 6.0}]}]}


def session(hand_font: str | None) -> bd.Session:
    s = bd.Session()
    cat = bd.Catalog({}, {})
    s.add({"kind": "direct", "text": "use", "ops": [{"op": "choose_option", "option": "t", "snapshot": SNAP}]},
          cat, lambda d: None)
    if hand_font:
        s.add({"kind": "direct", "text": "font", "ops": [{"op": "overlay_style", "font": hand_font}]}, cat, lambda d: None)
    return s


def main() -> int:
    print("the records")
    recs = looks.all_looks()
    check("the spec's seven looks", sorted(recs) == ["cinematic", "clean", "cozy", "film", "hype", "playful", "quiet"],
          str(sorted(recs)))
    for r in recs.values():
        t, m = r["type"], r["motion"]
        ok = (t["font"] in overlays.FONTS and t["backing"] in overlays.BACKINGS and len(t["palette"]) == 3
              and all(HEX.match(c) for c in t["palette"]) and len(m["curve"]) == 4 and 0.1 <= m["in_s"] <= 2.0
              and m["step_fps"] >= 0 and t["case"] in ("sentence", "lower", "upper")
              and set(m["measured"]) <= set(m) and date.fromisoformat(r["review_by"]) > date(2026, 9, 1)
              and r["status"] in ("prior", "calibrated"))
        check(f"{r['id']}: complete, drawable, dated", ok)
    check("chat can ask for any of them", set(llm.SCHEMA["properties"]["ops"]["items"]["properties"]["look"]["anyOf"][0]["enum"])
          == set(recs) and "set_look" in bd.LLM_OPS)

    print("set_look keeps what was set by hand")
    cat = bd.Catalog({}, {})
    mk = lambda d: None  # noqa: E731
    plain, hand = session(None), session("Rounded")
    for s in (plain, hand):
        s.add({"kind": "chat", "text": "make it cozy", "ops": [{"op": "set_look", "look": "cozy"}]}, cat, mk)
    sp, sh = overlays.style_of(plain.board), overlays.style_of(hand.board)
    cozy = recs["cozy"]
    check("the look fills in font, colour, backing", sp["font"] == "Editorial" and sp["color"] == cozy["type"]["palette"][0]
          and sp["backing"] == "none", str({k: sp[k] for k in ("font", "color", "backing")}))
    check("…and brings its motion", sp["motion"]["step_fps"] == 12 and sp["motion"]["enter"] == "card")
    diff = {k for k in sp if sp[k] != sh[k]}
    check("a hand-set font survives the look, and only it differs", diff == {"font"} and sh["font"] == "Rounded", str(diff))
    check("…and is reported as differing", looks.overrides(hand.board) == ["font"] and looks.overrides(plain.board) == [],
          f"{looks.overrides(hand.board)} / {looks.overrides(plain.board)}")
    check("the turn says what it kept", "kept your font" in hand.turns[-1].lines[0]["text"], hand.turns[-1].lines[0]["text"])
    hand.add({"kind": "direct", "text": "reset", "ops": [{"op": "set_look", "look": "cozy", "reset": True}]}, cat, mk)
    check("'use the look's' resets exactly that", overlays.style_of(hand.board)["font"] == "Editorial"
          and looks.overrides(hand.board) == [])
    prof = session(None)
    prof.add({"kind": "direct", "text": "titles", "ops": [{"op": "overlay_style", "font": "Mono", "source": "profile"}]}, cat, mk)
    prof.add({"kind": "direct", "text": "look", "ops": [{"op": "set_look", "look": "hype"}]}, cat, mk)
    check("the profile's saved font is a default, not a choice: the look replaces it",
          overlays.style_of(prof.board)["font"] == recs["hype"]["type"]["font"] and looks.overrides(prof.board) == [])
    t = plain.turns[-1]
    plain.toggle(t.id, cat, mk)
    check("undo takes the look off", "look" not in overlays.style_of(plain.board)
          and overlays.style_of(plain.board)["font"] == overlays.DEFAULT_STYLE["font"])
    bad = plain.add({"kind": "direct", "text": "x", "ops": [{"op": "set_look", "look": "neon"}]}, cat, mk)
    check("an unknown look is refused, not guessed", bool(bad.skipped), str(bad.skipped))
    check("no look: the style is exactly as before", overlays.style_of(session("Mono").board)
          == {**overlays.DEFAULT_STYLE, "font": "Mono"})

    print("beat lock")
    grid = {"bpm": 60.0, "phase": 0.0}
    items = [{"id": "o1", "kind": "title", "start": 1.1, "end": 3.1, "shown_end": 3.1},
             {"id": "o2", "kind": "caption", "start": 2.5, "end": 4.0, "shown_end": 4.0},
             {"id": "o3", "kind": "end", "start": 8.9, "end": 10.0, "shown_end": 10.0},
             {"id": "c", "kind": "chapters", "start": 0.0, "end": 10.0, "shown_end": 10.0}]
    out = {o["id"]: o for o in looks.beat_lock(items, grid, 10.0)}
    check("a word 0.1 s off lands on the beat, same length", (out["o1"]["start"], out["o1"]["end"]) == (1.0, 3.0),
          f"{out['o1']['start']}–{out['o1']['end']}")
    check("a word half a beat off stays put", out["o2"]["start"] == 2.5)
    check("a word that would run past the end stays put", out["o3"]["start"] == 8.9)
    check("the chapter bar is never moved", out["c"] == items[3])
    check("no steady beat, nothing moves", looks.beat_lock(items, None, 10.0) == items)
    check("only the loud looks lock to the beat",
          {k for k, r in recs.items() if r["motion"]["beat_lock"]} == {"playful", "hype"})

    print("the picture: a grade fitted to the footage")
    import tempfile
    os.environ.setdefault("VIBECUT_CACHE", tempfile.mkdtemp(prefix="vibecut-looks-"))
    import numpy as np
    from cutgrammar import grade
    # A neutral, mid-contrast frame: a grey ramp with a few coloured patches,
    # so warmth, black level, saturation and contrast all have room to move.
    rng = np.random.default_rng(3)
    img = np.zeros((27, 48, 3), np.uint8)
    img[..., :] = np.linspace(8, 230, 48, dtype=np.uint8)[None, :, None]
    img[3:13, 3:18] = (200, 80, 60)
    img[14:24, 24:44] = (50, 110, 190)
    img[5:10, 30:40] = (90, 170, 80)
    img = np.clip(img.astype(int) + rng.integers(-6, 7, img.shape), 0, 255).astype(np.uint8)
    px = grade.pixels(img[None])
    before = grade.stats(px)

    def after(lid: str) -> dict | None:
        fit = looks.fit_grade(recs[lid], px)
        if fit is None:
            return None
        lut = grade.Look(px, looks.grade_target(before, recs[lid]["grade"]), 1.0).lut()
        return grade.stats(grade.pixels(grade.apply_lut(img, lut)[None]))
    check("Clean has no grade", looks.fit_grade(recs["clean"], px) is None)
    cozy, hype, quiet, cine = after("cozy"), after("hype"), after("quiet"), after("cinematic")
    check("Cozy: warmer, lifted blacks, a little less colour",
          cozy["warmth"] > before["warmth"] + 3 and cozy["black"] > before["black"] + 6 and cozy["sat"] < before["sat"],
          f"warmth {before['warmth']}->{cozy['warmth']}, black {before['black']}->{cozy['black']}, sat {before['sat']}->{cozy['sat']}")
    check("Hype: more colour, more contrast, blacks kept deep",
          hype["sat"] > before["sat"] * 1.05 and hype["contrast"] > before["contrast"] * 1.05 and hype["black"] <= before["black"] + 2,
          f"sat {before['sat']}->{hype['sat']}, contrast {before['contrast']}->{hype['contrast']}, black {before['black']}->{hype['black']}")
    check("Quiet: muted and cooler", quiet["sat"] < cozy["sat"] and quiet["warmth"] < before["warmth"],
          f"sat {quiet['sat']} vs cozy {cozy['sat']}, warmth {before['warmth']}->{quiet['warmth']}")
    split = np.asarray(cine["high"]) - np.asarray(cine["shadow"])
    split0 = np.asarray(before["high"]) - np.asarray(before["shadow"])
    check("Cinematic: warm highlights over cool shadows, more than the footage had",
          (split[0] - split[2]) > (split0[0] - split0[2]) + 6, f"{split0[0] - split0[2]:.1f} -> {split[0] - split[2]:.1f}")
    check("the same look on the same pixels fits once (cached .cube)",
          looks.fit_grade(recs["cozy"], px)["lut"] == looks.fit_grade(recs["cozy"], px)["lut"])
    check("every shift stays inside grade.py's cap",
          all(abs(c) <= grade.MAX_SHIFT + 0.5 for st in (cozy, hype, quiet, cine) for c in np.asarray(st["cast"]) - np.asarray(before["cast"])))

    print("the picture: joins, and what wins")
    check("film dissolves between parts, cozy and hype swipe, clean cuts",
          looks.joins_of(recs["film"])["between"] == "dissolve" and looks.joins_of(recs["cozy"])["between"] == "swipe"
          and looks.joins_of(recs["hype"])["between"] == "swipe" and looks.joins_of(recs["clean"])["between"] == "cut"
          and looks.joins_of(recs["cozy"])["within"] == "cut")
    plain = looks.picture({"look": "cozy"}, None)
    check("a look alone gives the board its joins and promises the grade",
          plain["transitions"]["between"] == "swipe" and plain["look"]["pending"] and plain["name"] == "Cozy", str(plain))
    borrowed = {"ref": "r", "name": "Ref", "traits": ["look", "transitions"],
                "transitions": {"between": "flash", "within": "cut", "dur": 0.2, "open": False, "close": False},
                "look": {"lut": "/x.cube", "strength": 1.0, "words": []}, "letterbox": None, "report": None}
    kept = looks.picture({"look": "cozy", "style": borrowed}, px)
    check("a borrowed style's own look and joins win over the look's",
          kept["transitions"]["between"] == "flash" and kept["look"]["lut"] == "/x.cube")
    half = looks.picture({"look": "cozy", "style": {**borrowed, "look": None, "traits": ["transitions"]}}, px)
    check("…and the look fills in only what the borrowed style left empty",
          half["transitions"]["between"] == "flash" and half["look"] and half["look"]["lut"].endswith(".cube"), str(half.get("look")))
    check("no look, no style: nothing", looks.picture({}, px) is None)
    items = [{"kind": "shot", "shot_id": "a:0"}, {"kind": "shot", "shot_id": "a:1"}, {"kind": "gap"}, {"kind": "shot", "shot_id": "b:0"}]
    board = {"look": "hype", "beats": [{"shots": [{"id": "a:0"}, {"id": "a:1"}]}, {"shots": [{"id": "b:0"}]}]}
    pushed = looks.camera(items, board)
    check("Hype pushes into every shot, alternating, harder on a part's first shot",
          [it.get("punch") for it in pushed] == [0.05, -0.05, None, 0.09], str([it.get("punch") for it in pushed]))
    check("Cozy leaves the camera alone", looks.camera(items, {**board, "look": "cozy"}) == items)

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""The creator's caption recipe: the same style, one click, every time.

From the interviews, in the creator's words: "every time I click a saved
recipe, the fancy text, font, size and position are all there at once,
because mine are always the same." So a recipe is a flat, dated record of
exactly those settings, saved *from* a caption they already tuned (not
filled in on a form) and applied to new captions by default.

Fonts: only fonts already on the creator's machine -- a system family, or a
font file they point at. Nothing is bundled or shipped, and a font named in
a reference image is not a font we may render (see CLAUDE.md).
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

POSITIONS = ("lower_third", "center", "follow_speaker")
ENTERS = ("fade", "rise", "pop", "none")
FONT_FILE_EXT = (".ttf", ".otf", ".ttc", ".woff", ".woff2")
# Families macOS ships; the browser resolves them locally, nothing is sent.
SYSTEM_FAMILIES = ("PingFang SC", "Hiragino Sans GB", "Songti SC", "Kaiti SC", "Heiti SC",
                   "Helvetica Neue", "Avenir Next", "Futura", "Georgia", "Menlo", "system-ui")


class RecipeError(ValueError):
    pass


def _hex(v: object) -> str:
    if isinstance(v, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", v):
        return v.lower()
    raise RecipeError(f"a colour like #ffcc00, not {v!r}")


@dataclass
class Recipe:
    name: str = "My captions"
    family: str = "PingFang SC"        # a system family, or the family name of `font_file`
    font_file: str | None = None       # a font file on the creator's own disk
    size: float = 0.055                # text height, as a share of the frame's shorter side
    weight: int = 700
    color: str = "#ffffff"
    stroke_color: str | None = "#000000"
    stroke_width: float = 0.12         # in ems; 0 = none
    position: str = "lower_third"
    enter: str = "fade"
    enter_s: float = 0.25
    margin: float = 0.06               # the least room kept to every edge, share of the frame
    hold_s: float = 3.0
    max_lines: int = 2
    saved: float = field(default_factory=time.time)

    def check(self) -> "Recipe":
        self.name = (self.name or "").strip()[:40] or "My captions"
        if self.font_file:
            p = Path(self.font_file).expanduser()
            if p.suffix.lower() not in FONT_FILE_EXT:
                raise RecipeError("a font file is .ttf, .otf, .ttc, .woff or .woff2")
            if not p.is_file():
                raise RecipeError(f"no font file at {p}")
            self.font_file = str(p.resolve())
            self.family = self.family or p.stem
        elif self.family not in SYSTEM_FAMILIES:
            raise RecipeError(f"use a font on this Mac ({', '.join(SYSTEM_FAMILIES[:5])}, …) or point at a font file")
        if not 0.02 <= float(self.size) <= 0.2:
            raise RecipeError("size is between 2% and 20% of the frame")
        self.size = round(float(self.size), 4)
        if int(self.weight) not in range(100, 1000, 100):
            raise RecipeError("weight is 100–900")
        self.weight = int(self.weight)
        self.color = _hex(self.color)
        self.stroke_color = _hex(self.stroke_color) if self.stroke_color else None
        self.stroke_width = round(min(max(float(self.stroke_width), 0.0), 0.4), 3)
        if self.position not in POSITIONS:
            raise RecipeError(f"position is one of {', '.join(POSITIONS)}")
        if self.enter not in ENTERS:
            raise RecipeError(f"entrance is one of {', '.join(ENTERS)}")
        self.enter_s = round(min(max(float(self.enter_s), 0.0), 1.5), 3)
        self.margin = round(min(max(float(self.margin), 0.02), 0.2), 3)
        self.hold_s = round(min(max(float(self.hold_s), 0.5), 20.0), 2)
        self.max_lines = int(min(max(int(self.max_lines), 1), 4))
        return self

    def public(self) -> dict:
        return asdict(self)


def from_dict(d: dict) -> Recipe:
    known = {k: d[k] for k in Recipe.__dataclass_fields__ if k in d}
    return Recipe(**known).check()


def from_caption(caption: dict, name: str | None = None) -> Recipe:
    """'Save this caption as my recipe': its style as it looks now,
    including a size the creator has scaled by hand."""
    r = dict(caption["recipe"])
    r["size"] = round(float(r["size"]) * float(caption.get("scale", 1.0)), 4)
    if name:
        r["name"] = name
    r["saved"] = time.time()
    return from_dict(r)


class Book:
    """The creator's recipes on disk; the first is the one new captions use."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> list[Recipe]:
        try:
            data = json.loads(self.path.read_text())
        except (OSError, ValueError):
            return []
        out = []
        for d in data.get("recipes", []):
            try:
                out.append(from_dict(d))
            except (RecipeError, TypeError):
                continue    # a font file that moved: leave it out rather than guess
        return out

    def default(self) -> Recipe | None:
        rs = self.load()
        return rs[0] if rs else None

    def save(self, r: Recipe) -> list[Recipe]:
        """Keep `r` first (the default); a recipe of the same name is replaced."""
        rs = [x for x in self.load() if x.name != r.name]
        rs.insert(0, r.check())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"schema": "vibecut-recipes/1", "recipes": [x.public() for x in rs]},
                                  ensure_ascii=False, indent=2))
        os.replace(tmp, self.path)
        return rs

    def use(self, name: str) -> list[Recipe]:
        rs = self.load()
        hit = next((x for x in rs if x.name == name), None)
        if hit is None:
            raise RecipeError(f"no recipe called {name!r}")
        return self.save(hit)

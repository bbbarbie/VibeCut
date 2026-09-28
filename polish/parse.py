"""One sentence at an anchor -> operations on the layers.

The sentences creators actually say at a point are few and short, so they
are read by rules first -- no model, no key, no round trip -- and a model
is only asked (by the web layer) when no rule matches. Rules never guess:
"make it bigger" with no caption at the anchor is a question back, not a
bigger something-else.

"This" / "这段" / "这条" means the caption on screen at the anchor's time;
if none is, the nearest within NEAR_S; else there is nothing to act on.
"""

from __future__ import annotations

import re

from . import snap as sn

NEAR_S = 2.0
BIGGER, SMALLER = 1.2, 1 / 1.2

QUOTED = r"[「“\"'『《](.+?)[」”\"'』》]"
WRITE = re.compile(r"(?:这里|此处|这儿)?\s*(?:写上|写着|写|打上|加上|加|放上|放)\s*(?:字幕|文字|一行字|一句)?\s*[:：]?\s*"
                   + r"(?:" + QUOTED + r"|(.+))$")
WRITE_EN = re.compile(r"^(?:write|add text|put|caption|title|type)\s*[:：]?\s*(?:" + QUOTED + r"|(.+))$", re.I)
BOOM = re.compile(r"boom|砰|嘭|轰|特效|震一下|punch|impact", re.I)
BIG = re.compile(r"大一点|大点|放大|大一些|再大|bigger|larger|bigger text", re.I)
SMALL = re.compile(r"小一点|小点|缩小|小一些|再小|smaller", re.I)
DROP = re.compile(r"删掉|删除|去掉|不要了|拿掉|remove|delete|get rid", re.I)
SAVE_RECIPE = re.compile(r"存成配方|存为配方|保存.*配方|记住.*样式|save.*recipe|save (?:this|it) as", re.I)
USE_RECIPE = re.compile(r"用我的配方|套用.*配方|套配方|用配方|use my recipe|apply my recipe", re.I)
CHANGE = re.compile(r"(?:改成|换成|改为)\s*(?:" + QUOTED + r"|(.+))$|change (?:it|the text|this) to\s*(?:" + QUOTED + r"|(.+))$", re.I)


def _first(m: re.Match) -> str:
    return next((g for g in m.groups() if g), "").strip().strip("。.!！")


def caption_at(state: dict, t: float) -> dict | None:
    on = [c for c in state["captions"] if c["t"] - 1e-6 <= t <= c["t"] + c["dur"]]
    if on:
        return on[-1]
    near = [c for c in state["captions"] if min(abs(c["t"] - t), abs(c["t"] + c["dur"] - t)) <= NEAR_S]
    return min(near, key=lambda c: min(abs(c["t"] - t), abs(c["t"] + c["dur"] - t))) if near else None


def effect_at(state: dict, t: float) -> dict | None:
    near = [e for e in state["effects"] if abs(e["t"] - t) <= NEAR_S]
    return min(near, key=lambda e: abs(e["t"] - t)) if near else None


def parse(said: str, anchor: dict, state: dict, recipe: dict | None, onsets: list[float],
          beats: list[float]) -> dict:
    """-> {"ops": [...], "reply": str} | {"action": "save_recipe", "id": ...} | {"ask": str} | {"none": True}"""
    text = (said or "").strip()
    t = float(anchor["t"])
    here = caption_at(state, t)

    if SAVE_RECIPE.search(text):
        if not here:
            return {"ask": "Which caption? Click on one, then say it again."}
        return {"action": "save_recipe", "id": here["id"]}
    if USE_RECIPE.search(text):
        if not recipe:
            return {"ask": "You haven't saved a recipe yet — tune a caption, then say “save this as my recipe”."}
        if not here:
            return {"ask": "There's no caption here to restyle — click on one."}
        return {"ops": [{"op": "edit_caption", "id": here["id"], "recipe": recipe}], "reply": ""}
    if DROP.search(text):
        if BOOM.search(text):
            e = effect_at(state, t)
            return {"ops": [{"op": "drop_effect", "id": e["id"]}]} if e else {"ask": "There's no boom near here."}
        if not here:
            return {"ask": "There's no caption here to remove."}
        return {"ops": [{"op": "drop_caption", "id": here["id"]}]}
    if BOOM.search(text):
        at, why = sn.snap(t, onsets, beats)
        return {"ops": [{"op": "add_effect", "kind": "boom", "anchor": anchor, "t": at, "why": why}]}
    if BIG.search(text) or SMALL.search(text):
        if not here:
            return {"ask": "There are no words here to resize — click on a caption."}
        return {"ops": [{"op": "edit_caption", "id": here["id"], "scale": BIGGER if BIG.search(text) else SMALLER}]}
    m = CHANGE.search(text)
    if m and here:
        return {"ops": [{"op": "edit_caption", "id": here["id"], "text": _first(m)}]}
    m = WRITE.search(text) or WRITE_EN.search(text)
    if m and _first(m):
        if not recipe:
            return {"ask": "No style yet — pick one in Recipe first."}
        return {"ops": [{"op": "add_caption", "text": _first(m), "anchor": anchor, "recipe": recipe}]}
    return {"none": True}

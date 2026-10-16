"""Transitions the creator picks: one join, or every cut at once.

A look already brings a join family (looks/*.json `joins`: cut inside a
part, a dissolve or dip between parts). These are the creator's own picks
on top of it, made by clicking the dot between two shots: that one join, or
"Use for every cut". Cut stays the default, so nothing changes until a
choice is made (sarah, 2026-10-14: stylistic effects are opt-in).

Picks live on the board -- `picture_joins` (by the outgoing shot's entry key,
like set_join's sound) and `picture_all` -- so they are undone, replayed and
saved like every other edit. They are folded into the rendering style's
`transitions` policy (`fold`), which export.plan_transitions reads for the
preview and the file alike: what plays is what's exported.

Five of the kinds blend the two shots (an xfade over footage past the cut,
like a dissolve); a shot not filmed long enough past the cut falls back to a
plain cut and the export says so. Dip and flash fade inside the shots' own
frames and always fit.
"""

from __future__ import annotations

# kind -> what it's called, and the ffmpeg xfade it renders with (None = a
# fade inside each shot's own frames, or a cut)
KINDS: dict[str, dict] = {
    "cut":        {"name": "Cut",          "xfade": None},
    "dissolve":   {"name": "Fade",         "xfade": "fade"},
    "dip_black":  {"name": "Dip to black", "xfade": None},
    "flash":      {"name": "Flash",        "xfade": None},
    "zoom":       {"name": "Zoom through", "xfade": "zoomin"},
    "slide_up":   {"name": "Slide up",     "xfade": "slideup"},
    "blur":       {"name": "Blur",         "xfade": "hblur"},
    "light_leak": {"name": "Light leak",   "xfade": "custom"},
    # a whip between two stops of the day: slides sideways, smeared over the
    # middle of the move (export.SWIPE_BLUR); cozy and hype join parts with it
    "swipe":      {"name": "Swipe",        "xfade": "slideleft"},
}
BLENDS = {k for k, v in KINDS.items() if v["xfade"]}
DUR_DEFAULT = 0.5     # seconds the join takes [prior]
DUR_MIN, DUR_MAX = 0.2, 1.5

# A warm glow that sweeps across the cut while one shot gives way to the
# next, the way light leaks on film (yuv planes: lift Y, push V up and U
# down). xfade's P runs 1 -> 0 over the transition; A is the outgoing shot.
LIGHT_LEAK = ("st(0,A*P+B*(1-P));"
              "st(1,sin(PI*P)*exp(-(pow(X/W-(1.4*(1-P)-0.2),2)+pow(Y/H-0.4,2))*4));"
              "if(eq(PLANE,0),ld(0)+ld(1)*(235-ld(0))*0.85,"
              "if(eq(PLANE,1),ld(0)-ld(1)*40,ld(0)+ld(1)*45))")


class TransitionError(Exception):
    pass


def _dur(op: dict) -> float:
    d = op.get("dur")
    if d is None:
        return DUR_DEFAULT
    try:
        d = float(d)
    except (TypeError, ValueError) as e:
        raise TransitionError("a transition's length is a number of seconds") from e
    return round(max(DUR_MIN, min(DUR_MAX, d)), 2)


def apply(b: dict, op: dict, where) -> None:
    """set_transition {shot | all, kind, dur?}. kind "auto" = back to what
    the look does there. `where(key)` raises if the shot isn't in the edit."""
    kind = op.get("kind")
    if kind != "auto" and kind not in KINDS:
        raise TransitionError(f"a transition is one of {', '.join(KINDS)}, not {kind!r}")
    pick = None if kind == "auto" else {"kind": kind, "dur": _dur(op)}
    if op.get("all"):
        # every cut: one choice for the video, and the single-join picks go
        if pick:
            b["picture_all"] = pick
        else:
            b.pop("picture_all", None)
        b.pop("picture_joins", None)
        return
    k = op.get("shot")
    where(k)
    joins = dict(b.get("picture_joins") or {})
    if pick:
        joins[k] = pick
    else:
        joins.pop(k, None)
    if joins:
        b["picture_joins"] = joins
    else:
        b.pop("picture_joins", None)


def fold(b: dict | None, style: dict | None) -> dict | None:
    """The rendering style with the creator's picks in its transitions
    policy: `picture_all` replaces the look's between/within, and each
    single pick goes in `at` (outgoing entry key -> {kind, dur})."""
    b = b or {}
    every, one = b.get("picture_all"), b.get("picture_joins")
    if not every and not one:
        return style
    style = dict(style or {})
    pol = dict(style.get("transitions") or {"between": "cut", "within": "cut", "dur": DUR_DEFAULT,
                                            "open": False, "close": False})
    if every:
        pol.update(between=every["kind"], within=every["kind"], dur=every["dur"])
    if one:
        pol["at"] = {k: dict(v) for k, v in one.items()}
    style["transitions"] = pol
    style.setdefault("name", "plain")
    style.setdefault("traits", [])
    style.setdefault("ref", None)
    return style


def describe(a: dict | None, b: dict | None) -> list[dict]:
    if a is None or b is None:
        return []
    out = []
    ea, eb = a.get("picture_all"), b.get("picture_all")
    if ea != eb:
        out.append({"kind": "style", "text": f"Every cut is now a {KINDS[eb['kind']]['name'].lower()}" if eb
                    else "Cuts are back to what the look does"})
    ja, jb = a.get("picture_joins") or {}, b.get("picture_joins") or {}
    changed = [k for k in sorted(set(ja) | set(jb)) if ja.get(k) != jb.get(k)]
    if changed and not (eb and not jb and ea != eb):
        for k in changed:
            out.append({"kind": "style", "shot": k,
                        "text": f"A {KINDS[jb[k]['kind']]['name'].lower()} at one cut" if k in jb
                        else "One cut is back to what the look does"})
    return out

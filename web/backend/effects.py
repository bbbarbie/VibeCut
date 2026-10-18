"""Video effects the creator puts on a shot: the ones short-form edits use
most (CapCut, TikTok, Reels; sarah, 2026-10-18: "i want the popular ones to
all be in our app").

Opt-in like the transitions: a shot has none until one is picked in the
Effects tab, and it stays on the shot (board.set_shot `effect`, with
`effect_amount` from the Strength slider), through cuts and undo.

Each effect is a function of the time into the shot, so the preview
(frontend effectView.ts, the same numbers) and the export (`chain`, an
ffmpeg filter chain run on the shot after it is fitted to the frame) show
the same thing at the same moment. Everything is drawn from the footage
itself -- shaking, zooming, blurring, tinting the frames that were filmed --
so nothing generated reaches the viewer (CLAUDE.md non-goals). All sizes,
speeds and strengths are priors.
"""

from __future__ import annotations

# id -> name, in the order the tiles show them
KINDS: dict[str, str] = {
    "shake": "Shake",
    "zoom_in": "Zoom in",
    "zoom_out": "Zoom out",
    "pulse": "Pulse",
    "flash": "Flash",
    "strobe": "Strobe",
    "blur_in": "Blur in",
    "glow": "Glow",
    "vhs": "VHS",
    "glitch": "Glitch",
    "grain": "Film grain",
    "old_film": "Old film",
    "vignette": "Vignette",
    "disco": "Disco",
}
AMOUNT = (0.25, 2.0)   # the Strength slider, 25%..200%

# [priors] -- the same numbers are in effectView.ts
SHAKE = 0.06        # share of the frame the shake may wander at 100%
GLITCH = 0.08       # how far a glitch jump throws the picture
GLITCH_RATE = 8     # chances to jump per second
ZOOM = 0.15         # how far Zoom in / out travel over the shot
PULSE = 0.07        # how far each pulse pushes in
PULSE_EVERY = 0.5   # s between pulses (120 bpm)
FLASH_S = 0.4       # the white flash at the start of the shot
STROBE_HZ = 6
BLUR_IN_S = 0.7     # how long the shot takes to come into focus
BLUR = 0.02         # blur radius as a share of the frame width
GLOW = 0.025        # glow spread as a share of the frame width
SPLIT = 0.004       # VHS / glitch colour split as a share of the frame width
HUE_SPEED = 120     # Disco: degrees of hue a second


def clamp_amount(a) -> float:
    return round(max(AMOUNT[0], min(AMOUNT[1], float(a))), 2)


def _split_px(w: int, a: float, k: float = 1.0) -> int:
    return max(1, round(w * SPLIT * a * k))


def chain(kind: str | None, amount: float, size: dict, head_s: float, frames: int, fps: int) -> str:
    """The ffmpeg filters for one shot's effect, starting with a comma, or ''.

    `head_s` is how much footage before the cut the rendered piece starts
    with (a dissolve's handle), so time into the shot is t - head_s.
    `frames` is the shot's own length in frames."""
    if not kind or kind not in KINDS:
        return ""
    a = clamp_amount(amount)
    w, h = size["w"], size["h"]
    H = f"{head_s:.4f}"
    u = f"(t-{H})"
    U = f"(T-{H})"
    d = max(frames, 1) / fps

    def white(k: str, tag: str) -> str:
        return (f",split[{tag}a][{tag}b];[{tag}b]drawbox=x=0:y=0:w=iw:h=ih:color=white:t=fill[{tag}w];"
                f"[{tag}a][{tag}w]blend=all_expr='A+(B-A)*({k})'")

    def zoom(z: str) -> str:
        return (f",zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                f":d=1:s={w}x{h}:fps={fps},format=yuv420p")

    def wander(m: float, kx: str, ky: str) -> str:
        return (f",crop=w='iw*{1 - m:.4f}':h='ih*{1 - m:.4f}'"
                f":x='(iw-ow)/2*(1+{kx})':y='(ih-oh)/2*(1+{ky})',scale={w}:{h}:flags=bicubic,setsar=1")

    if kind == "shake":
        return wander(SHAKE * a, f"0.9*sin(29*{u})*sin(7.3*{u}+1)", f"0.9*cos(23*{u})*sin(5.1*{u})")
    if kind == "glitch":
        step = f"floor({u}*{GLITCH_RATE})"
        on = f"gt(mod(abs(sin({step}*12.9898)*43758.5),1),0.7)"
        side = f"(2*gt(sin({step}*78.233),0)-1)"
        r = _split_px(w, a, 2)
        return (wander(GLITCH * a, f"0.9*{on}*{side}", "0")
                + f",format=gbrp,rgbashift=rh=-{r}:bh={r},format=yuv420p")
    if kind == "zoom_in":
        return zoom(f"1+{ZOOM * a:.4f}*clip((in/{fps}-{H})/{d:.4f},0,1)")
    if kind == "zoom_out":
        return zoom(f"1+{ZOOM * a:.4f}*(1-clip((in/{fps}-{H})/{d:.4f},0,1))")
    if kind == "pulse":
        return zoom(f"1+{PULSE * a:.4f}*exp(-mod(max(in/{fps}-{H},0),{PULSE_EVERY})*8)")
    if kind == "flash":
        return white(f"{min(1.0, 0.9 * a):.3f}*clip(1-{U}/{FLASH_S},0,1)", "fl")
    if kind == "strobe":
        return white(f"{min(0.9, 0.55 * a):.3f}*gt(sin(2*PI*{STROBE_HZ}*{U}),0.5)", "st")
    if kind == "blur_in":
        s = max(1.0, BLUR * a * w)
        return (f",split[bia][bib];[bib]gblur=sigma={s:.2f}[big];"
                f"[bia][big]blend=all_expr='A+(B-A)*clip(1-{U}/{BLUR_IN_S},0,1)'")
    if kind == "glow":
        s = max(1.0, GLOW * w)
        return (f",format=gbrp,split[gla][glb];[glb]gblur=sigma={s:.2f}[glg];"
                f"[gla][glg]blend=all_mode=screen:all_opacity={min(1.0, 0.5 * a):.3f},format=yuv420p")
    if kind == "vhs":
        r = _split_px(w, a)
        return (f",eq=saturation=0.8:contrast=1.08,noise=alls={round(10 * a)}:allf=t"
                f",format=gbrp,rgbashift=rh=-{r}:bh={r},format=yuv420p"
                f",drawgrid=w=iw:h=4:t=1:c=black@{min(0.6, 0.3 * a):.2f}")
    if kind == "grain":
        return f",noise=alls={round(16 * a)}:allf=t+u"
    if kind == "old_film":
        s = min(1.0, 0.8 * a)
        # identity -> sepia, by s
        sep = [(.393, .769, .189), (.349, .686, .168), (.272, .534, .131)]
        m = [(1 - s) * (1 if i == j else 0) + s * sep[i][j] for i in range(3) for j in range(3)]
        rr, rg, rb, gr, gg, gb, br, bg, bb = (f"{x:.3f}" for x in m)
        return (f",format=gbrp,colorchannelmixer=rr={rr}:rg={rg}:rb={rb}:gr={gr}:gg={gg}:gb={gb}:br={br}:bg={bg}:bb={bb}"
                f",format=yuv420p,eq=brightness='{0.03 * a:.3f}*sin(50*{u})':eval=frame"
                f",noise=alls={round(14 * a)}:allf=t+u,vignette=angle={_vignette(a):.3f}")
    if kind == "vignette":
        return f",vignette=angle={_vignette(a):.3f}"
    if kind == "disco":
        return f",hue=h='{HUE_SPEED * a:.1f}*{u}'"
    return ""


def _vignette(a: float) -> float:
    # ffmpeg's default (PI/5) at 100%; never past a lens's worth of dark corners
    return min(1.2, 0.35 + 0.28 * a)


def describe(kind: str | None) -> str:
    return KINDS.get(kind or "", "No effect")

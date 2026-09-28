// Draw polish captions exactly where the backend placed them.
//
// polish/layout.py decides the lines, the size and the box (off faces,
// inside the safe area, no lonely last line); this only paints them. If the
// real font measures wider than the backend's glyph model, the text shrinks
// to the box -- it never grows past it, so the rules checked there hold here.

export type PolishRecipe = {
  name: string; family: string; font_file: string | null; size: number; weight: number; color: string
  stroke_color: string | null; stroke_width: number; position: string; enter: 'fade' | 'rise' | 'pop' | 'none'
  enter_s: number; margin: number; hold_s: number; max_lines: number
}
export type Placement = { lines: string[]; size: number; box: [number, number, number, number]; position: string
  moved: string | null; checks: { key: string; label: string; value: number | null; unit: string; verdict: string; detail: string }[] }
export type PolishCaption = { id: string; text: string; t: number; dur: number; scale: number; recipe: PolishRecipe; place: Placement | null
  anchor: { t: number; x: number; y: number; shot: number; frame: number } }
export type PolishEffect = { id: string; kind: 'boom'; t: number; dur: number; why: string }

const LINE_H = 1.25
type Ctx = CanvasRenderingContext2D | OffscreenCanvasRenderingContext2D

export const fontFamily = (r: PolishRecipe) =>
  `"${r.family}", "PingFang SC", "Hiragino Sans GB", system-ui, sans-serif`

/** Entrance at time t: opacity and a small offset/scale, from the recipe. */
export function entrance(r: PolishRecipe, since: number): { alpha: number; dy: number; scale: number } {
  const p = r.enter === 'none' || r.enter_s <= 0 ? 1 : Math.max(0, Math.min(1, since / r.enter_s))
  const e = 1 - (1 - p) ** 3
  if (r.enter === 'rise') return { alpha: e, dy: (1 - e) * 0.25, scale: 1 }
  if (r.enter === 'pop') return { alpha: Math.min(1, p * 2), dy: 0, scale: 0.8 + 0.2 * e + 0.06 * Math.sin(Math.PI * p) }
  return { alpha: e, dy: 0, scale: 1 }
}

export function drawCaptions(ctx: Ctx, W: number, H: number, caps: PolishCaption[], t: number): void {
  ctx.clearRect(0, 0, W, H)
  for (const c of caps) {
    const p = c.place
    if (!p || t < c.t || t >= c.t + c.dur) continue
    const r = c.recipe
    const [bx, by, bw, bh] = [p.box[0] * W, p.box[1] * H, p.box[2] * W, p.box[3] * H]
    let px = p.size * H
    ctx.font = `${r.weight} ${px}px ${fontFamily(r)}`
    const widest = Math.max(...p.lines.map((l) => ctx.measureText(l).width + (r.stroke_color ? r.stroke_width * px : 0)))
    if (widest > bw * 1.001) px *= bw / widest            // the real font is wider: fit the box, never leave it
    const en = entrance(r, t - c.t)
    const lineH = px * LINE_H
    const top = by + (bh - lineH * p.lines.length) / 2 + en.dy * px
    const cx = bx + bw / 2
    ctx.save()
    ctx.globalAlpha = en.alpha
    ctx.translate(cx, by + bh / 2)
    ctx.scale(en.scale, en.scale)
    ctx.translate(-cx, -(by + bh / 2))
    ctx.font = `${r.weight} ${px}px ${fontFamily(r)}`
    ctx.textAlign = 'center'
    ctx.textBaseline = 'top'
    ctx.lineJoin = 'round'
    p.lines.forEach((line, i) => {
      const y = top + i * lineH + (lineH - px) / 2
      if (r.stroke_color && r.stroke_width > 0) {
        ctx.strokeStyle = r.stroke_color
        ctx.lineWidth = r.stroke_width * px * 2           // the stroke sits half outside the glyph
        ctx.strokeText(line, cx, y)
      }
      ctx.fillStyle = r.color
      ctx.fillText(line, cx, y)
    })
    ctx.restore()
  }
}

/** How much a boom pushes the picture in at t (1 = not at all). */
export function boomScale(effects: PolishEffect[], t: number): number {
  let s = 1
  for (const e of effects) {
    if (e.kind !== 'boom' || t < e.t || t >= e.t + e.dur) continue
    const p = (t - e.t) / e.dur
    s = Math.max(s, 1 + 0.12 * Math.sin(Math.PI * Math.min(1, p * 1.4)) * (1 - p * 0.3))
  }
  return s
}

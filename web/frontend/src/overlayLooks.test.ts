// Every look moves words its own way -- and never out of the safe area.
//
// The seven look records (backend/looks/*.json) are drawn through the real
// drawOverlays onto a recording canvas, every intro frame at 30 fps, in both
// frame shapes. Each line of text must stay inside the safe area (where the
// platforms' buttons and captions don't cover it) on every frame, including
// Hype's slam from 1.5x and Cozy's rotated paper card. And each look's motion
// must be what its record says: stepped looks hold their steps, the bouncy one
// overshoots, and no look changes a video that doesn't use one.
import assert from 'node:assert/strict'
import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { test } from 'node:test'
import { bezier, drawOverlays, frameKey, safe } from './overlayDraw.ts'
import type { Motion, Overlay, OverlayStyle } from './types'

const DIR = join(import.meta.dirname, '../../backend/looks')
type Rec = { id: string; type: { font: OverlayStyle['font']; palette: string[]; backing: OverlayStyle['backing']; case: Motion['case']; track: number }
  motion: Omit<Motion, 'case' | 'track'> }
const LOOKS: Rec[] = readdirSync(DIR).filter((f) => f.endsWith('.json')).map((f) => JSON.parse(readFileSync(join(DIR, f), 'utf8')))

const styleOf = (r: Rec): OverlayStyle => ({
  font: r.type.font, color: r.type.palette[0], accent: r.type.palette[1], captions: 'bottom', backing: r.type.backing,
  look: r.id, motion: { ...r.motion, case: r.type.case, track: r.type.track },
})

const ov = (id: string, extra: Partial<Overlay>): Overlay => ({
  id, kind: 'title', text: 'Tokyo', sub: '', pos: 'center', size: 'M', anim: 'rise', dur: 3,
  anchor: { to: 'edit' }, at: 0, start: 0, end: 3, shown_end: 3, ...extra,
})
const WORDS: Overlay[] = [
  ov('t', { kind: 'title', text: 'A long weekend of rain and ramen in Tokyo', sub: 'May 2026', size: 'L', anim: 'rise' }),
  ov('p', { kind: 'part', text: 'Shibuya at night', sub: 'Day 2', pos: 'bottom-left', anim: 'slide' }),
  ov('d', { kind: 'date', text: 'Sat 2 May', pos: 'top-right', size: 'S', anim: 'type' }),
  ov('c', { kind: 'caption', text: 'we got completely lost and it was the best part of the trip', anim: 'fade' }),
]

// A canvas that draws nothing and remembers where each piece of text went,
// through translate / rotate / scale, as the four corners of its box.
function recorder() {
  let m = [1, 0, 0, 1, 0, 0]
  const stack: number[][] = []
  const boxes: [number, number][][] = []
  let px = 10
  const ctx = {
    font: '', textAlign: 'left', textBaseline: 'top', globalAlpha: 1, fillStyle: '', letterSpacing: '0px',
    shadowColor: '', shadowBlur: 0, shadowOffsetY: 0,
    clearRect() {}, beginPath() {}, fill() {}, fillRect() {}, roundRect() {},
    save() { stack.push([...m]) }, restore() { m = stack.pop() ?? [1, 0, 0, 1, 0, 0] },
    translate(x: number, y: number) { m = [m[0], m[1], m[2], m[3], m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5]] },
    scale(a: number, b: number) { m = [m[0] * a, m[1] * a, m[2] * b, m[3] * b, m[4], m[5]] },
    rotate(r: number) {
      const c = Math.cos(r), s = Math.sin(r)
      m = [m[0] * c + m[2] * s, m[1] * c + m[3] * s, -m[0] * s + m[2] * c, -m[1] * s + m[3] * c, m[4], m[5]]
    },
    // as browsers do: letter-spacing is in the measured width, trailing space included
    measureText(t: string) {
      px = parseFloat(/(\d+(?:\.\d+)?)px/.exec(ctx.font)?.[1] ?? '10')
      return { width: t.length * (px * 0.55 + parseFloat(ctx.letterSpacing)) }
    },
    fillText(t: string, x: number, y: number) {
      const ls = parseFloat(ctx.letterSpacing)
      const w = ctx.measureText(t).width
      const x0 = ctx.textAlign === 'center' ? x - w / 2 : ctx.textAlign === 'right' ? x - w : x
      const x1 = x0 + w - ls                      // the glyphs end before the last letter's spacing
      const pts: [number, number][] = [[x0, y], [x1, y], [x0, y + px], [x1, y + px]]
      boxes.push(pts.map(([a, b]) => [m[0] * a + m[2] * b + m[4], m[1] * a + m[3] * b + m[5]]))
    },
  }
  return { ctx, boxes }
}

for (const [W, H] of [[1080, 1920], [1920, 1080]]) {
  test(`every look keeps every word inside the ${W}x${H} safe area, every intro frame`, () => {
    const sa = safe(W, H)
    const tol = 2
    for (const r of LOOKS) {
      for (let f = 0; f <= 45; f++) {
        const { ctx, boxes } = recorder()
        drawOverlays(ctx as unknown as CanvasRenderingContext2D, W, H, WORDS, styleOf(r), [], f / 30)
        for (const b of boxes) for (const [x, y] of b) {
          assert.ok(x >= sa.l - tol && x <= W - sa.r + tol && y >= sa.t - tol && y <= H - sa.b + tol,
            `${r.id} frame ${f}: text at (${x.toFixed(0)}, ${y.toFixed(0)}) is outside the safe area`)
        }
      }
    }
  })
}

test('a stepped look holds its steps: Cozy shows 12 intro poses a second, not 30', () => {
  const cozy = styleOf(LOOKS.find((r) => r.id === 'cozy')!)
  const smooth = styleOf(LOOKS.find((r) => r.id === 'quiet')!)
  const intro = (s: OverlayStyle) => new Set(Array.from({ length: 30 }, (_, f) => frameKey([WORDS[0]], [], f / 30, s.motion))).size
  assert.ok(intro(cozy) <= 13, `cozy: ${intro(cozy)} distinct frames in the first second`)
  assert.ok(intro(smooth) >= 29, `quiet: ${intro(smooth)}`)
})

test('the curves are the records: ends pinned, Playful overshoots, the rest never do', () => {
  for (const r of LOOKS) {
    const f = bezier(r.motion.curve)
    assert.equal(f(0), 0)
    assert.equal(f(1), 1)
    const peak = Math.max(...Array.from({ length: 101 }, (_, i) => f(i / 100)))
    if (r.id === 'playful') assert.ok(peak > 1.05, `playful peaks at ${peak}`)
    else assert.ok(peak <= 1.0001, `${r.id} peaks at ${peak}`)
  }
})

test('without a look, nothing about the words changes', () => {
  const plain: OverlayStyle = { font: 'Clean', color: '#ffffff', accent: '#b9d9eb', captions: 'bottom', backing: 'shadow' }
  const keys = (s: OverlayStyle) => Array.from({ length: 40 }, (_, f) => frameKey(WORDS, [], f / 30, s.motion)).join(',')
  assert.equal(keys(plain), keys({ ...plain, motion: null }))
})

// Words dragged on the picture by hand: drawn where they were dropped, at
// their own size, still never out of the safe area -- the export draws them
// the same way, because it is the same function.
test('a caption placed by hand is drawn there, sized, and held inside the safe area', () => {
  const W = 1080, H = 1920
  const style = styleOf(LOOKS.find((r) => r.id === 'clean') ?? LOOKS[0])
  const cap = ov('c', { kind: 'caption', text: 'coffee run', anim: 'none' })
  const at = (place: Overlay['place']) => {
    const { ctx } = recorder()
    const out: import('./overlayDraw.ts').OverlayBox[] = []
    drawOverlays(ctx as unknown as CanvasRenderingContext2D, W, H, [{ ...cap, place }], style, [], 1.5, out)
    return out[0]
  }
  const usual = at(null), top = at({ x: 0.5, y: 0.3, scale: 1 }), big = at({ x: 0.5, y: 0.3, scale: 2 })
  assert.ok(usual.y > H * 0.6, 'a caption sits low by default')
  assert.ok(Math.abs(top.y + top.h / 2 - 0.3 * H) < 2 && Math.abs(top.x + top.w / 2 - W / 2) < 2, 'centred where it was dropped')
  assert.ok(Math.abs(big.w / top.w - 2) < 0.15, `twice the size: ${big.w / top.w}`)
  const edge = at({ x: 0.99, y: 0.99, scale: 1 }), sa = safe(W, H)
  assert.ok(edge.x + edge.w <= W - sa.r + 1 && edge.y + edge.h <= H - sa.b + 1, 'dropped at the edge, pulled back inside')
})

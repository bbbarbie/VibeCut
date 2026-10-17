// Caption templates and entrances: every one keeps every word inside the
// safe area on every intro frame, in both frame shapes -- the stamp starts
// at 2x, the slide starts off to the side -- and each draws what it says:
// an edge for Outlined, a backing for Label, the time on its own line, some
// words in colour for Pop, a typed caption written out letter by letter.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { drawOverlays, frameKey, safe, TEMPLATES, tinted } from './overlayDraw.ts'
import type { CaptionEnter, CaptionTemplate, Overlay, OverlayStyle } from './types'

const BASE: OverlayStyle = { font: 'Clean', color: '#ffffff', accent: '#b9d9eb', captions: 'bottom', backing: 'shadow' }
const ENTERS: CaptionEnter[] = ['fade', 'pop', 'slide', 'stamp', 'type', 'word']
const IDS = Object.keys(TEMPLATES) as CaptionTemplate[]
const cap = (text: string, extra: Partial<Overlay> = {}): Overlay => ({
  id: 'c', kind: 'caption', text, sub: '', pos: 'bottom', size: 'M', anim: 'fade', dur: 3,
  anchor: { to: 'edit' }, at: 0, start: 0, end: 3, shown_end: 3, ...extra,
})

type Drawn = { text: string; fill: string; stroked: boolean; pts: [number, number][] }
function recorder() {
  let m = [1, 0, 0, 1, 0, 0]
  const stack: number[][] = []
  const drawn: Drawn[] = []
  const rects: number[][] = []
  let px = 10
  const ctx = {
    font: '', textAlign: 'left', textBaseline: 'top', globalAlpha: 1, fillStyle: '', strokeStyle: '', lineWidth: 1,
    lineJoin: 'miter', letterSpacing: '0px', shadowColor: '', shadowBlur: 0, shadowOffsetY: 0,
    clearRect() {}, beginPath() {}, fill() {}, fillRect() {},
    roundRect(x: number, y: number, w: number, h: number) { rects.push([x, y, w, h]) },
    save() { stack.push([...m]) }, restore() { m = stack.pop() ?? [1, 0, 0, 1, 0, 0] },
    translate(x: number, y: number) { m = [m[0], m[1], m[2], m[3], m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5]] },
    scale(a: number, b: number) { m = [m[0] * a, m[1] * a, m[2] * b, m[3] * b, m[4], m[5]] },
    rotate(r: number) {
      const c = Math.cos(r), s = Math.sin(r)
      m = [m[0] * c + m[2] * s, m[1] * c + m[3] * s, -m[0] * s + m[2] * c, -m[1] * s + m[3] * c, m[4], m[5]]
    },
    measureText(t: string) {
      px = parseFloat(/(\d+(?:\.\d+)?)px/.exec(ctx.font)?.[1] ?? '10')
      return { width: t.length * (px * 0.55 + parseFloat(ctx.letterSpacing)) }
    },
    strokeText(t: string) { if (t.trim()) last.add(t) },
    fillText(t: string, x: number, y: number) {
      const ls = parseFloat(ctx.letterSpacing)
      const w = ctx.measureText(t).width
      const x0 = ctx.textAlign === 'center' ? x - w / 2 : ctx.textAlign === 'right' ? x - w : x
      const x1 = x0 + w - ls
      const pts: [number, number][] = [[x0, y], [x1, y], [x0, y + px], [x1, y + px]]
      drawn.push({ text: t, fill: String(ctx.fillStyle), stroked: last.has(t),
                   pts: pts.map(([a, b]) => [m[0] * a + m[2] * b + m[4], m[1] * a + m[3] * b + m[5]]) })
      last.clear()
    },
  }
  const last = new Set<string>()
  return { ctx, drawn, rects }
}
const draw = (style: OverlayStyle, o: Overlay, t: number, W = 1080, H = 1920) => {
  const r = recorder()
  drawOverlays(r.ctx as unknown as CanvasRenderingContext2D, W, H, [o], style, [], t)
  return r
}

for (const [W, H] of [[1080, 1920], [1920, 1080]]) {
  test(`every template and entrance keeps every word inside the ${W}x${H} safe area`, () => {
    const sa = safe(W, H), tol = 2
    const words = cap('7:42 am · we got completely lost and it was the best part of the trip', { sub: 'Shibuya' })
    for (const id of IDS) for (const enter of ENTERS) {
      for (let f = 0; f <= 75; f++) {
        for (const d of draw({ ...BASE, template: id, enter }, words, f / 30, W, H).drawn) for (const [x, y] of d.pts) {
          assert.ok(x >= sa.l - tol && x <= W - sa.r + tol && y >= sa.t - tol && y <= H - sa.b + tol,
            `${id} + ${enter} frame ${f}: "${d.text}" at (${x.toFixed(0)}, ${y.toFixed(0)}) is outside the safe area`)
        }
      }
    }
  })
}

test('each template draws what it says', () => {
  const held = 2
  const o = cap('12:30 · so much rice today')
  const out = draw({ ...BASE, template: 'outlined' }, o, held)
  assert.deepEqual(out.drawn.map((d) => d.text).join('|'), '12:30|so much rice today', 'the time on its own line, on top')
  assert.ok(out.drawn.every((d) => d.stroked), 'outlined: every word has its black edge')
  assert.ok(out.drawn[0].pts[0][1] < out.drawn[1].pts[0][1], 'the time is above')
  const label = draw({ ...BASE, template: 'label' }, o, held)
  assert.ok(label.rects.length >= 1 && label.drawn.every((d) => !d.stroked && d.fill === '#141414'), 'label: dark words on a backing')
  const pop = draw({ ...BASE, template: 'pop' }, o, held)
  const lit = pop.drawn.filter((d) => d.fill !== '#ffffff').map((d) => d.text)
  assert.ok(lit.includes('rice') || lit.includes('today') || lit.includes('much'), `pop: a word in colour (${lit})`)
  const bold = draw({ ...BASE, template: 'bold' }, cap('lunch'), held)
  assert.equal(bold.drawn[0].text, 'LUNCH', 'big & bold is capitals')
  const plain = draw(BASE, o, held)
  assert.equal(plain.drawn.length, 1, 'no template: the look\'s own one line')
})

test('typewriter writes the caption out; word by word adds whole words', () => {
  const o = cap('7:42 am · coffee run with friends')
  const said = (enter: CaptionEnter, t: number) => draw({ ...BASE, template: 'outlined', enter }, o, t).drawn.map((d) => d.text).join(' ')
  const typed = [0.05, 0.3, 0.6, 1.0, 2.0].map((t) => said('type', t))
  for (let i = 1; i < typed.length; i++) assert.ok(typed[i].length >= typed[i - 1].length, `typing only grows: ${typed}`)
  assert.equal(typed[typed.length - 1], '7:42 am coffee run with friends')
  assert.ok(typed[1].length < typed[3].length, 'part-way through, part of it')
  const worded = [0.1, 0.6, 1.2, 2.5].map((t) => said('word', t))
  const whole = new Set('7:42 am coffee run with friends'.split(' '))
  for (const w of worded) for (const x of w.split(' ').filter(Boolean)) assert.ok(whole.has(x), `"${x}" is a whole word`)
})

test('an entrance is part of the export frame key: picking one changes the intro frames', () => {
  const o = cap('coffee run')
  const keys = (s: OverlayStyle) => Array.from({ length: 20 }, (_, f) => frameKey([o], [], f / 30, s.motion, s)).join(',')
  assert.notEqual(keys({ ...BASE, enter: 'stamp' }), keys({ ...BASE, enter: 'type' }))
  assert.equal(keys(BASE), keys({ ...BASE, motion: null }))
})

test('a colour picked by hand is the colour drawn, and still reads', () => {
  const o = cap('so much rice today')
  const fills = (style: OverlayStyle) => draw(style, o, 2).drawn.map((d) => d.fill)
  assert.ok(fills({ ...BASE, text_color: '#ffd84d' }).every((f) => f === '#ffd84d'), 'no template: the words are yellow')
  assert.ok(fills({ ...BASE, template: 'outlined', text_color: '#ff9eb5' }).every((f) => f === '#ff9eb5'), 'outlined: the letters are pink')
  assert.ok(fills({ ...BASE, template: 'outlined' }).every((f) => f === '#ffffff'), 'nothing picked: the template\'s own white')
  // a boxed template takes the colour as its backing; the words go black or white, whichever reads
  assert.ok(fills({ ...BASE, template: 'label', text_color: '#ffd84d' }).every((f) => f === '#141414'))
  assert.ok(fills({ ...BASE, template: 'label', text_color: '#141414' }).every((f) => f === '#ffffff'))
  // dark letters on an edged or bare template get a white edge
  assert.equal(tinted(TEMPLATES.outlined, '#141414').stroke?.color, '#ffffff')
  assert.equal(tinted(TEMPLATES.outlined, '#ffd84d').stroke?.color, '#000000')
  assert.equal(tinted(TEMPLATES.handwritten, '#141414').stroke?.color, '#ffffff')
  assert.ok(draw({ ...BASE, template: 'quiet', text_color: '#141414' }, o, 2).drawn.every((d) => d.stroked), 'a dark pick on a bare template is edged')
})

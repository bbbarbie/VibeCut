// The browser paints polish captions inside the box the backend placed them
// in -- even when its real font measures wider -- so the face and safe-area
// rules checked in polish/layout.py still hold on screen.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { boomScale, drawCaptions, entrance, type PolishCaption, type PolishRecipe } from './polishDraw.ts'

const R: PolishRecipe = { name: 'Mine', family: 'PingFang SC', font_file: null, size: 0.06, weight: 700, color: '#ffffff',
  stroke_color: '#000000', stroke_width: 0.12, position: 'lower_third', enter: 'rise', enter_s: 0.25, margin: 0.06,
  hold_s: 3, max_lines: 2 }
const cap = (): { c: PolishCaption } => {
  return { c: { id: 'c1', text: '东京第一天', t: 21, dur: 3, scale: 1, recipe: R, anchor: { t: 21, x: 0.5, y: 0.8, shot: 1, frame: 630 },
    place: { lines: ['东京第一天'], size: 0.035, box: [0.3, 0.45, 0.4, 0.05], position: 'above the face', moved: 'moved', checks: [] } } }
}

function recorder(emPerChar: number) {
  let m = [1, 0, 0, 1, 0, 0]
  const st: number[][] = []
  const drawn: [number, number, number, number][] = []
  let px = 10
  const ctx = {
    font: '', textAlign: 'center', textBaseline: 'top', globalAlpha: 1, fillStyle: '', strokeStyle: '', lineWidth: 1, lineJoin: '',
    clearRect() {}, save() { st.push([...m]) }, restore() { m = st.pop()! },
    translate(x: number, y: number) { m = [m[0], m[1], m[2], m[3], m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5]] },
    scale(a: number, b: number) { m = [m[0] * a, m[1] * a, m[2] * b, m[3] * b, m[4], m[5]] },
    measureText(s: string) { px = parseFloat(/ (\d+(?:\.\d+)?)px/.exec(ctx.font)![1]); return { width: s.length * px * emPerChar } },
    strokeText() {},
    fillText(s: string, x: number, y: number) {
      const w = ctx.measureText(s).width
      const pts = [[x - w / 2, y], [x + w / 2, y + px]].map(([a, b]) => [m[0] * a + m[2] * b + m[4], m[1] * a + m[3] * b + m[5]])
      drawn.push([pts[0][0], pts[0][1], pts[1][0], pts[1][1]])
    },
  }
  return { ctx, drawn }
}

for (const [label, em] of [['as the backend measured', 1.0], ['a real font 30% wider', 1.3]] as const) {
  test(`drawn text stays inside its placed box (${label})`, () => {
    const W = 1080, H = 1920
    const { c } = cap()
    const { ctx, drawn } = recorder(em)
    drawCaptions(ctx as unknown as CanvasRenderingContext2D, W, H, [c], 23)     // fully in
    assert.equal(drawn.length, 1)
    const [x0, y0, x1, y1] = drawn[0]
    const [bx, by, bw, bh] = [c.place!.box[0] * W, c.place!.box[1] * H, c.place!.box[2] * W, c.place!.box[3] * H]
    const tol = 1
    assert.ok(x0 >= bx - tol && x1 <= bx + bw + tol && y0 >= by - tol && y1 <= by + bh + tol,
      `text ${[x0, y0, x1, y1].map(Math.round)} vs box ${[bx, by, bx + bw, by + bh].map(Math.round)}`)
  })
}

test('nothing is drawn outside the caption\'s time', () => {
  const { c } = cap()
  for (const t of [20.9, 24.0]) {
    const { ctx, drawn } = recorder(1)
    drawCaptions(ctx as unknown as CanvasRenderingContext2D, 1080, 1920, [c], t)
    assert.equal(drawn.length, 0, `t=${t}`)
  }
})

test('the entrance follows the recipe, and a boom is brief', () => {
  assert.equal(entrance(R, 0).alpha, 0)
  assert.equal(entrance(R, 1).alpha, 1)
  assert.equal(entrance({ ...R, enter: 'none' }, 0).alpha, 1)
  const e = [{ id: 'e', kind: 'boom' as const, t: 5, dur: 0.4, why: '' }]
  assert.equal(boomScale(e, 4.99), 1)
  assert.ok(boomScale(e, 5.15) > 1.05)
  assert.equal(boomScale(e, 5.41), 1)
})

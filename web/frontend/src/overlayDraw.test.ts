import assert from 'node:assert/strict'
import { test } from 'node:test'
import { busyFrames, envelope, frameKey, partAt, partsOf, phase, wrap } from './overlayDraw.ts'
import type { Overlay } from './types'

const ov = (id: string, start: number, end: number, extra: Partial<Overlay> = {}): Overlay => ({
  id, kind: 'title', text: 'Kyoto', sub: '', pos: 'center', size: 'M', anim: 'fade', dur: end - start,
  anchor: { to: 'edit' }, at: start, start, end, shown_end: end, ...extra,
})

test('the outro finishes before the end, so nothing vanishes on a cut', () => {
  const o = ov('a', 2, 5)
  const { outS } = envelope(o)
  assert.equal(phase(o, 5 - 1e-6).pout < 0.01, true)
  assert.ok(phase(o, 5 - outS - 0.01).pout === 1 && phase(o, 5 - outS).pout > 0.999)
  assert.equal(phase(o, 5).on, false)
})

test('a short overlay does not spend most of its life animating', () => {
  const { inS, outS } = envelope(ov('a', 0, 1))
  assert.ok(inS + outS <= 0.55, `${inS} + ${outS}`)
})

test('a title holding still has one key for its whole hold', () => {
  const o = ov('a', 0, 4)
  const fps = 30
  const hold = new Set<string>()
  for (let f = 16; f < 110; f++) hold.add(frameKey([o], [], f / fps))
  assert.equal(hold.size, 1)
  const intro = new Set<string>()
  for (let f = 0; f < 15; f++) intro.add(frameKey([o], [], f / fps))
  assert.equal(intro.size, 15)   // every intro frame differs
})

test('nothing on screen is an empty key and no busy frames', () => {
  assert.equal(frameKey([ov('a', 1, 2)], [], 3), '')
  assert.deepEqual(busyFrames([ov('a', 1, 1.1)], 30, 5), [30, 31, 32])
})

test('the chapter bar keys on which part is current', () => {
  const items = [{ beat_id: 't1', beat_title: 'Morning', seq_start: 0, seq_end: 3 },
    { beat_id: 't1', beat_title: 'Morning', seq_start: 3, seq_end: 6 },
    { beat_id: 't2', beat_title: 'Market', seq_start: 6, seq_end: 9 }]
  const parts = partsOf(items)
  assert.deepEqual(parts.map((p) => [p.title, p.start, p.end]), [['Morning', 0, 6], ['Market', 6, 9]])
  const bar = ov('c', 0, 9, { kind: 'chapters' })
  assert.notEqual(frameKey([bar], parts, 5), frameKey([bar], parts, 7))
  assert.equal(frameKey([bar], parts, 4), frameKey([bar], parts, 5))
  assert.equal(partAt(parts, 6), 1)
})

test('wrapping keeps words whole, splits CJK by character, and ellipsizes', () => {
  const m = (s: string) => s.length * 10
  assert.deepEqual(wrap(m, 'the quick brown fox', 100), ['the quick', 'brown fox'])
  assert.deepEqual(wrap(m, '我们终于到了京都', 40), ['我们终于', '到了京都'])
  const long = wrap(m, 'a b c d e f g h i j k l', 30, 2)
  assert.equal(long.length, 2)
  assert.ok(long[1].endsWith('…'))
})

import { test } from 'node:test'
import assert from 'node:assert/strict'
import { EFFECTS, effectAt, NO_FX } from './effectView.ts'

// The preview's effects follow the export's (backend effects.py, tests/test_effects.py).

test('no effect leaves the picture alone', () => {
  assert.deepEqual(effectAt(null, 1, 0.5, 3, 400, 225), NO_FX)
})

test('every effect does something somewhere in its shot', () => {
  for (const [id] of EFFECTS) {
    const any = [0, 0.03, 0.1, 0.5, 1.3, 2.9].some((u) => {
      const fx = effectAt(id, 1, u, 3, 400, 225)
      return fx.transform || fx.filter || fx.tint || fx.grain
    })
    assert.ok(any, id)
  }
})

test('flash and blur in are only at the start', () => {
  assert.ok(effectAt('flash', 1, 0.02, 3, 400, 225).tint)
  assert.equal(effectAt('flash', 1, 1, 3, 400, 225).tint, '')
  assert.ok(effectAt('blur_in', 1, 0.05, 3, 400, 225).filter)
  assert.equal(effectAt('blur_in', 1, 1, 3, 400, 225).filter, '')
})

test('zoom in grows over the shot, zoom out settles', () => {
  const z = (k: string, u: number) => Number(/scale\(([\d.]+)\)/.exec(effectAt(k, 1, u, 3, 400, 225).transform)![1])
  assert.ok(z('zoom_in', 2.9) > z('zoom_in', 0.1) + 0.1)
  assert.ok(z('zoom_out', 0.1) > z('zoom_out', 2.9) + 0.1)
})

test('stronger means more', () => {
  const blur = (a: number) => Number(/blur\(([\d.]+)px\)/.exec(effectAt('blur_in', a, 0.1, 3, 400, 225).filter)![1])
  assert.ok(blur(2) > blur(0.5) * 3)
})

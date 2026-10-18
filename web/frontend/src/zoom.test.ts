import { test } from 'node:test'
import assert from 'node:assert/strict'
import { anchoredScroll, clampZoom, fromSlider, toSlider, wheelFactor, ZOOM_MAX, ZOOM_MIN } from './zoom.ts'

test('wheel up zooms in, down zooms out, by the same amount', () => {
  assert.ok(wheelFactor(-10) > 1)
  assert.ok(wheelFactor(10) < 1)
  assert.ok(Math.abs(wheelFactor(-10) * wheelFactor(10) - 1) < 1e-9)
})

test('a mouse notch is a capped jump; a pinch step is small', () => {
  const notch = wheelFactor(-100)
  assert.ok(notch > 1.3 && notch < 1.8, `notch ${notch}`)
  assert.equal(wheelFactor(-1000), notch)
  const pinch = wheelFactor(-2)
  assert.ok(pinch > 1 && pinch < 1.05, `pinch ${pinch}`)
})

test('line-mode wheels count like pixel wheels', () => {
  assert.ok(Math.abs(wheelFactor(-3, 1) - wheelFactor(-48)) < 1e-9)
})

test('zoom is clamped and the slider round-trips', () => {
  assert.equal(clampZoom(0.2), ZOOM_MIN)
  assert.equal(clampZoom(500), ZOOM_MAX)
  for (const z of [1, 2.5, 7, 40]) assert.ok(Math.abs(fromSlider(toSlider(z)) - z) < 1e-9)
  assert.equal(toSlider(1), 0)
  assert.equal(toSlider(ZOOM_MAX), 1)
})

test('the moment under the pointer stays under the pointer', () => {
  assert.equal(anchoredScroll(900, 300, 800, 5000), 600)
  assert.equal(anchoredScroll(100, 300, 800, 5000), 0)
  assert.equal(anchoredScroll(4900, 100, 800, 5000), 4200)
})

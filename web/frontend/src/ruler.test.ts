import { test } from 'node:test'
import assert from 'node:assert/strict'
import { rulerLabel, rulerMarks, rulerScale } from './ruler.ts'

test('the labelled step follows the zoom, down to single frames', () => {
  assert.equal(rulerScale(1, 30).major, 120 * 30)        // whole long edit: 2 minutes
  assert.equal(rulerScale(20, 30).major, 5 * 30)         // 5s
  assert.equal(rulerScale(100, 30).major, 30)            // 1s
  assert.equal(rulerScale(150, 30).major, 15)            // half seconds
  assert.equal(rulerScale(400, 30).major, 5)             // 5 frames
  assert.equal(rulerScale(3000, 30).major, 1)            // single frames
  assert.equal(rulerScale(3000, 25).major, 1)
})

test('small ticks sit between labels at every zoom, never crowded', () => {
  for (const pps of [1, 5, 20, 60, 100, 150, 400, 900]) {
    const { major, minor } = rulerScale(pps, 30)
    assert.ok(minor > 0, `ticks at ${pps} px/s`)
    assert.equal(major % minor, 0)
    assert.ok((minor / 30) * pps >= 7)
  }
  assert.equal(rulerScale(3000, 30).minor, 0)            // a frame has nothing between
})

test('labels read as seconds, minutes, then frames', () => {
  assert.equal(rulerLabel(0, 30), '0s')
  assert.equal(rulerLabel(150, 30), '5s')
  assert.equal(rulerLabel(65 * 30, 30), '1:05')
  assert.equal(rulerLabel(45, 30), '15f')
  assert.equal(rulerLabel(31, 30), '1f')
  assert.equal(rulerLabel(30, 29.97), '1s')
})

test('marks cover the window asked for', () => {
  assert.deepEqual(rulerMarks(0, 23, 150, 30), [0, 150, 300, 450, 600])
  assert.deepEqual(rulerMarks(1, 1.2, 1, 30), [30, 31, 32, 33, 34, 35, 36])
  assert.deepEqual(rulerMarks(0, 1, 0, 30), [])
})

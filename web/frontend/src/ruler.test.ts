import { test } from 'node:test'
import assert from 'node:assert/strict'
import { rulerLabel, rulerMarks, rulerStep } from './ruler.ts'

test('the step widens as the timeline zooms out', () => {
  assert.equal(rulerStep(100), 1)
  assert.equal(rulerStep(20), 5)
  assert.equal(rulerStep(5), 15)
  assert.equal(rulerStep(1), 120)
  assert.equal(rulerStep(0.01), 600)
})

test('labels read as seconds, then minutes', () => {
  assert.equal(rulerLabel(0), '0s')
  assert.equal(rulerLabel(5), '5s')
  assert.equal(rulerLabel(59.6), '1:00')
  assert.equal(rulerLabel(65), '1:05')
  assert.equal(rulerLabel(600), '10:00')
})

test('marks run from the start to the end of the edit', () => {
  assert.deepEqual(rulerMarks(23, 5), [0, 5, 10, 15, 20])
  assert.deepEqual(rulerMarks(20, 5), [0, 5, 10, 15, 20])
})

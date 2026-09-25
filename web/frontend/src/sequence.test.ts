import assert from 'node:assert/strict'
import { test } from 'node:test'
import { beatAt, clock, locate, parseTimecode, readout, smpte, type SeqItem } from './sequence.ts'

test('typed timecodes: seconds, m:ss, h:mm:ss and SMPTE frames', () => {
  assert.equal(parseTimecode('21.3', 30), 21.3)
  assert.equal(parseTimecode('0:21.3', 30), 21.3)
  assert.equal(parseTimecode('1:02:03.5', 30), 3723.5)
  assert.ok(Math.abs(parseTimecode('00:00:21:09', 30)! - 21.3) < 1e-9)
  assert.equal(parseTimecode('21', 30), 21)
  for (const bad of ['', 'abc', '1:75', '00:00:21:40', '-3', '1::2', '0:21.3.4']) {
    assert.equal(parseTimecode(bad, 30), null, bad)
  }
})

test('clock and SMPTE formatting round-trip', () => {
  assert.equal(clock(21.3), '0:21.30')
  assert.equal(clock(3723.5), '1:02:03.50')
  assert.equal(smpte(21.3, 30), '00:00:21:09')
  assert.ok(Math.abs(parseTimecode(smpte(83.4, 30), 30)! - 83.4) < 1 / 30)
})

const item = (n: number, a: number, b: number): SeqItem => ({
  key: `k${n}`, kind: 'shot', shot_id: `s${n}`, clip_id: 'c', src_start: 100, src_end: 100 + b - a,
  seq_start: a, seq_end: b, beat_id: 't1', beat_title: 'x', n,
})
const items = [item(1, 0, 10), item(2, 10, 19.2), item(3, 19.2, 30)]

test('locate finds the item under the playhead by binary search', () => {
  assert.equal(locate(items, 0), 0)
  assert.equal(locate(items, 9.999), 0)
  assert.equal(locate(items, 10), 1)
  assert.equal(locate(items, 30), 2)
})

test('readout says what is at the playhead', () => {
  assert.equal(readout(items, null, 21.3), 'Shot 3 · 2.1s in · 0:21.30')
  assert.equal(readout(items, { bpm: 120, phase: 0 }, 21.3), 'Shot 3 · 2.1s in · 0:21.30 · beat 3 of 4')
  assert.deepEqual(beatAt({ bpm: 120, phase: 0.25 }, 0.1), null)
})

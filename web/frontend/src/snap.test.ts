// node --test src/snap.test.ts   (Node strips the types; no build step)
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { approaching, cutWhilePlaying, lowerBound, snap, step, thresholdSeconds, type Target } from './snap.ts'

const T: Target[] = [
  { t: 0, type: 'shot', label: 'shot 1 start' },
  { t: 4.0, type: 'motion', label: 'motion onset · shot 1' },
  { t: 7.5, type: 'silence', label: 'silence starts · shot 1' },
  { t: 10.0, type: 'shot', label: 'shot 2 start' },
  { t: 10.3, type: 'beat', label: 'beat 2 of 4 · bar 3' },
  { t: 21.3, type: 'shot', label: 'shot 3 start' },
]

// pxPerSec 20 -> base threshold 8px / 20 = 0.4s. Shot reach 0.6s, silence
// 0.4s, beat 0.36s, motion 0.24s.
const zoomedOut = { pxPerSec: 20 }
const zoomedIn = { pxPerSec: 400 }   // base 0.02s: fine control

test('returns the target when the raw position is within its threshold', () => {
  assert.deepEqual(snap(T, 9.6, zoomedOut), { t: 10.0, target: T[3] })
  assert.equal(snap(T, 7.2, zoomedOut).target?.label, 'silence starts · shot 1')
})

test('returns the raw position when nothing is within the threshold', () => {
  assert.deepEqual(snap(T, 15.0, zoomedOut), { t: 15.0, target: null })
})

test('stronger targets reach further than weaker ones at the same distance', () => {
  // 0.5s away: inside a shot boundary's reach (0.6s), outside motion's (0.24s)
  assert.equal(snap(T, 9.5, zoomedOut).target?.type, 'shot')
  assert.equal(snap(T, 4.5, zoomedOut).target, null)
  assert.equal(snap(T, 4.2, zoomedOut).target?.type, 'motion')
})

test('between two close targets, the weighted-nearest wins', () => {
  // 10.2: shot at 0.2s (score 0.13), beat at 0.1s (score 0.11) -> beat
  assert.equal(snap(T, 10.2, zoomedOut).target?.type, 'beat')
  // 10.1: shot 0.1 (0.067) beats beat 0.2 (0.22)
  assert.equal(snap(T, 10.1, zoomedOut).target?.type, 'shot')
})

test('the threshold scales with zoom: strong zoomed out, fine zoomed in', () => {
  assert.ok(Math.abs(thresholdSeconds(zoomedOut) - 0.4) < 1e-9)
  assert.ok(Math.abs(thresholdSeconds(zoomedIn) - 0.02) < 1e-9)
  assert.equal(snap(T, 9.8, zoomedOut).t, 10.0)          // 0.2s away: snaps when zoomed out
  assert.deepEqual(snap(T, 9.8, zoomedIn), { t: 9.8, target: null })  // not when zoomed in
  assert.equal(snap(T, 9.985, zoomedIn).t, 10.0)          // 15ms away still snaps zoomed in
})

test('holding the modifier returns the raw position, even on top of a target', () => {
  assert.deepEqual(snap(T, 9.99, { ...zoomedOut, disabled: true }), { t: 9.99, target: null })
  assert.equal(approaching(T, 9.99, { ...zoomedOut, disabled: true }), null)
})

test('lookup is a binary search over sorted targets', () => {
  assert.equal(lowerBound(T, -1), 0)
  assert.equal(lowerBound(T, 10.0), 3)
  assert.equal(lowerBound(T, 10.01), 4)
  assert.equal(lowerBound(T, 99), T.length)
  // thousands of targets: still exact, and cheap
  const many: Target[] = Array.from({ length: 20000 }, (_, i) => ({ t: i * 0.05, type: 'beat', label: `b${i}` }))
  const t0 = performance.now()
  for (let i = 0; i < 20000; i++) snap(many, (i * 0.0503) % 1000, zoomedIn)
  assert.ok(performance.now() - t0 < 200, 'snap must stay cheap on a dense list')
  assert.equal(snap(many, 500.012, zoomedIn).target?.label, 'b10000')
})

test('approaching sees a target a little before it snaps', () => {
  assert.equal(snap(T, 8.4, zoomedOut).target, null)
  assert.equal(approaching(T, 8.4, zoomedOut)?.label, 'silence starts · shot 1')
})

test('step moves to the next or previous target, optionally of one type', () => {
  assert.equal(step(T, 10.0, 1)?.t, 10.3)
  assert.equal(step(T, 10.0, -1)?.t, 7.5)
  assert.equal(step(T, 10.0, 1, 'shot')?.t, 21.3)
  assert.equal(step(T, 21.3, 1), null)
})

test('a cut tapped late during playback lands on the target just before it', () => {
  // the shot boundary is at 10.0; the tap came 0.25s late
  assert.equal(cutWhilePlaying(T, 10.25).t, 10.0)
  // nothing near: stays where it was tapped
  assert.deepEqual(cutWhilePlaying(T, 15.0), { t: 15.0, target: null })
})

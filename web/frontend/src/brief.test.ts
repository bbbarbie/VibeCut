import assert from 'node:assert/strict'
import { test } from 'node:test'
import { applies, composeBrief, lengthLabel, nearestMark, sayPicks } from './brief.ts'
import type { StyleQuestion } from './types.ts'

const Q: StyleQuestion[] = [
  { id: 'length', question: 'How long should it be?', multi: false, choices: [{ key: 'short', label: 'Short' }, { key: 'long', label: 'Long' }] },
  { id: 'pace', question: 'How should it feel?', multi: false, choices: [{ key: 'fast', label: 'Fast and punchy' }] },
  { id: 'focus', question: 'What should it mostly be about?', multi: true, choices: [{ key: 'people', label: 'People' }, { key: 'food', label: 'Food' }] },
  { id: 'extra1', question: 'Which day matters most?', multi: false, choices: [{ key: 'Saturday', label: 'Saturday' }] },
]

test('style answers travel structured, the rest as words', () => {
  const b = composeBrief('a day at Columbia', Q, {
    length: { keys: ['short'], other: '' }, pace: { keys: ['fast'], other: '' },
    focus: { keys: ['people', 'food'], other: '' }, extra1: { keys: ['Saturday'], other: '' },
  }, 'no screenshots')
  assert.deepEqual(b.style, { length: 'short', pace: 'fast' })
  assert.equal(b.message, 'a day at Columbia\nMostly about people, food.\nWhich day matters most? Saturday.\nno screenshots')
})

test('skipping everything sends just the description', () => {
  assert.deepEqual(composeBrief('  my trip  ', Q, {}), { message: 'my trip', style: {} })
})

test('typed answers are kept, never mistaken for a style key', () => {
  const b = composeBrief('trip', Q, { length: { keys: [], other: 'about 90 seconds' } })
  assert.deepEqual(b.style, {})
  assert.equal(b.message, 'trip\nHow long should it be? about 90 seconds')
})

test('picks read back in plain words', () => {
  assert.equal(sayPicks(Q, { length: { keys: ['short'], other: '' }, focus: { keys: ['people', 'food'], other: '' } }),
    'short, people + food')
})

test('the captions answer travels structured, so it can put words on screen', () => {
  const q: StyleQuestion[] = [{ id: 'captions', question: 'What words should be on screen?', multi: false,
    choices: [{ key: 'bold', label: 'Bold, Reels style' }] }]
  const b = composeBrief('trip', q, { captions: { keys: ['bold'], other: '' } })
  assert.deepEqual(b.style, { captions: 'bold' })
  assert.equal(b.message, 'trip')
})

test('the captions look is asked only when there are captions', () => {
  const caps: StyleQuestion[] = [
    { id: 'captions', question: 'Captions?', multi: false, choices: [{ key: 'describe', label: 'Describe' }, { key: 'none', label: 'No captions' }] },
    { id: 'caption_look', question: 'How should the captions look?', multi: false, when: { captions: ['describe', 'transcribe'] },
      choices: [{ key: 'bold', label: 'Bold' }] },
  ]
  assert.equal(applies(caps[1], {}), false)
  assert.equal(applies(caps[1], { captions: { keys: ['none'], other: '' } }), false)
  assert.equal(applies(caps[1], { captions: { keys: ['describe'], other: '' } }), true)
  const on = composeBrief('a day', caps, { captions: { keys: ['describe'], other: '' }, caption_look: { keys: ['bold'], other: '' } })
  assert.deepEqual(on.style, { captions: 'describe', caption_look: 'bold' })
  // a look picked, then captions switched off: the look doesn't travel
  const off = composeBrief('a day', caps, { captions: { keys: ['none'], other: '' }, caption_look: { keys: ['bold'], other: '' } })
  assert.deepEqual(off.style, { captions: 'none' })
})

test('the length slider travels as seconds, with the nearest mark', () => {
  const marks = [{ key: 'short', label: 'Short', seconds: 60 }, { key: 'medium', label: 'Medium', seconds: 116 }, { key: 'long', label: 'Long', seconds: 233 }]
  const qs: StyleQuestion[] = [{ id: 'length', question: 'How long should it be?', multi: false, choices: marks,
    slider: { min: 15, max: 233, marks, suggest: 'short', seconds: 60, why: '', kind: 'day' } }]
  const picks = { length: { keys: [nearestMark(marks, 100)], other: '', seconds: 100 } }
  assert.deepEqual(composeBrief('a day', qs, picks).style, { length: 'medium', seconds: 100 })
  assert.equal(sayPicks(qs, picks), 'about 1:40')
  assert.equal(lengthLabel(45), '45 s')
})

import assert from 'node:assert/strict'
import { test } from 'node:test'
import { composeBrief, sayPicks } from './brief.ts'
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

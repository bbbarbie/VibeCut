import assert from 'node:assert/strict'
import { test } from 'node:test'
import { deriveStage, reached } from './stage.ts'

const base = { clips: 8, workflow: 'cut-review', brief: false, proposals: false, board: false }

test('a project moves through footage, brief, cut and story', () => {
  assert.equal(deriveStage({ ...base, clips: 0 }), 'footage')
  assert.equal(deriveStage({ ...base, workflow: 'indexing' }), 'footage')
  assert.equal(deriveStage(base), 'brief')
  assert.equal(deriveStage({ ...base, brief: true }), 'cut')
  assert.equal(deriveStage({ ...base, workflow: 'story', brief: true }), 'brief')   // approved, nothing built yet
  assert.equal(deriveStage({ ...base, workflow: 'story', brief: true, proposals: true }), 'story')
  assert.equal(deriveStage({ ...base, workflow: 'styling', board: true }), 'story')
})

test('the steps already passed stay reachable', () => {
  assert.deepEqual(reached({ ...base, clips: 0 }), ['footage'])
  assert.deepEqual(reached({ ...base, brief: true }), ['footage', 'brief', 'cut'])
  assert.deepEqual(reached({ ...base, workflow: 'story', board: true }), ['footage', 'brief', 'cut', 'story'])
})

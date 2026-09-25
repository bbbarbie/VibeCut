import assert from 'node:assert/strict'
import { test } from 'node:test'
import { CREATIVE_TOOLS, makeBrief, readBriefs, storeBrief } from './creativeTools.ts'
import { emptyProfile } from './profile.ts'

test('all seven recording workflows can save independent briefs and creator snapshots', () => {
  const data = new Map<string, string>()
  const storage = { getItem: (k: string) => data.get(k) ?? null, setItem: (k: string, v: string) => { data.set(k, v) } }
  const creator = { ...emptyProfile(), name: 'Example', color: '#123456' }
  for (const tool of CREATIVE_TOOLS) storeBrief(storage, makeBrief(tool, tool.options[0], 'A short opening', '', creator))
  creator.name = 'Changed later'
  const loaded = readBriefs(storage)
  assert.equal(Object.keys(loaded).length, 7)
  for (const tool of CREATIVE_TOOLS) {
    assert.equal(loaded[tool.id].creator.name, 'Example')
    assert.equal(loaded[tool.id].creator.color, '#123456')
  }
})
test('briefs reject empty requests and unsupported options', () => {
  assert.throws(() => makeBrief(CREATIVE_TOOLS[0], 'Push in', '  ', '', emptyProfile()))
  assert.throws(() => makeBrief(CREATIVE_TOOLS[0], 'Nonexistent', 'Test', '', emptyProfile()))
})
test('malformed storage cannot be overwritten by saving a new brief', () => {
  let wrote = false
  const storage = { getItem: () => 'broken', setItem: () => { wrote = true } }
  assert.throws(() => storeBrief(storage, makeBrief(CREATIVE_TOOLS[0], 'Push in', 'Test', '', emptyProfile())))
  assert.equal(wrote, false)
})

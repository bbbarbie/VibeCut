import assert from 'node:assert/strict'
import { test } from 'node:test'
import { CREATIVE_TOOLS, guidedEditMessage, makeBrief, readBriefs, storeBrief, titlesRequest } from './creativeTools.ts'
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
test('the live guided edit becomes a constrained reversible storyboard request', () => {
  const tool = CREATIVE_TOOLS.find(t => t.id === 'guided-edit')!
  const creator = { ...emptyProfile(), pace: 'Quick' as const, avoid: 'flashy transitions' }
  const message = guidedEditMessage(makeBrief(tool, 'Daily vlog', 'Open on breakfast, then show the walk to class.', '', creator))
  assert.match(message, /daily vlog edit/)
  assert.match(message, /Open on breakfast/)
  assert.match(message, /quick pacing/)
  assert.match(message, /smallest reversible storyboard changes/)
  assert.throws(() => guidedEditMessage(makeBrief(CREATIVE_TOOLS[0], 'Push in', 'Move closer', '', creator)))
})
test('Titles & motion becomes a words-on-screen request carrying only the style it needs', () => {
  const tool = CREATIVE_TOOLS.find(t => t.id === 'motion-graphics')!
  const creator = { ...emptyProfile(), name: 'Mika', handle: 'mika', font: 'Editorial' as const, color: '#aabbcc', about: 'private notes' }
  const req = titlesRequest(makeBrief(tool, 'Part labels', 'Kyoto in three days', '', creator))
  assert.deepEqual(req.kinds, ['part'])
  assert.equal(req.title, 'Kyoto in three days')
  assert.deepEqual(Object.keys(req.profile).sort(), ['captionPosition', 'color', 'font', 'handle', 'name'])
  assert.throws(() => titlesRequest(makeBrief(CREATIVE_TOOLS[0], 'Push in', 'Move closer', '', creator)))
})

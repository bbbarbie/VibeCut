import assert from 'node:assert/strict'
import { test } from 'node:test'
import { decodeProfile, emptyProfile, loadProfile, PROFILE_KEY, safeReference, saveProfile } from './profile.ts'

test('creator preferences survive a fresh load independently of project state', () => {
  const data = new Map<string, string>()
  const storage = { getItem: (k: string) => data.get(k) ?? null, setItem: (k: string, v: string) => { data.set(k, v) } }
  const profile = { ...emptyProfile(), name: 'Sarah', vibes: ['Warm'], platforms: ['Instagram'],
    references: [{ url: 'https://example.com/video', note: 'Love the opening' }] }
  saveProfile(storage, profile)
  assert.deepEqual(loadProfile(storage), { profile, error: null })
  assert.equal(data.size, 1)
  assert.ok(data.has(PROFILE_KEY))
})
test('malformed and unsupported saved profiles recover with a visible error', () => {
  for (const raw of ['broken', 'null', '{"version":99}']) {
    const result = loadProfile({ getItem: () => raw })
    assert.deepEqual(result.profile, emptyProfile())
    assert.ok(result.error)
  }
})
test('untrusted fields cannot create unsafe links or unsupported styles', () => {
  const profile = decodeProfile(JSON.stringify({ version: 1, name: {}, vibes: ['Warm', 'unknown'],
    platforms: 'TikTok', color: 'red;display:none', pace: [], references: [
      null, { url: 'javascript:alert(1)', note: '' }, { url: 'https://example.com', note: 'Works' },
    ] }))
  assert.equal(profile.name, '')
  assert.deepEqual(profile.vibes, ['Warm'])
  assert.deepEqual(profile.platforms, [])
  assert.equal(profile.color, emptyProfile().color)
  assert.equal(profile.pace, 'Balanced')
  assert.equal(profile.references.length, 1)
  assert.equal(safeReference('data:text/html,test'), false)
  assert.equal(safeReference('not a url'), false)
})
test('storage errors are surfaced rather than claiming a successful save', () => {
  assert.throws(() => saveProfile({ setItem: () => { throw new Error('quota') } }, emptyProfile()), /quota/)
  assert.ok(loadProfile({ getItem: () => { throw new Error('blocked') } }).error)
})

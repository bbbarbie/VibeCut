// Where a project stands, from its state alone. The stepper, the primary
// action and the screen in the middle all read this one word, so they can
// never disagree.

export type Stage = 'footage' | 'brief' | 'cut' | 'story'
export const STAGES: { id: Stage; label: string; hint: string }[] = [
  { id: 'footage', label: 'Footage', hint: 'Your clips, read on this machine' },
  { id: 'brief', label: 'Style', hint: 'A few quick questions: length, pace, captions' },
  { id: 'cut', label: 'Rough trim', hint: 'Each clip trimmed to its best part' },
  { id: 'story', label: 'Edit', hint: 'Your video, shot by shot' },
]

export type StageInput = {
  clips: number
  workflow: string          // workflow.state on the session
  brief: boolean            // a description and style answers have been given
  proposals: boolean
  board: boolean
}

export function deriveStage(s: StageInput): Stage {
  if (s.clips === 0) return 'footage'
  if (s.workflow === 'intake' || s.workflow === 'indexing' || s.workflow === 'rough-cut') return 'footage'
  if (s.workflow === 'cut-review') return s.brief ? 'cut' : 'brief'
  // approved: the story exists once the brief has been turned into proposals
  if (s.proposals || s.board) return 'story'
  return 'brief'
}

/** Which steps are done, so the stepper can show ✓ and allow going back. */
export function reached(s: StageInput): Stage[] {
  const cur = deriveStage(s)
  const order: Stage[] = ['footage', 'brief', 'cut', 'story']
  const out = order.slice(0, order.indexOf(cur) + 1)
  // The gate was passed: the rough cut can be looked at again from the story.
  if (cur === 'story' && !out.includes('cut')) out.push('cut')
  return out
}

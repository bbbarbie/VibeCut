import { api } from './api'
import type { RefJob, Session } from './types'

// One step: a link (or a file path) in, the edit restyled out. Learns the
// video, starts from the chronological story if none is chosen yet, and
// borrows everything the reference offers that fits this edit. It is still
// one ordinary turn: Undo takes it back, and the style card can fine-tune.

export const STAGE: Record<RefJob['stage'], string> = {
  queued: 'Starting…', fetching: 'Downloading the video…', reading: 'Watching it…',
  learning: 'Learning its style…', done: 'Applying it to your video…', error: 'Failed',
}

export async function borrowNow(source: string, progress: (text: string, frac: number) => void): Promise<Session> {
  const rid = await learnRef(source, progress)
  return applyAll(rid, progress)
}

export async function learnRef(source: string, progress: (text: string, frac: number) => void): Promise<string> {
  let job = await api.refLearn(source.trim())
  while (job.stage !== 'done' && job.stage !== 'error') {
    progress(STAGE[job.stage], job.progress * 0.8)
    await new Promise((r) => setTimeout(r, 400))
    job = await api.refJob(job.id)
  }
  if (job.stage === 'error') throw new Error(job.error ?? 'Couldn’t learn from that video.')
  return job.rid
}

/** Everything the reference offers that fits this edit, as one turn. */
export async function applyAll(rid: string, progress: (text: string, frac: number) => void): Promise<Session> {
  progress(STAGE.done, 0.85)
  let card = await api.refCard(rid)
  if (!card.has_story) {
    const s = await api.session()
    const options = s.proposals?.options ?? []
    if (!options.length) throw new Error('Tell me in one line what your video is first (below) — then paste the link again.')
    const start = options.find((o) => o.key === 'time') ?? options[0]
    await api.ops([{ op: 'choose_option', option: start.key }], `Started from “${start.name}”`)
    card = await api.refCard(rid)
  }
  const traits = card.traits.filter((t) => t.available && t.on).map((t) => t.key)
  if (!traits.length) throw new Error('That video has nothing to borrow that fits this edit.')
  progress(STAGE.done, 0.95)
  return api.refApply(rid, traits, 'full')
}

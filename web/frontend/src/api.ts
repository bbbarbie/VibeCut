import type { SetupData } from './components/Setup'
import type { Habit, Capabilities, CutData, ExportJob, Job, LengthSlider, LookFit, PrefClass, Project, ProjectMeta, RefCard, RefJob, RefSummary, SceneWord, Session, StyleAnswers, StyleQuestion, TalkState } from './types'

export type MomentInfo = { header: string; key: string; llm: boolean; estimate: { tokens_in: number; usd: [number, number] } }
export type MomentAnswer = { reply: string; choices: string[]; ops: Record<string, unknown>[]
  preview: { lines: string[]; skipped: string[] } | null; header: string }

export type ProjectList = { projects: ProjectMeta[]; open: string | null; capabilities: Capabilities }
export type Opened = { project: ProjectMeta; session: Session }

export type VibeJob = { id: string; stage: 'learning' | 'done' | 'error'; lines: string[]; error: string | null; done: number; total: number; vibe: string | null; elapsed: number }

export type MakeJob = { id: string; stage: string; line: string; done: number; total: number; error: string | null; elapsed: number }

export type RemixJob = {
  id: string
  stage: 'queued' | 'references' | 'choosing' | 'music' | 'rendering' | 'done' | 'error'
  progress: number
  error: string | null
  lines: string[]
  elapsed: number
  file: string | null
  seconds: number | null
  music: { title: string; bpm: number; credit: string } | null
  fingerprint: string | null
  shots: number | null
}

async function j<T>(res: Promise<Response>): Promise<T> {
  const r = await res
  if (!r.ok) {
    let detail = r.statusText
    try { detail = (await r.json()).detail ?? detail } catch { /* not json */ }
    throw new Error(detail)
  }
  return r.json()
}

// Every change is a POST, and the server saves the project after each one:
// while none is in flight the draft is saved (the top bar says so).
let inFlight = 0
const savers = new Set<() => void>()
export const saving = {
  get: () => inFlight > 0,
  subscribe: (f: () => void) => { savers.add(f); return () => { savers.delete(f) } },
}
const post = (url: string, body: unknown) => {
  inFlight++
  savers.forEach((f) => f())
  return fetch(url, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) })
    .finally(() => { inFlight--; savers.forEach((f) => f()) })
}

export const api = {
  // projects: the dashboard's list, and which one is open
  projects: () => j<ProjectList>(fetch('/api/projects')),
  createProject: (name: string) => j<Opened>(post('/api/projects', { name })),
  openProject: (id: string) => j<Opened>(post(`/api/projects/${id}/open`, {})),
  closeProject: () => j<{ projects: ProjectMeta[]; open: null }>(post('/api/projects/close', {})),
  renameProject: (id: string, name: string) =>
    j<{ project: ProjectMeta }>(fetch(`/api/projects/${id}`, { method: 'PATCH', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ name }) })),
  deleteProject: (id: string) => j<{ projects: ProjectMeta[]; open: string | null }>(fetch(`/api/projects/${id}`, { method: 'DELETE' })),
  brief: (message: string | null, style?: StyleAnswers, said?: string) =>
    j<Session>(post('/api/project/brief', { message, style: style ?? null, said: said ?? '' })),
  project: () => j<Project>(fetch('/api/project')),
  clear: () => j<Project>(fetch('/api/project', { method: 'DELETE' })),
  locate: (files: { name: string; size: number; mtime: number; relpath: string }[]) =>
    j<{ resolved: Record<string, string>; missing: string[] }>(post('/api/locate', { files })),
  upload: (file: File, relpath: string, batch: string) =>
    j<{ path: string }>(fetch('/api/upload', {
      method: 'POST', body: file,
      headers: { 'x-relpath': encodeURIComponent(relpath), 'x-batch': batch },
    })),
  import: (paths: string[]) => j<Job>(post('/api/import', { paths })),
  job: (id: string) => j<Job>(fetch(`/api/jobs/${id}`)),
  session: () => j<Session>(fetch('/api/session')),
  cut: () => j<CutData>(fetch('/api/cut')),
  override: (target: string, action: string, range?: [number, number]) =>
    j<CutData>(post('/api/cut/override', { target, action, start: range?.[0] ?? null, end: range?.[1] ?? null })),
  approve: () => j<Session>(post('/api/cut/approve', {})),
  chat: (message: string, style?: StyleAnswers) => j<Session>(post('/api/chat', { message, style: style ?? null })),
  autoBrief: (picks?: { format: string; look: string }) => j<Session>(post('/api/brief/auto', picks ?? {})),
  setup: () => j<SetupData>(fetch('/api/brief/setup')),
  vibeStart: (req: { niche: string; name?: string; links: string[] }) => j<VibeJob>(post('/api/vibes', req)),
  vibeStatus: (id: string) => j<VibeJob>(fetch(`/api/vibes/jobs/${id}`)),
  vibeGet: (id: string) => j<{ id: string; name: string; recipe: any }>(fetch(`/api/vibes/${id}`)),
  get: (url: string) => j<any>(fetch(url)),
  profileGet: () => j<{ profile: Record<string, unknown> | null; at: number | null; cloud: { on: boolean } }>(fetch('/api/profile')),
  profilePut: (profile: Record<string, unknown>) => j<{ profile: Record<string, unknown>; at: number }>(post('/api/profile', { profile })),
  make: (picks: { format: string; look: string; music?: boolean; vibe?: string | null }) => j<MakeJob>(post('/api/make', picks)),
  makeStatus: (id: string) => j<MakeJob>(fetch(`/api/make/${id}`)),
  format: (format: string) => j<Session>(post('/api/format', { format })),
  pile: (clip: string, into: boolean) => j<Session>(post('/api/pile', { clip, into })),
  captions: (on: boolean) => j<Session>(post('/api/captions', { on })),
  bed: (on: boolean) => j<Session>(post('/api/bed', { on })),
  pace: (pace: string) => j<Session>(post('/api/pace', { pace })),
  guess: () => j<{ about: string }>(fetch('/api/brief/guess')),
  suggestions: () => j<{ suggestions: string[]; source: string }>(fetch('/api/brief/suggestions')),
  questions: (message: string) => j<{ questions: StyleQuestion[]; tailored: boolean }>(post('/api/brief/questions', { message })),
  ops: (ops: Record<string, unknown>[], label: string) => j<Session>(post('/api/ops', { ops, label })),
  length: () => j<LengthSlider & { current: number }>(fetch('/api/length')),
  setLength: (seconds: number) => j<Session & { length_note: string }>(post('/api/length', { seconds })),
  smooth: (order: boolean, nudge: boolean) => j<Session>(post('/api/smooth', { order, nudge })),
  // chat on pause: what the paused moment is (free), then one message about it (calls the model)
  moment: (t: number) => j<MomentInfo>(post('/api/moment', { t })),
  momentChat: (t: number, message: string, history: { who: 'you' | 'ai'; text: string }[]) =>
    j<MomentAnswer>(post('/api/moment/chat', { t, message, history })),
  toggle: (turn: number) => j<Session>(post(`/api/turns/${turn}/toggle`, {})),
  voiceover: (text: string) => j<Session>(post('/api/voiceover', { text })),
  suggest: (req: { id: string; klass: PrefClass | 'rejected'; rule?: string; scope?: string; counter?: string }) => j<Session>(post('/api/preferences/suggest', req)),
  classify: (req: { turn: number; klass: PrefClass; rule?: string; scope?: string; counter?: string; reason?: string }) =>
    j<Session>(post('/api/preferences/classify', req)),
  rule: (id: string, action: 'forget' | 'narrow') => j<Session>(post(`/api/preferences/${id}/${action}`, {})),
  suggestOverlays: (req: { profile: Record<string, unknown>; title?: string; kinds?: string[] }) =>
    j<Session>(post('/api/overlays/suggest', req)),
  exportCreate: (music: boolean) => j<ExportJob>(post('/api/export', { music })),
  exportFrame: (id: string, n: number, png: Blob) =>
    j<{ ok: boolean }>(fetch(`/api/export/${id}/frames/${n}`, { method: 'POST', body: png })),
  exportStart: (id: string, schedule: { frame: number | null; start: number; end: number }[]) =>
    j<ExportJob>(post(`/api/export/${id}/start`, { schedule })),
  exportStatus: (id: string) => j<ExportJob>(fetch(`/api/export/${id}`)),
  exportCancel: (id: string) => j<ExportJob>(post(`/api/export/${id}/cancel`, {})),
  talkStart: (req: { locale: string; script: string }) => j<TalkState>(post('/api/talk', req)),
  talkState: () => j<TalkState>(fetch('/api/talk')),
  talkToggle: (id: string) => j<TalkState>(post('/api/talk/toggle', { id })),
  talkApply: (captions: boolean, profile: Record<string, unknown>) => j<Session>(post('/api/talk/apply', { captions, profile })),
  exportReveal: (id: string) => fetch(`/api/export/${id}/reveal`, { method: 'POST' }),
  exportPhotos: (id: string) => j<{ ok: boolean }>(post(`/api/export/${id}/photos`, {})),
  habits: () => j<{ habits: Habit[]; phrases: string[]; last: { id: string; text: string }[] }>(fetch('/api/habits')),
  habitSwitch: (id: string, off: boolean, remake = false) => j<MakeJob & { habit?: Habit }>(post(`/api/habits/${encodeURIComponent(id)}`, { off, remake })),
  sceneVerdict: (beat: string, word: SceneWord) => j<Session>(post(`/api/scenes/${encodeURIComponent(beat)}/verdict`, { word })),
  exportVerdict: (n: number, wouldPost: boolean, note: string) => j<Session>(post(`/api/exports/${n}/verdict`, { post: wouldPost, note })),
  // Remix: reference reels + the shelf -> one finished short, then the board
  remixStart: (req: { refs: string[]; title?: string; sub?: string; length?: number }) =>
    j<RemixJob>(post('/api/remix', req)),
  remixStatus: (id: string) => j<RemixJob>(fetch(`/api/remix/${id}`)),
  // Borrow a feeling: a reference video's style, learnt and applied as one turn
  refLibrary: () => j<{ references: RefSummary[]; links: boolean }>(fetch('/api/references')),
  refLearn: (source: string) => j<RefJob>(post('/api/references', { source })),
  refJob: (id: string) => j<RefJob>(fetch(`/api/references/jobs/${id}`)),
  refCard: (rid: string) => j<RefCard>(fetch(`/api/references/${rid}`)),
  refLook: (rid: string, strength: 'subtle' | 'full') => j<LookFit>(post(`/api/references/${rid}/look`, { strength })),
  refApply: (rid: string, traits: string[], strength: 'subtle' | 'full') =>
    j<Session>(post(`/api/references/${rid}/apply`, { traits, strength })),
  refForget: (rid: string) => j<{ references: RefSummary[]; links: boolean }>(fetch(`/api/references/${rid}`, { method: 'DELETE' })),
  useTrack: (trackId: string | null) => j<Session>(post('/api/music/use', { track_id: trackId })),
}

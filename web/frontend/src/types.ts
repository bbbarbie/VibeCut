export type Shot = {
  id: string
  index: number
  start: number
  end: number
  best_t: number
  quality: number
  aesthetic: number | null
  labels: [string, number][]
  faces: number
  utility: boolean | null
  thumb: string
}

export type Clip = {
  id: string
  name: string
  duration: number
  width: number
  height: number
  capture_time: string | null
  gps: [number, number] | null
  sampling: string
  index_seconds: number
  video: string
  shots: Shot[]
  cut: { rejected: boolean; auto_rejected: boolean; zh: string; en: string; override: string | null
         flags: { code: string; zh: string; en: string }[]; windows: Record<string, [number, number]> } | null
}

export type Project = { clips: Clip[]; vision: string }

export type Job = {
  id: string
  known: number
  stage: 'queued' | 'indexing' | 'looking' | 'done' | 'error'
  done: number
  total: number
  errors: { path: string | null; error: string }[]
  vision: string | null
  elapsed: number
}

export type BeatShot = { id: string; clip_id: string; start: number; end: number; thumb: string; lean: boolean; gap?: boolean; why?: string }
export type Beat = { title: string; detail: string; lean: boolean; shots: BeatShot[] }
export type Option = {
  key: 'time' | 'place' | 'subject' | 'voice'
  name: string
  axis: string
  summary: string
  notes: string[]
  degraded: boolean
  same_order_as_time: number | null
  beats: Beat[]
  // the voiceover proposal only
  timing?: 'estimated' | 'text_only'
  gaps?: { line: number; text: string; at: number; dur: number; reason: string }[]
}
export type Proposals = {
  direction: string
  understood: { themes: string[]; used: string[]; ignored: string[]; matched_shots: number }
  notes: string[]
  options: Option[]
}

// The working storyboard -- edited by operations, never regenerated.
export type BoardShot = {
  id: string; key: string; clip_id: string | null; start: number; end: number; src_start: number; src_end: number
  thumb: string; lean: boolean; gap?: boolean
}
export type BoardBeat = { id: string; title: string; detail: string; shots: BoardShot[] }
export type Board = { option: string; name: string; structure: string; beats: BoardBeat[] }

export type DiffLine = {
  kind: 'removed' | 'added' | 'moved' | 'trimmed' | 'retitled' | 'swapped' | 'replaced' | 'none'
  text: string; beat?: string; shot?: string; thumb?: string
}
export type Diff = {
  beats: { removed: { id: string; title: string }[]; added: { id: string }[]; moved: { id: string }[]; retitled: { id: string }[] }
  shots: { removed: { id: string }[]; added: { id: string }[]; moved: { id: string }[]; trimmed: { id: string }[] }
  replaced: boolean
}
export type Turn = {
  id: number; kind: 'chat' | 'direct'; text: string; reply: string
  question: string | null; choices: string[]; lines: DiffLine[]; skipped: string[]
  undone: boolean; at: number; has_ops: boolean; direction: { themes: string[] } | null
}
import type { SeqItem } from './sequence'
import type { Target } from './snap'
export type TimelineData = { fps: number; total: number; items: SeqItem[]; targets: Target[]; grid: { bpm: number; phase: number } | null }
export type MusicTrack = { id: string; title: string; duration: number; bpm: number | null; audio: string }

export type CutSummary = { clips: number; kept: number; rejected: number; raw: number; cut: number; ratio: number | null; line_zh: string; line_en: string }
export type Workflow = { state: string; gate: string; decision: string | null; revision: number; history: { action: string; actor: string; note: string; at: number }[] }
export type CutShot = { id: string; full: [number, number]; auto: [number, number]; window: [number, number]; use: [number, number]
  target: number; whole: boolean; reason_zh: string; reason_en: string; notes: string[]; seconds: number[]; override: string | null }
export type CutClip = { id: string; name: string; duration: number; auto_rejected: boolean; rejected: boolean; override: string | null
  code: string; zh: string; en: string; flags: { code: string; zh: string; en: string }[]; talking: boolean; shots: Record<string, CutShot>
  evidence: string[]; unverified: string[] }
export type CutData = { workflow: Workflow; summary: CutSummary | null; clips: CutClip[] }

export type Session = {
  workflow: Workflow
  cut: CutSummary | null
  timeline: TimelineData
  music: MusicTrack | null
  board: Board | null
  structure_note: string | null
  last: { turn: number; diff: Diff | null; ghosts: { index: number; title: string; thumbs: string[] }[] } | null
  turns: Turn[]
  proposals: Proposals | null
  llm: boolean
  preferences: Preferences
  voiceover: { source: string; timing: 'estimated' | 'text_only'; lines: number; total: number } | null
}

// What edits teach -- only once the creator has sorted them.
export type PrefClass = 'long_term' | 'project' | 'single_edit' | 'compliance_fix' | 'rejected'
export type PrefCandidate = {
  turn: number; said: string; kind: 'chat' | 'direct'; lines: string[]; suggested: PrefClass
  readable: boolean; status: 'candidate' | 'confirmed' | 'rejected'; klass: PrefClass | null; rule: string | null
}
export type PrefRule = {
  id: string; klass: 'long_term' | 'project'; rule: string; scope: string; counter: string; reason: string
  active: boolean; evidence: { said: string; changed: string[] }; history: { at: number; action: string; klass: string; actor: string }[]
}
export type Preferences = { candidates: PrefCandidate[]; rules: PrefRule[] }

export type TimelineItem = { uid: string; shotId: string; clipId: string; start: number; end: number; thumb: string; beatId: string; beatTitle: string; mark?: Mark }
export type Mark = 'added' | 'moved' | 'trimmed'

export type Msg = { id: string; role: 'user' | 'app'; text: string; busy?: boolean; at: number }

// What the player is showing: one span of one file.
export type Segment = { key: string; clipId: string; start: number; end: number; autoplay: boolean }

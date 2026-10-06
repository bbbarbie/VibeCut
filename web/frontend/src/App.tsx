import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api } from './api'
import { Chat, type ChatItem } from './components/Chat'
import { KIND_META, partsOf } from './overlayDraw'
import { loadProfile } from './profile'
import { CutReview } from './components/CutReview'
import { StyleQuestions } from './components/StyleQuestions'
import { composeBrief, sayPicks, type Picks } from './brief'
import { Export } from './components/Export'
import { Remix } from './components/Remix'
import { BorrowStyle } from './components/BorrowStyle'
import { Overlays } from './components/Overlays'
import { TalkCut } from './components/TalkCut'
import { Keys } from './components/Keys'
import { Player } from './components/Player'
import { PauseChat } from './components/PauseChat'
import { LengthButton } from './components/LengthButton'
import type { OverlayEdit } from './components/OverlayCanvas'
import { Menu, SwapPicker, type MenuItem } from './components/Menus'
import { Music } from './components/Music'
import type { ClassifyReq } from './components/Remember'
import { Shelf } from './components/Shelf'
import { SmoothButton, Story, type PlayItem, type Selection } from './components/Story'
import { Timeline, type Marks } from './components/Timeline'
import { Footage, type Importing } from './components/Footage'
import { Brief } from './components/Brief'
import { fromDataTransfer, fromInput, takeHandoff, type Picked } from './drop'
import { bytes, uid } from './format'
import { clock, locate, toSource } from './sequence'
import { cutWhilePlaying, step } from './snap'
import { byKey } from './joinView'
import { go } from './router'
import { deriveStage, reached, STAGES, type Stage } from './stage'
import { phStore, snapStore, transport, transportStore, useStore } from './transport'
import { Button, Confirm, cx, Wordmark } from './ui'
import type { Capabilities, Clip, CutData, Msg, Option, Overlay, OverlayKind, Overlays as OverlayData, Segment, Session, Shot, StyleAnswers, StyleQuestion, TimelineData } from './types'

const hello: Msg = {
  id: 'hello', role: 'app', at: 0,
  text: 'Pick a story, then tell me what to change: “the opening is too slow”, “take out the market”, “end on the sunset”. Each message edits — nothing is regenerated, and everything can be undone.',
}
const EMPTY_TL: TimelineData = { fps: 30, total: 0, items: [], targets: [], grid: null }
const EMPTY_OVERLAYS: OverlayData = {
  items: [], findings: [], style: { font: 'Clean', color: '#ffffff', accent: '#b9d9eb', captions: 'bottom', backing: 'shadow' },
}
const NO_CAPS: Capabilities = { llm: false, speech: false, vision: 'unavailable', links: false, music_folder: null, platform: '' }
const shortDate = (iso: string | null | undefined) => {
  const m = iso?.match(/^(\d{4})-(\d\d)-(\d\d)/)
  if (!m) return null
  const d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]))
  return d.toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' }).replace(/,/g, '').toUpperCase()
}
const r3 = (x: number) => Math.round(x * 1000) / 1000

type Queue = { source: string; items: PlayItem[]; index: number }

function useNarrow(px = 1100): boolean {
  const [n, setN] = useState(() => window.innerWidth < px)
  useEffect(() => {
    const mq = window.matchMedia(`(max-width: ${px - 1}px)`)
    const f = () => setN(mq.matches)
    mq.addEventListener('change', f)
    return () => mq.removeEventListener('change', f)
  }, [px])
  return n
}

// One project's workspace. The stage in the middle (Footage · Brief ·
// Rough cut · Story) is derived from the project's state, never set by
// hand; the stepper only lets you look back at an earlier one.
export default function App({ id, view }: { id: string; view: 'story' | 'frames' }) {
  const level = view
  const setLevel = (k: 'story' | 'frames') => go({ kind: 'project', id, view: k })
  const narrow = useNarrow()
  const [opened, setOpened] = useState<'loading' | 'ok' | string>('loading')
  const [clips, setClips] = useState<Clip[]>([])
  const [session, setSession] = useState<Session | null>(null)
  const [local, setLocal] = useState<Msg[]>([hello])
  const [importing, setImporting] = useState<Importing>(null)
  const [dragging, setDragging] = useState(false)
  const [pending, setPending] = useState<string | null>(null)
  const [selected, setSelected] = useState<string | null>(null)   // Frames: timeline entry
  const [storySel, setStorySel] = useState<Selection>(null)
  const [menu, setMenu] = useState<{ kind: 'story-shot' | 'frames-shot' | 'gap'; key: string; anchor: DOMRect } | null>(null)
  const [swap, setSwap] = useState<{ key: string; thumb: string; id: string } | null>(null)
  const [undoable, setUndoable] = useState<{ turn: number; text: string } | null>(null)
  // The rough cut and its gate.
  const [cutData, setCutData] = useState<CutData | null>(null)
  const [approving, setApproving] = useState(false)
  const [segment, setSegment] = useState<Segment | null>(null)
  const [queue, setQueue] = useState<Queue | null>(null)
  const [marks, setMarks] = useState<Marks>({ in: null, out: null })
  const [flash, setFlash] = useState<string | null>(null)
  const [alt, setAlt] = useState(false)
  const [help, setHelp] = useState(false)
  const [selOverlay, setSelOverlay] = useState<string | null>(null)
  const [framesTab, setFramesTab] = useState<'shots' | 'words'>('shots')
  const [exporting, setExporting] = useState(false)
  const [remixing, setRemixing] = useState(false)
  const [referencing, setReferencing] = useState(false)
  const [talkOpen, setTalkOpen] = useState(false)
  const [more, setMore] = useState(false)
  const [chatOpen, setChatOpen] = useState(false)     // narrow screens: the chat as a drawer
  const [restart, setRestart] = useState(false)
  const [renaming, setRenaming] = useState(false)
  // Looking back at an earlier stage without leaving the story.
  const [peek, setPeek] = useState<Stage | null>(null)
  // The style questions after the first description.
  const [asking, setAsking] = useState<{ text: string; questions: StyleQuestion[] | null; tailored: boolean } | null>(null)
  const dragDepth = useRef(0)
  const videoRef = useRef<HTMLVideoElement>(null)
  const backRef = useRef<HTMLVideoElement>(null)
  const veilRef = useRef<HTMLDivElement>(null)
  const musicRef = useRef<HTMLAudioElement>(null)
  const mixRef = useRef<HTMLAudioElement>(null)
  const [boardPlay, setBoardPlay] = useState(false)
  const [boardShot, setBoardShot] = useState<string | null>(null)
  const tr = useStore(transportStore)
  const tl = session?.timeline ?? EMPTY_TL
  const fr = 1 / tl.fps
  const ovData = session?.overlays ?? EMPTY_OVERLAYS
  const caps = session?.capabilities ?? NO_CAPS
  const brief = session?.brief ?? null
  const parts = useMemo(() => partsOf(tl.items), [tl.items])
  const overlayView = useMemo(() => ({ items: ovData.items, style: ovData.style, parts }), [ovData, parts])
  const profileInitial = useMemo(() => {
    try { return loadProfile(window.localStorage).profile.name.trim().charAt(0).toUpperCase() || '☺' } catch { return '☺' }
  }, [])

  const shots = useMemo(() => {
    const m = new Map<string, { clip: Clip; shot: Shot }>()
    for (const c of clips) for (const s of c.shots) m.set(s.id, { clip: c, shot: s })
    return m
  }, [clips])

  const refresh = useCallback(async () => {
    const [p, s] = await Promise.all([api.project(), api.session()])
    setClips(p.clips)
    setSession(s)
  }, [])

  useEffect(() => {
    let live = true
    api.openProject(id)
      .then(async (r) => { if (!live) return; setSession(r.session); const p = await api.project(); if (live) { setClips(p.clips); setOpened('ok') } })
      .catch((e) => { if (live) setOpened((e as Error).message || 'This project could not be opened.') })
    transport.attach(videoRef.current, backRef.current, veilRef.current)
    return () => { live = false; transport.stop() }
  }, [id])
  useEffect(() => { transport.setItems(tl.items, tl.total) }, [tl])
  useEffect(() => {
    const byId = new Map(clips.map((c) => [c.id, c.samples]))
    transport.setSamples((id, t) => {
      const s = byId.get(id)
      if (!s?.times.length) return null
      let k = 0
      s.times.forEach((x, i) => { if (Math.abs(x - t) < Math.abs(s.times[k] - t)) k = i })
      return `${s.base}${k}`
    })
  }, [clips])
  const wfState = session?.workflow?.state
  useEffect(() => { if (wfState && wfState !== 'intake') api.cut().then(setCutData).catch(() => {}) }, [wfState, clips])
  const atGate = wfState === 'cut-review'

  // ---- where we are ----------------------------------------------------------
  const stage: Stage = deriveStage({
    clips: clips.length, workflow: wfState ?? 'intake', brief: !!brief,
    proposals: !!session?.proposals, board: !!session?.board,
  })
  const done = reached({ clips: clips.length, workflow: wfState ?? 'intake', brief: !!brief, proposals: !!session?.proposals, board: !!session?.board })
  const shown: Stage = peek && done.includes(peek) ? peek : stage
  useEffect(() => { if (peek && !done.includes(peek)) setPeek(null) }, [peek, done])
  useEffect(() => { if (shown !== 'story' && level === 'frames') setLevel('story') }, [shown]) // eslint-disable-line react-hooks/exhaustive-deps
  // Once a story is chosen the edit lives in Frames (sarah, 2026-10-04): opening
  // the project lands there; the Story view stays one click away.
  const [othersOpen, setOthersOpen] = useState(false)
  const landed = useRef(false)
  useEffect(() => {
    // wait until the stage is known (clips and the gate load after the session)
    if (landed.current || !session?.board || shown !== 'story') return
    landed.current = true
    if (level === 'story' && !othersOpen) setLevel('frames')
  }, [session, shown]) // eslint-disable-line react-hooks/exhaustive-deps
  const showStep = (s: Stage) => { setPeek(s === stage ? null : s); setMenu(null); stopQueue(); setSegment(null); if (s !== 'story') transport.stop() }

  const cutOverride = async (target: string, action: string, range?: [number, number]) => {
    setCutData(await api.override(target, action, range))
    await refresh()
  }
  const approveCut = async () => {
    setApproving(true)
    try {
      const s = await api.approve()
      setSession(s)
      setPeek(null)
      // The creator already said what the video is and how it should feel.
      if (s.brief && !s.proposals && !s.board) await send(s.brief.message, s.brief.style)
    } catch (e) { note((e as Error).message) } finally { setApproving(false) }
  }
  useEffect(() => {
    transport.attach(videoRef.current, backRef.current, veilRef.current)
    if (level === 'frames') transport.seek(phStore.get())
    else transport.stop()
    setMenu(null)
  }, [level, shown])
  useEffect(() => { transport.audio = session?.music ? musicRef.current : null }, [session?.music])
  const mixKey = session?.mix?.key
  const transList = session?.mix?.transitions
  useEffect(() => { transport.setTransitions(byKey(transList), tl.fps) }, [transList, tl.fps])
  useEffect(() => { transport.mix = mixKey ? mixRef.current : null; transport.mixBroken = false }, [mixKey])
  useEffect(() => { if (!tr.playing) setBoardPlay(false) }, [tr.playing])
  useEffect(() => {
    if (!boardPlay) { setBoardShot(null); return }
    const show = () => {
      const k = locate(tl.items, phStore.get())
      const it = k < 0 ? null : tl.items[k]
      setBoardShot(it && it.kind === 'shot' ? it.key : null)
    }
    show()
    return phStore.subscribe(show)
  }, [boardPlay, tl.items])

  const say = useCallback((text: string, busy = false) => {
    const id = uid()
    setLocal((ms) => [...ms, { id, role: 'app', text, busy, at: Date.now() }])
    return (next: string, stillBusy = false) =>
      setLocal((ms) => ms.map((m) => (m.id === id ? { ...m, text: next, busy: stillBusy } : m)))
  }, [])

  const flashTimer = useRef<number | undefined>(undefined)
  const undoTimer = useRef<number | undefined>(undefined)
  const note = (text: string) => {
    setFlash(text)
    window.clearTimeout(flashTimer.current)
    flashTimer.current = window.setTimeout(() => setFlash(null), 2800)
  }

  // ---- chat ------------------------------------------------------------------
  const chatItems: ChatItem[] = useMemo(() => {
    const out: (ChatItem & { at: number })[] = [
      ...local.map((m) => ({ type: 'local' as const, msg: m, at: m.at })),
      ...(session?.turns ?? []).map((t) => ({ type: 'turn' as const, turn: t, at: t.at * 1000 })),
    ]
    return out.sort((a, b) => a.at - b.at)
  }, [local, session])

  const send = async (text: string, style?: StyleAnswers) => {
    if (!clips.length) {
      setLocal((ms) => [...ms, { id: uid(), role: 'user', text, at: Date.now() }])
      say('Add some clips first — then there’s something to arrange.')
      return
    }
    // The first description: ask a few style questions before anything is built.
    if (!style && !session?.board && !session?.proposals && !brief) { askStyle(text); return }
    setPending(text)
    try {
      setSession(await api.chat(text, style))
      setPeek(null)
    } catch (e) {
      setLocal((ms) => [...ms, { id: uid(), role: 'user', text, at: Date.now() }])
      say((e as Error).message)
    } finally {
      setPending(null)
    }
  }

  const askStyle = (text: string) => {
    setAsking({ text, questions: null, tailored: false })
    api.questions(text)
      .then((r) => setAsking((a) => a && a.text === text ? { ...a, questions: r.questions, tailored: r.tailored } : a))
      .catch(() => setAsking((a) => a && a.text === text ? { ...a, questions: [] } : a))
  }
  // No "what's this video about?" any more (sarah, 2026-10-06): the clips
  // say it (day / trip, what's in them), and the questions open straight away.
  const startQuestions = () => {
    if (asking) return
    api.guess().then((r) => r.about, () => '').then((about) => askStyle(about || 'My video'))
  }
  const answered = async (picks: Picks, extra: string) => {
    if (!asking?.questions) return
    const { text, questions } = asking
    setAsking(null)
    const b = { ...composeBrief(text, questions, picks, extra), said: sayPicks(questions, picks) }
    try {
      const s = await api.brief(b.message, b.style, b.said)
      setSession(s)
      setPeek(null)
      // Past the gate already (approved earlier, nothing built): build now.
      if (s.workflow.state !== 'cut-review' && !s.proposals && !s.board) await send(b.message, b.style)
    } catch (e) { note((e as Error).message) }
  }

  const offerUndo = (s: Session) => {
    const t = s.turns.at(-1)
    if (t?.skipped.length) note(`Couldn’t: ${t.skipped[0]}`)
    if (t && t.lines.length && !t.skipped.length) {
      setUndoable({ turn: t.id, text: t.lines.map((l) => l.text).join(' · ') })
      window.clearTimeout(undoTimer.current)
      undoTimer.current = window.setTimeout(() => setUndoable(null), 7000)
    }
  }

  const run = async (ops: Record<string, unknown>[], label: string) => {
    try {
      const s = await api.ops(ops, label)
      setSession(s)
      offerUndo(s)
      return s
    } catch (e) {
      note(`Couldn’t apply that: ${(e as Error).message}`)
      return null
    }
  }

  const toggle = async (turn: number) => { setSession(await api.toggle(turn)) }
  const classify = async (req: ClassifyReq) => { setSession(await api.classify(req)) }
  const changeRule = async (id: string, action: 'forget' | 'narrow') => {
    try { setSession(await api.rule(id, action)) } catch (e) { note((e as Error).message) }
  }

  // ---- import ----------------------------------------------------------------
  const runImport = useCallback(async (paths: string[], picked: number, sizeText: string) => {
    let job = await api.import(paths)
    while (job.stage !== 'done' && job.stage !== 'error') {
      const frac = job.stage === 'looking' ? 0.95 : 0.3 + 0.6 * (job.done / Math.max(1, job.total))
      setImporting({ frac, text: job.stage === 'looking'
        ? `Read ${job.total} clip${job.total === 1 ? '' : 's'}. Looking at what’s in each shot…`
        : `Reading clip ${Math.min(job.done + 1, job.total)} of ${job.total}${sizeText} — shots, capture time, place, quality, sound…` })
      await new Promise((r) => setTimeout(r, 250))
      job = await api.job(job.id)
    }
    await refresh()
    const added = job.total - job.errors.length
    if (job.stage === 'error') throw new Error(job.errors.at(-1)?.error ?? 'The import failed.')
    return { added, known: job.known, errors: job.errors.length, picked }
  }, [refresh])

  const importPicked = useCallback(async (picked: Picked[]) => {
    if (!picked.length) { note('No .mp4 or .mov files in that drop.'); return }
    if (importing) return
    // Stay on the footage screen while it reads: the creator sees the clips
    // land and moves on when they choose to, not when the machine is done.
    if (shown === 'footage') setPeek('footage')
    const size = picked.reduce((n, p) => n + p.file.size, 0)
    setImporting({ frac: 0.03, text: `Found ${picked.length} clip${picked.length === 1 ? '' : 's'} (${bytes(size)}). Finding ${picked.length === 1 ? 'it' : 'them'} on disk…` })
    try {
      const loc = await api.locate(picked.map((p) => ({
        name: p.file.name, size: p.file.size, mtime: p.file.lastModified, relpath: p.relpath,
      })))
      const paths = picked.map((p) => loc.resolved[p.relpath]).filter(Boolean)
      const missing = picked.filter((p) => !loc.resolved[p.relpath])
      if (missing.length) {
        const batch = uid()
        let k = 0
        for (const p of missing) {
          setImporting({ frac: 0.05 + 0.25 * (k / missing.length), text: `Copying ${missing.length} clip${missing.length === 1 ? '' : 's'} I couldn’t find on disk into the local cache… ${k}/${missing.length}` })
          paths.push((await api.upload(p.file, p.relpath, batch)).path)
          k++
        }
      }
      const r = await runImport(paths, picked.length, ` (${bytes(size)})`)
      const known = r.known ? ` (${r.known} already here)` : ''
      const line = `Added ${r.added} clip${r.added === 1 ? '' : 's'}${known}${r.errors ? ` · ${r.errors} couldn’t be read` : ''}.`
      if (stage === 'story') say(`${line} ${session?.board ? 'They’re on the shelf — nothing in your story changed.' : 'They’re on the shelf.'}`)
      else note(line)
    } catch (e) {
      note(`Import failed: ${(e as Error).message}`)
    } finally {
      setImporting(null)
    }
  }, [importing, runImport, say, stage, shown, session?.board])

  // Clips picked on the home page before this video existed: read them now.
  useEffect(() => {
    if (opened !== 'ok') return
    const p = takeHandoff()
    if (p?.length) importPicked(p)
  }, [opened]) // eslint-disable-line react-hooks/exhaustive-deps

  const retryImport = async (paths: string[]) => {
    if (importing) return
    setImporting({ frac: 0.03, text: `Trying ${paths.length} file${paths.length === 1 ? '' : 's'} again…` })
    try { const r = await runImport(paths, paths.length, ''); note(`Added ${r.added} clip${r.added === 1 ? '' : 's'}${r.errors ? ` · ${r.errors} still can’t be read` : ''}.`) }
    catch (e) { note((e as Error).message) }
    finally { setImporting(null) }
  }

  useEffect(() => {
    const isFiles = (e: DragEvent) => e.dataTransfer?.types.includes('Files')
    const enter = (e: DragEvent) => { if (isFiles(e)) { dragDepth.current++; setDragging(true) } }
    const leave = (e: DragEvent) => { if (isFiles(e) && --dragDepth.current <= 0) { dragDepth.current = 0; setDragging(false) } }
    const over = (e: DragEvent) => { if (isFiles(e)) e.preventDefault() }
    const drop = async (e: DragEvent) => {
      if (!isFiles(e)) return
      e.preventDefault()
      dragDepth.current = 0
      setDragging(false)
      importPicked(await fromDataTransfer(e.dataTransfer!))
    }
    window.addEventListener('dragenter', enter)
    window.addEventListener('dragleave', leave)
    window.addEventListener('dragover', over)
    window.addEventListener('drop', drop)
    return () => {
      window.removeEventListener('dragenter', enter)
      window.removeEventListener('dragleave', leave)
      window.removeEventListener('dragover', over)
      window.removeEventListener('drop', drop)
    }
  }, [importPicked])

  // ---- previews (shelf, storyboard cards): a queue of spans ------------------
  const stopQueue = () => { setQueue(null) }
  const playAt = (q: Queue, k: number) => {
    const it = q.items[k]
    if (!it) { stopQueue(); videoRef.current?.pause(); return }
    transport.stop()
    setQueue({ ...q, index: k })
    setSegment({ key: uid(), clipId: it.clipId, start: it.start, end: it.end, autoplay: true })
  }
  const playSource = (source: string, list: PlayItem[]) => {
    if (source === 'board') {
      if (boardPlay) { transport.stop(); return }
      stopQueue()
      setSegment(null)
      transport.attach(videoRef.current, backRef.current, veilRef.current)
      transport.seek(0)
      transport.play(1)
      setBoardPlay(true)
      return
    }
    if (boardPlay) transport.stop()
    if (queue?.source === source) { stopQueue(); videoRef.current?.pause(); return }
    if (list.length) playAt({ source, items: list, index: 0 }, 0)
  }
  // A shot or a part of the story plays as the edit, not as its raw clip, so
  // its words on screen, joins and sound are what you see.
  const until = useRef<number | null>(null)
  const playEdit = (from: number, to: number) => {
    stopQueue()
    setSegment(null)
    transport.stop()
    transport.attach(videoRef.current, backRef.current, veilRef.current)
    transport.seek(from)
    until.current = to
    transport.play(1)
    setBoardPlay(true)
  }
  useEffect(() => phStore.subscribe(() => {
    if (until.current != null && phStore.get() >= until.current - 0.03) { until.current = null; transport.stop() }
  }), [])
  useEffect(() => { if (!tr.playing) until.current = null }, [tr.playing])
  const spanOf = (keys: string[]) => {
    const its = tl.items.filter((x) => keys.includes(x.key))
    return its.length ? [Math.min(...its.map((x) => x.seq_start)), Math.max(...its.map((x) => x.seq_end))] as const : null
  }
  const preview = (clipId: string, start: number, end: number, shotId: string) => {
    transport.stop()
    stopQueue()
    setSegment({ key: shotId + uid(), clipId, start, end, autoplay: true })
  }
  const timelineOwns = () => { stopQueue(); setSegment(null) }

  // ---- the edit at the playhead ------------------------------------------------
  const tlRef = useRef(tl)
  tlRef.current = tl
  const here = (t: number) => {
    const items = tlRef.current.items
    const k = locate(items, t)
    return k < 0 ? null : items[k]
  }

  const cutAt = async (t: number, why = '') => {
    const it = here(t)
    if (!it) return
    if (it.kind === 'gap') { note('Nothing to cut in a gap'); return }
    if (t - it.seq_start < fr / 2 || it.seq_end - t < fr / 2) { note(`Already a cut at ${clock(t)}`); return }
    const s = await run([{ op: 'split', shot: it.key, at: r3(toSource(it, t)) }], `You cut shot ${it.n} at ${clock(t)}`)
    if (s) note(why || `Cut at ${clock(t)}`)
  }

  const cut = () => {
    const t = phStore.get()
    if (transportStore.get().playing) {
      const r = cutWhilePlaying(tlRef.current.targets, t)
      const d = r.t - t
      cutAt(r.t, r.target ? `Cut on ${r.target.label} (${d >= 0 ? '+' : ''}${d.toFixed(2)}s from your tap)`
        : `Cut at ${clock(t)} — nothing to snap to nearby`)
    } else {
      cutAt(t)
    }
  }

  const trimToPlayhead = async (edge: 'in' | 'out', leaveGap: boolean) => {
    const t = phStore.get()
    const it = here(edge === 'out' ? t - 1e-6 : t)
    if (!it || it.kind === 'gap') { note('Put the playhead inside a shot'); return }
    const s = await run([{ op: 'trim', shot: it.key, edge, to: r3(toSource(it, t)), leave_gap: leaveGap || undefined }],
      `You trimmed the ${edge === 'in' ? 'start' : 'end'} of shot ${it.n} to the playhead${leaveGap ? ' (gap left)' : ''}`)
    if (s && edge === 'in' && !leaveGap) transport.seek(it.seq_start)
  }

  const trimBy = (units: number, unit: 'frame' | 'second' | 'beat') => {
    const t = phStore.get()
    const it = here(t)
    if (!it || it.kind === 'gap') { note('Put the playhead inside a shot'); return }
    const g = tlRef.current.grid
    if (unit === 'beat' && !g) { note('No beat grid — pick a track with a steady tempo under “Music”'); return }
    const size = unit === 'frame' ? fr : unit === 'second' ? 1 : 60 / g!.bpm
    const word = unit === 'frame' ? 'frame' : unit === 'second' ? 'second' : 'beat'
    run([{ op: 'trim', shot: it.key, edge: 'out', to: r3(it.src_end + units * size) }],
      `You made shot ${it.n} one ${word} ${units < 0 ? 'shorter' : 'longer'}`)
  }

  const deleteSelection = async (leaveGap: boolean) => {
    const items = tlRef.current.items
    if (marks.in != null && marks.out != null && marks.out > marks.in) {
      let a = marks.in
      let z = marks.out
      const ia = items[locate(items, a)]
      const iz = items[locate(items, z - 1e-6)]
      if (ia.kind === 'gap') a = ia.seq_start
      if (iz.kind === 'gap') z = iz.seq_end
      const s = await run([{
        op: 'drop_range', from_shot: ia.key, from_at: r3(toSource(ia, a)),
        to_shot: iz.key, to_at: r3(toSource(iz, z)), leave_gap: leaveGap || undefined,
      }], `You ${leaveGap ? 'lifted' : 'removed'} ${clock(a)}–${clock(z)}`)
      if (s) { setMarks({ in: null, out: null }); transport.seek(a) }
      return
    }
    if (selected) {
      const it = items.find((i) => i.key === selected)
      await run([{ op: 'drop_shot', shot: selected, leave_gap: leaveGap || undefined }],
        `You ${leaveGap ? 'lifted' : 'deleted'} ${it?.kind === 'gap' ? 'a gap' : `shot ${it?.n}`}`)
      setSelected(null)
      return
    }
    note('Select a shot, or mark In (I) and Out (O), then Delete')
  }

  const goTo = (t: number, target: Parameters<typeof snapStore.set>[0] = null) => {
    transport.seek(t)
    snapStore.set(target)
  }

  // ---- keyboard: industry conventions ----------------------------------------
  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (exporting || referencing || remixing || restart || renaming) return
      if (e.key === 'Alt') setAlt(true)
      const tag = (e.target as HTMLElement).tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA') return
      if (shown !== 'story') return
      if (level !== 'frames' && !((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'z')) return
      const t = phStore.get()
      const mod = e.metaKey || e.ctrlKey
      const k = e.key.toLowerCase()
      const playing = transportStore.get().playing
      const rate = transportStore.get().rate
      let handled = true

      if (mod && k === 'z') {
        const turns = session?.turns ?? []
        const target = e.shiftKey ? [...turns].reverse().find((x) => x.undone && x.has_ops)
          : [...turns].reverse().find((x) => !x.undone && x.has_ops)
        if (target) toggle(target.id)
      } else if ((mod && k === 'k') || (k === 'b' && !mod)) cut()
      else if (e.code === 'Space') { timelineOwns(); if (playing) transport.stop(); else { snapStore.set(null); transport.play(1) } }
      else if (k === 'l' && !mod) { timelineOwns(); snapStore.set(null); transport.play(playing && rate > 0 ? Math.min(rate * 2, 8) : 1) }
      else if (k === 'j' && !mod) { timelineOwns(); snapStore.set(null); transport.play(playing && rate < 0 ? Math.max(rate * 2, -8) : -1) }
      else if (k === 'k' && !mod) transport.stop()
      else if (k === 'i' && !mod) { setMarks((m) => ({ in: t, out: m.out != null && m.out > t ? m.out : null })); note(`In at ${clock(t)}`) }
      else if (k === 'o' && !mod) { setMarks((m) => ({ in: m.in != null && m.in < t ? m.in : null, out: t })); note(`Out at ${clock(t)}`) }
      else if (k === 'x' && e.altKey) { setMarks({ in: null, out: null }); note('Marks cleared') }
      else if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
        const dir = e.key === 'ArrowRight' ? 1 : -1
        if (playing) transport.stop()
        if (e.altKey) {
          const g = step(tlRef.current.targets, t, dir)
          if (g) goTo(g.t, { target: g, snapped: true })
        } else goTo(t + dir * (e.shiftKey ? 1 : fr))
      } else if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
        if (playing) transport.stop()
        const g = step(tlRef.current.targets, t, e.key === 'ArrowDown' ? 1 : -1, 'shot')
        if (g) goTo(g.t, { target: g, snapped: true })
      } else if (k === 'q' && !mod) trimToPlayhead('in', e.altKey)
      else if (k === 'w' && !mod) trimToPlayhead('out', e.altKey)
      else if (e.key === ',' || e.key === '.' || e.key === '<' || e.key === '>' || e.code === 'Comma' || e.code === 'Period') {
        const units = e.code === 'Comma' || e.key === ',' || e.key === '<' ? -1 : 1
        trimBy(units, mod ? 'beat' : e.shiftKey ? 'second' : 'frame')
      } else if (e.key === 'Delete' || e.key === 'Backspace') deleteSelection(e.altKey)
      else if (e.key === '?') setHelp((h) => !h)
      else if (e.key === 'Escape') { setHelp(false); setSelected(null) }
      else handled = false
      if (handled) e.preventDefault()
    }
    const up = (e: KeyboardEvent) => { if (e.key === 'Alt') setAlt(false) }
    const blur = () => setAlt(false)
    window.addEventListener('keydown', down)
    window.addEventListener('keyup', up)
    window.addEventListener('blur', blur)
    return () => {
      window.removeEventListener('keydown', down)
      window.removeEventListener('keyup', up)
      window.removeEventListener('blur', blur)
    }
  })

  // ---- direct timeline edits ----------------------------------------------------
  const reorder = (key: string, to: number) => {
    const items = tl.items
    const from = items.findIndex((x) => x.key === key)
    if (from < 0 || to === from || to === from + 1) return
    const rest = items.filter((x) => x.key !== key)
    const target = rest[to > from ? to - 1 : to]
    run([target ? { op: 'move_shot', shot: key, beat: target.beat_id, before: target.key }
      : { op: 'move_shot', shot: key, beat: rest.at(-1)?.beat_id ?? null }], 'You moved a shot on the timeline')
  }
  const insertShot = (shotId: string, at: number) => {
    const items = tl.items
    const onBoard = items.find((i) => i.key === shotId)
    if (onBoard) { reorder(onBoard.key, at); return }
    const target = items[at]
    run([target ? { op: 'add_shot', shot: shotId, beat: target.beat_id, before: target.key }
      : { op: 'add_shot', shot: shotId, beat: items.at(-1)?.beat_id ?? null }], 'You added a shot from the shelf')
  }
  const beatById = (id: string) => session?.board?.beats.find((b) => b.id === id)
  const beatIndex = (id: string) => session?.board?.beats.findIndex((b) => b.id === id) ?? -1
  const beatAction = (action: 'play' | 'up' | 'down' | 'remove' | 'frames', id: string) => {
    const b = beatById(id)
    if (!b) return
    const i = beatIndex(id)
    if (action === 'play') {
      const span = spanOf(b.shots.map((x) => x.key))
      if (span) playEdit(span[0], span[1])
      else playSource(`beat:${id}`, b.shots.filter((x) => !x.gap && x.clip_id).map((x) => ({ id: x.id, clipId: x.clip_id!, start: x.start, end: x.end })))
    } else if (action === 'up') run([{ op: 'move_beat', beat: id, to_index: i - 1 }], `You moved “${b.title}” up`)
    else if (action === 'down') run([{ op: 'move_beat', beat: id, to_index: i + 1 }], `You moved “${b.title}” down`)
    else if (action === 'remove') { setStorySel(null); run([{ op: 'drop_beat', beat: id }], `You removed “${b.title}”`) }
    else if (action === 'frames') {
      stopQueue()
      setSegment(null)
      setLevel('frames')
      const first = tl.items.find((it) => it.beat_id === id)
      if (first) setTimeout(() => { transport.seek(first.seq_start); snapStore.set(null) }, 50)
    }
  }
  const moveBeat = (id: string, to: number) => run([{ op: 'move_beat', beat: id, to_index: to }], `You moved “${beatById(id)?.title}”`)
  const retitle = (id: string, title: string) => run([{ op: 'retitle_beat', beat: id, title }], `You renamed “${beatById(id)?.title}”`)
  const entry = (key: string) => session?.board?.beats.flatMap((b) => b.shots).find((x) => x.key === key)
  const doSwap = (key: string, withShot: string | null) =>
    run([{ op: 'swap_shot', shot: key, with_shot: withShot }], withShot ? 'You swapped a shot' : 'You asked for a better shot')

  const menuItems = (): { title: string; items: MenuItem[] } => {
    if (!menu) return { title: '', items: [] }
    const e = entry(menu.key)
    const it = tl.items.find((x) => x.key === menu.key)
    if (menu.kind === 'gap') {
      return { title: `Empty space · ${it ? (it.seq_end - it.seq_start).toFixed(1) : '?'}s`, items: [
        { label: 'Close up this empty space', onClick: () => run([{ op: 'drop_shot', shot: menu.key }], 'You closed up an empty space') },
        { label: 'Keep it', onClick: () => {} },
      ] }
    }
    const openSwap = () => e && setSwap({ key: menu.key, thumb: e.thumb, id: e.id })
    if (menu.kind === 'story-shot') {
      return { title: `This shot · ${e ? (e.end - e.start).toFixed(1) : '?'}s`, items: [
        { label: 'Watch this shot', onClick: () => {
          const span = spanOf([menu.key])
          if (span) playEdit(span[0], span[1])
          else if (e?.clip_id) preview(e.clip_id, e.start, e.end, e.id)
        } },
        { label: 'Swap for a different shot…', onClick: openSwap },
        { label: 'Remove from the story', danger: true, onClick: () => run([{ op: 'drop_shot', shot: menu.key }], 'You removed a shot') },
      ] }
    }
    const t = phStore.get()
    return { title: `Shot ${it?.n ?? ''} · at ${clock(t)}`, items: [
      { label: 'Play from here', onClick: () => { timelineOwns(); transport.play(1) } },
      { label: 'Cut the shot in two here', hint: 'B', onClick: () => cutAt(t) },
      { label: 'Start the shot here', hint: 'Q', onClick: () => trimToPlayhead('in', false) },
      { label: 'End the shot here', hint: 'W', onClick: () => trimToPlayhead('out', false) },
      { label: 'Swap for a different shot…', onClick: openSwap },
      { label: 'Remove — the rest moves up', hint: 'Delete', danger: true, onClick: () => run([{ op: 'drop_shot', shot: menu.key }], `You removed shot ${it?.n}`) },
      { label: 'Remove — leave empty space', hint: '⌥ Delete', danger: true, onClick: () => run([{ op: 'drop_shot', shot: menu.key, leave_gap: true }], `You removed shot ${it?.n}, leaving the space`) },
    ] }
  }
  // ---- words on screen ------------------------------------------------------
  const runOverlay = async (ops: Record<string, unknown>[], label: string) => {
    const before = new Set(ovData.items.map((o) => o.id))
    const s = await run(ops, label)
    const added = s?.overlays.items.find((o) => !before.has(o.id))
    if (added) { setSelOverlay(added.id); showOverlay(added) }
    return s
  }
  const showOverlay = (o: Overlay) => {
    const t = phStore.get()
    if (t < o.start || t >= o.shown_end) transport.seek(Math.min(o.start + 0.6, (o.start + o.shown_end) / 2))
  }
  const watchOverlay = (o: Overlay) => {
    stopQueue()
    setSegment(null)
    transport.seek(Math.max(0, o.start - 0.8))
    transport.play(1)
  }
  const suggestOverlays = async () => {
    const { profile } = loadProfile(window.localStorage)
    const said = session?.proposals?.direction?.trim()
    const s = await api.suggestOverlays({ profile, title: said && said.length <= 48 ? said : undefined })
    setSession(s)
    offerUndo(s)
  }
  const newOverlayAt = (kind: OverlayKind): Record<string, unknown> => {
    const { profile } = loadProfile(window.localStorage)
    const items = tl.items
    const beatId = level === 'story' && storySel ? storySel.beat : null
    const it = level === 'frames' ? items[locate(items, phStore.get())]
      : beatId ? items.find((x) => x.beat_id === beatId) : items[0]
    const where = kind === 'end' || kind === 'chapters' ? {}
      : level === 'frames' ? { start: r3(phStore.get()) }
        : beatId ? { beat: beatId, at: 0.3 } : { start: 0.4 }
    const partNo = it ? parts.findIndex((p) => p.id === it.beat_id) + 1 : 1
    const clip = it?.clip_id ? clips.find((c) => c.id === it.clip_id) : null
    const handle = profile.handle.trim() ? (profile.handle.startsWith('@') ? profile.handle : '@' + profile.handle.trim()) : ''
    const words: Record<OverlayKind, Record<string, unknown>> = {
      title: { text: session?.board?.name ?? 'Title' },
      part: { text: it?.beat_title ?? 'Part', sub: `Part ${partNo}` },
      name: { text: profile.name.trim() || 'Name', sub: handle },
      caption: { text: 'What you said here' },
      date: { text: shortDate(clip?.capture_time) ?? shortDate(new Date().toISOString())! },
      end: { text: 'Thanks for watching', sub: handle },
      chapters: {},
    }
    return { ...where, ...words[kind] }
  }
  const editOverlayOnTimeline = (id: string, patch: { start?: number; dur?: number }) => {
    const o = ovData.items.find((x) => x.id === id)
    const what = patch.start != null ? 'moved' : 'changed the length of'
    run([{ op: 'edit_overlay', overlay: id, ...patch }], `You ${what} the ${o ? KIND_META[o.kind].label.toLowerCase() : 'overlay'}`)
  }
  const selectOverlay = (id: string | null) => {
    setSelOverlay(id)
    const o = id ? ovData.items.find((x) => x.id === id) : null
    if (o && level === 'frames') { setFramesTab('words'); timelineOwns(); showOverlay(o) }
  }
  // Words dragged on the picture: one undoable edit per drop.
  const overlayEdit: OverlayEdit | undefined = session?.board ? {
    selected: selOverlay,
    onSelect: (id) => setSelOverlay(id),
    onPlace: (id, place) => {
      const o = ovData.items.find((x) => x.id === id)
      const name = o ? KIND_META[o.kind].label.toLowerCase() : 'words'
      run([{ op: 'edit_overlay', overlay: id, place }], place ? `You moved the ${name}` : `You put the ${name} back in its usual place`)
    },
    onPlaceAll: (place) => {
      const ops = ovData.items.filter((o) => o.kind === 'caption').map((o) => ({ op: 'edit_overlay', overlay: o.id, place }))
      if (ops.length) run(ops, 'You put every caption in the same place')
    },
    onOpen: (id) => selectOverlay(id),
  } : undefined
  const overlaysPanel = session?.board ? (
    <Overlays data={ovData} items={tl.items} level={level} selected={selOverlay} busy={!!pending}
              onSelect={selectOverlay} onRun={runOverlay} onSuggest={suggestOverlays} onWatch={watchOverlay} newAt={newOverlayAt} />
  ) : null
  const applyTalk = async (captions: boolean) => {
    const { profile } = loadProfile(window.localStorage)
    const s = await api.talkApply(captions, profile)
    setSession(s)
    offerUndo(s)
    setTalkOpen(false)
    setPeek(null)
  }
  const openTalk = () => { transport.stop(); stopQueue(); setMenu(null); setLevel('story'); setTalkOpen(true) }
  const openExport = () => { transport.stop(); videoRef.current?.pause(); stopQueue(); setMenu(null); setExporting(true) }
  const openRemix = () => { transport.stop(); videoRef.current?.pause(); stopQueue(); setMenu(null); setReferencing(false); setRemixing(true) }
  const remixDone = async () => { await refresh(); setPeek(null); setLevel('frames') }
  const startOver = async () => {
    setRestart(false)
    try { await api.clear(); await refresh(); setLocal([hello]); setPeek(null); setCutData(null); setLevel('story') }
    catch (e) { note((e as Error).message) }
  }
  const rename = async (name: string) => {
    setRenaming(false)
    if (!name.trim() || name.trim() === session?.project?.name) return
    try { await api.renameProject(id, name.trim()); setSession(await api.session()) } catch (e) { note((e as Error).message) }
  }

  const usedIds = useMemo(() => new Set((session?.board?.beats ?? []).flatMap((b) => b.shots.map((x) => x.id))), [session])
  const apply = async (o: Option) => {
    await run([{ op: 'choose_option', option: o.key }], `You started from “${o.name}”`)
    setOthersOpen(false)
    setLevel('frames')
  }
  const clear = () => session?.board && run(session.board.beats.map((b) => ({ op: 'drop_beat', beat: b.id })),
    'You cleared the timeline')

  const marksOf = useMemo(() => {
    const d = session?.last?.diff && !session.last.diff.replaced ? session.last.diff : null
    const m: Record<string, 'added' | 'moved' | 'trimmed' | undefined> = {}
    d?.shots.added.forEach((x) => { m[x.id] = 'added' })
    d?.shots.moved.forEach((x) => { m[x.id] ??= 'moved' })
    d?.shots.trimmed.forEach((x) => { m[x.id] ??= 'trimmed' })
    return m
  }, [session])

  const label = queue && segment
    ? (() => {
      const c = clips.find((x) => x.id === segment.clipId)
      return `${queue.source === 'board' ? 'Storyboard' : 'Preview'} ${queue.index + 1}/${queue.items.length} · ${c?.name ?? ''} · ${clock(segment.start)}–${clock(segment.end)}`
    })()
    : segment ? clips.find((x) => x.id === segment.clipId)?.name ?? '' : tl.items.length ? 'Timeline' : ''
  const storyLabel = queue
    ? `${queue.source === 'board' ? 'Your story'
      : queue.source.startsWith('card:') ? `“${session?.proposals?.options.find((o) => `card:${o.key}` === queue.source)?.name ?? 'Option'}”`
        : queue.source.startsWith('beat:') ? `“${beatById(queue.source.slice(5))?.title ?? 'This part'}”` : 'Preview'} — shot ${queue.index + 1} of ${queue.items.length}`
    : segment ? (clips.find((x) => x.id === segment.clipId)?.name ?? 'One shot') : 'Nothing playing'
  const activeShot = queue ? queue.items[queue.index]?.id ?? null
    : segment ? [...shots.values()].find((v) => v.clip.id === segment.clipId && v.shot.start <= segment.start
      && segment.start < v.shot.end)?.shot.id ?? null : null

  // ---- screens -------------------------------------------------------------
  if (opened !== 'ok') {
    return (
      <div className="grid h-full place-items-center bg-ink p-6">
        {opened === 'loading' ? <p className="text-[13px] text-muted">Opening…</p> : (
          <div className="max-w-md text-center">
            <h2 className="font-serif text-[24px] text-zinc-100">This video couldn’t be opened</h2>
            <p className="mt-2 text-[13px] text-zinc-400">{opened}</p>
            <Button variant="primary" className="mt-4" onClick={() => go({ kind: 'projects' })}>Back to your videos</Button>
          </div>
        )}
      </div>
    )
  }

  const player = (big: boolean) => (
    <Player videoRef={videoRef} backRef={backRef} veilRef={veilRef} bars={session?.mix?.bars} segment={segment}
            label={big ? label : tr.playing && !segment ? 'Your story, with its captions — click to pause' : storyLabel}
            gap={tr.gap && !segment} overlay={overlayView} frame={tl.frame} overlayEdit={overlayEdit}
            onTime={() => {}} onEnd={() => { if (queue) playAt(queue, queue.index + 1) }} onPlayingChange={() => {}} />
  )
  // Chat on pause: only while the edit is stopped on a frame, about that frame.
  const pauseChat = session?.board && !tr.playing && !segment
    ? <PauseChat busy={!!pending} onApply={(ops, label) => run(ops, label)} items={tl.items}
                 clipName={(id) => clips.find((c) => c.id === id)?.name ?? id} />
    : null
  const chat = (
    <Chat items={chatItems} pending={pending} onSend={send} onToggle={toggle}
          disabled={!!pending} llm={caps.llm} hasBoard={!!session?.board || !!session?.proposals}
          prefs={session?.preferences ?? null} onClassify={classify} onRule={changeRule}
          review={session?.last ? { turn: session.last.turn, items: session.last.review ?? [] } : null} />
  )

  const centre = talkOpen && caps.speech
    ? <TalkCut onApply={applyTalk} onWatch={preview} onClose={() => setTalkOpen(false)} />
    : shown === 'footage' ? (
      <Footage clips={clips} importing={importing} errors={session?.import_errors ?? []} vision={caps.vision}
               onPick={(fl) => importPicked(fromInput(fl))} onRetry={retryImport}
               onDecide={(c, a) => { cutOverride(c.id, a).catch((e) => note((e as Error).message)) }}
               canContinue={!!clips.length && !importing && stage !== 'footage'} briefDone={!!brief}
               onNext={() => { showStep(stage === 'story' ? 'story' : brief ? 'cut' : 'brief'); if (!brief) startQuestions() }} />
    ) : shown === 'brief' ? (
      <Brief brief={brief} busy={!!pending || !!asking} onStart={startQuestions} onContinue={() => showStep(stage === 'story' ? 'story' : 'cut')} />
    ) : shown === 'cut' && cutData ? (
      <CutReview data={cutData} clips={clips} approved={!atGate} busy={approving}
                 onOverride={cutOverride} onApprove={approveCut} onWatch={preview}
                 onClose={() => showStep('story')} />
    ) : shown === 'cut' ? (
      <div className="grid flex-1 place-items-center text-[13px] text-muted">Working out the rough cut…</div>
    ) : (
      <Story
        session={session}
        clips={clips}
        asking={!!pending}
        playing={boardPlay ? 'board' : queue?.source ?? null}
        nowShot={boardPlay ? (boardShot && entry(boardShot)?.id) ?? null : queue ? queue.items[queue.index]?.id ?? null : null}
        selected={storySel}
        onUse={apply}
        onPlay={playSource}
        onSelect={(sel, anchor) => {
          setStorySel(sel)
          if (sel?.kind === 'shot' && anchor) {
            setMenu({ kind: entry(sel.key)?.gap ? 'gap' : 'story-shot', key: sel.key, anchor })
          } else setMenu(null)
        }}
        onMoveBeat={moveBeat}
        onRetitle={retitle}
        onBeatAction={beatAction}
        onReference={() => setReferencing(true)}
        othersOpen={othersOpen}
        onOthersOpen={setOthersOpen}
        onSmooth={async (order, nudge) => { const s = await api.smooth(order, nudge); setSession(s); offerUndo(s) }}
        onJoin={(after, sound) => run([{ op: 'set_join', shot: after, sound }],
          sound === 'default' ? 'Sound back to automatic' : 'Changed how the sound crosses a cut')}
      />
    )

  const storyStage = shown === 'story' && !talkOpen
  const cols = storyStage && level === 'frames' ? (narrow ? 'grid-cols-[minmax(0,1fr)]' : 'grid-cols-[320px_minmax(0,1fr)]')
    : storyStage ? (narrow ? 'grid-cols-[minmax(0,1fr)]' : 'grid-cols-[320px_minmax(0,1fr)_420px]')
      : narrow || shown === 'footage' || shown === 'brief' ? 'grid-cols-[minmax(0,1fr)]' : 'grid-cols-[minmax(0,1fr)_400px]'

  return (
    <>
    {asking && <StyleQuestions questions={asking.questions} tailored={asking.tailored}
                               onDone={answered} onCancel={() => setAsking(null)} />}
    <div className="grid h-full grid-rows-[48px_1fr]">
      <header className="flex items-center gap-2 border-b border-line bg-ink px-3">
        <button type="button" onClick={() => go({ kind: 'projects' })} title="All your videos" className="flex items-center gap-2 rounded-md px-1 py-0.5 hover:bg-raised">
          <Wordmark />
        </button>
        <span className="text-zinc-700" aria-hidden>/</span>
        {renaming ? (
          <input autoFocus defaultValue={session?.project?.name ?? ''} maxLength={80}
                 onBlur={(e) => rename(e.currentTarget.value)}
                 onKeyDown={(e) => { if (e.key === 'Enter') rename(e.currentTarget.value); if (e.key === 'Escape') setRenaming(false) }}
                 className="min-w-0 max-w-[220px] rounded-md border border-accent/60 bg-panel px-2 py-0.5 text-[13px] text-zinc-100 outline-none" />
        ) : (
          <button type="button" onClick={() => setRenaming(true)} title="Rename"
                  className="min-w-0 max-w-[220px] truncate rounded-md px-1.5 py-0.5 text-[13px] text-zinc-200 hover:bg-raised">{session?.project?.name ?? '…'}</button>
        )}
        {importing && <span className="hidden truncate text-[11px] text-accent md:inline" title={importing.text}>reading clips…</span>}

        <div className="flex-1" />
        <Stepper current={shown} derived={stage} done={done} onGo={showStep} compact={narrow} />
        {storyStage && (
          <div className="ml-2 flex rounded-lg border border-line bg-panel p-0.5 text-[12px]">
            {([['story', 'Story', 'Your video as parts and shots — reorder, remove, swap'],
               ['frames', 'Frames', 'The detailed timeline — cut and trim frame by frame']] as const).map(([k, name, tip]) => (
              <button key={k} type="button" title={tip} onClick={() => setLevel(k)}
                      className={`rounded-md px-2.5 py-1 ${level === k ? 'bg-zinc-700 text-zinc-100' : 'text-muted hover:text-zinc-200'}`}>
                {name}
              </button>
            ))}
          </div>
        )}
        <div className="flex-1" />

        {narrow && storyStage && <Button size="sm" onClick={() => setChatOpen((o) => !o)} aria-pressed={chatOpen}>Chat</Button>}
        {clips.length > 0 && shown === 'story' && (
          <Button size="sm" onClick={() => { transport.stop(); setMenu(null); setReferencing(true) }}
                  title="Make yours feel like a video you love — its pace, cuts and colour, never its frames">Reference</Button>
        )}
        <div className="relative">
          <Button size="sm" variant="ghost" onClick={() => setMore((m) => !m)} aria-haspopup="menu" aria-expanded={more}>More ▾</Button>
          {more && (
            <MoreMenu onClose={() => setMore(false)} items={[
              { label: 'Talking to camera…', hint: caps.speech ? 'Transcribe on this Mac, cut pauses and retakes' : 'Needs macOS 26 with the Xcode command-line tools', disabled: !caps.speech || !clips.length, onClick: openTalk },
              { label: 'Build a short from reference reels…', hint: caps.links ? 'Their pace and length, your clips, free music' : 'Links need yt-dlp; files work', disabled: !clips.length, onClick: openRemix },
              { label: 'Keyboard shortcuts', hint: 'Frames view', onClick: () => setHelp(true) },
              { label: 'Polish a finished video', hint: 'A separate tool for a video you already cut', onClick: () => go({ kind: 'polish' }) },
              { label: 'Start this video over…', hint: 'Clears the footage list and the story; files stay', danger: true, disabled: !clips.length, onClick: () => setRestart(true) },
            ]} />
          )}
        </div>
        <span className="mx-1 h-5 w-px shrink-0 bg-line" aria-hidden />
        <button type="button" title="Your profile" aria-label="Your profile" onClick={() => { transport.stop(); go({ kind: 'profile' }) }}
                className="grid size-8 shrink-0 place-items-center rounded-full bg-zinc-700 font-serif text-[15px] font-semibold text-zinc-100 ring-1 ring-zinc-500/40 hover:ring-accent">
          {profileInitial}
        </button>
        <Button variant="primary" size="sm" disabled={!session?.board} onClick={openExport}
                title={session?.board ? 'Render the edit, its captions and its music to one video file' : 'Pick a story first'}>
          Export{session?.exports.length ? ` · ${session.exports.length}` : ''}
        </Button>
      </header>

      <div className={cx('relative grid min-h-0', cols)}>
        {storyStage && (narrow ? (chatOpen && (
          <div className="absolute inset-y-0 left-0 z-30 w-[min(360px,90vw)] shadow-2xl shadow-black/60" onKeyDown={(e) => { if (e.key === 'Escape') setChatOpen(false) }}>{chat}</div>
        )) : chat)}

        {storyStage && level === 'frames' ? (
          <main className="relative flex min-h-0 min-w-0 flex-col">
            <div className="flex min-h-0 flex-1">
              <div className="flex min-h-0 min-w-0 flex-1 flex-col bg-panel">
                {session?.board && (
                  <div className="flex h-8 shrink-0 items-end gap-1 border-b border-line px-3" role="tablist">
                    {([['shots', 'Shots'], ['words', `Captions${ovData.items.length ? ` · ${ovData.items.length}` : ''}`]] as const).map(([k, name]) => (
                      <button key={k} type="button" role="tab" aria-selected={framesTab === k} onClick={() => setFramesTab(k)}
                              className={`shrink-0 whitespace-nowrap rounded-t-md px-2.5 py-1 text-[11px] ${framesTab === k ? 'bg-raised text-zinc-100' : 'text-muted hover:text-zinc-200'}`}>{name}</button>
                    ))}
                    {/* what used to live only on the Story page */}
                    <div className="ml-auto flex items-center gap-1 self-center [&>*]:shrink-0 [&>button]:whitespace-nowrap [&>div>button]:whitespace-nowrap">
                      <button type="button" onClick={() => playSource('board', [])}
                              className="rounded-md bg-zinc-800 px-2 py-1 text-[11px] text-zinc-100 hover:bg-zinc-700">
                        {boardPlay ? 'Stop' : 'Play all'}
                      </button>
                      <LengthButton total={tl.total} onDone={(r) => { setSession(r); offerUndo(r); note(r.length_note) }} />
                      <SmoothButton small rough={(session.seams ?? []).filter((x) => x.verdict !== 'ok').length}
                                    onSmooth={async (order, nudge) => { const r = await api.smooth(order, nudge); setSession(r); offerUndo(r) }} />
                      {session.proposals && (
                        <button type="button" onClick={() => { setOthersOpen(true); setLevel('story') }}
                                title="The other proposals built from your brief"
                                className="rounded-md border border-line px-2 py-1 text-[11px] text-zinc-300 hover:bg-raised">Other stories</button>
                      )}
                    </div>
                  </div>
                )}
                {framesTab === 'words' && overlaysPanel ? (
                  <div className="min-h-0 flex-1 overflow-y-auto p-3">{overlaysPanel}</div>
                ) : (
                  <Shelf clips={clips} activeShot={activeShot} busy={!!importing}
                         onPick={(fl) => importPicked(fromInput(fl))}
                         onPreview={(c, sh) => preview(c.id, sh.start, sh.end, sh.id)}
                         onAdd={(_, sh) => insertShot(sh.id, tl.items.length)}
                         onUseRejected={(c) => cutOverride(c.id, 'keep')} />
                )}
              </div>
              <div className="flex w-[44%] min-w-[320px] flex-col">{player(true)}{pauseChat}</div>
            </div>
            <Timeline tl={tl} marks={marks} marksOf={marksOf} selected={selected} flash={flash} alt={alt}
                      onSelect={(key, anchor) => {
                        timelineOwns()
                        setSelected(key)
                        const it = tl.items.find((x) => x.key === key)
                        if (key && anchor && it) setMenu({ kind: it.kind === 'gap' ? 'gap' : 'frames-shot', key, anchor })
                      }}
                      onReorder={reorder} onInsertShot={insertShot} onClear={clear} onHelp={() => setHelp(true)}
                      overlays={ovData.items} selectedOverlay={selOverlay} onSelectOverlay={selectOverlay}
                      onOverlayEdit={editOverlayOnTimeline} onExport={openExport} />
            {undoable && <UndoToast text={undoable.text} onUndo={() => { toggle(undoable.turn); setUndoable(null) }} />}
            {flash && level !== 'frames' && <Flash text={flash} />}
          </main>
        ) : (
          <>
            <main className="relative flex min-h-0 min-w-0 flex-col bg-panel">
              {centre}
              {undoable && <UndoToast text={undoable.text} onUndo={() => { toggle(undoable.turn); setUndoable(null) }} />}
              {flash && <Flash text={flash} />}
            </main>
            {/* Footage and the brief have no preview panel (sarah: the stacks use
                the width, a clip plays in place; the brief is just one line). Hidden, not removed: the player's videos
                stay attached to the transport. */}
            <aside className={cx('flex min-h-0 flex-col gap-3 overflow-y-auto border-line bg-panel p-3',
              narrow ? 'border-t max-h-[46vh]' : 'border-l', (shown === 'footage' || shown === 'brief') && 'hidden')}>
              <div className="flex aspect-[16/10] w-full shrink-0 flex-col overflow-hidden rounded-xl border border-line"
                   onClick={() => { if (tr.playing && !segment) transport.stop() }}>
                {player(false)}
              </div>
              {!segment && !tr.playing && !session?.board && <p className="px-1 text-[12px] text-muted">Press Watch on anything to see it here.</p>}
              {pauseChat && <div className="overflow-hidden rounded-xl border border-line">{pauseChat}</div>}
              {storyStage && overlaysPanel}
              {storyStage && session?.board && <Music board={session.board} inUse={session.music?.id ?? null} onSession={setSession} />}
            </aside>
          </>
        )}
      </div>

      {menu && (() => { const m = menuItems(); return <Menu anchor={menu.anchor} title={m.title} items={m.items} onClose={() => setMenu(null)} /> })()}
      {swap && (
        <SwapPicker clips={clips} used={usedIds} current={swap}
                    onPick={(w) => { doSwap(swap.key, w); setSwap(null) }} onClose={() => setSwap(null)} />
      )}
      {session?.music && <audio ref={musicRef} src={session.music.audio} preload="auto" />}
      {session?.mix && <audio ref={mixRef} src={session.mix.audio} preload="auto"
                              onError={() => { transport.mixBroken = true }} />}
      {help && <Keys onClose={() => setHelp(false)} />}
      {exporting && <Export tl={tl} overlays={ovData} parts={parts} music={session?.music?.title ?? null} style={session?.board?.style}
                            history={session?.exports ?? []} onClose={() => { setExporting(false); api.session().then(setSession).catch(() => {}) }} />}
      {remixing && <Remix onClose={() => setRemixing(false)} onDone={remixDone} canLinks={caps.links} />}
      {referencing && <BorrowStyle onClose={() => setReferencing(false)} onRemix={openRemix}
                                   onApplied={(s) => { setSession(s); offerUndo(s); setReferencing(false); setPeek(null); setLevel('frames') }} />}
      {restart && <Confirm title="Start this video over?" action="Start over" danger onNo={() => setRestart(false)} onYes={startOver}
                           text="The footage list, the rough cut, the story and its history are cleared. Your clip files and anything you exported are untouched." />}

      {dragging && (
        <div className="pointer-events-none fixed inset-0 z-50 grid place-items-center bg-black/60 backdrop-blur-[2px]">
          <div className="rounded-2xl border-2 border-dashed border-accent px-10 py-8 text-center">
            <div className="text-[18px] font-semibold text-zinc-100">Drop clips or a folder</div>
            <div className="mt-1 text-[12px] text-muted">.mp4 / .mov — added to this video, read on this computer</div>
          </div>
        </div>
      )}
    </div>
    </>
  )
}

// Footage · Brief · Rough cut · Story. The current one is lit; passed ones
// can be looked at again; the ones ahead say what will happen there.
function Stepper({ current, derived, done, onGo, compact }: {
  current: Stage; derived: Stage; done: Stage[]; onGo: (s: Stage) => void; compact: boolean
}) {
  return (
    <nav aria-label="Steps" className="flex items-center rounded-lg border border-line bg-panel p-0.5">
      {STAGES.map((s, i) => {
        const passed = done.includes(s.id) && s.id !== derived
        const can = done.includes(s.id)
        const cur = s.id === current
        return (
          <button key={s.id} type="button" disabled={!can} onClick={() => onGo(s.id)} aria-current={cur ? 'step' : undefined}
                  title={s.hint}
                  className={cx('flex items-center gap-1.5 rounded-md px-2.5 py-1 text-[12px] disabled:cursor-default',
                    cur ? 'bg-zinc-700 text-zinc-100' : can ? 'text-zinc-300 hover:bg-raised' : 'text-zinc-600')}>
            <span className={cx('grid size-4 place-items-center rounded-full text-[9px] font-semibold',
              cur ? 'bg-accent text-accent-ink' : passed ? 'bg-emerald-400/20 text-emerald-300' : 'bg-zinc-800 text-zinc-500')}>{passed ? '✓' : i + 1}</span>
            {(!compact || cur) && <span>{s.label}</span>}
          </button>
        )
      })}
    </nav>
  )
}

function MoreMenu({ items, onClose }: { items: { label: string; hint?: string; onClick: () => void; danger?: boolean; disabled?: boolean }[]; onClose: () => void }) {
  const box = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const away = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) onClose() }
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    const t = setTimeout(() => window.addEventListener('mousedown', away), 0)
    window.addEventListener('keydown', esc)
    return () => { clearTimeout(t); window.removeEventListener('mousedown', away); window.removeEventListener('keydown', esc) }
  }, [onClose])
  return (
    <div ref={box} role="menu" className="absolute right-0 top-9 z-40 w-72 rounded-xl border border-line bg-panel p-1.5 shadow-2xl shadow-black/60">
      {items.map((it) => (
        <button key={it.label} type="button" role="menuitem" disabled={it.disabled} onClick={() => { onClose(); it.onClick() }}
                className={cx('block w-full rounded-md px-2.5 py-1.5 text-left text-[13px] disabled:opacity-40',
                  it.danger ? 'text-rose-200 hover:bg-rose-500/10' : 'text-zinc-100 hover:bg-zinc-800')}>
          {it.label}
          {it.hint && <span className="block text-[10px] leading-snug text-muted">{it.hint}</span>}
        </button>
      ))}
    </div>
  )
}

function UndoToast({ text, onUndo }: { text: string; onUndo: () => void }) {
  return (
    <div className="pointer-events-auto absolute bottom-4 left-1/2 z-30 flex max-w-[90%] -translate-x-1/2 items-center gap-3 rounded-xl border border-line bg-zinc-900 px-4 py-2 shadow-2xl shadow-black/60">
      <span className="truncate text-[12px] text-zinc-200">{text}</span>
      <button type="button" onClick={onUndo} className="shrink-0 rounded-md bg-zinc-700 px-2.5 py-1 text-[12px] text-zinc-100 hover:bg-zinc-600">Undo</button>
    </div>
  )
}

// A short note about something that just happened (or couldn't).
function Flash({ text }: { text: string }) {
  return (
    <div role="status" className="pointer-events-none absolute left-1/2 top-3 z-30 max-w-[90%] -translate-x-1/2 truncate rounded-lg border border-line bg-zinc-900/95 px-3 py-1.5 text-[12px] text-zinc-100 shadow-xl">
      {text}
    </div>
  )
}

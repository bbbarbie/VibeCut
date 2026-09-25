import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api } from './api'
import { Chat, type ChatItem } from './components/Chat'
import { CreatorProfile } from './components/CreatorProfile'
import { CreativeTools } from './components/CreativeTools'
import { CutReview } from './components/CutReview'
import { Keys } from './components/Keys'
import { Player } from './components/Player'
import { Menu, SwapPicker, type MenuItem } from './components/Menus'
import { Music } from './components/Music'
import { Shelf } from './components/Shelf'
import { Story, type PlayItem, type Selection } from './components/Story'
import { Timeline, type Marks } from './components/Timeline'
import { fromDataTransfer, fromInput, type Picked } from './drop'
import { bytes, dur, uid } from './format'
import { clock, locate, toSource } from './sequence'
import { cutWhilePlaying, step } from './snap'
import { phStore, snapStore, transport, transportStore, useStore } from './transport'
import type { Clip, CutData, Msg, Option, Segment, Session, Shot, TimelineData } from './types'

const hello: Msg = {
  id: 'hello', role: 'app', at: 0,
  text: 'Hi — I’m here to help you shape the video. Once you’ve picked a story, you can also just tell me what to change: “the opening is too slow”, “take out the market”, “end on the sunset”. Everything can be undone.',
}
const EMPTY_TL: TimelineData = { fps: 30, total: 0, items: [], targets: [], grid: null }
const r3 = (x: number) => Math.round(x * 1000) / 1000

type Queue = { source: string; items: PlayItem[]; index: number }

export default function App() {
  const [profileOpen, setProfileOpen] = useState(window.location.hash === '#profile')
  const [toolsOpen, setToolsOpen] = useState(window.location.hash === '#tools')
  const profileButton = useRef<HTMLButtonElement>(null)
  useEffect(() => {
    const change = () => { setProfileOpen(window.location.hash === '#profile'); setToolsOpen(window.location.hash === '#tools'); transport.stop() }
    window.addEventListener('hashchange', change)
    return () => window.removeEventListener('hashchange', change)
  }, [])
  const [clips, setClips] = useState<Clip[]>([])
  const [session, setSession] = useState<Session | null>(null)
  const [local, setLocal] = useState<Msg[]>([hello])
  const [importing, setImporting] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [pending, setPending] = useState<string | null>(null)
  const [selected, setSelected] = useState<string | null>(null)   // Frames: timeline entry
  // Two levels. Story is where people live; Frames is the detailed timeline.
  const [level, setLevel] = useState<'story' | 'frames'>('story')
  const [storySel, setStorySel] = useState<Selection>(null)
  const [menu, setMenu] = useState<{ kind: 'story-shot' | 'frames-shot' | 'gap'; key: string; anchor: DOMRect } | null>(null)
  const [swap, setSwap] = useState<{ key: string; thumb: string; id: string } | null>(null)
  const [undoable, setUndoable] = useState<{ turn: number; text: string } | null>(null)
  // The rough cut and its gate.
  const [cutData, setCutData] = useState<CutData | null>(null)
  const [showCut, setShowCut] = useState(false)
  const [approving, setApproving] = useState(false)
  const [segment, setSegment] = useState<Segment | null>(null)
  const [queue, setQueue] = useState<Queue | null>(null)
  const [marks, setMarks] = useState<Marks>({ in: null, out: null })
  const [flash, setFlash] = useState<string | null>(null)
  const [alt, setAlt] = useState(false)
  const [help, setHelp] = useState(false)
  const dragDepth = useRef(0)
  const videoRef = useRef<HTMLVideoElement>(null)
  const musicRef = useRef<HTMLAudioElement>(null)
  const tr = useStore(transportStore)
  const tl = session?.timeline ?? EMPTY_TL
  const fr = 1 / tl.fps

  const shots = useMemo(() => {
    const m = new Map<string, { clip: Clip; shot: Shot }>()
    for (const c of clips) for (const s of c.shots) m.set(s.id, { clip: c, shot: s })
    return m
  }, [clips])

  useEffect(() => {
    api.project().then((p) => setClips(p.clips)).catch(() => {})
    api.session().then(setSession).catch(() => {})
    transport.video = videoRef.current
  }, [])
  useEffect(() => { transport.setItems(tl.items, tl.total) }, [tl])
  const wfState = session?.workflow?.state
  useEffect(() => { if (wfState && wfState !== 'intake') api.cut().then(setCutData).catch(() => {}) }, [wfState, clips])
  const atGate = wfState === 'cut-review'
  const cutOverride = async (target: string, action: string) => {
    setCutData(await api.override(target, action))
    const [p, s] = await Promise.all([api.project(), api.session()])
    setClips(p.clips)
    setSession(s)
  }
  const approveCut = async () => {
    setApproving(true)
    try { setSession(await api.approve()); setShowCut(false) } finally { setApproving(false) }
  }
  useEffect(() => {
    transport.video = videoRef.current
    if (level === 'frames') transport.seek(phStore.get())
    else transport.stop()
    setMenu(null)
  }, [level])
  useEffect(() => { transport.audio = session?.music ? musicRef.current : null }, [session?.music])

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

  const send = async (text: string) => {
    if (!clips.length) {
      setLocal((ms) => [...ms, { id: uid(), role: 'user', text, at: Date.now() }])
      say('Drop some clips in first — then there’s something to arrange.')
      return
    }
    setPending(text)
    try {
      setSession(await api.chat(text))
    } catch (e) {
      setLocal((ms) => [...ms, { id: uid(), role: 'user', text, at: Date.now() }])
      say((e as Error).message)
    } finally {
      setPending(null)
    }
  }

  const run = async (ops: Record<string, unknown>[], label: string) => {
    try {
      const s = await api.ops(ops, label)
      setSession(s)
      const t = s.turns.at(-1)
      if (t?.skipped.length) note(`Couldn’t: ${t.skipped[0]}`)
      if (t && t.lines.length && !t.skipped.length) {
        setUndoable({ turn: t.id, text: t.lines.map((l) => l.text).join(' · ') })
        window.clearTimeout(undoTimer.current)
        undoTimer.current = window.setTimeout(() => setUndoable(null), 7000)
      }
      return s
    } catch (e) {
      note(`Couldn’t apply that: ${(e as Error).message}`)
      return null
    }
  }

  const toggle = async (turn: number) => { setSession(await api.toggle(turn)) }

  // ---- import ----------------------------------------------------------------
  const importPicked = useCallback(async (picked: Picked[]) => {
    if (!picked.length) { say('No .mp4 or .mov files in that drop.'); return }
    if (importing) return
    setImporting(true)
    const t0 = performance.now()
    const size = picked.reduce((n, p) => n + p.file.size, 0)
    const update = say(`Found ${picked.length} clip${picked.length === 1 ? '' : 's'} (${bytes(size)}). Finding ${picked.length === 1 ? 'it' : 'them'} on disk…`, true)
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
          update(`Copying ${missing.length} clip(s) I couldn’t find on disk into the local cache… ${k}/${missing.length}`, true)
          paths.push((await api.upload(p.file, p.relpath, batch)).path)
          k++
        }
      }
      let job = await api.import(paths)
      while (job.stage !== 'done' && job.stage !== 'error') {
        update(job.stage === 'looking'
          ? `Indexed ${job.total} clip(s). Looking at each shot (on-device)…`
          : `Indexing ${job.done}/${job.total} — shots, capture time, GPS, quality, sound…`, true)
        await new Promise((r) => setTimeout(r, 250))
        job = await api.job(job.id)
      }
      const [p, s] = await Promise.all([api.project(), api.session()])
      setClips(p.clips)
      setSession(s)
      const secs = ((performance.now() - t0) / 1000).toFixed(1)
      const nShots = p.clips.reduce((n, c) => n + c.shots.length, 0)
      const added = job.total - job.errors.length
      const errs = job.errors.length ? `\n${job.errors.length} file(s) couldn’t be read: ${job.errors.map((e) => e.path?.split('/').pop()).join(', ')}` : ''
      const known = job.known ? ` (${job.known} already on the shelf, not redone)` : ''
      const next = s.board ? 'They’re on the shelf — nothing in your storyboard changed.'
        : s.proposals ? 'They’re on the shelf.' : 'Now tell me what the video is — one line is enough.'
      update(`Added ${added} clip${added === 1 ? '' : 's'}${known} in ${secs}s. The shelf now has ${p.clips.length} clips, ${nShots} shots.${errs}\n\n${next}`)
    } catch (e) {
      update(`Import failed: ${(e as Error).message}`)
    } finally {
      setImporting(false)
    }
  }, [importing, say])

  useEffect(() => {
    const isFiles = (e: DragEvent) => !profileOpen && !toolsOpen && e.dataTransfer?.types.includes('Files')
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
  }, [importPicked, profileOpen, toolsOpen])

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
    if (queue?.source === source) { stopQueue(); videoRef.current?.pause(); return }
    if (list.length) playAt({ source, items: list, index: 0 }, 0)
  }
  const preview = (clipId: string, start: number, end: number, shotId: string) => {
    transport.stop()
    stopQueue()
    setSegment({ key: shotId + uid(), clipId, start, end, autoplay: true })
  }
  // The timeline takes the player back: previews stop.
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
      // Tapped during playback: land on the nearest meaningful moment.
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

  const go = (t: number, target: Parameters<typeof snapStore.set>[0] = null) => {
    transport.seek(t)
    snapStore.set(target)
  }

  // ---- keyboard: industry conventions ----------------------------------------
  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (profileOpen || toolsOpen) return
      if (e.key === 'Alt') setAlt(true)
      const tag = (e.target as HTMLElement).tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA') return
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
          if (g) go(g.t, { target: g, snapped: true })
        } else go(t + dir * (e.shiftKey ? 1 : fr))
      } else if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
        if (playing) transport.stop()
        const g = step(tlRef.current.targets, t, e.key === 'ArrowDown' ? 1 : -1, 'shot')
        if (g) go(g.t, { target: g, snapped: true })
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

  // ---- direct timeline edits (drag still works; nothing requires it) ----------
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
      playSource(`beat:${id}`, b.shots.filter((x) => !x.gap && x.clip_id).map((x) => ({ id: x.id, clipId: x.clip_id!, start: x.start, end: x.end })))
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
        { label: 'Watch this shot', onClick: () => e?.clip_id && preview(e.clip_id, e.start, e.end, e.id) },
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
  const usedIds = useMemo(() => new Set((session?.board?.beats ?? []).flatMap((b) => b.shots.map((x) => x.id))), [session])

  const apply = (o: Option) => run([{ op: 'choose_option', option: o.key }], `You started from “${o.name}”`)
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
      return `${queue.source === 'board' ? 'Storyboard' : 'Preview'} ${queue.index + 1}/${queue.items.length} · ${c?.name ?? ''} · ${dur(segment.start)}–${dur(segment.end)}`
    })()
    : segment ? clips.find((x) => x.id === segment.clipId)?.name ?? '' : tl.items.length ? 'Timeline' : ''
  // Story level talks in parts and shots, never in file names or times.
  const storyLabel = queue
    ? `${queue.source === 'board' ? 'Your story'
      : queue.source.startsWith('card:') ? `“${session?.proposals?.options.find((o) => `card:${o.key}` === queue.source)?.name ?? 'Option'}”`
        : queue.source.startsWith('beat:') ? `“${beatById(queue.source.slice(5))?.title ?? 'This part'}”` : 'Preview'} — shot ${queue.index + 1} of ${queue.items.length}`
    : segment ? 'One shot' : 'Nothing playing'
  const activeShot = queue ? queue.items[queue.index]?.id ?? null
    : segment ? [...shots.values()].find((v) => v.clip.id === segment.clipId && v.shot.start <= segment.start
      && segment.start < v.shot.end)?.shot.id ?? null : null

  return (
    <>
    {profileOpen && <CreatorProfile onTools={() => { window.location.hash = 'tools' }} onClose={() => {
      window.history.replaceState(null, '', window.location.pathname + window.location.search)
      setProfileOpen(false)
      requestAnimationFrame(() => profileButton.current?.focus())
    }} />}
    {toolsOpen && <CreativeTools onProfile={() => { window.location.hash = 'profile' }} onClose={() => {
      window.history.replaceState(null, '', window.location.pathname + window.location.search)
      setToolsOpen(false)
    }} />}
    <div className="grid h-full grid-rows-[44px_1fr]" style={profileOpen || toolsOpen ? { display: 'none' } : undefined}>
      <header className="flex items-center gap-3 border-b border-line bg-ink px-4">
        <span className="font-serif text-[19px] font-semibold tracking-tight text-zinc-100">Vibe<span className="text-accent">Cut</span></span>
        <span className="text-[11px] text-muted">no amateur tells</span>
        <div className="ml-6 flex rounded-lg border border-line bg-panel p-0.5 text-[12px]">
          {([['story', 'Story', 'Your video as parts and shots — reorder, remove, swap'],
             ['frames', 'Frames', 'The detailed timeline — cut and trim frame by frame']] as const).map(([k, name, tip]) => (
            <button key={k} type="button" title={tip} onClick={() => setLevel(k)}
                    className={`rounded-md px-3 py-1 ${level === k ? 'bg-zinc-700 text-zinc-100' : 'text-muted hover:text-zinc-200'}`}>
              {name}
            </button>
          ))}
        </div>
        <div className="flex-1" />
        <button type="button" onClick={() => {
          transport.stop(); videoRef.current?.pause(); setMenu(null); setSwap(null); setHelp(false)
          window.location.hash = 'tools'
        }} className="shrink-0 rounded-lg border border-accent/30 px-3 py-1 text-[12px] text-accent hover:bg-raised">Creative tools</button>
        <button ref={profileButton} type="button" onClick={() => {
          transport.stop(); videoRef.current?.pause(); setMenu(null); setSwap(null); setHelp(false)
          window.location.hash = 'profile'
        }} className="shrink-0 rounded-lg border border-accent/30 px-3 py-1 text-[12px] text-accent hover:bg-raised">Creator profile</button>
        {session?.cut && (
          <button type="button" onClick={() => { setLevel('story'); setShowCut(true) }}
                  title={`${session.cut.line_en} — click to see what was cut and why`}
                  className="truncate rounded-md px-2 py-1 font-serif text-[14px] text-zinc-300 hover:bg-raised">
            {session.cut.line_zh}{atGate ? ' · 待你确认' : ''}
          </button>
        )}
        {importing && <span className="text-[11px] text-accent">indexing…</span>}
        <span className="text-[11px] text-zinc-600" title="Video, thumbnails and index stay on this Mac. With chat edits on, the storyboard's text (titles, shot labels, durations) goes to the language model.">
          footage stays on this Mac{session?.llm ? ' · storyboard text goes to Claude' : ''}
        </span>
      </header>

      <div className={`grid min-h-0 ${level === 'story' ? 'grid-cols-[320px_minmax(0,1fr)_440px]' : 'grid-cols-[320px_minmax(0,1fr)]'}`}>
        <Chat items={chatItems} pending={pending} onSend={send} onToggle={toggle}
              disabled={!!pending} llm={session?.llm ?? false} hasBoard={!!session?.board} />

        {level === 'story' ? (
          <>
            <main className="relative flex min-h-0 min-w-0 flex-col bg-panel">
              {(atGate || showCut) && cutData ? (
                <CutReview data={cutData} clips={clips} approved={!atGate} busy={approving}
                           onOverride={cutOverride} onApprove={approveCut} onWatch={preview}
                           onClose={() => setShowCut(false)} />
              ) : (
              <Story
                session={session}
                clips={clips}
                asking={!!pending}
                playing={queue?.source ?? null}
                nowShot={queue ? queue.items[queue.index]?.id ?? null : null}
                selected={storySel}
                onPick={(fl) => importPicked(fromInput(fl))}
                onAsk={send}
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
              />
              )}
              {undoable && <UndoToast text={undoable.text} onUndo={() => { toggle(undoable.turn); setUndoable(null) }} />}
            </main>
            <aside className="flex min-h-0 flex-col gap-3 overflow-y-auto border-l border-line bg-panel p-3">
              <div className="flex aspect-[16/10] w-full shrink-0 flex-col overflow-hidden rounded-xl border border-line">
                <Player videoRef={videoRef} segment={segment} label={storyLabel} gap={false}
                        onTime={() => {}} onEnd={() => { if (queue) playAt(queue, queue.index + 1) }} onPlayingChange={() => {}} />
              </div>
              {!segment && <p className="px-1 text-[12px] text-muted">Press Watch on anything to see it here.</p>}
              {session?.board && <Music board={session.board} inUse={session.music?.id ?? null} onSession={setSession} />}
            </aside>
          </>
        ) : (
          <main className="relative flex min-h-0 min-w-0 flex-col">
            <div className="flex min-h-0 flex-1">
              <Shelf
                clips={clips}
                activeShot={activeShot}
                busy={importing}
                onPick={(fl) => importPicked(fromInput(fl))}
                onPreview={(c, sh) => preview(c.id, sh.start, sh.end, sh.id)}
                onAdd={(_, sh) => insertShot(sh.id, tl.items.length)}
                onUseRejected={(c) => cutOverride(c.id, 'keep')}
              />
              <div className="flex w-[44%] min-w-[320px] flex-col">
                <Player
                  videoRef={videoRef}
                  segment={segment}
                  label={label}
                  gap={tr.gap && !segment}
                  onTime={() => {}}
                  onEnd={() => { if (queue) playAt(queue, queue.index + 1) }}
                  onPlayingChange={() => {}}
                />
              </div>
            </div>
            <Timeline
              tl={tl}
              marks={marks}
              marksOf={marksOf}
              selected={selected}
              flash={flash}
              alt={alt}
              onSelect={(key, anchor) => {
                timelineOwns()
                setSelected(key)
                const it = tl.items.find((x) => x.key === key)
                if (key && anchor && it) setMenu({ kind: it.kind === 'gap' ? 'gap' : 'frames-shot', key, anchor })
              }}
              onReorder={reorder}
              onInsertShot={insertShot}
              onClear={clear}
              onHelp={() => setHelp(true)}
            />
            {undoable && <UndoToast text={undoable.text} onUndo={() => { toggle(undoable.turn); setUndoable(null) }} />}
          </main>
        )}
      </div>

      {menu && (() => { const m = menuItems(); return <Menu anchor={menu.anchor} title={m.title} items={m.items} onClose={() => setMenu(null)} /> })()}
      {swap && (
        <SwapPicker clips={clips} used={usedIds} current={swap}
                    onPick={(w) => { doSwap(swap.key, w); setSwap(null) }} onClose={() => setSwap(null)} />
      )}
      {session?.music && <audio ref={musicRef} src={session.music.audio} preload="auto" />}
      {help && <Keys onClose={() => setHelp(false)} />}

      {dragging && (
        <div className="pointer-events-none fixed inset-0 z-50 grid place-items-center bg-black/60 backdrop-blur-[2px]">
          <div className="rounded-2xl border-2 border-dashed border-accent px-10 py-8 text-center">
            <div className="text-[18px] font-semibold text-zinc-100">Drop clips or a folder</div>
            <div className="mt-1 text-[12px] text-muted">.mp4 / .mov — added to this session, indexed on this Mac</div>
          </div>
        </div>
      )}
    </div>
    </>
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

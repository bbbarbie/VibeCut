import { useEffect, useMemo, useRef, useState } from 'react'
import { clock, locate, parseTimecode, readout, smpte, type SeqItem } from '../sequence'
import { approaching, snap, type Target, type TargetType } from '../snap'
import { phStore, snapStore, transport, transportStore, useStore } from '../transport'
import type { JoinInfo, Overlay, SoundStrip, TimelineData } from '../types'
import { KIND_META } from '../overlayDraw'
import { SHOT_MIME } from './Shelf'
import { Icon, type IconName } from './icons'

const TL_MIME = 'application/x-vibecut-tl'
const MIN_W = 56
const GAP = 2
const PAD = 12

export const TICK: Record<TargetType, string> = {
  shot: '#44403c', silence: '#059669', motion: '#d97706', beat: '#1f5f8b', word: '#7c3aed',
}
const TICK_H: Record<TargetType, number> = { shot: 14, silence: 9, motion: 7, beat: 6, word: 8 }
const MARK_CLS = { added: 'bg-emerald-400', moved: 'bg-amber-300', trimmed: 'bg-sky-400' } as const
export type Marks = { in: number | null; out: number | null }

const LANE_ROW = 20
const SOUND_H = 26   // a row of the Audio lane: sound taken off shots, the music
// The lanes, top to bottom: the ruler, the parts' names, the picture (Video),
// the captions, then the sound (Audio) -- as in her reference picture
// (sarah, 2026-10-16), each named in a column on the left.
const VIDEO_TOP = 48
const LANE_GAP = 6
const LABEL_W = 96
type Drag = { id: string; mode: 'move' | 'end'; x0: number; grab: number; start: number; end: number; moved: boolean }

export function Timeline({ tl, marks, marksOf, selected, flash, alt, onSelect, onReorder,
  onInsertShot, onClear, onHelp, overlays = [], selectedOverlay = null, onSelectOverlay, onOverlayEdit, onExport, onTrimEdge,
  selectedAudio = null, onSelectAudio, onAudioMove, joins = [], selectedJoin = null, onSelectJoin,
  music = null, onSelectMusic, onSplit, onDelete, height = 290 }: {
  tl: TimelineData
  marks: Marks
  marksOf: Record<string, 'added' | 'moved' | 'trimmed' | undefined>
  selected: string | null

  flash: string | null
  alt: boolean
  onSelect: (key: string | null, anchor: DOMRect | null) => void
  onReorder: (key: string, toIndex: number) => void
  onInsertShot: (shotId: string, at: number) => void
  onClear: () => void
  onHelp: () => void
  overlays?: Overlay[]
  selectedOverlay?: string | null
  onSelectOverlay?: (id: string) => void
  onOverlayEdit?: (id: string, patch: { start?: number; dur?: number }) => void
  onExport?: () => void
  /** a shot's start ('in') or end ('out') dragged to this source time */
  onTrimEdge?: (key: string, edge: 'in' | 'out', to: number) => void
  selectedAudio?: string | null
  /** a sound strip clicked: its tools show in the bar below */
  onSelectAudio?: (id: string, anchor: DOMRect) => void
  /** a sound strip dragged to start at this point of the edit */
  onAudioMove?: (id: string, at: number) => void
  /** every cut (session.mix.joins): a dot between the two shots opens its transitions below */
  joins?: JoinInfo[]
  selectedJoin?: string | null
  onSelectJoin?: (after: string) => void
  /** the song under the edit, drawn along the Audio lane; clicking it opens its controls */
  music?: { title: string } | null
  onSelectMusic?: () => void
  /** the toolbar's Split (at the playhead) and Delete (the selection) */
  onSplit?: () => void
  onDelete?: () => void
  height?: number
}) {
  const ph = useStore(phStore)
  const tr = useStore(transportStore)
  const sn = useStore(snapStore)
  const track = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(800)
  const [zoom, setZoom] = useState(1)
  const [dropAt, setDropAt] = useState<number | null>(null)
  const [tc, setTc] = useState<string | null>(null)   // timecode being typed
  const [tcBad, setTcBad] = useState(false)
  const scrubbing = useRef(false)
  // A shot's end being dragged: where it would land, in source seconds.
  const [edge, setEdge] = useState<{ key: string; edge: 'in' | 'out'; to: number } | null>(null)
  const edging = useRef<{ x: number; base: number; pps: number } | null>(null)
  const items = tl.items
  useEffect(() => { if (!edging.current) setEdge(null) }, [items])

  useEffect(() => {
    const el = track.current
    if (!el) return
    const ro = new ResizeObserver(() => setWidth(el.clientWidth))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  // The scale (pixels per second) stays put while the edit changes under it,
  // as in CapCut: trimming a shot grows or shrinks that shot and slides the
  // ones after it, it doesn't squeeze every shot to fit again (sarah,
  // 2026-10-17). It is fitted to the edit only when the timeline's width
  // changes, a different edit is shown, or she zooms herself.
  const fitNow = () => tl.total > 0 ? Math.max(0.5, (width - 2 * PAD - items.length * GAP) / tl.total) : 10
  const [scale, setScale] = useState<number | null>(null)
  const seen = useRef<{ keys: Set<string>; edit: number }>({ keys: new Set(), edit: 0 })
  const edit = useMemo(() => {
    const s = seen.current
    if (!items.some((it) => s.keys.has(it.key))) s.edit += 1   // nothing in common: another edit
    s.keys = new Set(items.map((it) => it.key))
    return s.edit
  }, [items])
  const hasEdit = tl.total > 0
  useEffect(() => { if (hasEdit) setScale(fitNow()) }, [width, edit, hasEdit]) // eslint-disable-line react-hooks/exhaustive-deps
  const zoomTo = (z: number) => { setScale(fitNow()); setZoom(z) }
  const pps = (scale ?? fitNow()) * zoom
  // Geometry: widths proportional to duration, with a floor so a short
  // shot stays hittable. Position <-> time is exact within each block.
  // A shot whose end is being dragged is drawn at its new length while the
  // drag lasts: dragging the end pushes the later shots along, dragging the
  // start moves that edge with the pointer.
  const geo = useMemo(() => {
    const dur = (it: SeqItem) => {
      const d = it.seq_end - it.seq_start
      if (edge?.key !== it.key) return d
      const grow = edge.edge === 'out' ? edge.to - it.src_end : it.src_start - edge.to
      return Math.max(0, d + grow / (it.speed ?? 1))
    }
    const w = items.map((it) => Math.max(MIN_W, dur(it) * pps))
    const left: number[] = []
    w.forEach((_, k) => left.push(k ? left[k - 1] + w[k - 1] + GAP : 0))
    const k = edge?.edge === 'in' ? items.findIndex((it) => it.key === edge.key) : -1
    if (k >= 0) {
      // the start follows the pointer; the shots after stay until it's let go
      const was = Math.max(MIN_W, (items[k].seq_end - items[k].seq_start) * pps)
      for (let j = k; j < left.length; j++) left[j] -= w[k] - was
    }
    const end = Math.max(...w.map((x, j) => left[j] + x), 0)
    return { w, left, end }
  }, [items, pps, edge])

  const xOf = (t: number) => {
    const k = locate(items, t)
    if (k < 0) return PAD
    const it = items[k]
    const d = Math.max(it.seq_end - it.seq_start, 1e-6)
    return PAD + geo.left[k] + Math.min(1, (t - it.seq_start) / d) * geo.w[k]
  }
  const tOf = (x: number): { t: number; localPps: number } => {
    x -= PAD
    let lo = 0
    let hi = items.length - 1
    while (lo < hi) {
      const mid = (lo + hi + 1) >> 1
      if (geo.left[mid] <= x) lo = mid
      else hi = mid - 1
    }
    const it = items[lo]
    if (!it) return { t: 0, localPps: pps }
    const d = it.seq_end - it.seq_start
    const f = Math.max(0, Math.min(1, (x - geo.left[lo]) / geo.w[lo]))
    return { t: it.seq_start + f * d, localPps: geo.w[lo] / Math.max(d, 1e-6) }
  }

  // Scrub: snapped to the nearest target within reach at *this* zoom;
  // Alt held = exactly where the pointer is.
  const scrubTo = (clientX: number, bypass: boolean) => {
    const el = track.current!
    const { t, localPps } = tOf(clientX - el.getBoundingClientRect().left + el.scrollLeft)
    const opts = { pxPerSec: localPps, disabled: bypass }
    const r = snap(tl.targets, t, opts)
    transport.seek(r.t)
    const near = r.target ? null : approaching(tl.targets, t, opts)
    snapStore.set(r.target ? { target: r.target, snapped: true } : near ? { target: near, snapped: false } : null)
  }

  // Keep the playhead in view while it moves.
  useEffect(() => {
    const el = track.current
    if (!el || scrubbing.current) return
    const x = xOf(ph)
    if (x < el.scrollLeft + 40 || x > el.scrollLeft + el.clientWidth - 40) {
      el.scrollLeft = Math.max(0, x - el.clientWidth / 3)
    }
  }, [ph]) // eslint-disable-line react-hooks/exhaustive-deps

  const indexAt = (clientX: number) => {
    const el = track.current!
    const x = clientX - el.getBoundingClientRect().left + el.scrollLeft - PAD
    for (let k = 0; k < items.length; k++) if (x < geo.left[k] + geo.w[k] / 2) return k
    return items.length
  }
  const accepts = (e: React.DragEvent) =>
    e.dataTransfer.types.includes(TL_MIME) || e.dataTransfer.types.includes(SHOT_MIME)

  const jump = () => {
    if (tc == null) return
    const t = parseTimecode(tc, tl.fps)
    if (t == null) { setTcBad(true); return }
    transport.seek(t)   // typed = meant exactly: no snapping
    snapStore.set(null)
    setTc(null)
    ;(document.activeElement as HTMLElement)?.blur()
  }

  // Words on screen get their own lane above the shots, stacked when they overlap.
  const [drag, setDrag] = useState<Drag | null>(null)
  const lanes = useMemo(() => {
    const ends: number[] = []
    const row = new Map<string, number>()
    for (const o of overlays) {
      let r = ends.findIndex((e) => e <= o.start + 1e-3)
      if (r < 0) { r = Math.min(ends.length, 2); if (r === ends.length) ends.push(0) }
      ends[r] = Math.max(ends[r], o.shown_end)
      row.set(o.id, r)
    }
    return { row, n: ends.length }
  }, [overlays])
  const strips: SoundStrip[] = tl.audio?.strips ?? []
  const silent = useMemo(() => new Set(tl.audio?.off ?? []), [tl.audio])
  // Measured from the bottom: Audio (strips, then the music), Captions, and
  // the picture takes what is left.
  const audioRows = (strips.length ? 1 : 0) + 1
  const audioH = audioRows * SOUND_H + (audioRows - 1) * 4 + 8
  const capH = Math.max(1, lanes.n) * LANE_ROW + 8
  const audioBottom = 8
  const capBottom = audioBottom + audioH + LANE_GAP
  const shotsBottom = capBottom + capH + LANE_GAP
  const musicBottom = audioBottom + 4
  const stripBottom = musicBottom + SOUND_H + 4
  const [moving, setMoving] = useState<{ id: string; x0: number; grab: number; at: number; moved: boolean } | null>(null)
  const overlayTime = (clientX: number, bypass: boolean) => {
    const el = track.current!
    const { t, localPps } = tOf(clientX - el.getBoundingClientRect().left + el.scrollLeft)
    return snap(tl.targets, t, { pxPerSec: localPps, disabled: bypass }).t
  }

  const rate = tr.rate
  const hl = sn?.target
  const hlX = hl ? xOf(hl.t) : null
  const inX = marks.in != null ? xOf(marks.in) : null
  const outX = marks.out != null ? xOf(marks.out) : null

  return (
    <section className="flex min-h-0 shrink-0 flex-col" style={{ height }}>
      <header className="flex h-12 shrink-0 items-center gap-2.5 border-b border-line px-3">
        <div className="flex items-center gap-1">
          <TB title="Play backwards (J — press again to go faster)" onClick={() => transport.play(rate < 0 ? Math.max(rate * 2, -8) : -1)}>◀◀</TB>
          <TB title="Play / pause (Space)" onClick={() => (tr.playing ? transport.stop() : transport.play(1))} wide>
            <Icon name={tr.playing ? 'pause' : 'play'} size={18} />
          </TB>
          <TB title="Play forwards (L — press again to go faster)" onClick={() => transport.play(rate > 0 ? Math.min(rate * 2, 8) : 1)}>▶▶</TB>
          {tr.playing && rate !== 1 && <span className="w-8 text-[11px] tabular-nums text-accent">{rate > 0 ? `${rate}×` : `−${-rate}×`}</span>}
        </div>
        <span className="h-6 w-px bg-line" aria-hidden />
        {onSplit && <Tool icon="split" label="Split" title="Split the shot at the playhead (B)" onClick={onSplit} disabled={!items.length} />}
        {onDelete && <Tool icon="trash" label="Delete" title="Delete the selected shot, or the marked part (Delete)" onClick={onDelete} disabled={!items.length} />}
        <span className="h-6 w-px bg-line" aria-hidden />

        <input
          value={tc ?? smpte(ph, tl.fps)}
          // Focus empties the box (current time stays visible as the
          // placeholder), so what you type is the whole value.
          placeholder={smpte(ph, tl.fps)}
          onFocus={() => { setTc(''); setTcBad(false) }}
          onChange={(e) => { setTc(e.target.value); setTcBad(false) }}
          onBlur={() => setTc(null)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') jump()
            if (e.key === 'Escape') { setTc(null); (e.target as HTMLElement).blur() }
            e.stopPropagation()
          }}
          title="Go to a time: type 21.3, 0:21.3 or 00:00:21:09 and press Enter. It goes exactly there."
          className={`w-[92px] rounded-md border bg-raised px-1.5 py-0.5 font-mono text-[12px] tabular-nums outline-none ${tcBad ? 'border-rose-400 text-rose-200' : 'border-line text-zinc-100 focus:border-zinc-500'}`}
        />
        <span className="shrink-0 text-[12px] tabular-nums text-zinc-100" title="What's under the playhead">
          {items.length ? readout(items, tl.grid, ph) : '—'}
        </span>

        <div className="min-w-0 flex-1" />
        {flash && <span className="min-w-0 truncate text-[11px] text-accent">{flash}</span>}
        {(marks.in != null || marks.out != null) && (
          <span className="shrink-0 text-[11px] tabular-nums text-zinc-300">
            Marked {marks.in != null ? clock(marks.in) : '…'} → {marks.out != null ? clock(marks.out) : '…'}
            {marks.in != null && marks.out != null && marks.out > marks.in ? ` (${(marks.out - marks.in).toFixed(2)}s)` : ''}
          </span>
        )}
        <span className={`flex shrink-0 items-center gap-1.5 text-[11px] ${alt ? 'text-amber-200' : 'text-muted'}`}
              title="The playhead sticks to these moments: a new shot, sound stopping or starting, movement, a music beat. Hold ⌥ (Alt) to place it exactly where you point.">
          {alt ? 'sticking off' : 'sticks to'}
          {!alt && (['shot', 'silence', 'motion', 'beat'] as TargetType[]).map((t) => (
            <i key={t} className="inline-block h-2.5 w-[3px] rounded-sm" style={{ background: TICK[t] }} title={t} />
          ))}
        </span>
        <div className="flex shrink-0 items-center gap-1.5" title="Zoom the timeline">
          <button type="button" aria-label="Zoom out" onClick={() => zoomTo(Math.max(1, zoom / 1.5))}
                  className="grid size-7 place-items-center rounded-md text-zinc-300 hover:bg-raised"><Icon name="minus" size={18} /></button>
          <input type="range" min={1} max={40} step={0.5} value={zoom} aria-label="Zoom"
                 onChange={(e) => zoomTo(Number(e.target.value))} className="w-24 accent-[#1f5f8b]" />
          <button type="button" aria-label="Zoom in" onClick={() => zoomTo(Math.min(40, zoom * 1.5))}
                  className="grid size-7 place-items-center rounded-md text-zinc-300 hover:bg-raised"><Icon name="plus" size={18} /></button>
        </div>
        {onExport && (
          <button type="button" onClick={onExport} disabled={!items.length} title="Render the edit, its captions and its music to one video file"
                  className="shrink-0 rounded-md bg-accent px-2 py-0.5 text-[11px] font-semibold text-accent-ink disabled:opacity-30">Export…</button>
        )}
        <button type="button" onClick={onHelp} title="Keyboard shortcuts"
                className="grid size-6 shrink-0 place-items-center rounded-md border border-line text-[12px] text-muted hover:text-zinc-200">?</button>
        <button type="button" onClick={onClear} disabled={!items.length}
                className="shrink-0 rounded-md px-1.5 py-1 text-[11px] text-muted hover:text-zinc-200 disabled:opacity-30">Clear</button>
      </header>

      <div className="flex min-h-0 flex-1">
      {items.length > 0 && (
        <div className="relative shrink-0 border-r border-line" style={{ width: LABEL_W }} aria-hidden>
          <LaneLabel icon="video" style={{ top: VIDEO_TOP, bottom: shotsBottom }}>Video</LaneLabel>
          <LaneLabel icon="lines" style={{ bottom: capBottom, height: capH }}>Captions</LaneLabel>
          <LaneLabel icon="music" style={{ bottom: audioBottom, height: audioH }}>Audio</LaneLabel>
        </div>
      )}
      <div
        ref={track}
        className="relative min-h-0 flex-1 select-none overflow-x-auto overflow-y-hidden"
        onDragOver={(e) => {
          if (!accepts(e)) return
          e.preventDefault()
          setDropAt(indexAt(e.clientX))
        }}
        onDragLeave={(e) => { if (!e.currentTarget.contains(e.relatedTarget as Node)) setDropAt(null) }}
        onDrop={(e) => {
          e.preventDefault()
          const at = indexAt(e.clientX)
          setDropAt(null)
          const moving = e.dataTransfer.getData(TL_MIME)
          const shot = e.dataTransfer.getData(SHOT_MIME)
          if (moving) onReorder(moving, at)
          else if (shot) onInsertShot(shot, at)
        }}
      >
        {items.length === 0 ? (
          <div className="absolute inset-3 grid place-items-center rounded-lg border border-dashed border-zinc-800 text-[12px] text-zinc-600">
            Your edit is on its way. You can also drag shots here from above
          </div>
        ) : (
          <div className="relative h-full" style={{ width: geo.end + 2 * PAD }}>
            {/* ruler: every snap target, click or drag to scrub */}
            <div
              className="absolute inset-x-0 top-0 h-7 cursor-ew-resize border-b border-line bg-ink/60"
              onPointerDown={(e) => {
                scrubbing.current = true
                e.currentTarget.setPointerCapture(e.pointerId)
                if (tr.playing) transport.stop()
                scrubTo(e.clientX, e.altKey)
              }}
              onPointerMove={(e) => { if (scrubbing.current) scrubTo(e.clientX, e.altKey) }}
              onPointerUp={() => { scrubbing.current = false }}
            >
              <svg className="absolute inset-0 h-full" width={geo.end + 2 * PAD}>
                {inX != null && outX != null && outX > inX && (
                  <rect x={inX} y={0} width={outX - inX} height={28} fill="#1f5f8b" opacity={0.18} />
                )}
                {tl.targets.map((g: Target, i) => (
                  <line key={i} x1={xOf(g.t)} x2={xOf(g.t)} y1={28 - TICK_H[g.type]} y2={28}
                        stroke={TICK[g.type]} strokeWidth={g.type === 'shot' ? 1.5 : 1} opacity={g === hl ? 1 : 0.55} />
                ))}
                {inX != null && <path d={`M${inX},2 v24 h5`} stroke="#1f5f8b" fill="none" strokeWidth={2} />}
                {outX != null && <path d={`M${outX},2 v24 h-5`} stroke="#1f5f8b" fill="none" strokeWidth={2} />}
              </svg>
            </div>

            {/* the Captions and Audio lanes' bands */}
            <div className="pointer-events-none absolute inset-x-0 rounded-md bg-violet-900/40" style={{ bottom: capBottom, height: capH }} />
            <div className="pointer-events-none absolute inset-x-0 rounded-md bg-raised/70" style={{ bottom: audioBottom, height: audioH }} />
            {music && (
              <button type="button" onPointerDown={(e) => e.stopPropagation()} onClick={onSelectMusic}
                      title={`${music.title}: click for the music's controls`}
                      className="absolute flex items-center gap-2 overflow-hidden rounded-md px-2.5 font-serif text-[14px] text-[#1d5c46] hover:brightness-95"
                      style={{ left: PAD, width: Math.max(40, geo.end), bottom: musicBottom, height: SOUND_H,
                        background: 'repeating-linear-gradient(90deg, #bfe3d3 0 2px, #cdeadd 2px 5px)' }}>
                <Icon name="music" size={16} />
                <span className="truncate">{music.title}</span>
              </button>
            )}

            {overlays.map((o) => {
              const d = drag?.id === o.id ? drag : null
              const a = d ? d.start : o.start
              const z = d ? d.end : o.shown_end
              const x = xOf(a)
              const w = Math.max(12, xOf(Math.min(z, tl.total)) - x)
              const meta = KIND_META[o.kind]
              const edge = o.dur != null || o.anchor.to === 'edit'
              return (
                <div key={o.id}
                     title={`${meta.label}: ${o.kind === 'chapters' ? 'chapter bar' : o.text}\nDrag to move (it sticks to cuts; hold ⌥ for exact), drag the right edge to change its length`}
                     onPointerDown={(e) => {
                       if (e.button !== 0) return
                       e.stopPropagation()
                       e.currentTarget.setPointerCapture(e.pointerId)
                       const box = e.currentTarget.getBoundingClientRect()
                       const mode = edge && e.clientX > box.right - 7 ? 'end' : 'move'
                       // where on the pill it was grabbed, so the pill doesn't jump under the pointer
                       setDrag({ id: o.id, mode, x0: e.clientX, grab: e.clientX - box.left, start: o.start, end: o.shown_end, moved: false })
                     }}
                     onPointerMove={(e) => {
                       if (!d) return
                       if (!d.moved && Math.abs(e.clientX - d.x0) < 4) return
                       if (d.mode === 'move') {
                         const t = Math.max(0, overlayTime(e.clientX - d.grab, e.altKey))
                         setDrag({ ...d, moved: true, start: t, end: t + (o.shown_end - o.start) })
                       } else {
                         const t = Math.max(o.start + 0.5, overlayTime(e.clientX, e.altKey))
                         setDrag({ ...d, moved: true, end: t })
                       }
                     }}
                     onPointerUp={() => {
                       if (!d) return
                       setDrag(null)
                       if (!d.moved) { onSelectOverlay?.(o.id); return }
                       if (d.mode === 'move') onOverlayEdit?.(o.id, { start: Math.round(d.start * 1000) / 1000 })
                       else onOverlayEdit?.(o.id, { dur: Math.round((d.end - o.start) * 1000) / 1000 })
                     }}
                     className={`absolute flex cursor-grab items-center gap-1 overflow-hidden rounded-md px-1.5 text-[12px] leading-none text-stone-900 active:cursor-grabbing ${
                       selectedOverlay === o.id ? 'ring-2 ring-accent' : ''} ${d?.moved ? 'opacity-80' : ''}`}
                     style={{ left: x, width: w, bottom: capBottom + capH - 4 - ((lanes.row.get(o.id) ?? 0) + 1) * LANE_ROW + 3, height: LANE_ROW - 3, background: meta.color }}>
                  <span className="shrink-0 font-semibold">{meta.icon}</span>
                  <span className="truncate">{o.kind === 'chapters' ? 'Chapter bar' : o.text}</span>
                  {edge && <span className="absolute inset-y-0 right-0 w-1.5 cursor-ew-resize bg-black/20" />}
                </div>
              )
            })}

            {items.map((it: SeqItem, k) => (k === 0 || items[k - 1].beat_id !== it.beat_id) && (
              <div key={`beat-${it.beat_id}-${k}`} className="pointer-events-none absolute top-8 truncate text-[10px] font-medium text-zinc-400"
                   style={{ left: geo.left[k] + PAD, maxWidth: 220, top: 31 }}>
                {it.beat_title}
              </div>
            ))}

            {items.map((it, k) => {
              const thumb = it.kind === 'shot' ? `/api/thumbs/${it.clip_id}/shot${String(Number(it.shot_id!.split(':')[1])).padStart(3, '0')}.jpg` : null
              const mark = marksOf[it.key]
              const ed = edge?.key === it.key ? edge : null
              const grow = ed ? (ed.edge === 'out' ? ed.to - it.src_end : it.src_start - ed.to) : 0
              const sp = it.speed ?? 1   // source seconds per second of the edit
              const w = geo.w[k]
              const lo = it.src_min ?? it.src_start
              const hi = it.src_max ?? it.src_end
              // Drag either end: shorter, or longer up to the whole shot as filmed.
              const handle = (side: 'in' | 'out') => onTrimEdge && it.kind === 'shot' && (
                <div
                  title={side === 'in' ? 'Drag to change where this shot starts' : 'Drag to change where this shot ends'}
                  className={`absolute inset-y-0 z-10 w-2.5 cursor-ew-resize bg-white/0 hover:bg-white/60 ${side === 'in' ? 'left-0 rounded-l-md' : 'right-0 rounded-r-md'} ${ed?.edge === side ? 'bg-white/80' : ''}`}
                  onPointerDown={(e) => {
                    if (e.button !== 0) return
                    e.stopPropagation(); e.preventDefault()
                    e.currentTarget.setPointerCapture(e.pointerId)
                    edging.current = { x: e.clientX, base: side === 'in' ? it.src_start : it.src_end, pps: pps / sp }
                    setEdge({ key: it.key, edge: side, to: edging.current.base })
                  }}
                  onPointerMove={(e) => {
                    const g = edging.current
                    if (!g) return
                    const t = g.base + (e.clientX - g.x) / g.pps
                    const to = side === 'in' ? Math.max(lo, Math.min(t, it.src_end - 0.2)) : Math.min(hi, Math.max(t, it.src_start + 0.2))
                    setEdge({ key: it.key, edge: side, to })
                  }}
                  onPointerUp={() => {
                    const g = edging.current
                    edging.current = null
                    const cur = edge
                    if (g && cur && Math.abs(cur.to - g.base) > 1 / 30) {
                      // hold the new length until the trimmed edit comes back, so the shot doesn't flick back first
                      onTrimEdge(it.key, side, cur.to)
                      window.setTimeout(() => setEdge((x) => (x === cur ? null : x)), 3000)
                    } else setEdge(null)
                  }}
                />
              )
              return (
                <div
                  key={it.key}
                  draggable={!edge}
                  onDragStart={(e) => { if (edging.current) { e.preventDefault(); return } e.dataTransfer.setData(TL_MIME, it.key); e.dataTransfer.effectAllowed = 'move' }}
                  onPointerDown={(e) => {
                    if (e.button !== 0) return
                    const rect = e.currentTarget.getBoundingClientRect()
                    scrubTo(e.clientX, e.altKey)   // a click also puts the playhead there
                    onSelect(it.key, new DOMRect(e.clientX - 1, rect.top, 2, rect.height))
                  }}
                  className={`group absolute cursor-pointer overflow-hidden rounded-md ${it.kind === 'gap'
                    ? 'bg-[repeating-linear-gradient(45deg,#efebe4,#efebe4_6px,#e2ddd4_6px,#e2ddd4_12px)]' : 'bg-black'} ${
                    selected === it.key ? 'ring-2 ring-accent' : 'ring-1 ring-zinc-800 hover:ring-zinc-600'}`}
                  style={{
                    top: VIDEO_TOP, bottom: shotsBottom, left: geo.left[k] + PAD, width: w, zIndex: ed ? 5 : undefined,
                    backgroundImage: thumb ? `url(${thumb})` : undefined,
                    backgroundSize: 'auto 100%', backgroundRepeat: 'repeat-x', backgroundPosition: 'center',
                  }}
                  title={it.kind === 'gap' ? `${(it.seq_end - it.seq_start).toFixed(2)}s gap` : `Shot ${it.n} · ${(it.seq_end - it.seq_start).toFixed(2)}s`}
                >
                  {mark && <div className={`absolute inset-x-0 top-0 h-1 ${MARK_CLS[mark]}`} />}
                  {handle('in')}
                  {handle('out')}
                  {ed && <div className="pointer-events-none absolute left-1/2 top-1 -translate-x-1/2 rounded bg-black/80 px-1.5 text-[12px] tabular-nums text-zinc-100">{((it.src_end - it.src_start + grow) / sp).toFixed(1)}s</div>}
                  <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/80 to-transparent px-1.5 pb-1 pt-3 text-[10px] tabular-nums text-zinc-200">
                    {it.kind === 'gap' ? 'gap ' : it.n != null ? `${it.n} · ` : ''}{(it.seq_end - it.seq_start).toFixed(1)}s{sp !== 1 ? ` · ${sp}×` : ''}{it.mute ? ' · muted' : it.gain != null ? ` · ${Math.round(it.gain * 100)}%` : ''}{silent.has(it.key) ? ' · sound below' : ''}
                  </div>
                </div>
              )
            })}

            {/* the cut between two shots: click to pick how the picture changes there */}
            {onSelectJoin && items.map((it, k) => {
              const nx = items[k + 1]
              if (!nx || it.kind !== 'shot' || nx.kind !== 'shot') return null
              const j = joins.find((x) => x.after === it.key)
              if (!j) return null
              const on = selectedJoin === it.key, styled = j.picture !== 'cut'
              return (
                <button key={`join-${it.key}`} type="button"
                        title={styled ? 'How the picture changes here — click to change it' : 'A plain cut — click to pick a transition'}
                        onPointerDown={(e) => e.stopPropagation()}
                        onClick={(e) => { e.stopPropagation(); onSelectJoin(it.key) }}
                        className={`absolute z-20 flex size-[22px] -translate-x-1/2 items-center justify-center rounded-full border-2 text-[11px] leading-none shadow ${
                          on ? 'border-accent bg-accent text-accent-ink ring-4 ring-accent/30'
                            : styled ? 'border-accent bg-white text-accent' : 'border-stone-300 bg-white text-stone-400 hover:border-accent'}`}
                        style={{ left: geo.left[k + 1] + PAD - GAP / 2, top: VIDEO_TOP + 4 }}>
                  {styled ? '✦' : '·'}
                </button>
              )
            })}

            {strips.map((a) => {
              const m = moving?.id === a.id ? moving : null
              const at = m ? m.at : a.at
              const x = xOf(Math.min(at, tl.total))
              const w = Math.max(28, Math.min(geo.end + PAD, xOf(Math.min(at + a.dur, tl.total))) - x)
              const label = `Sound of shot ${a.n ?? ''}`.trim()
              return (
                <div key={a.id}
                     title={`${label} · ${a.mute ? 'muted' : `${Math.round(a.gain * 100)}%`}\nClick to change its volume and fades. Drag to move it (it sticks to cuts; hold ⌥ for exact).`}
                     onPointerDown={(e) => {
                       if (e.button !== 0) return
                       e.stopPropagation()
                       e.currentTarget.setPointerCapture(e.pointerId)
                       setMoving({ id: a.id, x0: e.clientX, grab: e.clientX - e.currentTarget.getBoundingClientRect().left, at: a.at, moved: false })
                     }}
                     onPointerMove={(e) => {
                       if (!m) return
                       if (!m.moved && Math.abs(e.clientX - m.x0) < 4) return
                       setMoving({ ...m, moved: true, at: Math.max(0, Math.min(tl.total - 0.1, overlayTime(e.clientX - m.grab, e.altKey))) })
                     }}
                     onPointerUp={(e) => {
                       if (!m) return
                       setMoving(null)
                       if (!m.moved) { onSelectAudio?.(a.id, e.currentTarget.getBoundingClientRect()); return }
                       if (Math.abs(m.at - a.at) > 1 / 60) onAudioMove?.(a.id, Math.round(m.at * 1000) / 1000)
                     }}
                     className={`absolute flex cursor-grab items-center gap-1.5 overflow-hidden rounded-md px-1.5 font-serif text-[12px] leading-none active:cursor-grabbing ${
                       a.mute ? 'bg-stone-300 text-stone-600' : 'bg-teal-600 text-white'} ${
                       selectedAudio === a.id ? 'ring-2 ring-accent' : ''} ${m?.moved ? 'opacity-80' : ''}`}
                     style={{ left: x, width: w, bottom: stripBottom, height: SOUND_H,
                       backgroundImage: a.mute ? undefined : 'repeating-linear-gradient(90deg, rgba(255,255,255,.18) 0 2px, transparent 2px 5px)' }}>
                  <span className="shrink-0">{a.mute ? '🔇' : '♪'}</span>
                  <span className="truncate">{label}{a.mute ? ' · muted' : a.gain !== 1 ? ` · ${Math.round(a.gain * 100)}%` : ''}</span>
                </div>
              )
            })}

            {dropAt != null && (
              <div className="pointer-events-none absolute w-0.5 rounded bg-accent"
                   style={{ top: VIDEO_TOP - 4, bottom: shotsBottom - 4, left: (dropAt < items.length ? geo.left[dropAt] : geo.end + GAP) + PAD - 2 }} />
            )}

            {/* the snapped / approaching target, named */}
            {hl && hlX != null && (
              <div className="pointer-events-none absolute top-0 bottom-0" style={{ left: hlX }}>
                <div className="absolute top-0 bottom-0 w-px" style={{ background: TICK[hl.type], opacity: sn?.snapped ? 0.9 : 0.4 }} />
                <div className={`absolute top-7 -translate-x-1/2 whitespace-nowrap rounded px-1.5 py-0.5 text-[10px] ${sn?.snapped
                  ? 'bg-zinc-100 text-zinc-900' : 'bg-zinc-800 text-zinc-300'}`}>
                  {sn?.snapped ? '⤓ ' : '→ '}{hl.label}
                </div>
              </div>
            )}

            {/* playhead */}
            <div className="pointer-events-none absolute top-0 bottom-0 w-px bg-white" style={{ left: xOf(ph) }}>
              <div className="-ml-[5px] size-[11px] rounded-sm bg-white" />
            </div>
          </div>
        )}
      </div>
      </div>
    </section>
  )
}

function LaneLabel({ icon, style, children }: { icon: IconName; style: React.CSSProperties; children: React.ReactNode }) {
  return (
    <div className="absolute inset-x-0 flex items-center gap-2 px-3 font-serif text-[15px] text-zinc-200" style={style}>
      <Icon name={icon} size={18} className="shrink-0 text-zinc-400" />{children}
    </div>
  )
}

function Tool({ icon, label, title, onClick, disabled }: { icon: IconName; label: string; title: string; onClick: () => void; disabled?: boolean }) {
  return (
    <button type="button" onClick={onClick} title={title} disabled={disabled}
            className="flex h-8 shrink-0 items-center gap-1.5 rounded-md px-2 font-serif text-[15px] text-zinc-100 hover:bg-raised disabled:opacity-35">
      <Icon name={icon} size={18} />{label}
    </button>
  )
}

function TB({ children, onClick, title, wide }: { children: React.ReactNode; onClick: () => void; title: string; wide?: boolean }) {
  return (
    <button type="button" onClick={onClick} title={title}
            className={`grid h-8 place-items-center rounded-md bg-raised text-[11px] text-zinc-100 hover:bg-zinc-700 ${wide ? 'w-10' : 'w-8'}`}>
      {children}
    </button>
  )
}

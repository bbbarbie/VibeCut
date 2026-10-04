import { useEffect, useMemo, useRef, useState } from 'react'
import { clock, locate, parseTimecode, readout, smpte, type SeqItem } from '../sequence'
import { approaching, snap, type Target, type TargetType } from '../snap'
import { phStore, snapStore, transport, transportStore, useStore } from '../transport'
import type { Overlay, TimelineData } from '../types'
import { KIND_META } from '../overlayDraw'
import { SHOT_MIME } from './Shelf'

const TL_MIME = 'application/x-vibecut-tl'
const MIN_W = 56
const GAP = 2
const PAD = 12

export const TICK: Record<TargetType, string> = {
  shot: '#e4e4e7', silence: '#6ee7b7', motion: '#fcd34d', beat: '#b9d9eb', word: '#c4b5fd',
}
const TICK_H: Record<TargetType, number> = { shot: 14, silence: 9, motion: 7, beat: 6, word: 8 }
const MARK_CLS = { added: 'bg-emerald-400', moved: 'bg-amber-300', trimmed: 'bg-sky-400' } as const
export type Marks = { in: number | null; out: number | null }

const LANE_ROW = 17
type Drag = { id: string; mode: 'move' | 'end'; x0: number; grab: number; start: number; end: number; moved: boolean }

export function Timeline({ tl, marks, marksOf, selected, flash, alt, onSelect, onReorder,
  onInsertShot, onClear, onHelp, overlays = [], selectedOverlay = null, onSelectOverlay, onOverlayEdit, onExport }: {
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
  const items = tl.items

  useEffect(() => {
    const el = track.current
    if (!el) return
    const ro = new ResizeObserver(() => setWidth(el.clientWidth))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  // Geometry: widths proportional to duration, with a floor so a short
  // shot stays hittable. Position <-> time is exact within each block.
  const fit = tl.total > 0 ? Math.max(0.5, (width - 2 * PAD - items.length * GAP) / tl.total) : 10
  const pps = fit * zoom
  const geo = useMemo(() => {
    const w = items.map((it) => Math.max(MIN_W, (it.seq_end - it.seq_start) * pps))
    const left: number[] = []
    w.forEach((_, k) => left.push(k ? left[k - 1] + w[k - 1] + GAP : 0))
    return { w, left, end: (left.at(-1) ?? 0) + (w.at(-1) ?? 0) }
  }, [items, pps])

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
  const laneH = lanes.n ? lanes.n * LANE_ROW + 6 : 0
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
    <section className="flex h-[250px] shrink-0 flex-col border-t border-line bg-panel">
      <header className="flex h-10 shrink-0 items-center gap-2.5 border-b border-line px-3">
        <div className="flex items-center gap-1">
          <TB title="Play backwards (J — press again to go faster)" onClick={() => transport.play(rate < 0 ? Math.max(rate * 2, -8) : -1)}>◀◀</TB>
          <TB title="Play / pause (Space)" onClick={() => (tr.playing ? transport.stop() : transport.play(1))} wide>
            {tr.playing ? '❚❚' : '▶'}
          </TB>
          <TB title="Play forwards (L — press again to go faster)" onClick={() => transport.play(rate > 0 ? Math.min(rate * 2, 8) : 1)}>▶▶</TB>
          {tr.playing && rate !== 1 && <span className="w-8 text-[11px] tabular-nums text-accent">{rate > 0 ? `${rate}×` : `−${-rate}×`}</span>}
        </div>

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
        <label className="flex shrink-0 items-center gap-1.5 text-[11px] text-muted">
          Zoom
          <input type="range" min={1} max={40} step={0.5} value={zoom}
                 onChange={(e) => setZoom(Number(e.target.value))} className="w-20 accent-[#b9d9eb]" />
        </label>
        {onExport && (
          <button type="button" onClick={onExport} disabled={!items.length} title="Render the edit, its captions and its music to one video file"
                  className="shrink-0 rounded-md bg-accent px-2 py-0.5 text-[11px] font-semibold text-accent-ink disabled:opacity-30">Export…</button>
        )}
        <button type="button" onClick={onHelp} title="Keyboard shortcuts"
                className="grid size-6 shrink-0 place-items-center rounded-md border border-line text-[12px] text-muted hover:text-zinc-200">?</button>
        <button type="button" onClick={onClear} disabled={!items.length}
                className="shrink-0 rounded-md px-1.5 py-1 text-[11px] text-muted hover:text-zinc-200 disabled:opacity-30">Clear</button>
      </header>

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
            Choose a story first — or drag shots here from above
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
                  <rect x={inX} y={0} width={outX - inX} height={28} fill="#b9d9eb" opacity={0.18} />
                )}
                {tl.targets.map((g: Target, i) => (
                  <line key={i} x1={xOf(g.t)} x2={xOf(g.t)} y1={28 - TICK_H[g.type]} y2={28}
                        stroke={TICK[g.type]} strokeWidth={g.type === 'shot' ? 1.5 : 1} opacity={g === hl ? 1 : 0.55} />
                ))}
                {inX != null && <path d={`M${inX},2 v24 h5`} stroke="#b9d9eb" fill="none" strokeWidth={2} />}
                {outX != null && <path d={`M${outX},2 v24 h-5`} stroke="#b9d9eb" fill="none" strokeWidth={2} />}
              </svg>
            </div>

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
                     className={`absolute flex cursor-grab items-center gap-1 overflow-hidden rounded px-1 text-[10px] leading-none text-zinc-900 active:cursor-grabbing ${
                       selectedOverlay === o.id ? 'ring-2 ring-white' : ''} ${d?.moved ? 'opacity-80' : ''}`}
                     style={{ left: x, width: w, top: 31 + (lanes.row.get(o.id) ?? 0) * LANE_ROW, height: LANE_ROW - 3, background: meta.color }}>
                  <span className="shrink-0 font-semibold">{meta.icon}</span>
                  <span className="truncate">{o.kind === 'chapters' ? 'Chapter bar' : o.text}</span>
                  {edge && <span className="absolute inset-y-0 right-0 w-1.5 cursor-ew-resize bg-black/20" />}
                </div>
              )
            })}

            {items.map((it: SeqItem, k) => (k === 0 || items[k - 1].beat_id !== it.beat_id) && (
              <div key={`beat-${it.beat_id}-${k}`} className="pointer-events-none absolute top-8 truncate text-[10px] font-medium text-zinc-400"
                   style={{ left: geo.left[k] + PAD, maxWidth: 220, top: 32 + laneH }}>
                {it.beat_title}
              </div>
            ))}

            {items.map((it, k) => {
              const thumb = it.kind === 'shot' ? `/api/thumbs/${it.clip_id}/shot${String(Number(it.shot_id!.split(':')[1])).padStart(3, '0')}.jpg` : null
              const mark = marksOf[it.key]
              return (
                <div
                  key={it.key}
                  draggable
                  onDragStart={(e) => { e.dataTransfer.setData(TL_MIME, it.key); e.dataTransfer.effectAllowed = 'move' }}
                  onPointerDown={(e) => {
                    if (e.button !== 0) return
                    const rect = e.currentTarget.getBoundingClientRect()
                    scrubTo(e.clientX, e.altKey)   // a click also puts the playhead there
                    onSelect(it.key, new DOMRect(e.clientX - 1, rect.top, 2, rect.height))
                  }}
                  className={`group absolute bottom-3 cursor-pointer overflow-hidden rounded-md ${it.kind === 'gap'
                    ? 'bg-[repeating-linear-gradient(45deg,#18181b,#18181b_6px,#27272a_6px,#27272a_12px)]' : 'bg-black'} ${
                    selected === it.key ? 'ring-2 ring-accent' : 'ring-1 ring-zinc-800 hover:ring-zinc-600'}`}
                  style={{
                    top: 50 + laneH, left: geo.left[k] + PAD, width: geo.w[k],
                    backgroundImage: thumb ? `url(${thumb})` : undefined,
                    backgroundSize: 'auto 100%', backgroundRepeat: 'repeat-x', backgroundPosition: 'center',
                  }}
                  title={it.kind === 'gap' ? `${(it.seq_end - it.seq_start).toFixed(2)}s gap` : `Shot ${it.n} · ${(it.seq_end - it.seq_start).toFixed(2)}s`}
                >
                  {mark && <div className={`absolute inset-x-0 top-0 h-1 ${MARK_CLS[mark]}`} />}
                  <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/80 to-transparent px-1.5 pb-1 pt-3 text-[10px] tabular-nums text-zinc-200">
                    {it.kind === 'gap' ? 'gap ' : it.n != null ? `${it.n} · ` : ''}{(it.seq_end - it.seq_start).toFixed(1)}s
                  </div>
                </div>
              )
            })}

            {dropAt != null && (
              <div className="pointer-events-none absolute bottom-2 w-0.5 rounded bg-accent"
                   style={{ top: 46 + laneH, left: (dropAt < items.length ? geo.left[dropAt] : geo.end + GAP) + PAD - 2 }} />
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
    </section>
  )
}

function TB({ children, onClick, title, wide }: { children: React.ReactNode; onClick: () => void; title: string; wide?: boolean }) {
  return (
    <button type="button" onClick={onClick} title={title}
            className={`grid h-7 place-items-center rounded-md bg-raised text-[11px] text-zinc-100 hover:bg-zinc-700 ${wide ? 'w-9' : 'w-7'}`}>
      {children}
    </button>
  )
}

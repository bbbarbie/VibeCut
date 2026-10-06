import { useEffect, useRef, useState } from 'react'
import type { Clip, CutClip, CutData, CutShot } from '../types'
import { dur } from '../format'

// The one gate: what the rough cut threw away and trimmed, and why.
// Nothing here is deleted -- every decision is one click from undone.
export function CutReview({ data, clips, approved, busy, onOverride, onApprove, onWatch, onClose }: {
  data: CutData
  clips: Clip[]
  approved: boolean
  busy: boolean
  onOverride: (target: string, action: string, range?: [number, number]) => void
  onApprove: () => void
  onWatch: (clipId: string, start: number, end: number, id: string) => void
  onClose?: () => void
}) {
  const thumb = (cid: string) => clips.find((c) => c.id === cid)?.shots[0]?.thumb ?? ''
  const thrown = data.clips.filter((c) => c.rejected)
  const kept = data.clips.filter((c) => !c.rejected)
  const s = data.summary
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto p-5 pb-28">
        <p className="text-[12px] text-muted">{approved ? 'The rough cut · approved — changes here still apply to the story' : 'The rough cut · before the story is built'}</p>
        <h2 className="mt-1 font-serif text-[26px] text-zinc-100">Here’s what I’d throw away</h2>
        <p className="mt-1 max-w-2xl text-[13px] text-zinc-400">
          Nothing is deleted from your clips. Thrown-away clips wait on the shelf, and every trim is just a start and an end point. Change anything with one click, then approve.
        </p>
        {s && (
          <div className="mt-4 rounded-xl border border-line bg-raised px-4 py-3">
            <div className="font-serif text-[22px] text-zinc-100">{s.line_en}</div>
          </div>
        )}

        <h3 className="mt-6 text-[11px] font-semibold uppercase tracking-wider text-muted">Thrown away · {thrown.length}</h3>
        {thrown.length === 0 && <p className="mt-2 text-[12px] text-muted">Nothing — every clip had something usable.</p>}
        <div className="mt-2 grid grid-cols-[repeat(auto-fill,minmax(210px,1fr))] gap-2">
          {thrown.map((c) => (
            <div key={c.id} className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-2">
              <div className="relative">
                <img src={thumb(c.id)} className="aspect-video w-full rounded object-cover" />
                <span className="absolute bottom-1 right-1 rounded bg-black/70 px-1 text-[10px] tabular-nums text-zinc-300">{dur(c.duration)}</span>
              </div>
              <div className="mt-1.5 truncate text-[11px] text-zinc-400">{c.name}</div>
              <div className="text-[13px] leading-snug text-zinc-100">{c.override === 'reject' ? 'You threw this away' : c.en}</div>
              {c.override !== 'reject' && c.unverified?.length > 0 && (
                <div className="text-[11px] leading-snug text-amber-200/80" title="Judged from about one frame a second — what happened between them wasn’t seen">
                  Judged from a few frames — play it to be sure
                </div>
              )}
              <div className="mt-2 flex gap-1.5">
                <Btn onClick={() => onWatch(c.id, 0, c.duration, c.id)}>Watch</Btn>
                {c.override === 'reject'
                  ? <Btn onClick={() => onOverride(c.id, 'auto')}>Undo</Btn>
                  : <Btn primary onClick={() => onOverride(c.id, 'keep')}>Use it anyway</Btn>}
              </div>
            </div>
          ))}
        </div>

        <h3 className="mt-7 text-[11px] font-semibold uppercase tracking-wider text-muted">Kept, and trimmed to the best part · {kept.length}</h3>
        <div className="mt-2 space-y-2">
          {kept.map((c) => <KeptRow key={c.id} c={c} clip={clips.find((x) => x.id === c.id)} thumb={thumb(c.id)} onOverride={onOverride} onWatch={onWatch} />)}
        </div>
      </div>

      <div className="absolute inset-x-0 bottom-0 flex items-center gap-4 border-t border-line bg-panel/95 px-5 py-3 backdrop-blur">
        <div className="min-w-0">
          <div className="truncate font-serif text-[17px] text-zinc-100">{s?.line_en}</div>
          <div className="text-[11px] text-muted">{approved ? 'Already approved. Your changes are recorded.' : 'Nothing is built on this until you approve it.'}</div>
        </div>
        <div className="ml-auto flex gap-2">
          {approved && onClose && <Btn onClick={onClose}>Back to my story</Btn>}
          {!approved && (
            <button type="button" onClick={onApprove} disabled={busy}
                    className="rounded-lg bg-accent px-5 py-2 text-[13px] font-semibold text-accent-ink disabled:opacity-40">
              Looks right — continue
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

function KeptRow({ c, clip, thumb, onOverride, onWatch }: {
  c: CutClip; clip?: Clip; thumb: string
  onOverride: (target: string, action: string, range?: [number, number]) => void
  onWatch: (clipId: string, start: number, end: number, id: string) => void
}) {
  const shots = Object.values(c.shots)
  return (
    <div className="rounded-xl border border-line bg-raised/60 px-3 py-2.5">
      <div className="flex items-center gap-3">
        <img src={thumb} className="h-10 w-16 shrink-0 rounded object-cover" />
        <div className="min-w-0">
          <div className="truncate text-[12px] text-zinc-300">{c.name} <span className="text-muted">· {dur(c.duration)}{c.talking ? ' · someone talking' : ''}</span></div>
          {c.override === 'keep' && <div className="text-[11px] text-accent">You kept it (I’d have left it out: {c.en}) <button type="button" className="underline" onClick={() => onOverride(c.id, 'auto')}>Undo</button></div>}
          {c.flags.map((f) => <div key={f.code} className="text-[11px] text-amber-200/90">{f.en}</div>)}
        </div>
        <div className="ml-auto shrink-0">
          <Btn danger onClick={() => onOverride(c.id, 'reject')}>Throw away</Btn>
        </div>
      </div>
      {shots.map((s) => <ShotBar key={s.id} clipId={c.id} clip={clip} s={s} single={shots.length === 1} onOverride={onOverride} onWatch={onWatch} />)}
    </div>
  )
}

const MIN_KEEP_S = 1   // same floor as cut.MIN_SET_S

// m:ss.t -- a tenth of a second matters when you're placing a cut
const stamp = (t: number) => `${Math.floor(t / 60)}:${(t % 60).toFixed(1).padStart(4, '0')}`

function ShotBar({ clipId, clip, s, single, onOverride, onWatch }: {
  clipId: string; clip?: Clip; s: CutShot; single: boolean
  onOverride: (target: string, action: string, range?: [number, number]) => void
  onWatch: (clipId: string, start: number, end: number, id: string) => void
}) {
  const [a, b] = s.full
  const len = Math.max(b - a, 1e-6)
  const bar = useRef<HTMLDivElement>(null)
  const [hover, setHover] = useState<number | null>(null)
  // While a handle is held, the range is local; it's sent once, on release.
  const [drag, setDrag] = useState<{ edge: 0 | 1; range: [number, number] } | null>(null)
  // What was just sent shows until the server answers with a new range.
  const key = s.use.join(',')
  const [sent, setSent] = useState<{ range: [number, number]; was: string } | null>(null)
  if (sent && sent.was !== key) setSent(null)     // the answer arrived
  const [u0, u1] = drag?.range ?? (sent?.was === key ? sent.range : null) ?? s.use
  const pct = (t: number) => `${((t - a) / len) * 100}%`
  const max = Math.max(...s.seconds, 0.001)
  const at = (clientX: number) => {
    const r = bar.current!.getBoundingClientRect()
    return Math.round((a + Math.min(Math.max((clientX - r.left) / r.width, 0), 1) * len) * 10) / 10
  }
  const place = (edge: 0 | 1, t: number, from: [number, number]): [number, number] => {
    const span = Math.min(MIN_KEEP_S, len)
    return edge === 0 ? [Math.max(a, Math.min(t, from[1] - span)), from[1]]
      : [from[0], Math.min(b, Math.max(t, from[0] + span))]
  }
  const commit = (range: [number, number]) => {
    if (Math.abs(range[0] - s.use[0]) < 0.05 && Math.abs(range[1] - s.use[1]) < 0.05) return
    setSent({ range, was: key })
    onOverride(s.id, 'set', range)
  }
  const peekAt = drag ? drag.range[drag.edge] : hover
  // The preview stays mounted once used, so its video isn't reloaded per hover.
  const [last, setLast] = useState<number | null>(null)
  const move = (d: { edge: 0 | 1; range: [number, number] }) => { setDrag(d); setLast(d.range[d.edge]) }
  const handle = (edge: 0 | 1) => (
    <div role="slider" tabIndex={0} aria-label={edge === 0 ? 'Start of what’s kept' : 'End of what’s kept'}
         aria-valuemin={a} aria-valuemax={b} aria-valuenow={edge === 0 ? u0 : u1} aria-valuetext={stamp(edge === 0 ? u0 : u1)}
         className="group absolute inset-y-0 z-10 flex w-3 -translate-x-1/2 cursor-ew-resize touch-none items-center justify-center outline-none"
         style={{ left: pct(edge === 0 ? u0 : u1) }}
         onPointerDown={(e) => {
           e.preventDefault(); e.stopPropagation()
           e.currentTarget.setPointerCapture(e.pointerId)
           move({ edge, range: [u0, u1] })
         }}
         onPointerMove={(e) => { if (drag) move({ ...drag, range: place(drag.edge, at(e.clientX), drag.range) }) }}
         onPointerUp={() => { if (drag) { commit(drag.range); setDrag(null) } }}
         onPointerCancel={() => setDrag(null)}
         onKeyDown={(e) => {
           const d = e.key === 'ArrowLeft' ? -0.5 : e.key === 'ArrowRight' ? 0.5 : 0
           if (!d) return
           e.preventDefault()
           commit(place(edge, (edge === 0 ? u0 : u1) + d, [u0, u1]))
         }}>
      <span className="h-5 w-1.5 rounded-full bg-accent shadow ring-1 ring-black/40 transition-transform group-hover:scale-y-110 group-focus-visible:ring-2 group-focus-visible:ring-white" />
    </div>
  )
  return (
    <div className="mt-2 pl-[76px]">
      {!single && <div className="mb-0.5 text-[10px] text-muted">shot {Number(s.id.split(':')[1]) + 1}</div>}
      <div className="relative">
        {last !== null && clip && <Peek clip={clip} t={last} left={(last - a) / len} shown={peekAt !== null} />}
        {/* the whole clip, with the kept part lit; the little bars are how good each second is.
            Hover to see any moment; drag the lit part's ends to set it yourself. */}
        <div ref={bar} className="relative h-7 cursor-crosshair rounded-md bg-zinc-900"
             onPointerMove={(e) => { if (!drag) { const t = at(e.clientX); setHover(t); setLast(t) } }}
             onPointerLeave={() => setHover(null)}>
          <div className="absolute inset-0 flex items-end overflow-hidden rounded-md">
            {s.seconds.map((v, i) => (
              <div key={i} className="flex-1 bg-zinc-600/60" style={{ height: `${Math.max(8, (v / max) * 100)}%`, marginRight: 1 }} />
            ))}
          </div>
          <div className="pointer-events-none absolute inset-y-0 rounded-md border-2 border-accent bg-accent/25" style={{ left: pct(u0), width: `calc(${pct(u1)} - ${pct(u0)})` }} />
          {hover !== null && !drag && <div className="pointer-events-none absolute inset-y-0 w-px bg-white/80" style={{ left: pct(hover) }} />}
          {handle(0)}
          {handle(1)}
        </div>
      </div>
      <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="text-[12px] tabular-nums text-zinc-200">keeps {dur(u0)}–{dur(u1)} · {(u1 - u0).toFixed(0)}s of {len.toFixed(0)}s</span>
        <span className="text-[12px] text-zinc-300">
          {drag ? 'Let go to keep this' : s.override === 'full' ? 'You kept the whole clip' : s.override === 'set' ? 'You set this part yourself' : s.reason_en}
        </span>
      </div>
      <div className="mt-1.5 flex flex-wrap gap-1.5">
        <Btn onClick={() => onWatch(clipId, u0, u1, s.id)}>Watch what’s kept</Btn>
        <Btn onClick={() => onOverride(s.id, 'shorter')} disabled={u1 - u0 <= 1.5}>Shorter</Btn>
        <Btn onClick={() => onOverride(s.id, 'longer')} disabled={u1 - u0 >= len - 0.1}>Longer</Btn>
        {s.override === 'full' ? <Btn onClick={() => onOverride(s.id, 'auto')}>Undo whole clip</Btn>
          : !s.whole && <Btn onClick={() => onOverride(s.id, 'full')}>Keep the whole clip</Btn>}
        {(s.override || Math.abs((s.window[1] - s.window[0]) - (s.auto[1] - s.auto[0])) > 0.05) && s.override !== 'full' &&
          <Btn onClick={() => onOverride(s.id, 'auto')}>Back to my suggestion</Btn>}
      </div>
    </div>
  )
}

// The frame at one moment of a clip, floating over the bar. The nearest
// index frame (about one a second) shows at once; the clip itself is seeked
// underneath and takes over when it lands on the exact moment.
function Peek({ clip, t, left, shown }: { clip: Clip; t: number; left: number; shown: boolean }) {
  const vid = useRef<HTMLVideoElement>(null)
  const want = useRef(t)
  const busy = useRef(false)
  const [landed, setLanded] = useState<number | null>(null)
  const seek = () => {
    const v = vid.current
    if (!v || busy.current || v.readyState < 1) return
    if (Math.abs(v.currentTime - want.current) < 0.04) { setLanded(v.currentTime); return }
    busy.current = true
    v.currentTime = want.current
  }
  useEffect(() => { want.current = t; seek() }, [t])
  const times = clip.samples?.times ?? []
  let near = -1
  times.forEach((x, i) => { if (near < 0 || Math.abs(x - t) < Math.abs(times[near] - t)) near = i })
  const exact = landed !== null && Math.abs(landed - t) < 0.15
  const tall = clip.height > clip.width
  const w = tall ? 118 : 208
  const h = tall ? 210 : 117
  return (
    <div className={`pointer-events-none absolute bottom-full z-20 mb-2 -translate-x-1/2 ${shown ? '' : 'invisible'}`}
         style={{ left: `clamp(${w / 2}px, ${left * 100}%, calc(100% - ${w / 2}px))` }}>
      <div className="relative overflow-hidden rounded-lg border border-line bg-black shadow-2xl" style={{ width: w, height: h }}>
        {near >= 0 && <img src={`${clip.samples!.base}${near}`} className="absolute inset-0 size-full object-cover" alt="" />}
        <video ref={vid} src={clip.video} muted playsInline preload="auto"
               className={`absolute inset-0 size-full object-cover ${exact ? 'opacity-100' : 'opacity-0'}`}
               onLoadedMetadata={seek}
               onSeeked={(e) => { busy.current = false; setLanded(e.currentTarget.currentTime); seek() }} />
        <span className="absolute bottom-1 left-1/2 -translate-x-1/2 rounded bg-black/75 px-1.5 py-px text-[11px] tabular-nums text-zinc-100">{stamp(t)}</span>
      </div>
    </div>
  )
}

function Btn({ children, onClick, primary, danger, disabled }: {
  children: React.ReactNode; onClick: () => void; primary?: boolean; danger?: boolean; disabled?: boolean
}) {
  return (
    <button type="button" onClick={onClick} disabled={disabled}
            className={`rounded-md px-2.5 py-1 text-[12px] disabled:opacity-30 ${primary ? 'bg-accent font-semibold text-accent-ink'
              : danger ? 'border border-rose-400/40 text-rose-200 hover:bg-rose-500/10' : 'border border-line text-zinc-200 hover:bg-zinc-800'}`}>
      {children}
    </button>
  )
}

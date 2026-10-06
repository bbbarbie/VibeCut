import { useEffect, useRef, useState } from 'react'
import type { Clip, ImportError, Shot } from '../types'
import { dur, when } from '../format'
import { Button, Notice, Progress, cx } from '../ui'

// The footage stage: what's in the project, how the reading is going, what
// couldn't be read (with a retry), and the one way forward. Every clip is
// only read; nothing is copied, moved or changed.
//
// sarah (2026-10-06): a grid of every clip asked her to inspect each one.
// What she needs from this page is the rough cut's first call -- which clips
// it keeps, which it leaves out -- and a way to overrule it. So clips are
// sorted into two photo stacks as they're read; opening a stack shows its
// clips one by one (left-out ones say why), a double-click moves a clip to
// the other stack, and "Looks good" moves on.

export type Importing = { text: string; frac: number | null } | null

type Side = 'kept' | 'out'
type Decide = 'keep' | 'reject' | 'auto'

const side = (c: Clip): Side => (c.cut?.rejected ? 'out' : 'kept')

/** The decision that moves a clip to the other stack. Going back to the rough
 *  cut's own call is 'auto', so overruling twice leaves no override behind. */
function flipAction(c: Clip): Decide {
  const auto = !!c.cut?.auto_rejected
  if (side(c) === 'kept') return auto ? 'auto' : 'reject'
  return auto ? 'keep' : 'auto'
}

// The whole sort plays in about this long, however many clips there are:
// long enough to see clips land, short enough never to be waited on.
const SORT_MS = 2400

export function Footage({ clips, importing, errors, vision, onPick, onRetry, onPreview, onDecide, onNext, canContinue, briefDone }: {
  clips: Clip[]
  importing: Importing
  errors: ImportError[]
  vision: string
  onPick: (files: FileList) => void
  onRetry: (paths: string[]) => void
  onPreview: (clip: Clip, shot: Shot) => void
  /** keep / reject a clip the rough cut left out, or 'auto' to give the call back */
  onDecide: (clip: Clip, action: Decide) => void
  onNext: () => void
  canContinue: boolean
  briefDone: boolean
}) {
  const folder = useRef<HTMLInputElement>(null)
  const files = useRef<HTMLInputElement>(null)
  const retryable = errors.map((e) => e.path).filter((p): p is string => !!p)
  const [open, setOpen] = useState<Side | null>(null)
  const [moved, setMoved] = useState<{ clip: Clip; to: Side } | null>(null)

  // Clips arrive all at once when a read finishes; they're dealt onto the
  // stacks one at a time. Only clips that come from an import on this page
  // are dealt -- reopening a project shows its stacks straight away.
  const [sorted, setSorted] = useState<Set<string>>(() => new Set(clips.map((c) => c.id)))
  const armed = useRef(false)
  const batch = useRef(0)
  if (importing) armed.current = true
  const pending = clips.filter((c) => !sorted.has(c.id))
  useEffect(() => {
    if (!pending.length) { armed.current = !!importing; batch.current = 0; return }
    if (!armed.current) { setSorted(new Set(clips.map((c) => c.id))); return }
    if (importing) return // dealt once the read is done, so the counts are final
    batch.current = Math.max(batch.current, pending.length)
    const t = setTimeout(() => setSorted((s) => new Set(s).add(pending[0].id)),
      Math.max(30, Math.min(180, SORT_MS / batch.current)))
    return () => clearTimeout(t)
  }, [pending.length, pending[0]?.id, importing]) // eslint-disable-line react-hooks/exhaustive-deps
  const sorting = pending.length > 0 && !importing && armed.current
  const dealt = batch.current - pending.length

  const flip = (c: Clip) => { const to: Side = side(c) === 'kept' ? 'out' : 'kept'; onDecide(c, flipAction(c)); setMoved({ clip: c, to }) }
  useEffect(() => { if (!moved) return; const t = setTimeout(() => setMoved(null), 6000); return () => clearTimeout(t) }, [moved])

  const inputs = (
    <>
      {/* @ts-expect-error -- non-standard but supported everywhere that matters */}
      <input ref={folder} type="file" className="hidden" webkitdirectory="" multiple
             onChange={(e) => { if (e.target.files) onPick(e.target.files); e.target.value = '' }} />
      <input ref={files} type="file" className="hidden" multiple accept=".mp4,.mov,video/mp4,video/quicktime"
             onChange={(e) => { if (e.target.files) onPick(e.target.files); e.target.value = '' }} />
    </>
  )

  if (!clips.length && !importing && !errors.length) {
    return (
      <div className="grid min-h-0 flex-1 place-items-center p-8">
        {inputs}
        <div className="w-full max-w-xl rounded-2xl border border-dashed border-zinc-700 p-10 text-center">
          <h2 className="font-serif text-[26px] text-zinc-100">Start with your clips</h2>
          <p className="mt-2 text-[13px] text-zinc-400">Drag a folder of videos anywhere onto this window, or choose one. Every clip is read once, on this computer.</p>
          <div className="mt-6 flex justify-center gap-2">
            <Button variant="primary" size="lg" onClick={() => folder.current?.click()}>Choose a folder</Button>
            <Button size="lg" onClick={() => files.current?.click()}>Choose some clips</Button>
          </div>
          <p className="mt-4 text-[11px] text-muted">.mp4 and .mov · nothing is uploaded or changed</p>
        </div>
      </div>
    )
  }

  const shown = clips.filter((c) => sorted.has(c.id))
  const kept = shown.filter((c) => side(c) === 'kept')
  const out = shown.filter((c) => side(c) === 'out')
  const done = !importing && !sorting

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {inputs}
      <div className="flex min-h-0 flex-1 flex-col overflow-y-auto p-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="min-w-0">
            <h2 className="font-serif text-[24px] leading-tight text-zinc-100">Footage</h2>
            <p className="mt-0.5 text-[12px] text-zinc-400">
              {clips.length ? <>{clips.length} clip{clips.length === 1 ? '' : 's'} · {dur(clips.reduce((n, c) => n + c.duration, 0))}</> : 'Nothing read yet'}
            </p>
          </div>
          <div className="ml-auto flex gap-2">
            <Button disabled={!!importing} onClick={() => files.current?.click()}>Add clips</Button>
            <Button disabled={!!importing} onClick={() => folder.current?.click()}>Add a folder</Button>
          </div>
        </div>

        {errors.length > 0 && (
          <Notice tone="bad" className="mt-4">
            <div className="flex items-start gap-3">
              <div className="min-w-0 flex-1">
                <div className="font-medium">{errors.length} file{errors.length === 1 ? '' : 's'} couldn’t be read</div>
                <ul className="mt-1 space-y-0.5 text-[11px] text-rose-100/80">
                  {errors.map((e, i) => <li key={i} className="truncate" title={e.path ?? ''}>{e.path ? e.path.split('/').pop() : 'The import'} — {e.error}</li>)}
                </ul>
              </div>
              {retryable.length > 0 && <Button size="sm" disabled={!!importing} onClick={() => onRetry(retryable)}>Try again</Button>}
            </div>
          </Notice>
        )}

        {vision !== 'ready' && clips.length > 0 && (
          <p className="mt-3 text-[11px] text-muted">
            {vision === 'building' ? 'Building the on-device helper that names what’s in each shot…'
              : 'On-device labels (what’s in each shot, faces) need macOS — shots are grouped by colour instead, so “subject by subject” is cruder.'}
          </p>
        )}

        {open
          ? <Strip side={open} clips={open === 'kept' ? kept : out} other={open === 'kept' ? out.length : kept.length}
                   onSwitch={() => setOpen(open === 'kept' ? 'out' : 'kept')} onClose={() => setOpen(null)}
                   onPreview={onPreview} onFlip={flip} />
          : (
            <div className="flex flex-1 flex-wrap items-center justify-center gap-x-16 gap-y-6 py-4">
              <Stack side="kept" clips={kept} onOpen={() => setOpen('kept')} />
              <Stack side="out" clips={out} onOpen={() => setOpen('out')} />
            </div>
          )}
      </div>

      {/* In the page's flow, not floating over it: on a short window it used to
          hide the stack names and the left-out reasons. */}
      <div className="shrink-0 border-t border-line bg-panel px-5 py-3" aria-live="polite">
        {!done ? (
          <div className="mx-auto max-w-xl">
            <Progress frac={importing ? (importing.frac ?? 0.05) : dealt / Math.max(1, batch.current)} />
            <p className="mt-1.5 truncate text-center text-[12px] text-zinc-300">
              {importing ? importing.text : `Sorting clip ${Math.min(dealt + 1, batch.current)} of ${batch.current}…`}
            </p>
          </div>
        ) : (
          <div className="flex items-center gap-4">
            <div className="min-w-0 text-[12px] text-zinc-400">
              {moved
                ? <>Moved {moved.clip.name} to {moved.to === 'kept' ? 'Kept' : 'Left out'}. <button type="button" className="text-zinc-200 underline decoration-zinc-500 hover:text-white"
                    onClick={() => { const c = clips.find((x) => x.id === moved.clip.id); if (c) onDecide(c, flipAction(c)); setMoved(null) }}>Undo</button></>
                : !clips.length ? 'Add some clips to begin.'
                  : `${kept.length} kept · ${out.length} left out. Open a stack to check; double-click a clip to move it.`}
            </div>
            <Button variant="primary" size="lg" className="ml-auto" disabled={!canContinue} onClick={onNext}
                    title={briefDone ? 'On to the rough cut' : 'Next, say what this video is'}>
              Looks good →
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}

// A fanned pile like a photo stack in Messages: the last few clips dealt on
// top, a count, and the whole pile opens on a click or a sideways swipe.
function Stack({ side: s, clips, onOpen }: { side: Side; clips: Clip[]; onOpen: () => void }) {
  const down = useRef<number | null>(null)
  const top = clips.slice(-3)
  const tilt = ['-rotate-6 -translate-x-3', 'rotate-4 translate-x-3', 'rotate-0']
  const red = s === 'out'
  return (
    <div className="flex flex-col items-center gap-3">
      <button type="button" disabled={!clips.length} onClick={onOpen} aria-label={`Open ${red ? 'Left out' : 'Kept'}, ${clips.length} clips`}
              onPointerDown={(e) => { down.current = e.clientX }}
              onPointerUp={(e) => { if (down.current !== null && Math.abs(e.clientX - down.current) > 30) onOpen(); down.current = null }}
              onWheel={(e) => { if (clips.length && Math.abs(e.deltaX) > 20) onOpen() }}
              className="group relative h-[150px] w-[210px] touch-pan-y">
        {!clips.length && (
          <div className={cx('absolute inset-0 grid place-items-center rounded-2xl border-2 border-dashed text-[12px]',
            red ? 'border-rose-900/70 text-rose-300/60' : 'border-zinc-700 text-muted')}>
            {red ? 'Nothing left out' : 'Nothing yet'}
          </div>
        )}
        {top.map((c, i) => {
          const k = i + (3 - top.length)
          const thumb = c.shots[0]?.thumb
          return (
            <div key={c.id} style={{ zIndex: i }}
                 className={cx('absolute inset-0 overflow-hidden rounded-2xl border-[3px] shadow-xl shadow-black/60 transition-transform duration-300',
                   red ? 'border-rose-950 bg-rose-950' : 'border-zinc-100 bg-zinc-900', tilt[k],
                   i === top.length - 1 && 'motion-safe:animate-[vc-deal_380ms_cubic-bezier(.2,.9,.3,1.2)] group-hover:-translate-y-1')}>
              {thumb && <img src={thumb} alt="" draggable={false} className="size-full object-cover" />}
              {red && <div className="absolute inset-0 bg-rose-950/35" />}
            </div>
          )
        })}
        {clips.length > 0 && (
          <span className={cx('absolute -right-3 -top-3 z-10 grid h-8 min-w-8 place-items-center rounded-full px-2 text-[14px] font-semibold tabular-nums shadow-lg',
            red ? 'bg-rose-800 text-rose-50' : 'bg-zinc-100 text-zinc-900')}>{clips.length}</span>
        )}
      </button>
      <div className="text-center">
        <div className={cx('font-serif text-[20px]', red ? 'text-rose-200' : 'text-zinc-100')}>{red ? 'Left out' : 'Kept'}</div>
        <div className="text-[11px] text-muted">{clips.length ? 'Click or swipe to look through' : ' '}</div>
      </div>
    </div>
  )
}

// One stack laid out to swipe through. A click plays the clip; a double-click
// moves it to the other stack. Left-out clips say why the rough cut left them.
function Strip({ side: s, clips, other, onSwitch, onClose, onPreview, onFlip }: {
  side: Side; clips: Clip[]; other: number
  onSwitch: () => void; onClose: () => void
  onPreview: (clip: Clip, shot: Shot) => void; onFlip: (clip: Clip) => void
}) {
  const row = useRef<HTMLDivElement>(null)
  const click = useRef<number | undefined>(undefined)
  const red = s === 'out'
  useEffect(() => {
    const key = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', key)
    return () => window.removeEventListener('keydown', key)
  }, [onClose])
  useEffect(() => () => window.clearTimeout(click.current), [])
  const by = (n: number) => row.current?.scrollBy({ left: n * 256, behavior: 'smooth' })
  return (
    <div className="mt-3 flex min-h-0 flex-1 flex-col">
      <div className="flex items-center gap-3">
        <Button size="sm" onClick={onClose}>‹ Both stacks</Button>
        <h3 className={cx('font-serif text-[20px]', red ? 'text-rose-200' : 'text-zinc-100')}>{red ? 'Left out' : 'Kept'} · {clips.length}</h3>
        <span className="text-[11px] text-muted">Click to watch · double-click to move it to {red ? 'Kept' : 'Left out'}</span>
        <Button size="sm" className="ml-auto" onClick={onSwitch}>{red ? 'Kept' : 'Left out'} · {other} ›</Button>
      </div>
      {!clips.length
        ? <p className="mt-10 text-center text-[13px] text-muted">{red ? 'The rough cut kept everything.' : 'Nothing kept yet.'}</p>
        : (
          <div className="relative mt-3">
            <div ref={row} className="flex snap-x snap-mandatory gap-4 overflow-x-auto scroll-smooth px-1 pb-3">
              {clips.map((c) => {
                const first = c.shots[0]
                const mine = c.cut?.override
                return (
                  <div key={c.id} title="Double-click to move it to the other stack"
                       onClick={() => { window.clearTimeout(click.current); click.current = window.setTimeout(() => first && onPreview(c, first), 230) }}
                       onDoubleClick={() => { window.clearTimeout(click.current); onFlip(c) }}
                       className={cx('w-[240px] shrink-0 cursor-pointer select-none snap-center rounded-2xl border p-2 transition-colors motion-safe:animate-[vc-deal_260ms_ease-out]',
                         red ? 'border-rose-900/80 bg-rose-950/70 hover:bg-rose-950' : 'border-line bg-raised hover:border-zinc-600')}>
                    <div className="relative aspect-video overflow-hidden rounded-xl bg-black">
                      {first && <img src={first.thumb} alt="" loading="lazy" draggable={false}
                                     className={cx('size-full', c.height > c.width ? 'object-contain' : 'object-cover')} />}
                      <span className="absolute bottom-1 right-1 rounded bg-black/70 px-1 text-[10px] tabular-nums text-zinc-200">{dur(c.duration)}</span>
                      {c.shots.length > 1 && <span className="absolute left-1 top-1 rounded bg-black/70 px-1 text-[10px] text-zinc-200">{c.shots.length} shots</span>}
                    </div>
                    <div className="mt-2 truncate px-0.5 text-[12px] text-zinc-100" title={c.name}>{c.name}</div>
                    <div className="truncate px-0.5 text-[10px] text-muted">{when(c.capture_time) || 'no date'}</div>
                    {/* The rough cut's call is a suggestion: a two-second clip may be a
                        mis-tap or a short video on purpose, and only the creator knows. */}
                    {red && (
                      <p className="mt-1.5 rounded-lg bg-rose-900/40 px-2 py-1.5 text-[11px] leading-snug text-rose-100">
                        {mine === 'reject' ? 'You moved it here.' : `Left out: ${c.cut?.en}`}
                      </p>
                    )}
                    {!red && mine === 'keep' && c.cut?.auto_rejected && (
                      <p className="mt-1.5 rounded-lg bg-emerald-500/10 px-2 py-1.5 text-[11px] leading-snug text-emerald-200">
                        You kept it. The rough cut would have left it out: {c.cut.en}
                      </p>
                    )}
                  </div>
                )
              })}
            </div>
            {clips.length > 3 && (
              <>
                <button type="button" aria-label="Back" onClick={() => by(-2)}
                        className="absolute -left-2 top-[58px] grid size-9 place-items-center rounded-full bg-black/70 text-[18px] text-zinc-100 hover:bg-black">‹</button>
                <button type="button" aria-label="More" onClick={() => by(2)}
                        className="absolute -right-2 top-[58px] grid size-9 place-items-center rounded-full bg-black/70 text-[18px] text-zinc-100 hover:bg-black">›</button>
              </>
            )}
          </div>
        )}
    </div>
  )
}

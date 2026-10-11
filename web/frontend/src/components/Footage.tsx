import { useEffect, useRef, useState } from 'react'
import type { Clip, ImportError } from '../types'
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
// clips in a column (left-out ones say why), a clip is moved by dragging it
// onto the other stack or with its "Move to" button, and "Looks good" moves on.

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

export function Footage({ clips, importing, errors, vision, onPick, onRetry, onDecide, onNext, canContinue, briefDone }: {
  clips: Clip[]
  importing: Importing
  errors: ImportError[]
  vision: string
  onPick: (files: FileList) => void
  onRetry: (paths: string[]) => void
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
          <p className="mt-2 font-serif text-[17px] text-zinc-200">Drag a folder of videos anywhere onto this window, or choose one. Every clip is read once, on this computer.</p>
          <div className="mt-6 flex justify-center gap-2">
            <Button variant="primary" size="lg" onClick={() => folder.current?.click()}>Choose a folder</Button>
            <Button size="lg" onClick={() => files.current?.click()}>Choose some clips</Button>
          </div>
          <p className="mt-4 font-serif text-[17px] text-zinc-200">.mp4 and .mov · nothing is uploaded or changed</p>
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
            <p className="mt-0.5 font-serif text-[16px] text-zinc-300">
              {clips.length ? <>{clips.length} clip{clips.length === 1 ? '' : 's'} · {dur(clips.reduce((n, c) => n + c.duration, 0))}</> : 'Nothing read yet'}
            </p>
          </div>
          <div className="ml-auto flex gap-2">
            <Button disabled={!!importing} onClick={() => files.current?.click()}>Add clips</Button>
            <Button disabled={!!importing} onClick={() => folder.current?.click()}>Add folder</Button>
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
          <p className="mt-3 font-serif text-[17px] text-zinc-200">
            {vision === 'building' ? 'Building the on-device helper that names what’s in each shot…'
              : 'On-device labels (what’s in each shot, faces) need macOS — shots are grouped by colour instead, so “subject by subject” is cruder.'}
          </p>
        )}

        {open
          ? <Opened side={open} clips={open === 'kept' ? kept : out} others={open === 'kept' ? out : kept}
                   onSwitch={() => setOpen(open === 'kept' ? 'out' : 'kept')} onClose={() => setOpen(null)}
                   onFlip={flip} />
          : (
            <div className="flex flex-1 flex-col items-center justify-center gap-4 py-4">
              <div className="flex flex-wrap items-center justify-center gap-x-16 gap-y-6">
                <Stack side="kept" clips={kept} onOpen={() => setOpen('kept')} />
                <Stack side="out" clips={out} onOpen={() => setOpen('out')} />
              </div>
              {shown.length > 0 && <p className="text-center font-serif text-[17px] text-zinc-200">Click or swipe a stack to look through it</p>}
            </div>
          )}
      </div>

      {/* In the page's flow, not floating over it: on a short window it used to
          hide the stack names and the left-out reasons. */}
      <div className="shrink-0 border-t border-line bg-panel px-5 py-3" aria-live="polite">
        {!done ? (
          <div className="mx-auto max-w-xl">
            <Progress frac={importing ? (importing.frac ?? 0.05) : dealt / Math.max(1, batch.current)} />
            <p className="mt-1.5 truncate text-center font-serif text-[17px] text-zinc-200">
              {importing ? importing.text : `Sorting clip ${Math.min(dealt + 1, batch.current)} of ${batch.current}…`}
            </p>
          </div>
        ) : (
          <div className="flex items-center gap-4">
            <div className="min-w-0 font-serif text-[17px] text-zinc-200">
              {moved
                ? <>Moved {moved.clip.name} to {moved.to === 'kept' ? 'Kept' : 'Left out'}. <button type="button" className="text-zinc-200 underline decoration-zinc-500 hover:text-white"
                    onClick={() => { const c = clips.find((x) => x.id === moved.clip.id); if (c) onDecide(c, flipAction(c)); setMoved(null) }}>Undo</button></>
                : !clips.length ? 'Add some clips to begin.' : null}
            </div>
            <Button variant="primary" size="lg" className="ml-auto" disabled={!canContinue} onClick={onNext}
                    title={briefDone ? 'On to the rough trim' : 'Next, say what this video is'}>
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
          <div className={cx('absolute inset-0 grid place-items-center rounded-2xl border-2 border-dashed font-serif text-[17px]',
            red ? 'border-rose-900/70 text-rose-300/80' : 'border-zinc-700 text-zinc-400')}>
            {red ? 'Nothing left out' : 'Nothing yet'}
          </div>
        )}
        {top.map((c, i) => {
          const k = i + (3 - top.length)
          const thumb = c.shots[0]?.thumb
          return (
            <div key={c.id} style={{ zIndex: i }}
                 className={cx('on-video absolute inset-0 overflow-hidden rounded-2xl border-[3px] shadow-xl shadow-black/60 transition-transform duration-300',
                   red ? 'border-rose-950 bg-rose-950' : 'border-zinc-100 bg-zinc-900', tilt[k],
                   i === top.length - 1 && 'motion-safe:animate-[vc-deal_380ms_cubic-bezier(.2,.9,.3,1.2)] group-hover:-translate-y-1')}>
              {thumb && <img src={thumb} alt="" draggable={false} className="size-full object-cover" />}
              {red && <div className="absolute inset-0 bg-rose-950/35" />}
            </div>
          )
        })}
        {clips.length > 0 && (
          <span className={cx('absolute -right-3 -top-3 z-10 grid h-8 min-w-8 place-items-center rounded-full px-2 text-[14px] font-semibold tabular-nums shadow-lg',
            red ? 'on-video bg-rose-800 text-rose-50' : 'bg-zinc-100 text-zinc-900')}>{clips.length}</span>
        )}
      </button>
      <div className="text-center">
        <div className={cx('font-serif text-[20px]', red ? 'text-rose-200' : 'text-zinc-100')}>{red ? 'Left out' : 'Kept'}</div>
      </div>
    </div>
  )
}

// One stack opened, as in sarah's sketch (2026-10-06): its clips become a
// column you scroll down, on the side the stack already sits on, and the other
// stack shrinks to the opposite side as the place to drop a clip. A click
// plays a clip where it is and offers the move as a button; no double-click.
const CLIP = 'text/x-vibecut-clip'

function Opened({ side: s, clips, others, onSwitch, onClose, onFlip }: {
  side: Side; clips: Clip[]; others: Clip[]
  onSwitch: () => void; onClose: () => void
  onFlip: (clip: Clip) => void
}) {
  const [playing, setPlaying] = useState<string | null>(null)
  const [over, setOver] = useState(false)
  const [dragging, setDragging] = useState(false)
  const red = s === 'out'
  const there = red ? 'Kept' : 'Left out'
  useEffect(() => {
    const key = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', key)
    return () => window.removeEventListener('keydown', key)
  }, [onClose])
  useEffect(() => setPlaying(null), [s])
  const byId = (id: string) => clips.find((c) => c.id === id)

  const target = (
    <div onDragOver={(e) => { if (e.dataTransfer.types.includes(CLIP)) { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; setOver(true) } }}
         onDragLeave={() => setOver(false)}
         onDrop={(e) => { e.preventDefault(); setOver(false); const c = byId(e.dataTransfer.getData(CLIP)); if (c) onFlip(c) }}
         className={cx('flex w-full max-w-[260px] flex-col items-center justify-center gap-3 self-stretch rounded-3xl border-2 border-dashed transition-all duration-300',
           over ? (red ? 'border-zinc-300 bg-zinc-100/10' : 'border-rose-400 bg-rose-950/50')
             : dragging ? 'border-zinc-600' : 'border-transparent')}>
      <div className={cx('origin-center transition-all duration-300 motion-safe:animate-[vc-zoom_300ms_ease-out]',
        over ? 'scale-90 opacity-100' : dragging ? 'scale-75 opacity-90' : 'scale-[.6] opacity-75 hover:opacity-100')}>
        <Stack side={red ? 'kept' : 'out'} clips={others} onOpen={onSwitch} />
      </div>
      <p className="max-w-[200px] text-center font-serif text-[17px] leading-snug text-zinc-200">
        {dragging ? `Drop here to move it to ${there}` : `Drag a clip here to move it to ${there}`}
      </p>
    </div>
  )

  const column = (
    <div className="flex min-h-0 min-w-0 flex-col">
      {!clips.length
        ? <p className="mt-10 text-center font-serif text-[17px] text-zinc-200">{red ? 'The rough cut kept everything.' : 'Nothing kept yet.'}</p>
        : (
          <div className="min-h-0 flex-1 overflow-y-auto px-1 motion-safe:animate-[vc-zoom_300ms_ease-out]">
            <div className="mx-auto flex max-w-[400px] flex-col gap-4 pb-4">
              {clips.map((c) => {
                const first = c.shots[0]
                const mine = c.cut?.override
                const on = playing === c.id
                return (
                  <div key={c.id} draggable
                       onDragStart={(e) => { e.dataTransfer.setData(CLIP, c.id); e.dataTransfer.effectAllowed = 'move'; setDragging(true) }}
                       onDragEnd={() => { setDragging(false); setOver(false) }}
                       onClick={() => setPlaying((p) => (p === c.id ? null : c.id))}
                       className={cx('cursor-pointer select-none rounded-2xl border p-2 transition-colors',
                         red ? 'border-rose-900/80 bg-rose-950/70 hover:bg-rose-950' : 'border-line bg-raised hover:border-zinc-600',
                         on && (red ? 'border-rose-500' : 'border-zinc-400'))}>
                    <div className="relative aspect-video overflow-hidden rounded-xl bg-black">
                      {on
                        ? <video src={`/api/video/${c.id}`} autoPlay playsInline onEnded={() => setPlaying(null)}
                                 className="size-full object-contain" />
                        : first && <img src={first.thumb} alt="" loading="lazy" draggable={false}
                                        className={cx('size-full', c.height > c.width ? 'object-contain' : 'object-cover')} />}
                      <span className="absolute right-1.5 top-1.5 rounded bg-black/70 px-1.5 text-[12px] tabular-nums text-zinc-200">{dur(c.duration)}</span>
                      {c.shots.length > 1 && <span className="absolute left-1.5 top-1.5 rounded bg-black/70 px-1.5 text-[12px] text-zinc-200">{c.shots.length} shots</span>}
                      {/* The reason sits on the picture so it's seen even when the page
                          is short. The rough cut's call is a suggestion: a two-second clip
                          may be a mis-tap or a short video on purpose; only the creator knows. */}
                      {red && !on && (
                        <p className="absolute inset-x-0 bottom-0 bg-rose-950/90 px-2.5 py-1.5 text-[13px] leading-snug text-rose-100">
                          {mine === 'reject' ? 'You moved it here.' : `Left out: ${c.cut?.en}`}
                        </p>
                      )}
                      {!red && !on && mine === 'keep' && c.cut?.auto_rejected && (
                        <p className="absolute inset-x-0 bottom-0 bg-emerald-950/90 px-2.5 py-1.5 text-[13px] leading-snug text-emerald-100">
                          You kept it. The rough cut would have left it out: {c.cut.en}
                        </p>
                      )}
                    </div>
                    <div className="mt-2 flex items-center gap-3 px-0.5">
                      <span className="min-w-0 truncate text-[13px] text-zinc-100" title={c.name}>{c.name}</span>
                      <span className="shrink-0 text-[12px] text-zinc-400">{when(c.capture_time) || 'no date'}</span>
                      {on && (
                        <Button size="sm" variant="primary" className="ml-auto shrink-0"
                                onClick={(e) => { e.stopPropagation(); setPlaying(null); onFlip(c) }}>
                          Move to {there}
                        </Button>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}
    </div>
  )

  return (
    // Header and column stay in the middle whichever stack is open (sarah:
    // it moved left or right); only the small stack changes side.
    <div className="mt-3 flex min-h-0 flex-1 flex-col">
      <div className="flex items-center justify-center gap-3">
        <Button size="sm" onClick={onClose}>‹ Both stacks</Button>
        <h3 className={cx('font-serif text-[22px]', red ? 'text-rose-200' : 'text-zinc-100')}>{red ? 'Left out' : 'Kept'} · {clips.length}</h3>
      </div>
      <p className="mt-1.5 text-center font-serif text-[17px] text-zinc-200">Click a clip to play it</p>
      <div className="mt-3 grid min-h-0 flex-1 grid-cols-[minmax(0,1fr)_minmax(0,420px)_minmax(0,1fr)] grid-rows-[minmax(0,1fr)] gap-6">
        <div className="flex min-h-0 justify-end">{red && target}</div>
        {column}
        <div className="flex min-h-0 justify-start">{!red && target}</div>
      </div>
    </div>
  )
}

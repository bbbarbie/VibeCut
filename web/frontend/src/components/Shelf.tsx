import { useRef, useState } from 'react'
import type { Clip } from '../types'
import { dur } from '../format'
import { Button, cx } from '../ui'
import { Stack, type Side } from './Footage'

export const SHOT_MIME = 'application/x-vibecut-shot'

// Media in Frames: two piles, as on Footage (sarah, 2026-10-13: "just the two
// piles of kept and left out"). Here Kept means in the video, Left out means
// not. Opening a pile shows its clips; clicking one plays it and offers the
// move, and only then says why a clip was left out. A move changes the video
// as one undoable turn.
export function Shelf({ clips, inEdit, onPreview, onMove, onPick, busy }: {
  clips: Clip[]
  /** ids of the clips the edit uses */
  inEdit: Set<string>
  onPreview: (clip: Clip) => void
  onMove: (clip: Clip, into: boolean) => Promise<void>
  onPick: (files: FileList) => void
  busy: boolean
}) {
  const folderInput = useRef<HTMLInputElement>(null)
  const fileInput = useRef<HTMLInputElement>(null)
  const [open, setOpen] = useState<Side | null>(null)
  const kept = clips.filter((c) => inEdit.has(c.id))
  const out = clips.filter((c) => !inEdit.has(c.id))

  return (
    <section className="flex min-h-0 min-w-0 flex-1 flex-col border-r border-line bg-panel">
      <header className="flex h-12 shrink-0 items-center gap-3 border-b border-line px-4">
        {open
          ? <>
              <Button size="sm" onClick={() => setOpen(null)}>‹ Both piles</Button>
              <span className={cx('font-serif text-[18px]', open === 'out' ? 'text-rose-200' : 'text-zinc-100')}>
                {open === 'kept' ? 'Kept' : 'Left out'} · {(open === 'kept' ? kept : out).length}
              </span>
            </>
          : <span className="font-serif text-[18px] text-zinc-100">Media</span>}
        <div className="flex-1" />
        <Button size="sm" disabled={busy} onClick={() => fileInput.current?.click()}>Add clips</Button>
        <Button size="sm" disabled={busy} onClick={() => folderInput.current?.click()}>Add folder</Button>
        <input ref={fileInput} type="file" className="hidden" multiple accept=".mp4,.mov,video/mp4,video/quicktime"
               onChange={(e) => { if (e.target.files) onPick(e.target.files); e.target.value = '' }} />
        {/* @ts-expect-error -- non-standard but supported everywhere that matters */}
        <input ref={folderInput} type="file" className="hidden" webkitdirectory="" multiple
               onChange={(e) => { if (e.target.files) onPick(e.target.files); e.target.value = '' }} />
      </header>

      {clips.length === 0 ? (
        <button type="button" onClick={() => folderInput.current?.click()}
                className="m-4 grid flex-1 place-items-center rounded-xl border border-dashed border-zinc-700 text-center hover:border-zinc-500">
          <div>
            <div className="font-serif text-[18px] text-zinc-200">Drop a folder or clips here</div>
            <div className="mt-1 font-serif text-[16px] text-zinc-300">.mp4 and .mov · they stay on this Mac, nothing is uploaded</div>
          </div>
        </button>
      ) : open ? (
        <Pile key={open} side={open} clips={open === 'kept' ? kept : out} others={open === 'kept' ? out : kept}
              onSwitch={() => setOpen(open === 'kept' ? 'out' : 'kept')}
              onPreview={onPreview} onMove={onMove} />
      ) : (
        <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-5 overflow-y-auto p-6">
          <div className="flex flex-wrap items-center justify-center gap-x-14 gap-y-8">
            <Stack side="kept" clips={kept} onOpen={() => setOpen('kept')} />
            <Stack side="out" clips={out} onOpen={() => setOpen('out')} />
          </div>
          <p className="text-center font-serif text-[17px] text-zinc-200">Click a pile to look through it</p>
        </div>
      )}
    </section>
  )
}

function Pile({ side, clips, others, onSwitch, onPreview, onMove }: {
  side: Side; clips: Clip[]; others: Clip[]
  onSwitch: () => void
  onPreview: (clip: Clip) => void
  onMove: (clip: Clip, into: boolean) => Promise<void>
}) {
  const [chosen, setChosen] = useState<string | null>(null)
  const [moving, setMoving] = useState(false)
  const red = side === 'out'
  const there = red ? 'Kept' : 'Left out'

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        {!clips.length
          ? <p className="mt-10 text-center font-serif text-[17px] text-zinc-200">{red ? 'Every clip is in the video.' : 'Nothing in the video yet.'}</p>
          : (
            <div className="grid auto-rows-min grid-cols-[repeat(auto-fill,minmax(148px,1fr))] gap-3">
              {clips.map((c) => {
                const on = chosen === c.id
                const first = c.shots[0]
                return (
                  <div key={c.id}
                       draggable={!!first}
                       onDragStart={(e) => { if (first) { e.dataTransfer.setData(SHOT_MIME, first.id); e.dataTransfer.effectAllowed = 'copy' } }}
                       onClick={() => { setChosen(on ? null : c.id); if (!on) onPreview(c) }}
                       className={cx('cursor-pointer select-none rounded-lg border p-1 transition-colors',
                         red ? 'border-rose-900/70 bg-rose-950/60 hover:bg-rose-950' : 'border-transparent hover:bg-raised',
                         on && (red ? 'border-rose-500' : 'border-accent bg-raised'))}>
                    <div className="relative aspect-video overflow-hidden rounded-md bg-black">
                      {first && <img src={first.thumb} alt="" loading="lazy" draggable={false}
                                     className={cx('size-full', c.height > c.width ? 'object-contain' : 'object-cover')} />}
                      <span className="absolute bottom-1 right-1 rounded bg-black/70 px-1 text-[12px] tabular-nums text-zinc-200">{dur(c.duration)}</span>
                    </div>
                    {on && (
                      <div className="mt-2 flex flex-col gap-2 px-0.5 pb-1">
                        {red && <p className="font-serif text-[15px] leading-snug text-rose-200">{why(c)}</p>}
                        <Button size="sm" variant="primary" disabled={moving}
                                onClick={async (e) => {
                                  e.stopPropagation()
                                  setMoving(true)
                                  try { await onMove(c, red); setChosen(null) } finally { setMoving(false) }
                                }}>
                          {moving ? 'Moving…' : `Move to ${there}`}
                        </Button>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
      </div>
      <div className="flex shrink-0 items-center justify-center gap-3 border-t border-line px-4 py-2">
        <span className="font-serif text-[16px] text-zinc-200">Click a clip to play it.</span>
        <Button size="sm" onClick={onSwitch}>Open {there} · {others.length}</Button>
      </div>
    </div>
  )
}

/** Why a clip isn't in the video, in the creator's words where it was their call. */
function why(c: Clip): string {
  if (c.cut?.rejected) return c.cut.override === 'reject' ? 'You left it out.' : `Left out: ${c.cut.en}`
  return 'The story didn’t use it. It can go in.'
}

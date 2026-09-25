import { useRef, useState } from 'react'
import type { Board, BoardBeat, BoardShot, Clip, Option, Session } from '../types'
import { dur } from '../format'

// The Story level: the edit as parts and shots, nothing else. No timecodes,
// no tracks, no frames -- those live one level down, in Frames.

export type PlayItem = { id: string; clipId: string; start: number; end: number }
export type Selection = { kind: 'shot'; key: string; beat: string } | { kind: 'beat'; beat: string } | null

const EXAMPLES = ['A weekend in Tokyo, mostly the food', 'My sister’s wedding day', 'A day at the beach with friends']

const beatLength = (b: BoardBeat) => b.shots.reduce((n, s) => n + s.end - s.start, 0)
const playItems = (beats: { shots: { id: string; clip_id: string | null; start: number; end: number; gap?: boolean }[] }[]): PlayItem[] =>
  beats.flatMap((b) => b.shots.filter((s) => !s.gap && s.clip_id).map((s) => ({ id: s.id, clipId: s.clip_id!, start: s.start, end: s.end })))

export function Story({ session, clips, asking, playing, nowShot, selected, onPick, onAsk, onUse, onPlay,
  onSelect, onMoveBeat, onRetitle, onBeatAction }: {
  session: Session | null
  clips: Clip[]
  asking: boolean
  playing: string | null
  nowShot: string | null
  selected: Selection
  onPick: (files: FileList) => void
  onAsk: (text: string) => void
  onUse: (o: Option) => void
  onPlay: (source: string, items: PlayItem[]) => void
  onSelect: (sel: Selection, anchor: DOMRect | null) => void
  onMoveBeat: (beat: string, to: number) => void
  onRetitle: (beat: string, title: string) => void
  onBeatAction: (action: 'play' | 'up' | 'down' | 'remove' | 'frames', beat: string) => void
}) {
  const board = session?.board ?? null
  const proposals = session?.proposals ?? null
  const [showOthers, setShowOthers] = useState(false)

  if (!clips.length) return <Empty onPick={onPick} />
  if (!board && !proposals) return <Ask clips={clips} asking={asking} onAsk={onAsk} />
  if (!board || showOthers) {
    return (
      <div className="min-h-0 flex-1 overflow-y-auto p-5">
        <div className="mb-4 flex items-baseline gap-3">
          <h2 className="font-serif text-[24px] text-zinc-100">Three ways to tell it</h2>
          <span className="text-[12px] text-muted">Watch one, then pick the one closest to what you want. You can change anything after.</span>
          {board && <button type="button" onClick={() => setShowOthers(false)} className="ml-auto text-[12px] text-accent hover:underline">Back to my story</button>}
        </div>
        <div className="grid grid-cols-3 gap-4">
          {proposals!.options.map((o) => (
            <OptionCard key={o.key} o={o} current={board?.option === o.key} playing={playing === `card:${o.key}`}
                        onPlay={() => onPlay(`card:${o.key}`, playItems(o.beats.map((b) => ({ shots: b.shots.map((s) => ({ ...s, clip_id: s.clip_id })) }))))}
                        onUse={() => { onUse(o); setShowOthers(false) }} />
          ))}
        </div>
      </div>
    )
  }
  return (
    <BoardRows session={session!} board={board} playing={playing} nowShot={nowShot} selected={selected}
               onPlay={onPlay} onSelect={onSelect} onMoveBeat={onMoveBeat} onRetitle={onRetitle}
               onBeatAction={onBeatAction} onOthers={() => setShowOthers(true)} />
  )
}

// ---- before anything is loaded ---------------------------------------------

function Empty({ onPick }: { onPick: (f: FileList) => void }) {
  const folder = useRef<HTMLInputElement>(null)
  const files = useRef<HTMLInputElement>(null)
  return (
    <div className="grid min-h-0 flex-1 place-items-center p-8">
      <div className="w-full max-w-xl rounded-2xl border border-dashed border-zinc-700 p-10 text-center">
        <h2 className="font-serif text-[26px] text-zinc-100">Start with your clips</h2>
        <p className="mt-2 text-[13px] text-zinc-400">Drag a folder of videos anywhere onto this window, or choose one.</p>
        <div className="mt-6 flex justify-center gap-2">
          <button type="button" onClick={() => folder.current?.click()}
                  className="rounded-lg bg-accent px-4 py-2 text-[13px] font-semibold text-accent-ink">Choose a folder</button>
          <button type="button" onClick={() => files.current?.click()}
                  className="rounded-lg border border-line px-4 py-2 text-[13px] text-zinc-200 hover:bg-raised">Choose some clips</button>
        </div>
        <p className="mt-4 text-[11px] text-muted">.mp4 and .mov · they stay on this computer</p>
        {/* @ts-expect-error -- non-standard but supported everywhere that matters */}
        <input ref={folder} type="file" className="hidden" webkitdirectory="" multiple
               onChange={(e) => { if (e.target.files) onPick(e.target.files); e.target.value = '' }} />
        <input ref={files} type="file" className="hidden" multiple accept=".mp4,.mov,video/mp4,video/quicktime"
               onChange={(e) => { if (e.target.files) onPick(e.target.files); e.target.value = '' }} />
      </div>
    </div>
  )
}

// ---- clips loaded, nothing proposed yet: ask, right here ---------------------

function Ask({ clips, asking, onAsk }: { clips: Clip[]; asking: boolean; onAsk: (t: string) => void }) {
  const [text, setText] = useState('')
  const shots = clips.flatMap((c) => c.shots.map((s) => ({ ...s, clip: c })))
  const go = (t: string) => { if (t.trim() && !asking) onAsk(t.trim()) }
  return (
    <div className="min-h-0 flex-1 overflow-y-auto p-8">
      <div className="mx-auto max-w-2xl">
        <p className="text-[12px] text-muted">{clips.length} clips loaded</p>
        <h2 className="mt-1 font-serif text-[26px] text-zinc-100">What’s this video about?</h2>
        <p className="mt-1 text-[13px] text-zinc-400">One line is enough. You’ll get three different ways to put it together.</p>
        <div className="mt-4 flex gap-2">
          <input autoFocus value={text} onChange={(e) => setText(e.target.value)} disabled={asking}
                 onKeyDown={(e) => { if (e.key === 'Enter') go(text) }}
                 placeholder="e.g. a weekend in Tokyo, mostly the food"
                 className="min-w-0 flex-1 rounded-lg border border-line bg-raised px-3 py-2 text-[14px] text-zinc-100 outline-none placeholder:text-zinc-500 focus:border-zinc-500" />
          <button type="button" onClick={() => go(text)} disabled={asking || !text.trim()}
                  className="rounded-lg bg-accent px-4 text-[13px] font-semibold text-accent-ink disabled:opacity-30">
            {asking ? 'Thinking…' : 'Show me'}
          </button>
        </div>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {EXAMPLES.map((x) => (
            <button key={x} type="button" onClick={() => setText(x)}
                    className="rounded-full border border-line px-2.5 py-1 text-[11px] text-muted hover:text-zinc-200">{x}</button>
          ))}
        </div>
        <div className="mt-8 grid grid-cols-6 gap-1.5 opacity-80">
          {shots.slice(0, 24).map((s) => (
            <img key={s.id} src={s.thumb} className="aspect-video w-full rounded object-cover" />
          ))}
        </div>
      </div>
    </div>
  )
}

// ---- the three options, side by side ----------------------------------------

function OptionCard({ o, current, playing, onPlay, onUse }: {
  o: Option; current: boolean; playing: boolean; onPlay: () => void; onUse: () => void
}) {
  const shots = o.beats.reduce((n, b) => n + b.shots.length, 0)
  const length = o.beats.reduce((n, b) => n + b.shots.reduce((m, s) => m + s.end - s.start, 0), 0)
  return (
    <article className={`flex min-w-0 flex-col rounded-xl border bg-raised ${current ? 'border-accent/60' : 'border-line'}`}>
      <div className="px-4 pt-4">
        <h3 className="font-serif text-[20px] text-zinc-100">{o.name}</h3>
        <p className="mt-1 text-[12px] leading-snug text-zinc-400">{o.summary}</p>
        {o.notes.map((t) => <p key={t} className="mt-2 rounded-md bg-amber-300/10 px-2 py-1.5 text-[11px] text-amber-200/90">{t}</p>)}
        <div className="mt-3 flex gap-2">
          <button type="button" onClick={onPlay}
                  className="flex items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 text-[12px] text-zinc-200 hover:bg-zinc-800">
            {playing ? <><i className="block size-2 bg-current" /> Stop</> : <><i className="block size-0 border-y-[5px] border-l-[8px] border-y-transparent border-l-current" /> Watch</>}
          </button>
          <button type="button" onClick={onUse}
                  className="rounded-lg bg-accent px-3 py-1.5 text-[12px] font-semibold text-accent-ink hover:brightness-110">
            {current ? 'Start over from this' : 'Use this one'}
          </button>
          <span className="ml-auto self-center text-[11px] tabular-nums text-muted">{o.beats.length} parts · {dur(length)}</span>
        </div>
      </div>
      <ol className="mt-3 min-h-0 flex-1 space-y-2.5 overflow-y-auto border-t border-line px-4 py-3">
        {o.beats.map((b, i) => (
          <li key={i}>
            <div className="flex items-baseline gap-2">
              <span className="text-[10px] tabular-nums text-zinc-600">{i + 1}</span>
              <span className="truncate font-serif text-[15px] text-zinc-200">{b.title}</span>
              <span className="ml-auto shrink-0 text-[10px] text-muted">{b.shots.length} shot{b.shots.length === 1 ? '' : 's'}</span>
            </div>
            <div className="mt-1 flex gap-0.5 overflow-hidden pl-4">
              {b.shots.slice(0, 8).map((s) => <img key={s.id} src={s.thumb} className="h-8 w-14 shrink-0 rounded-sm object-cover" />)}
              {b.shots.length > 8 && <span className="self-center pl-1 text-[10px] text-muted">+{b.shots.length - 8}</span>}
            </div>
          </li>
        ))}
      </ol>
      <p className="border-t border-line px-4 py-2 text-[10px] text-muted">{shots} shots</p>
    </article>
  )
}

// ---- the chosen story: one row per part --------------------------------------

function BoardRows({ session, board, playing, nowShot, selected, onPlay, onSelect, onMoveBeat, onRetitle,
  onBeatAction, onOthers }: {
  session: Session; board: Board; playing: string | null; nowShot: string | null; selected: Selection
  onPlay: (source: string, items: PlayItem[]) => void
  onSelect: (sel: Selection, anchor: DOMRect | null) => void
  onMoveBeat: (beat: string, to: number) => void
  onRetitle: (beat: string, title: string) => void
  onBeatAction: (action: 'play' | 'up' | 'down' | 'remove' | 'frames', beat: string) => void
  onOthers: () => void
}) {
  const [dragBeat, setDragBeat] = useState<string | null>(null)
  const [dropAt, setDropAt] = useState<number | null>(null)
  const [renaming, setRenaming] = useState<string | null>(null)
  const rows = useRef<HTMLOListElement>(null)
  const total = board.beats.reduce((n, b) => n + beatLength(b), 0)
  const d = session.last?.diff && !session.last.diff.replaced ? session.last.diff : null
  const changed = new Map<string, string>()
  d?.shots.added.forEach((x) => changed.set(x.id, 'ring-2 ring-emerald-400'))
  d?.shots.moved.forEach((x) => { if (!changed.has(x.id)) changed.set(x.id, 'ring-2 ring-amber-300') })
  d?.shots.trimmed.forEach((x) => { if (!changed.has(x.id)) changed.set(x.id, 'ring-2 ring-sky-400') })
  const movedBeats = new Set(d?.beats.moved.map((x) => x.id))
  const ghosts = session.last?.ghosts ?? []

  const indexAt = (y: number) => {
    const els = Array.from(rows.current?.querySelectorAll('[data-row]') ?? [])
    for (let i = 0; i < els.length; i++) {
      const r = els[i].getBoundingClientRect()
      if (y < r.top + r.height / 2) return i
    }
    return els.length
  }

  return (
    <div className="min-h-0 flex-1 overflow-y-auto p-5" onClick={(e) => { if (e.target === e.currentTarget) onSelect(null, null) }}>
      <div className="mb-4 flex items-end gap-3">
        <div className="min-w-0">
          <h2 className="font-serif text-[24px] leading-tight text-zinc-100">Your story</h2>
          <p className="mt-0.5 text-[12px] text-zinc-400">{session.structure_note}</p>
        </div>
        <div className="ml-auto flex shrink-0 items-center gap-2">
          <span className="text-[12px] tabular-nums text-muted">{board.beats.length} parts · {dur(total)}</span>
          <button type="button" onClick={() => onPlay('board', playItems(board.beats))}
                  className="flex items-center gap-1.5 rounded-lg bg-zinc-800 px-3 py-1.5 text-[12px] text-zinc-100 hover:bg-zinc-700">
            {playing === 'board' ? <><i className="block size-2 bg-current" /> Stop</>
              : <><i className="block size-0 border-y-[5px] border-l-[8px] border-y-transparent border-l-current" /> Watch it all</>}
          </button>
          <button type="button" onClick={onOthers} className="rounded-lg border border-line px-3 py-1.5 text-[12px] text-zinc-300 hover:bg-raised">
            Other ways to tell it
          </button>
        </div>
      </div>

      <ol ref={rows} className="space-y-2"
          onDragOver={(e) => { if (dragBeat) { e.preventDefault(); setDropAt(indexAt(e.clientY)) } }}
          onDrop={(e) => {
            e.preventDefault()
            if (dragBeat && dropAt != null) {
              const from = board.beats.findIndex((b) => b.id === dragBeat)
              const to = dropAt > from ? dropAt - 1 : dropAt
              if (to !== from) onMoveBeat(dragBeat, to)
            }
            setDragBeat(null)
            setDropAt(null)
          }}>
        {board.beats.map((b, i) => {
          const sel = selected?.kind === 'beat' && selected.beat === b.id
          const ghost = ghosts.filter((g) => g.index === i)
          return (
            <li key={b.id} className="relative">
              {ghost.map((g) => <Ghost key={g.title} title={g.title} thumbs={g.thumbs} />)}
              {dropAt === i && dragBeat && <div className="absolute -top-1.5 inset-x-0 h-0.5 rounded bg-accent" />}
              <div
                data-row
                draggable={renaming !== b.id}
                onDragStart={(e) => { setDragBeat(b.id); e.dataTransfer.effectAllowed = 'move'; e.dataTransfer.setData('text/plain', b.id) }}
                onDragEnd={() => { setDragBeat(null); setDropAt(null) }}
                className={`group rounded-xl border px-3 py-2.5 transition-colors ${sel ? 'border-accent/70 bg-raised' : 'border-line bg-raised/60 hover:bg-raised'}
                  ${movedBeats.has(b.id) ? 'ring-1 ring-amber-300/60' : ''} ${dragBeat === b.id ? 'opacity-40' : ''}`}
              >
                <div className="flex items-center gap-2">
                  <span className="cursor-grab select-none text-[14px] leading-none text-zinc-600 group-hover:text-zinc-400" title="Drag to move this part">⋮⋮</span>
                  <span className="w-4 text-[11px] tabular-nums text-zinc-600">{i + 1}</span>
                  {renaming === b.id ? (
                    <RenameField initial={b.title} onDone={(t) => { setRenaming(null); if (t && t !== b.title) onRetitle(b.id, t) }} />
                  ) : (
                    <button type="button" onClick={(e) => onSelect({ kind: 'beat', beat: b.id }, e.currentTarget.getBoundingClientRect())}
                            className="min-w-0 truncate text-left font-serif text-[17px] text-zinc-100 hover:underline decoration-zinc-600 underline-offset-4"
                            title="Click for options: rename, move, remove…">
                      {b.title}
                    </button>
                  )}
                  {movedBeats.has(b.id) && <span className="text-[10px] text-amber-200">moved</span>}
                  <span className="ml-auto shrink-0 text-[11px] tabular-nums text-muted">{b.shots.length} shot{b.shots.length === 1 ? '' : 's'} · {dur(beatLength(b))}</span>
                </div>

                {sel && renaming !== b.id && (
                  <div className="mt-2 flex flex-wrap gap-1.5 pl-9">
                    <Act onClick={() => setRenaming(b.id)}>Rename</Act>
                    <Act onClick={() => onBeatAction('play', b.id)}>Watch this part</Act>
                    <Act onClick={() => onBeatAction('up', b.id)} disabled={i === 0}>Move up</Act>
                    <Act onClick={() => onBeatAction('down', b.id)} disabled={i === board.beats.length - 1}>Move down</Act>
                    <Act onClick={() => onBeatAction('remove', b.id)} danger>Remove this part</Act>
                    <Act onClick={() => onBeatAction('frames', b.id)} title="Open this part on the detailed timeline, to cut and trim frame by frame">
                      Fine-tune in Frames →
                    </Act>
                  </div>
                )}

                <div className="mt-2 flex gap-1 overflow-x-auto pb-1 pl-9">
                  {b.shots.map((s) => (
                    <ShotThumb key={s.key} s={s}
                               selected={selected?.kind === 'shot' && selected.key === s.key}
                               now={nowShot === s.id}
                               ring={changed.get(s.key) ?? (s.lean ? 'ring-1 ring-accent/60' : '')}
                               onClick={(e) => onSelect({ kind: 'shot', key: s.key, beat: b.id }, e.currentTarget.getBoundingClientRect())} />
                  ))}
                </div>
              </div>
            </li>
          )
        })}
        {ghosts.filter((g) => g.index >= board.beats.length).map((g) => <li key={g.title}><Ghost title={g.title} thumbs={g.thumbs} /></li>)}
        {dropAt === board.beats.length && dragBeat && <li className="h-0.5 rounded bg-accent" />}
      </ol>
    </div>
  )
}

function ShotThumb({ s, selected, now, ring, onClick }: {
  s: BoardShot; selected: boolean; now: boolean; ring: string
  onClick: (e: React.MouseEvent<HTMLButtonElement>) => void
}) {
  const len = s.end - s.start
  return (
    <button type="button" onClick={onClick}
            title={s.gap ? `${len.toFixed(1)}s of empty space` : `${len.toFixed(1)}s — click for options`}
            className={`relative h-[62px] shrink-0 overflow-hidden rounded-md bg-black ${selected ? 'ring-2 ring-accent' : now ? 'ring-2 ring-zinc-200' : ring}`}
            style={{ width: 110 }}>
      {s.gap ? (
        <div className="grid size-full place-items-center bg-[repeating-linear-gradient(45deg,#18181b,#18181b_6px,#27272a_6px,#27272a_12px)] text-[10px] text-zinc-500">empty</div>
      ) : (
        <img src={s.thumb} className="size-full object-cover" draggable={false} />
      )}
      <span className="absolute bottom-0.5 right-0.5 rounded bg-black/70 px-1 text-[10px] tabular-nums text-zinc-200">{len < 10 ? len.toFixed(1) : Math.round(len)}s</span>
    </button>
  )
}

function Ghost({ title, thumbs }: { title: string; thumbs: string[] }) {
  return (
    <div className="mb-2 rounded-xl border border-dashed border-rose-400/40 bg-rose-500/5 px-3 py-2 opacity-80">
      <div className="flex items-center gap-2 pl-9">
        <span className="font-serif text-[15px] text-rose-200 line-through">{title}</span>
        <span className="text-[11px] text-rose-300/80">just removed</span>
      </div>
      <div className="mt-1 flex gap-1 pl-9 grayscale">
        {thumbs.slice(0, 8).map((t, j) => <img key={j} src={t} className="h-8 w-14 rounded-sm object-cover opacity-50" />)}
      </div>
    </div>
  )
}

function RenameField({ initial, onDone }: { initial: string; onDone: (t: string | null) => void }) {
  const [v, setV] = useState(initial)
  return (
    <input autoFocus value={v} onChange={(e) => setV(e.target.value)}
           onFocus={(e) => e.currentTarget.select()}
           onKeyDown={(e) => {
             if (e.key === 'Enter') onDone(v.trim())
             if (e.key === 'Escape') onDone(null)
             e.stopPropagation()
           }}
           onBlur={() => onDone(v.trim())}
           className="min-w-0 flex-1 rounded-md border border-accent/60 bg-panel px-2 py-0.5 font-serif text-[17px] text-zinc-100 outline-none" />
  )
}

export function Act({ children, onClick, danger, disabled, title }: {
  children: React.ReactNode; onClick: () => void; danger?: boolean; disabled?: boolean; title?: string
}) {
  return (
    <button type="button" onClick={onClick} disabled={disabled} title={title}
            className={`rounded-md border px-2.5 py-1 text-[12px] disabled:opacity-30 ${danger
              ? 'border-rose-400/40 text-rose-200 hover:bg-rose-500/10' : 'border-line text-zinc-200 hover:bg-zinc-800'}`}>
      {children}
    </button>
  )
}

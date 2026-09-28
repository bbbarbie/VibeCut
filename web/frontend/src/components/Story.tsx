import { useRef, useState } from 'react'
import type { Board, BoardBeat, BoardShot, Clip, JoinInfo, JoinSound, Option, Seam, Session } from '../types'
import { dur } from '../format'
import { Button } from '../ui'

// The Story level: the edit as parts and shots, nothing else. No timecodes,
// no tracks, no frames -- those live one level down, in Frames.

export type PlayItem = { id: string; clipId: string; start: number; end: number }
export type Selection = { kind: 'shot'; key: string; beat: string } | { kind: 'beat'; beat: string } | null

const beatLength = (b: BoardBeat) => b.shots.reduce((n, s) => n + s.end - s.start, 0)
const playItems = (beats: { shots: { id: string; clip_id: string | null; start: number; end: number; gap?: boolean }[] }[]): PlayItem[] =>
  beats.flatMap((b) => b.shots.filter((s) => !s.gap && s.clip_id).map((s) => ({ id: s.id, clipId: s.clip_id!, start: s.start, end: s.end })))

export function Story({ session, clips, asking, playing, nowShot, selected, onUse, onPlay,
  onSelect, onMoveBeat, onRetitle, onBeatAction, onReference, onJoin, onSmooth }: {
  session: Session | null
  clips: Clip[]
  asking: boolean
  playing: string | null
  nowShot: string | null
  selected: Selection
  onUse: (o: Option) => void
  onPlay: (source: string, items: PlayItem[]) => void
  onSelect: (sel: Selection, anchor: DOMRect | null) => void
  onMoveBeat: (beat: string, to: number) => void
  onRetitle: (beat: string, title: string) => void
  onBeatAction: (action: 'play' | 'up' | 'down' | 'remove' | 'frames', beat: string) => void
  onReference?: () => void
  onJoin?: (after: string, sound: JoinSound) => void
  onSmooth?: (order: boolean, nudge: boolean) => Promise<void>
}) {
  const board = session?.board ?? null
  const proposals = session?.proposals ?? null
  const [showOthers, setShowOthers] = useState(false)

  if (!clips.length || (!board && !proposals)) {
    return (
      <div className="grid min-h-0 flex-1 place-items-center p-8 text-center">
        <p className="max-w-sm text-[13px] text-zinc-400">{asking ? 'Building three ways to tell it…' : 'Nothing to show yet — the story is built from your brief, after the rough cut.'}</p>
      </div>
    )
  }
  if (!board || showOthers) {
    const n = proposals!.options.length
    return (
      <div className="min-h-0 flex-1 overflow-y-auto p-5">
        <div className="mb-1 flex flex-wrap items-baseline gap-3">
          <h2 className="font-serif text-[24px] text-zinc-100">{n === 4 ? 'Four' : 'Three'} ways to tell it</h2>
          {board && <Button variant="ghost" size="sm" className="ml-auto" onClick={() => setShowOthers(false)}>Back to my story</Button>}
        </div>
        <p className="mb-4 text-[12px] text-zinc-400">Watch one, then start from the one closest to what you want. You can change anything after — by talking, or by hand.</p>
        <div className="grid gap-4" style={{ gridTemplateColumns: `repeat(${n > 3 ? 2 : n}, minmax(0, 1fr))` }}>
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
               onBeatAction={onBeatAction} onOthers={() => setShowOthers(true)} onReference={onReference} onJoin={onJoin} onSmooth={onSmooth} />
  )
}

// ---- the three options, side by side ----------------------------------------

function OptionCard({ o, current, playing, onPlay, onUse }: {
  o: Option; current: boolean; playing: boolean; onPlay: () => void; onUse: () => void
}) {
  const shots = o.beats.reduce((n, b) => n + b.shots.filter((s) => !s.gap).length, 0)
  const length = o.beats.reduce((n, b) => n + b.shots.reduce((m, s) => m + s.end - s.start, 0), 0)
  return (
    <article className={`flex min-w-0 flex-col rounded-xl border bg-raised ${current ? 'border-accent/60' : 'border-line'}`}>
      <div className="px-4 pt-4">
        <h3 className="font-serif text-[20px] text-zinc-100">{o.name}</h3>
        <p className="mt-1 text-[12px] leading-snug text-zinc-400">{o.summary}</p>
        {o.notes.map((t) => <p key={t} className="mt-2 rounded-md bg-amber-300/10 px-2 py-1.5 text-[11px] text-amber-200/90">{t}</p>)}
        {o.gaps && o.gaps.length > 0 && (
          <details className="mt-2 text-[11px]">
            <summary className="cursor-pointer text-amber-200/90">Lines with nothing to show ({o.gaps.length})</summary>
            <ul className="mt-1 space-y-1">
              {o.gaps.map((g) => (
                <li key={`${g.line}-${g.at}`} className="text-zinc-400">
                  <span className="tabular-nums text-zinc-500">{dur(g.at)}</span> “{g.text}” <span className="text-muted">— {g.reason}</span>
                </li>
              ))}
            </ul>
          </details>
        )}
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <button type="button" onClick={onPlay}
                  className="flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-lg border border-line px-3 py-1.5 text-[12px] text-zinc-200 hover:bg-zinc-800">
            {playing ? <><i className="block size-2 bg-current" /> Stop</> : <><i className="block size-0 border-y-[5px] border-l-[8px] border-y-transparent border-l-current" /> Watch</>}
          </button>
          <button type="button" onClick={onUse}
                  className="shrink-0 whitespace-nowrap rounded-lg bg-accent px-3 py-1.5 text-[12px] font-semibold text-accent-ink hover:brightness-110">
            {current ? 'Start over from this' : 'Use this one'}
          </button>
        </div>
        <p className="mt-2 text-[11px] tabular-nums text-muted">{o.beats.length} part{o.beats.length === 1 ? '' : 's'} · {dur(length)} · {shots} shot{shots === 1 ? '' : 's'}</p>
      </div>
      <ol className="mt-3 min-h-0 flex-1 space-y-2.5 overflow-y-auto border-t border-line px-4 py-3">
        {o.beats.map((b, i) => (
          <li key={i}>
            <div className="flex items-baseline gap-2">
              <span className="text-[10px] tabular-nums text-zinc-600">{i + 1}</span>
              <span className="truncate font-serif text-[15px] text-zinc-200">{b.title}</span>
              <span className="ml-auto shrink-0 text-[10px] text-muted">{b.shots.every((s) => s.gap) ? 'nothing to show yet' : `${b.shots.filter((s) => !s.gap).length} shot${b.shots.filter((s) => !s.gap).length === 1 ? '' : 's'}`}</span>
            </div>
            <div className="mt-1 flex gap-0.5 overflow-hidden pl-4">
              {b.shots.slice(0, 8).map((s, k) => s.gap
                ? <span key={`gap${k}`} title={s.why} className="h-8 w-14 shrink-0 rounded-sm bg-[repeating-linear-gradient(45deg,#18181b,#18181b_4px,#27272a_4px,#27272a_8px)]" />
                : <img key={s.id} src={s.thumb} className="h-8 w-14 shrink-0 rounded-sm object-cover" />)}
              {b.shots.length > 8 && <span className="self-center pl-1 text-[10px] text-muted">+{b.shots.length - 8}</span>}
            </div>
          </li>
        ))}
      </ol>
    </article>
  )
}

// ---- the chosen story: one row per part --------------------------------------

function BoardRows({ session, board, playing, nowShot, selected, onPlay, onSelect, onMoveBeat, onRetitle,
  onBeatAction, onOthers, onReference, onJoin, onSmooth }: {
  session: Session; board: Board; playing: string | null; nowShot: string | null; selected: Selection
  onJoin?: (after: string, sound: JoinSound) => void
  onSmooth?: (order: boolean, nudge: boolean) => Promise<void>
  onPlay: (source: string, items: PlayItem[]) => void
  onSelect: (sel: Selection, anchor: DOMRect | null) => void
  onMoveBeat: (beat: string, to: number) => void
  onRetitle: (beat: string, title: string) => void
  onBeatAction: (action: 'play' | 'up' | 'down' | 'remove' | 'frames', beat: string) => void
  onOthers: () => void
  onReference?: () => void
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
  const seamAt = new Map((session.seams ?? []).map((x) => [x.after, x]))
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
      <div className="mb-1 flex flex-wrap items-center gap-2">
        <h2 className="mr-2 font-serif text-[24px] leading-tight text-zinc-100">{board.name}</h2>
        <span className="text-[12px] tabular-nums text-muted">{board.beats.length} parts · {dur(total)}</span>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <button type="button" onClick={() => onPlay('board', playItems(board.beats))}
                  className="flex items-center gap-1.5 rounded-lg bg-zinc-800 px-3 py-1.5 text-[12px] text-zinc-100 hover:bg-zinc-700">
            {playing === 'board' ? <><i className="block size-2 bg-current" /> Stop</>
              : <><i className="block size-0 border-y-[5px] border-l-[8px] border-y-transparent border-l-current" /> Watch it all</>}
          </button>
          <Button onClick={onOthers} title="The other proposals built from your brief">Other ways to tell it</Button>
          {onSmooth && <SmoothButton rough={(session.seams ?? []).filter((x) => x.verdict !== 'ok').length} onSmooth={onSmooth} />}
        </div>
      </div>
      <p className="mb-4 text-[12px] leading-snug text-zinc-400">
        {session.structure_note}{board.style ? <> Feels like “{board.style.name}”{onReference ? <> · <button type="button" className="text-accent hover:underline" onClick={onReference}>change</button></> : null}.</> : null}
      </p>

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
              {i > 0 && onJoin && (() => {
                const prev = board.beats[i - 1].shots.at(-1)
                const j = prev && session.mix?.joins.find((x) => x.after === prev.key)
                return j ? <JoinChip join={j} seam={seamAt.get(j.after)} onPick={(sound) => onJoin(j.after, sound)} /> : null
              })()}
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
                  {b.shots.map((s, k) => (
                    <div key={s.key} className="flex shrink-0 items-center gap-1">
                    {k > 0 && <CutMark seam={seamAt.get(b.shots[k - 1].key)} />}
                    <ShotThumb s={s}
                               selected={selected?.kind === 'shot' && selected.key === s.key}
                               now={nowShot === s.id}
                               ring={changed.get(s.key) ?? (s.lean ? 'ring-1 ring-accent/60' : '')}
                               onClick={(e) => onSelect({ kind: 'shot', key: s.key, beat: b.id }, e.currentTarget.getBoundingClientRect())} />
                    </div>
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

// ---- how the sound crosses from one part to the next ---------------------------

const JOIN_WORDS: Record<Exclude<JoinSound, 'default'>, { chip: string; menu: string; hint: string }> = {
  carry_out: { chip: '♪ sound flows on', menu: 'Let the sound flow on', hint: 'This part’s sound keeps going for a moment under the next — the change feels like one movement' },
  carry_in: { chip: '♪ next sound first', menu: 'Hear the next part first', hint: 'The next part’s sound starts a moment before its picture — it pulls you forward' },
  cut: { chip: '✂ clean break', menu: 'Clean break', hint: 'Sound and picture change together, softened so it doesn’t click' },
}

// ---- smoother cuts: asked for, one undoable turn --------------------------------

function SmoothButton({ rough, onSmooth }: { rough: number; onSmooth: (order: boolean, nudge: boolean) => Promise<void> }) {
  const [open, setOpen] = useState(false)
  const [order, setOrder] = useState(true)
  const [nudge, setNudge] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const go = async () => {
    setBusy(true); setError(null)
    try { await onSmooth(order, nudge); setOpen(false) } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }
  return (
    <div className="relative">
      <button type="button" onClick={() => setOpen((o) => !o)}
              title="See which cuts feel rough, and try a smoother version you can undo"
              className="rounded-lg border border-line px-3 py-1.5 text-[12px] text-zinc-300 hover:bg-raised">
        Smoother cuts{rough > 0 && <span className="ml-1.5 rounded bg-amber-300/15 px-1 text-[10px] text-amber-200">{rough} rough</span>}
      </button>
      {open && (
        <div className="absolute right-0 top-9 z-30 w-72 rounded-xl border border-line bg-panel p-3 text-[12px] shadow-xl">
          <p className="text-zinc-300">{rough ? `${rough} cut${rough === 1 ? '' : 's'} may feel rough — marked ! on the story.` : 'No cut is flagged as rough.'} Try:</p>
          <label className="mt-2 flex items-start gap-2 text-zinc-200">
            <input type="checkbox" checked={order} onChange={(e) => setOrder(e.target.checked)} className="mt-0.5" />
            <span>Reorder shots inside a part<span className="block text-[11px] text-muted">Parts stay where they are; time only runs backwards if it clearly helps</span></span>
          </label>
          <label className="mt-2 flex items-start gap-2 text-zinc-200">
            <input type="checkbox" checked={nudge} onChange={(e) => setNudge(e.target.checked)} className="mt-0.5" />
            <span>Cut on the movement<span className="block text-[11px] text-muted">Slide a shot a second or two so the cut lands while something moves — never on a word</span></span>
          </label>
          {error && <p className="mt-2 text-[11px] text-amber-200">{error}</p>}
          <div className="mt-3 flex items-center justify-between">
            <span className="text-[10px] text-muted">One step, undoable. First guesses.</span>
            <button type="button" disabled={busy || (!order && !nudge)} onClick={go}
                    className="rounded-lg bg-accent px-3 py-1 font-semibold text-accent-ink disabled:opacity-40">{busy ? 'Trying…' : 'Try it'}</button>
          </div>
        </div>
      )}
    </div>
  )
}

// ---- what a cut will feel like (report only; the numbers are on hover) ---------

const SEAM_TONE = { ok: 'border-line', warn: 'border-amber-300/70', bad: 'border-rose-400/80' } as const

function seamText(seam: Seam | undefined): string {
  if (!seam) return ''
  const rough = seam.findings.filter((f) => f.verdict === 'warn' || f.verdict === 'bad')
  const lines = (rough.length ? rough : seam.findings).map((f) =>
    `${f.verdict === 'pending' ? '·' : f.verdict === 'ok' ? '✓' : '!'} ${f.label}: ${f.value ?? '–'}${f.unit ? ' ' + f.unit : ''} — ${f.detail}`)
  return (rough.length ? 'This cut may feel rough:\n' : 'This cut reads smoothly:\n') + lines.join('\n')
}

function CutMark({ seam }: { seam: Seam | undefined }) {
  if (!seam || seam.verdict === 'ok') return <span className="h-8 w-px shrink-0 bg-zinc-800" />
  return (
    <span title={seamText(seam)}
          className={`grid h-5 w-3 shrink-0 cursor-help place-items-center rounded-sm text-[9px] font-bold ${seam.verdict === 'bad' ? 'bg-rose-400/20 text-rose-300' : 'bg-amber-300/15 text-amber-200'}`}>
      !
    </span>
  )
}

function JoinChip({ join, seam, onPick }: { join: JoinInfo; seam?: Seam; onPick: (s: JoinSound) => void }) {
  const [open, setOpen] = useState(false)
  const w = JOIN_WORDS[join.sound]
  const tone = seam && seam.verdict !== 'ok' ? SEAM_TONE[seam.verdict] : null
  return (
    <div className="relative -mt-1 mb-1 flex justify-center">
      <button type="button" onClick={() => setOpen((o) => !o)}
              title={(join.fits ? w.hint : 'There’s no footage past this cut to carry the sound with, so it plays as a clean break. Trim the shot a little earlier to make room.')
                + (seam ? '\n\n' + seamText(seam) : '')}
              className={`rounded-full border px-2 py-0.5 text-[10px] ${tone ?? (join.set ? 'border-accent/50' : 'border-line')} ${join.set ? 'text-accent' : 'text-muted hover:text-zinc-300'}`}>
        {tone && <span className={seam!.verdict === 'bad' ? 'text-rose-300' : 'text-amber-200'}>! </span>}
        {join.fits ? w.chip : `${JOIN_WORDS.cut.chip} — no footage to carry`}{join.set ? '' : ' · auto'}
      </button>
      {open && (
        <div className="absolute top-6 z-20 w-64 rounded-lg border border-line bg-panel p-1 shadow-xl">
          {(Object.keys(JOIN_WORDS) as (keyof typeof JOIN_WORDS)[]).map((k) => (
            <button key={k} type="button" onClick={() => { setOpen(false); onPick(k) }}
                    className={`block w-full rounded-md px-2 py-1.5 text-left text-[12px] hover:bg-raised ${join.sound === k ? 'text-accent' : 'text-zinc-200'}`}>
              {JOIN_WORDS[k].menu}
              <span className="block text-[10px] leading-snug text-muted">{JOIN_WORDS[k].hint}</span>
            </button>
          ))}
          {join.set && (
            <button type="button" onClick={() => { setOpen(false); onPick('default') }}
                    className="block w-full rounded-md px-2 py-1.5 text-left text-[12px] text-muted hover:bg-raised">Back to automatic</button>
          )}
        </div>
      )}
    </div>
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

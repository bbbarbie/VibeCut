import { useEffect, useRef, useState } from 'react'
import type { DiffLine, Msg, Turn } from '../types'

const EXAMPLE = 'three days in Tokyo, lean into the food'

export type ChatItem = { type: 'local'; msg: Msg } | { type: 'turn'; turn: Turn }

const MARK: Record<DiffLine['kind'], { sym: string; cls: string }> = {
  removed: { sym: '−', cls: 'text-rose-300 bg-rose-400/10' },
  added: { sym: '+', cls: 'text-emerald-300 bg-emerald-400/10' },
  swapped: { sym: '⇄', cls: 'text-emerald-300 bg-emerald-400/10' },
  moved: { sym: '↕', cls: 'text-amber-200 bg-amber-300/10' },
  trimmed: { sym: '⟷', cls: 'text-sky-300 bg-sky-400/10' },
  retitled: { sym: 'Aa', cls: 'text-violet-300 bg-violet-400/10' },
  replaced: { sym: '▸', cls: 'text-zinc-300 bg-zinc-700/40' },
  none: { sym: '·', cls: 'text-zinc-500 bg-zinc-800/40' },
}

export function Chat({ items, pending, onSend, onToggle, disabled, llm, hasBoard }: {
  items: ChatItem[]
  pending: string | null
  onSend: (text: string) => void
  onToggle: (turn: number) => void
  disabled: boolean
  llm: boolean
  hasBoard: boolean
}) {
  const [text, setText] = useState('')
  const end = useRef<HTMLDivElement>(null)
  useEffect(() => { end.current?.scrollIntoView({ behavior: 'smooth' }) }, [items.length, pending])

  const send = (t = text) => {
    t = t.trim()
    if (!t || disabled) return
    onSend(t)
    setText('')
  }
  const lastQuestion = [...items].reverse().find((i) => i.type === 'turn')
  const openChoices = lastQuestion?.type === 'turn' && lastQuestion.turn.question && !lastQuestion.turn.undone
    ? lastQuestion.turn.id : null

  return (
    <aside className="flex min-h-0 flex-col border-r border-line bg-panel">
      <header className="flex h-10 shrink-0 items-center justify-between border-b border-line px-4">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-muted">Chat</span>
        {!llm && <span className="text-[10px] text-muted" title="Typed edits need a language model: add ANTHROPIC_API_KEY to web/.env. Everything else works without it.">typed edits are off</span>}
      </header>

      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto px-4 py-4">
        {items.map((it) => it.type === 'local'
          ? <Local key={it.msg.id} m={it.msg} />
          : <TurnView key={`t${it.turn.id}`} t={it.turn} onToggle={onToggle}
                      onChoice={openChoices === it.turn.id ? (c) => send(c) : undefined} />)}
        {pending && (
          <>
            <div className="flex justify-end">
              <div className="max-w-[85%] rounded-2xl rounded-br-md bg-accent px-3 py-2 font-serif text-[16px] leading-snug text-accent-ink">{pending}</div>
            </div>
            <div className="text-zinc-400"><span className="mr-2 inline-block size-2 animate-pulse rounded-full bg-accent align-middle" />Working out the edit…</div>
          </>
        )}
        <div ref={end} />
      </div>

      <div className="shrink-0 border-t border-line p-3">
        <div className="rounded-xl border border-line bg-raised focus-within:border-zinc-500">
          <textarea
            rows={2}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() }
            }}
            placeholder={hasBoard ? 'Edit it — “the opening is too slow”, “cut the market”, “end on the sunset”'
              : `What's this video? e.g. “${EXAMPLE}”`}
            className="block w-full resize-none bg-transparent px-3 pt-2.5 text-[13px] text-zinc-100 outline-none placeholder:text-zinc-500"
          />
          <div className="flex items-center justify-between px-2 pb-2">
            {!hasBoard ? (
              <button type="button" onClick={() => setText(EXAMPLE)}
                      className="rounded-md px-1.5 py-1 text-[11px] text-muted hover:text-zinc-300">
                Try an example
              </button>
            ) : <span className="px-1.5 text-[11px] text-zinc-600">Each message edits — nothing is regenerated</span>}
            <button
              type="button"
              onClick={() => send()}
              disabled={disabled || !text.trim()}
              className="rounded-lg bg-accent px-3 py-1 text-[12px] font-semibold text-accent-ink disabled:opacity-30"
            >
              Send
            </button>
          </div>
        </div>
      </div>
    </aside>
  )
}

function Local({ m }: { m: Msg }) {
  if (m.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-md bg-accent px-3 py-2 font-serif text-[16px] leading-snug text-accent-ink">{m.text}</div>
      </div>
    )
  }
  return (
    <div className="max-w-[95%] whitespace-pre-line font-serif text-[16px] leading-relaxed text-zinc-200">
      {m.busy && <span className="mr-2 inline-block size-2 animate-pulse rounded-full bg-accent align-middle" />}
      {m.text}
    </div>
  )
}

function TurnView({ t, onToggle, onChoice }: {
  t: Turn; onToggle: (id: number) => void; onChoice?: (c: string) => void
}) {
  const faded = t.undone ? 'opacity-40' : ''
  const undo = t.has_ops && (
    <button type="button" onClick={() => onToggle(t.id)}
            className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] ${t.undone
              ? 'text-accent hover:bg-raised' : 'text-muted hover:bg-raised hover:text-zinc-200'}`}
            title={t.undone ? 'Re-apply this turn' : 'Undo this turn — later turns stay'}>
      {t.undone ? 'Redo' : 'Undo'}
    </button>
  )

  return (
    <div className="space-y-1.5">
      {t.kind === 'direct' ? (
        // Direct edits (Apply, timeline drag/delete) are one compact row.
        <div className="flex items-center gap-2 text-[11px]">
          <span className={`h-px w-3 bg-line ${faded}`} />
          <span className={`min-w-0 flex-1 truncate text-muted ${t.undone ? 'line-through opacity-50' : ''}`}
                title={t.lines.map((l) => l.text).join(' · ')}>
            {t.text}{t.lines[0] && t.lines[0].kind !== 'replaced' && t.lines[0].kind !== 'none'
              ? <span className="text-zinc-500"> — {t.lines.map((l) => l.text).join(' · ')}</span> : null}
          </span>
          {t.skipped.length > 0 && <span className="text-amber-200/80" title={t.skipped.join('\n')}>skipped</span>}
          {undo}
        </div>
      ) : (
        <div className="flex justify-end">
          <div className={`max-w-[85%] rounded-2xl rounded-br-md bg-accent px-3 py-2 font-serif text-[16px] leading-snug text-accent-ink ${faded}`}>{t.text}</div>
        </div>
      )}

      {t.kind === 'chat' && (t.reply || t.question || t.lines.length > 0 || t.skipped.length > 0 || t.direction) && (
        <div className={`rounded-lg border border-line bg-raised/60 px-2.5 py-2 ${t.undone ? 'opacity-50' : ''}`}>
          <div className="flex items-start gap-2">
            <div className={`min-w-0 flex-1 font-serif text-[16px] leading-snug ${t.undone ? 'line-through decoration-zinc-600' : ''}`}>
              {t.question ? <span className="text-zinc-100">{t.question}</span>
                : t.reply ? <span className="text-zinc-300">{t.reply}</span>
                  : t.direction ? <span className="text-zinc-300">Three proposals{t.direction.themes.length ? `, leaning into ${t.direction.themes.join(' + ')}` : ''} — choose one in the middle.</span>
                    : null}
            </div>
            {undo}
          </div>

          {t.question && t.choices.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {t.choices.map((c) => (
                <button key={c} type="button" disabled={!onChoice} onClick={() => onChoice?.(c)}
                        className="rounded-full border border-accent/50 px-2.5 py-1 text-[12px] text-accent hover:bg-accent hover:text-accent-ink disabled:border-line disabled:text-muted disabled:hover:bg-transparent">
                  {c}
                </button>
              ))}
            </div>
          )}

          {t.lines.filter((l) => l.kind !== 'none' || !t.direction).length > 0 && (
            <ul className={`mt-2 space-y-1 ${t.undone ? 'line-through decoration-zinc-600' : ''}`}>
              {t.lines.filter((l) => l.kind !== 'none' || !t.direction).map((l, i) => (
                <li key={i} className="flex items-center gap-2 text-[12px]">
                  <span className={`grid h-5 min-w-5 place-items-center rounded px-1 text-[11px] font-semibold ${MARK[l.kind].cls}`}>{MARK[l.kind].sym}</span>
                  <span className="min-w-0 flex-1 text-zinc-300">{l.text}</span>
                  {l.thumb && <img src={l.thumb} className="h-5 w-9 shrink-0 rounded-sm object-cover" />}
                </li>
              ))}
            </ul>
          )}
          {t.skipped.map((s) => (
            <p key={s} className="mt-1.5 text-[11px] text-amber-200/80">Skipped: {s}</p>
          ))}
        </div>
      )}
    </div>
  )
}

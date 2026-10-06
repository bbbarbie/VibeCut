import { useEffect, useRef, useState } from 'react'
import { api, type MomentAnswer, type MomentInfo } from '../api'
import { locate, type SeqItem } from '../sequence'
import { phStore, useStore } from '../transport'
import { Button, cx } from '../ui'

// Pausing the preview means something here is wrong or should change
// (sarah, 2026-10-05). So the chat lives on the pause: it opens pinned to the
// paused moment, the AI is told exactly what's on screen there, and an edit
// it proposes changes nothing until Apply -- one undoable step, like any
// other. Nothing is sent to the AI until Send; the cost of one message is
// shown before it is.

type Line = { who: 'you' | 'ai'; text: string; answer?: MomentAnswer; applied?: boolean }

const money = ([lo, hi]: [number, number]) => {
  const c = (x: number) => (x < 0.01 ? '<1¢' : `${Math.round(x * 100)}¢`)
  return c(lo) === c(hi) ? c(lo) : `${c(lo)}–${c(hi)}`
}

const clock = (t: number) => `${Math.floor(t / 60)}:${(t % 60).toFixed(1).padStart(4, '0')}`

export function PauseChat({ onApply, busy, items, clipName }: {
  onApply: (ops: Record<string, unknown>[], label: string) => Promise<unknown>
  busy: boolean
  items: SeqItem[]
  clipName: (clipId: string) => string
}) {
  const t = useStore(phStore)
  // The header is read off the timeline already here, so it follows the
  // playhead at once (a jump to another clip waited on the server before);
  // only the cost comes from the server.
  const it = items[locate(items, t)]
  const here = it && (it.kind === 'gap' ? `Empty space · ${clock(t)}` : `Shot ${it.n} · ${clock(t)} · ${clipName(it.clip_id!)}`)
  const [info, setInfo] = useState<MomentInfo | null>(null)
  const [lines, setLines] = useState<Line[]>([])
  const [draft, setDraft] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const key = useRef<string | null>(null)

  // what's under the playhead (free: nothing goes to the AI)
  useEffect(() => {
    let live = true
    const id = setTimeout(() => {
      api.moment(t).then((m) => {
        if (!live) return
        setInfo(m)
      }).catch(() => { if (live) setInfo(null) })
    }, 200)
    return () => { live = false; clearTimeout(id) }
  }, [t])

  useEffect(() => {
    if (it && it.key !== key.current) { key.current = it.key; setLines([]); setError(null) }
  }, [it?.key]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!it) return null
  const llm = info?.llm ?? false
  const send = async (text: string) => {
    const msg = text.trim()
    if (!msg || sending) return
    setDraft('')
    setError(null)
    const history = lines.map((l) => ({ who: l.who, text: l.text }))
    setLines((ls) => [...ls, { who: 'you', text: msg }])
    setSending(true)
    try {
      const a = await api.momentChat(t, msg, history)
      setLines((ls) => [...ls, { who: 'ai', text: a.reply || (a.ops.length ? 'Here’s a change for this moment.' : 'Done.'), answer: a }])
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSending(false)
    }
  }
  const apply = async (i: number) => {
    const l = lines[i]
    if (!l.answer?.ops.length) return
    const asked = [...lines.slice(0, i)].reverse().find((x) => x.who === 'you')?.text ?? 'Change at this moment'
    await onApply(l.answer.ops, asked)
    setLines((ls) => ls.map((x, k) => (k === i ? { ...x, applied: true } : x)))
  }

  return (
    <div className="flex min-h-0 flex-col border-t border-line bg-panel">
      <div className="flex items-center gap-2 px-3 pt-2 text-[11px]">
        <span className="size-1.5 rounded-full bg-accent" aria-hidden />
        <span className="truncate font-medium text-zinc-200">{here}</span>
        <span className="ml-auto shrink-0 text-muted">{!info ? '' : llm ? `about ${money(info.estimate.usd)} a message` : 'AI off'}</span>
      </div>
      {lines.length > 0 && (
        <div className="max-h-56 min-h-0 space-y-2 overflow-y-auto px-3 pt-2 text-[12px]">
          {lines.map((l, i) => (
            <div key={i} className={cx('rounded-lg px-2.5 py-1.5', l.who === 'you' ? 'ml-6 bg-zinc-800 text-zinc-100' : 'mr-6 bg-raised text-zinc-200')}>
              <p className="whitespace-pre-wrap">{l.text}</p>
              {l.answer?.preview && l.answer.ops.length > 0 && (
                <div className="mt-1.5 border-t border-line pt-1.5">
                  {l.answer.preview.lines.map((x, k) => <p key={k} className="text-[11px] text-zinc-400">· {x}</p>)}
                  {l.answer.preview.skipped.map((x, k) => <p key={`s${k}`} className="text-[11px] text-amber-200">Can’t do: {x}</p>)}
                  <div className="mt-1.5 flex items-center gap-2">
                    {l.applied
                      ? <span className="text-[11px] text-emerald-300">Applied — Undo takes it back</span>
                      : <Button size="sm" variant="primary" disabled={busy} onClick={() => { apply(i).catch((e) => setError((e as Error).message)) }}>Apply</Button>}
                  </div>
                </div>
              )}
              {l.answer?.choices.length ? (
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {l.answer.choices.map((c) => (
                    <button key={c} type="button" disabled={!llm || sending} onClick={() => send(c)}
                            className="rounded-full border border-line px-2 py-0.5 text-[11px] text-zinc-300 hover:bg-zinc-800">{c}</button>
                  ))}
                </div>
              ) : null}
            </div>
          ))}
          {sending && <p className="mr-6 text-[11px] text-muted">Looking at this moment…</p>}
        </div>
      )}
      {error && <p className="px-3 pt-1.5 text-[11px] text-amber-200">{error}</p>}
      {!info ? null : llm ? (
        <form className="flex gap-2 p-3" onSubmit={(e) => { e.preventDefault(); send(draft) }}>
          <input value={draft} onChange={(e) => setDraft(e.target.value)} disabled={sending}
                 placeholder="What’s wrong here, or what should change?"
                 className="min-w-0 flex-1 rounded-lg border border-line bg-zinc-900 px-2.5 py-1.5 text-[12px] text-zinc-100 placeholder:text-zinc-500 focus:border-accent focus:outline-none" />
          <Button size="sm" variant="primary" type="submit" disabled={!draft.trim() || sending}>Send</Button>
        </form>
      ) : (
        <p className="p-3 text-[12px] text-zinc-400">
          Chatting about this moment needs the AI turned on (the Anthropic key). It’s off, so nothing is sent and nothing is spent.
        </p>
      )}
    </div>
  )
}

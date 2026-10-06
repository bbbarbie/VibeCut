import { useEffect, useRef, useState } from 'react'
import { applies, type Picks } from '../brief'
import type { StyleQuestion } from '../types'

// Asked once, after the first description and before anything is cut: a
// few multiple-choice questions, one at a time, like an editor would ask.
// Every question can be skipped; skipping all of them is fine too.
export function StyleQuestions({ description, questions, tailored, onDone, onCancel }: {
  description: string
  questions: StyleQuestion[] | null        // null while they load
  tailored: boolean
  onDone: (picks: Picks, extra: string) => void
  onCancel: () => void
}) {
  const [step, setStep] = useState(0)
  const [picks, setPicks] = useState<Picks>({})
  const [extra, setExtra] = useState('')
  const card = useRef<HTMLDivElement>(null)
  // A question that depends on an earlier answer (the captions' look) is
  // only asked when that answer calls for it.
  const qs = (questions ?? []).filter((x) => applies(x, picks))
  const last = step >= qs.length           // the "anything else?" step
  const q = last ? null : qs[step]
  const p = q ? picks[q.id] ?? { keys: [], other: '' } : null

  useEffect(() => {
    const key = (e: KeyboardEvent) => { if (e.key === 'Escape') onCancel() }
    window.addEventListener('keydown', key)
    return () => window.removeEventListener('keydown', key)
  }, [onCancel])
  useEffect(() => { card.current?.focus() }, [step, questions])

  const set = (id: string, next: { keys: string[]; other: string }) => setPicks((ps) => ({ ...ps, [id]: next }))
  const choose = (key: string) => {
    if (!q || !p) return
    if (q.multi) {
      set(q.id, { ...p, keys: p.keys.includes(key) ? p.keys.filter((k) => k !== key) : [...p.keys, key] })
    } else {
      set(q.id, { ...p, keys: p.keys[0] === key ? [] : [key] })
      if (p.keys[0] !== key) window.setTimeout(() => setStep((s) => s + 1), 180)
    }
  }
  const finish = () => onDone(picks, extra)

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4 backdrop-blur-[2px]" role="dialog" aria-modal="true"
         aria-label="A few questions about your video" onMouseDown={(e) => { if (e.target === e.currentTarget) onCancel() }}>
      <div ref={card} tabIndex={-1}
           onKeyDown={(e) => {
             const typing = (e.target as HTMLElement).tagName === 'INPUT' || (e.target as HTMLElement).tagName === 'TEXTAREA'
             const n = Number(e.key)
             if (!typing && q && n >= 1 && n <= q.choices.length) choose(q.choices[n - 1].key)
           }}
           className="w-full max-w-[520px] rounded-2xl border border-line bg-raised shadow-2xl outline-none">
        <div className="border-b border-line px-5 pb-3 pt-4">
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-accent">Before I cut anything</span>
            <span className="flex-1" />
            {questions && (
              <span className="flex gap-1" aria-hidden>
                {[...qs, null].map((_, i) => (
                  <i key={i} className={`block h-1.5 rounded-full transition-all ${i === step ? 'w-4 bg-accent' : i < step ? 'w-1.5 bg-accent/50' : 'w-1.5 bg-zinc-700'}`} />
                ))}
              </span>
            )}
            <button type="button" onClick={onCancel} aria-label="Close" className="ml-2 text-[16px] leading-none text-muted hover:text-zinc-200">×</button>
          </div>
          <p className="mt-1.5 truncate font-serif text-[15px] italic text-zinc-400" title={description}>“{description}”</p>
        </div>

        <div className="min-h-[260px] px-5 py-4">
          {!questions ? (
            <p className="py-16 text-center text-[13px] text-muted">
              <span className="mr-2 inline-block size-2 animate-pulse rounded-full bg-accent" />Thinking of a few questions…
            </p>
          ) : q && p ? (
            <>
              <h2 className="font-serif text-[22px] leading-tight text-zinc-100">{q.question}</h2>
              <p className="mt-1 text-[12px] text-muted">{q.multi ? q.hint ?? 'Pick any' : 'Pick one'}</p>
              <div className="mt-3 space-y-1.5">
                {q.choices.map((c, i) => {
                  const on = p.keys.includes(c.key)
                  return (
                    <button key={c.key} type="button" onClick={() => choose(c.key)} aria-pressed={on}
                            className={`flex w-full items-center gap-3 rounded-xl border px-3 py-2.5 text-left transition-colors ${on ? 'border-accent bg-accent/10' : 'border-line hover:border-zinc-500 hover:bg-zinc-800/60'}`}>
                      <span className={`grid size-5 shrink-0 place-items-center rounded-md border text-[10px] tabular-nums ${on ? 'border-accent bg-accent text-accent-ink' : 'border-zinc-600 text-muted'}`}>
                        {on ? '✓' : i + 1}
                      </span>
                      <span className="min-w-0">
                        <span className="block text-[14px] text-zinc-100">{c.label}</span>
                        {c.hint && <span className="block text-[12px] text-muted">{c.hint}</span>}
                      </span>
                    </button>
                  )
                })}
                <input value={p.other} onChange={(e) => set(q.id, { ...p, other: e.target.value })}
                       onKeyDown={(e) => { if (e.key === 'Enter') setStep((s) => s + 1) }}
                       placeholder="Something else…"
                       className="w-full rounded-xl border border-dashed border-line bg-transparent px-3 py-2.5 text-[13px] text-zinc-100 outline-none placeholder:text-zinc-500 focus:border-zinc-500" />
              </div>
            </>
          ) : (
            <>
              <h2 className="font-serif text-[22px] leading-tight text-zinc-100">Anything else I should know?</h2>
              <p className="mt-1 text-[12px] text-muted">Optional. A moment you want in, something to leave out.</p>
              <textarea autoFocus value={extra} onChange={(e) => setExtra(e.target.value)} rows={3}
                        onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); finish() } }}
                        placeholder="e.g. end on the sunset, skip the lecture slides"
                        className="mt-3 w-full resize-none rounded-xl border border-line bg-panel px-3 py-2.5 text-[13px] text-zinc-100 outline-none placeholder:text-zinc-500 focus:border-zinc-500" />
              {tailored && <p className="mt-2 text-[11px] text-zinc-600">Some of these questions were written by Claude from your description.</p>}
            </>
          )}
        </div>

        <div className="flex items-center gap-2 border-t border-line px-5 py-3">
          {step > 0 && questions && (
            <button type="button" onClick={() => setStep((s) => s - 1)} className="text-[12px] text-muted hover:text-zinc-200">← Back</button>
          )}
          <span className="flex-1" />
          {questions && (last ? (
            <button type="button" onClick={finish}
                    className="rounded-lg bg-accent px-4 py-1.5 text-[13px] font-semibold text-accent-ink hover:brightness-110">Build my edit</button>
          ) : (
            <>
              <button type="button" onClick={finish} className="rounded-lg px-3 py-1.5 text-[12px] text-muted hover:text-zinc-200">Skip the rest</button>
              <button type="button" onClick={() => setStep((s) => s + 1)}
                      className="rounded-lg border border-line px-4 py-1.5 text-[13px] text-zinc-100 hover:bg-zinc-800">
                {p && (p.keys.length || p.other.trim()) ? 'Next' : 'Skip'}
              </button>
            </>
          ))}
        </div>
      </div>
    </div>
  )
}

import { useState } from 'react'
import type { PrefCandidate, PrefClass, PrefRule } from '../types'

// An edit is not a taste. Each one can be sorted by the creator -- and only
// "for this video" and "every video" are ever used again. Nothing is learned
// by leaving it alone.

const CHOICES: { klass: PrefClass; label: string; hint: string }[] = [
  { klass: 'single_edit', label: 'Just here', hint: 'Fixes this spot. Nothing is learned.' },
  { klass: 'project', label: 'For this video', hint: 'Used for the rest of this edit, then forgotten.' },
  { klass: 'long_term', label: 'Every video', hint: 'Kept for future edits too. Say when it applies and when it doesn’t.' },
  { klass: 'compliance_fix', label: 'Privacy or rights', hint: 'A face, a screen, music you can’t use — never treated as taste.' },
  { klass: 'rejected', label: 'Don’t learn', hint: 'Nothing is kept.' },
]
const CLASS_LABEL: Record<PrefClass, string> = Object.fromEntries(CHOICES.map((c) => [c.klass, c.label])) as Record<PrefClass, string>

export type ClassifyReq = { turn: number; klass: PrefClass; rule?: string; scope?: string; counter?: string; reason?: string }

export function Remember({ c, onClassify }: { c: PrefCandidate; onClassify: (r: ClassifyReq) => Promise<void> }) {
  const [open, setOpen] = useState(false)
  const [klass, setKlass] = useState<PrefClass>(c.suggested)
  const [rule, setRule] = useState(c.said)
  const [scope, setScope] = useState('')
  const [counter, setCounter] = useState('')
  const [error, setError] = useState<string | null>(null)

  if (c.status !== 'candidate') {
    return <span className="text-[10px] text-muted">{c.klass ? `Sorted: ${CLASS_LABEL[c.klass].toLowerCase()}` : ''}</span>
  }
  if (!c.readable) return null
  if (!open) {
    return (
      <button type="button" onClick={() => setOpen(true)}
              className={`rounded px-1.5 py-0.5 text-[10px] hover:bg-raised ${c.suggested === 'long_term' ? 'text-accent' : 'text-muted hover:text-zinc-200'}`}
              title="Should VibeCut remember this edit? Nothing is learned unless you say so.">
        {c.suggested === 'long_term' ? 'Keep this for next time?' : 'Remember…'}
      </button>
    )
  }
  const learned = klass === 'project' || klass === 'long_term'
  const save = async () => {
    setError(null)
    try { await onClassify({ turn: c.turn, klass, rule, scope, counter }); setOpen(false) } catch (e) { setError((e as Error).message) }
  }
  return (
    <div className="mt-2 w-full rounded-lg border border-line bg-panel p-2 text-[11px]">
      <div className="flex flex-wrap gap-1">
        {CHOICES.map((x) => (
          <button key={x.klass} type="button" onClick={() => setKlass(x.klass)} title={x.hint}
                  className={`rounded-full border px-2 py-0.5 ${klass === x.klass ? 'border-accent bg-accent text-accent-ink' : 'border-line text-zinc-300 hover:bg-raised'}`}>
            {x.label}
          </button>
        ))}
      </div>
      <p className="mt-1.5 text-muted">{CHOICES.find((x) => x.klass === klass)?.hint}</p>
      {learned && (
        <div className="mt-1.5 space-y-1">
          <input value={rule} onChange={(e) => setRule(e.target.value)} placeholder="The rule, in your words"
                 className="block w-full rounded border border-line bg-raised px-2 py-1 text-zinc-100 outline-none focus:border-zinc-500" />
          {klass === 'long_term' && (
            <>
              <input value={scope} onChange={(e) => setScope(e.target.value)} placeholder="When it applies — e.g. travel vlogs, openings"
                     className="block w-full rounded border border-line bg-raised px-2 py-1 text-zinc-100 outline-none focus:border-zinc-500" />
              <input value={counter} onChange={(e) => setCounter(e.target.value)} placeholder="When it doesn’t — e.g. slow, quiet pieces"
                     className="block w-full rounded border border-line bg-raised px-2 py-1 text-zinc-100 outline-none focus:border-zinc-500" />
            </>
          )}
        </div>
      )}
      {error && <p className="mt-1 text-rose-300">{error}</p>}
      <div className="mt-1.5 flex justify-end gap-2">
        <button type="button" onClick={() => setOpen(false)} className="px-1.5 text-muted hover:text-zinc-200">Cancel</button>
        <button type="button" onClick={save} className="rounded bg-accent px-2 py-0.5 font-semibold text-accent-ink">Save</button>
      </div>
    </div>
  )
}

export function Rules({ rules, onRule }: { rules: PrefRule[]; onRule: (id: string, action: 'forget' | 'narrow') => void }) {
  const active = rules.filter((r) => r.active)
  if (!active.length) return null
  return (
    <details className="border-b border-line px-4 py-2 text-[11px]">
      <summary className="cursor-pointer text-zinc-300">Remembered ({active.length})</summary>
      <ul className="mt-1.5 space-y-1.5">
        {active.map((r) => (
          <li key={r.id} className="rounded-md bg-raised/60 px-2 py-1.5">
            <div className="text-zinc-200">{r.rule}</div>
            <div className="text-muted">
              {r.klass === 'long_term' ? 'Every video' : 'This video'}
              {r.scope && ` · when: ${r.scope}`}{r.counter && ` · not when: ${r.counter}`}
            </div>
            <div className="mt-1 flex gap-2">
              {r.klass === 'long_term' && <button type="button" onClick={() => onRule(r.id, 'narrow')} className="text-muted hover:text-zinc-200">Only this video</button>}
              <button type="button" onClick={() => onRule(r.id, 'forget')} className="text-muted hover:text-rose-300">Forget</button>
            </div>
          </li>
        ))}
      </ul>
    </details>
  )
}

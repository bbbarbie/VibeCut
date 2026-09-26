import { useState } from 'react'
import { borrowNow } from '../borrow'
import type { Session } from '../types'

// Paste a link to a video you love; your edit takes on its pace, cuts and colour.
export function MatchStyle({ onDone, onAdjust }: { onDone: (s: Session) => void; onAdjust: () => void }) {
  const [src, setSrc] = useState('')
  const [busy, setBusy] = useState<{ text: string; frac: number } | null>(null)
  const [error, setError] = useState('')

  const go = async () => {
    if (!src.trim() || busy) return
    setError('')
    setBusy({ text: 'Starting…', frac: 0.02 })
    try {
      onDone(await borrowNow(src, (text, frac) => setBusy({ text, frac })))
      setSrc('')
    } catch (e) { setError((e as Error).message) } finally { setBusy(null) }
  }

  return (
    <div className="rounded-xl border border-accent/30 bg-panel px-3 py-2.5">
      <form className="flex items-center gap-2" onSubmit={(e) => { e.preventDefault(); void go() }}>
        <span className="shrink-0 text-[12px] text-accent">◈ Make it feel like</span>
        <input value={src} onChange={(e) => { setSrc(e.target.value); setError('') }} disabled={!!busy}
               placeholder="paste a link to a video you love"
               className="min-w-0 flex-1 rounded-lg border border-line bg-ink px-2.5 py-1.5 text-[12px] text-zinc-100 placeholder:text-zinc-500 focus:border-accent/60 focus:outline-none" />
        <button type="submit" disabled={!src.trim() || !!busy}
                className="shrink-0 rounded-lg bg-accent px-3 py-1.5 text-[12px] font-semibold text-accent-ink disabled:opacity-40">
          {busy ? 'Working…' : 'Go'}
        </button>
        <button type="button" onClick={onAdjust} title="See what it learnt and choose what to borrow"
                className="shrink-0 text-[11px] text-muted hover:text-zinc-200">Fine-tune…</button>
      </form>
      {busy && <div className="mt-2">
        <div className="h-1 overflow-hidden rounded-full bg-zinc-800"><div className="h-full rounded-full bg-accent transition-[width] duration-300" style={{ width: `${busy.frac * 100}%` }} /></div>
        <p className="mt-1 text-[11px] text-muted">{busy.text}</p>
      </div>}
      {error && <p className="mt-1.5 text-[12px] text-rose-300">{error}</p>}
    </div>
  )
}

import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import type { Session } from '../types'

// How quick the cuts are, read from the footage (tempo.py) and changeable
// here, as one undoable turn. Says why it picked what it picked.
const PACES = [['fast', 'Quick cuts'], ['balanced', 'Steady cuts'], ['calm', 'Calm cuts']] as const

export function PaceButton({ pace, why, story, onDone }: {
  pace?: string; why?: string; story?: string; onDone: (s: Session) => void
}) {
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const box = useRef<HTMLDivElement>(null)
  const btn = useRef<HTMLButtonElement>(null)
  const [pos, setPos] = useState<{ left: number; top: number } | null>(null)

  useEffect(() => {
    if (!open) return
    const r = btn.current?.getBoundingClientRect()
    if (r) setPos({ top: r.bottom + 6, left: Math.max(8, Math.min(r.right - 320, window.innerWidth - 328)) })
    const away = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) setOpen(false) }
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    window.addEventListener('mousedown', away)
    window.addEventListener('keydown', esc)
    return () => { window.removeEventListener('mousedown', away); window.removeEventListener('keydown', esc) }
  }, [open])

  const pick = async (p: string) => {
    if (busy || p === pace) return
    setBusy(true)
    try { onDone(await api.pace(p)); setOpen(false) } finally { setBusy(false) }
  }
  const name = PACES.find(([k]) => k === pace)?.[1] ?? 'Tempo'

  return (
    <div ref={box} className="relative">
      <button ref={btn} type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open}
              title="How quick the cuts are, read from your clips"
              className="whitespace-nowrap rounded-md border border-line px-2 py-1 text-[11px] text-zinc-300 hover:bg-raised">
        {name}
      </button>
      {open && pos && (
        <div className="fixed z-40 w-[320px] rounded-xl border border-line bg-raised p-4 font-serif shadow-2xl" style={pos}>
          {why && <p className="text-[15px] leading-snug text-zinc-200">{why}</p>}
          {story && <p className="mt-2 text-[15px] leading-snug text-zinc-200">{story}</p>}
          <div className="mt-3 flex gap-1.5">
            {PACES.map(([k, label]) => (
              <button key={k} type="button" disabled={busy} onClick={() => pick(k)}
                      className={`flex-1 rounded-md border px-2 py-1.5 font-serif text-[15px] ${k === pace ? 'border-accent text-zinc-100' : 'border-line text-zinc-300 hover:bg-zinc-800'}`}>
                {label.split(' ')[0]}
              </button>
            ))}
          </div>
          {busy && <p className="mt-2 text-[15px] text-zinc-200">Changing the edit…</p>}
        </div>
      )}
    </div>
  )
}

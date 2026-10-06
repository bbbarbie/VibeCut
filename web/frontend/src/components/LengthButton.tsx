import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { lengthLabel } from '../brief'
import type { LengthSlider as Slider, Session } from '../types'
import { LengthSlider } from './LengthSlider'

// The length slider again, in Frames: change how long the video is without
// redoing the brief. Letting go makes it so, as one undoable turn (shorter:
// the weakest shots go; longer: good shots come back where they happened).
export function LengthButton({ total, onDone }: { total: number; onDone: (s: Session & { length_note: string }) => void }) {
  const [open, setOpen] = useState(false)
  const [slider, setSlider] = useState<Slider | null>(null)
  const [value, setValue] = useState(total)
  const [busy, setBusy] = useState(false)
  const box = useRef<HTMLDivElement>(null)
  const btn = useRef<HTMLButtonElement>(null)
  const [pos, setPos] = useState<{ left: number; top: number } | null>(null)

  useEffect(() => { if (!busy) setValue(total) }, [total, busy])
  useEffect(() => {
    if (!open) return
    // placed on the page, kept inside the window (the bar is narrow and sits at the edge)
    const r = btn.current?.getBoundingClientRect()
    if (r) setPos({ top: r.bottom + 6, left: Math.max(8, Math.min(r.right - 320, window.innerWidth - 328)) })
    api.length().then(setSlider).catch(() => setSlider(null))
    const away = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) setOpen(false) }
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    window.addEventListener('mousedown', away)
    window.addEventListener('keydown', esc)
    return () => { window.removeEventListener('mousedown', away); window.removeEventListener('keydown', esc) }
  }, [open])

  const commit = async (sec: number) => {
    if (Math.abs(sec - total) < 1.5 || busy) return
    setBusy(true)
    try { onDone(await api.setLength(sec)) } finally { setBusy(false) }
  }

  return (
    <div ref={box} className="relative">
      <button ref={btn} type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open}
              title="How long the video is. Drag to make it shorter or longer."
              className="whitespace-nowrap rounded-md border border-line px-2 py-1 text-[11px] tabular-nums text-zinc-300 hover:bg-raised">
        Length {lengthLabel(total)}
      </button>
      {open && pos && (
        <div className="fixed z-40 w-[320px] rounded-xl border border-line bg-raised p-4 shadow-2xl" style={pos}>
          {slider ? (
            <>
              <LengthSlider compact slider={slider} value={value} onChange={setValue} onCommit={commit} />
              <p className="mt-2 text-[11px] text-zinc-500">{busy ? 'Changing the edit…' : 'Let go to change the edit. Undo puts it back.'}</p>
            </>
          ) : <p className="w-60 text-[12px] text-muted">Reading your footage…</p>}
        </div>
      )}
    </div>
  )
}

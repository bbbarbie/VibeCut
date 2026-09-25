import { useEffect, useRef } from 'react'
import type { Clip } from '../types'

// Select, then act: the actions for a thing appear next to it when you
// click it. There is no tool to pick first and no mode to be in.

export type MenuItem = { label: string; hint?: string; onClick: () => void; danger?: boolean; disabled?: boolean }

export function Menu({ anchor, title, items, onClose }: {
  anchor: DOMRect; title?: string; items: MenuItem[]; onClose: () => void
}) {
  const box = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const away = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) onClose() }
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    const t = setTimeout(() => window.addEventListener('mousedown', away), 0)
    window.addEventListener('keydown', esc)
    return () => { clearTimeout(t); window.removeEventListener('mousedown', away); window.removeEventListener('keydown', esc) }
  }, [onClose])

  // Below the thing, or above it if there's no room; kept on screen.
  const W = 250
  const left = Math.min(Math.max(8, anchor.left + anchor.width / 2 - W / 2), window.innerWidth - W - 8)
  const below = anchor.bottom + 8 + items.length * 34 + 40 < window.innerHeight
  const style = below ? { left, top: anchor.bottom + 6, width: W } : { left, bottom: window.innerHeight - anchor.top + 6, width: W }

  return (
    <div ref={box} style={style} className="fixed z-40 rounded-xl border border-line bg-panel p-1.5 shadow-2xl shadow-black/60">
      {title && <div className="px-2.5 pb-1 pt-1 text-[11px] text-muted">{title}</div>}
      {items.map((it) => (
        <button key={it.label} type="button" disabled={it.disabled}
                onClick={() => { it.onClick(); onClose() }}
                className={`flex w-full items-baseline justify-between gap-2 rounded-md px-2.5 py-1.5 text-left text-[13px] disabled:opacity-30 ${it.danger
                  ? 'text-rose-200 hover:bg-rose-500/10' : 'text-zinc-100 hover:bg-zinc-800'}`}>
          <span>{it.label}</span>
          {it.hint && <span className="shrink-0 text-[11px] text-muted">{it.hint}</span>}
        </button>
      ))}
    </div>
  )
}

// Choose the replacement for a shot from everything on the shelf.
export function SwapPicker({ clips, used, current, onPick, onClose }: {
  clips: Clip[]; used: Set<string>; current: { thumb: string; id: string }
  onPick: (withShot: string | null) => void; onClose: () => void
}) {
  useEffect(() => {
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', esc)
    return () => window.removeEventListener('keydown', esc)
  }, [onClose])
  const shelf = clips.flatMap((c) => c.shots.map((s) => ({ ...s, clip: c })))
    .filter((s) => !used.has(s.id) && !s.utility)
    .sort((a, b) => b.quality - a.quality)

  return (
    <div className="fixed inset-0 z-40 grid place-items-center bg-black/60" onMouseDown={onClose}>
      <div className="flex max-h-[80vh] w-[760px] flex-col rounded-2xl border border-line bg-panel p-5" onMouseDown={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-3">
          <img src={current.thumb} className="h-12 w-20 rounded object-cover" />
          <div>
            <h3 className="font-serif text-[20px] text-zinc-100">Swap this shot for…</h3>
            <p className="text-[12px] text-muted">It takes the same place and the same length in your story.</p>
          </div>
          <button type="button" onClick={onClose} className="ml-auto text-[12px] text-muted hover:text-zinc-200">Cancel</button>
        </div>
        <button type="button" onClick={() => onPick(null)}
                className="mt-4 rounded-lg border border-accent/50 px-3 py-2 text-left text-[13px] text-accent hover:bg-accent/10">
          Let VibeCut choose — a similar shot that’s better made (sharper, better lit)
        </button>
        <p className="mt-4 text-[11px] text-muted">
          {shelf.length ? `Or pick one yourself — ${shelf.length} shots that aren’t in your story yet, best first:` : 'Every shot is already in your story.'}
        </p>
        <div className="mt-2 grid min-h-0 grid-cols-5 gap-2 overflow-y-auto pb-1">
          {shelf.map((s) => (
            <button key={s.id} type="button" onClick={() => onPick(s.id)}
                    className="group relative overflow-hidden rounded-md bg-black text-left ring-accent hover:ring-2">
              <img src={s.thumb} className="aspect-video w-full object-cover" />
              <span className="absolute bottom-0.5 right-0.5 rounded bg-black/70 px-1 text-[10px] tabular-nums text-zinc-200">
                {Math.round(s.end - s.start)}s
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

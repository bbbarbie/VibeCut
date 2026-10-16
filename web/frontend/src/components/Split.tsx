import { useCallback, useRef, useState, type CSSProperties } from 'react'
import { cx } from '../ui'

// The edit screen's panel sizes, which the creator sets by dragging the
// borders (sarah, 2026-10-14: "make the borders adjustable", the preview the
// biggest part). Remembered in this browser; if storage is off the defaults
// still work.
export type Layout = { side: number; inspector: number; timeline: number }

const KEY = 'vibecut.layout.v2'
// The preview takes whatever is left, so these defaults are what make it the
// biggest area: the clip grid and the inspector at the width of three tiles.
const LAYOUT: Layout = { side: 340, inspector: 360, timeline: 290 }
const LIMITS: Record<keyof Layout, [number, number]> = {
  side: [240, 600], inspector: [300, 560], timeline: [190, 560],
}

const clamp = (k: keyof Layout, v: number) => Math.round(Math.min(LIMITS[k][1], Math.max(LIMITS[k][0], v)))

function read(): Layout {
  try {
    const s = JSON.parse(localStorage.getItem(KEY) ?? '{}') as Partial<Layout>
    const out = { ...LAYOUT }
    for (const k of Object.keys(LAYOUT) as (keyof Layout)[]) {
      if (typeof s[k] === 'number' && Number.isFinite(s[k])) out[k] = clamp(k, s[k]!)
    }
    return out
  } catch { return { ...LAYOUT } }
}

export function useLayout() {
  const [layout, setLayout] = useState<Layout>(read)
  const set = useCallback((k: keyof Layout, v: number, save = false) => {
    setLayout((l) => {
      const next = { ...l, [k]: clamp(k, v) }
      if (save) { try { localStorage.setItem(KEY, JSON.stringify(next)) } catch { /* private window */ } }
      return next
    })
  }, [])
  return [layout, set] as const
}

/**
 * A border you can drag. Always visible (a grip in its middle), never a
 * hidden gesture; arrow keys move it too. `grow` is the direction that makes
 * the panel bigger: +1 when dragging right / down grows it, -1 when dragging
 * left / up does.
 */
export function Handle({ axis, size, grow = 1, max, onSize, label, className, style }: {
  axis: 'x' | 'y'
  size: number
  grow?: 1 | -1
  /** a tighter upper bound than LIMITS, from the space there is now */
  max?: () => number
  onSize: (v: number, save: boolean) => void
  label: string
  className?: string
  style?: CSSProperties
}) {
  const from = useRef<{ at: number; size: number } | null>(null)
  const [active, setActive] = useState(false)
  const fit = (v: number) => (max ? Math.min(v, max()) : v)
  const x = axis === 'x'
  return (
    <div role="separator" aria-orientation={x ? 'vertical' : 'horizontal'} aria-label={label} aria-valuenow={size}
         tabIndex={0} title={label}
         onPointerDown={(e) => {
           if (e.button !== 0) return
           e.preventDefault()
           e.currentTarget.setPointerCapture(e.pointerId)
           from.current = { at: x ? e.clientX : e.clientY, size }
           setActive(true)
         }}
         onPointerMove={(e) => {
           const f = from.current
           if (!f) return
           onSize(fit(f.size + grow * ((x ? e.clientX : e.clientY) - f.at)), false)
         }}
         onPointerUp={(e) => {
           const f = from.current
           from.current = null
           setActive(false)
           if (f) onSize(fit(f.size + grow * ((x ? e.clientX : e.clientY) - f.at)), true)
         }}
         onPointerCancel={() => { from.current = null; setActive(false) }}
         onKeyDown={(e) => {
           const keys: Record<string, number> = x ? { ArrowLeft: -1, ArrowRight: 1 } : { ArrowUp: -1, ArrowDown: 1 }
           const d = keys[e.key]
           if (!d) return
           e.preventDefault()
           e.stopPropagation() // not also a frame step on the timeline
           onSize(fit(size + grow * d * (e.shiftKey ? 64 : 16)), true)
         }}
         style={style}
         className={cx('group relative z-20 flex shrink-0 touch-none select-none items-center justify-center outline-none',
           x ? 'w-2 cursor-col-resize' : 'h-2 cursor-row-resize', className)}>
      <span aria-hidden className={cx('absolute bg-line', x ? 'inset-y-0 left-1/2 w-px' : 'inset-x-0 top-1/2 h-px')} />
      <span aria-hidden className={cx('relative rounded-full transition-colors',
        x ? 'h-10 w-1.5' : 'h-1.5 w-10',
        active ? 'bg-accent' : 'bg-zinc-600 group-hover:bg-accent group-focus-visible:bg-accent')} />
    </div>
  )
}

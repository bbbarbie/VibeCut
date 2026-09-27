import { useEffect, useRef } from 'react'
import { drawOverlays, ensureFonts, type Part } from '../overlayDraw'
import { phStore } from '../transport'
import type { Overlay, OverlayStyle } from '../types'

export type OverlayView = { items: Overlay[]; style: OverlayStyle; parts: Part[] }

// The live preview of words on screen: the same drawOverlays the export
// uses, redrawn whenever the playhead moves. Sized to the stage in device
// pixels; the composition scales with it, so it matches the export frame.
export function OverlayCanvas({ view, width, height }: { view: OverlayView; width: number; height: number }) {
  const ref = useRef<HTMLCanvasElement>(null)
  const viewRef = useRef(view)
  useEffect(() => { viewRef.current = view }, [view])

  useEffect(() => {
    const c = ref.current
    if (!c) return
    const dpr = window.devicePixelRatio || 1
    c.width = Math.max(1, Math.round(width * dpr))
    c.height = Math.max(1, Math.round(height * dpr))
    const ctx = c.getContext('2d')!
    let raf = 0
    const draw = () => {
      cancelAnimationFrame(raf)
      raf = requestAnimationFrame(() => {
        const v = viewRef.current
        drawOverlays(ctx, c.width, c.height, v.items, v.style, v.parts, phStore.get())
      })
    }
    draw()
    let live = true
    ensureFonts(view.style).then(() => { if (live) draw() })
    const off = phStore.subscribe(draw)
    return () => { live = false; off(); cancelAnimationFrame(raf) }
  }, [width, height, view])

  return <canvas ref={ref} className="pointer-events-none absolute inset-0 z-[5] size-full" aria-hidden="true" />
}

import { useEffect, useRef, useState } from 'react'
import { drawOverlays, ensureFonts, safe, type OverlayBox, type Part } from '../overlayDraw'
import { phStore } from '../transport'
import type { Overlay, OverlayPlace, OverlayStyle } from '../types'

export type OverlayView = { items: Overlay[]; style: OverlayStyle; parts: Part[] }

// Moving words by hand on the picture: pick one, drag it, drag a corner to
// size it. Each drop is one undoable edit; export draws the same place.
export type OverlayEdit = {
  selected: string | null
  onSelect: (id: string | null) => void
  onPlace: (id: string, place: OverlayPlace | null) => void
  onPlaceAll: (place: OverlayPlace) => void
  onOpen: (id: string) => void
}

const SNAP = 0.02   // pulls onto the centre lines within 2% of the frame
type Drag = { id: string; mode: 'move' | 'scale'; x0: number; y0: number; start: OverlayPlace; d0: number; moved: boolean }
type Guides = { v: boolean; h: boolean } | null

// The live preview of words on screen: the same drawOverlays the export
// uses, redrawn whenever the playhead moves. Sized to the stage in device
// pixels; the composition scales with it, so it matches the export frame.
export function OverlayCanvas({ view, width, height, edit }: { view: OverlayView; width: number; height: number; edit?: OverlayEdit }) {
  const ref = useRef<HTMLCanvasElement>(null)
  const boxes = useRef<OverlayBox[]>([])
  const [drag, setDrag] = useState<Drag | null>(null)
  const [live, setLive] = useState<{ id: string; place: OverlayPlace } | null>(null)
  const [guides, setGuides] = useState<Guides>(null)
  const [selBox, setSelBox] = useState<OverlayBox | null>(null)
  const shown: OverlayView = live
    ? { ...view, items: view.items.map((o) => (o.id === live.id ? { ...o, place: live.place } : o)) }
    : view
  const viewRef = useRef(shown)
  viewRef.current = shown
  const selRef = useRef(edit?.selected ?? null)
  selRef.current = edit?.selected ?? null

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
        const out: OverlayBox[] = []
        drawOverlays(ctx, c.width, c.height, v.items, v.style, v.parts, phStore.get(), out)
        boxes.current = out.map((b) => ({ id: b.id, x: b.x / dpr, y: b.y / dpr, w: b.w / dpr, h: b.h / dpr }))
        const s = boxes.current.find((b) => b.id === selRef.current) ?? null
        setSelBox((old) => (old && s && Math.abs(old.x - s.x) + Math.abs(old.y - s.y) + Math.abs(old.w - s.w) + Math.abs(old.h - s.h) < 0.5
          && old.id === s.id ? old : s))
      })
    }
    draw()
    let alive = true
    ensureFonts(shown.style).then(() => { if (alive) draw() })
    const off = phStore.subscribe(draw)
    return () => { alive = false; off(); cancelAnimationFrame(raf) }
  }, [width, height, shown, edit?.selected]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { setLive(null) }, [view])

  const placeOf = (id: string): OverlayPlace => {
    const o = view.items.find((x) => x.id === id)
    if (o?.place) return o.place
    const b = boxes.current.find((x) => x.id === id)
    return b ? { x: (b.x + b.w / 2) / width, y: (b.y + b.h / 2) / height, scale: 1 } : { x: 0.5, y: 0.5, scale: 1 }
  }
  const local = (e: React.PointerEvent) => {
    const r = (e.currentTarget as HTMLElement).getBoundingClientRect()
    return { x: e.clientX - r.left, y: e.clientY - r.top }
  }
  const hit = (x: number, y: number) =>
    [...boxes.current].reverse().find((b) => x >= b.x - 6 && x <= b.x + b.w + 6 && y >= b.y - 6 && y <= b.y + b.h + 6) ?? null
  const onCorner = (x: number, y: number) => !!selBox &&
    // the handles are drawn 4 px outside the box
    [[selBox.x - 4, selBox.y - 4], [selBox.x + selBox.w + 4, selBox.y - 4], [selBox.x - 4, selBox.y + selBox.h + 4],
      [selBox.x + selBox.w + 4, selBox.y + selBox.h + 4]]
      .some(([cx, cy]) => Math.abs(x - cx) <= 10 && Math.abs(y - cy) <= 10)

  if (!edit) return <canvas ref={ref} className="pointer-events-none absolute inset-0 z-[5] size-full" aria-hidden="true" />

  const down = (e: React.PointerEvent) => {
    const p = local(e)
    const scaling = onCorner(p.x, p.y)
    const b = scaling ? selBox : hit(p.x, p.y)
    if (!b) { if (edit.selected) { edit.onSelect(null); e.stopPropagation() } return }
    e.stopPropagation()
    edit.onSelect(b.id)
    const start = placeOf(b.id)
    const cx = start.x * width, cy = start.y * height
    ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
    setDrag({ id: b.id, mode: scaling ? 'scale' : 'move', x0: p.x, y0: p.y, start, d0: Math.max(8, Math.hypot(p.x - cx, p.y - cy)), moved: false })
  }
  const move = (e: React.PointerEvent) => {
    if (!drag) {
      const p = local(e)
      ;(e.currentTarget as HTMLElement).style.cursor = onCorner(p.x, p.y) ? 'nwse-resize' : hit(p.x, p.y) ? 'move' : 'default'
      return
    }
    const p = local(e)
    let place: OverlayPlace
    if (drag.mode === 'move') {
      let x = drag.start.x + (p.x - drag.x0) / width
      let y = drag.start.y + (p.y - drag.y0) / height
      const v = Math.abs(x - 0.5) < SNAP, h = Math.abs(y - 0.5) < SNAP
      if (v) x = 0.5
      if (h) y = 0.5
      x = Math.min(1, Math.max(0, x)); y = Math.min(1, Math.max(0, y))
      setGuides({ v, h })
      place = { ...drag.start, x, y }
    } else {
      const cx = drag.start.x * width, cy = drag.start.y * height
      const k = Math.hypot(p.x - cx, p.y - cy) / drag.d0
      place = { ...drag.start, scale: Math.min(3, Math.max(0.4, drag.start.scale * k)) }
      setGuides(null)
    }
    if (!drag.moved && Math.hypot(p.x - drag.x0, p.y - drag.y0) > 3) setDrag({ ...drag, moved: true })
    setLive({ id: drag.id, place })
  }
  const up = () => {
    if (drag?.moved && live) edit.onPlace(drag.id, live.place)
    setDrag(null)
    setGuides(null)
    // keep showing the dropped place until the edit comes back
    if (!drag?.moved) setLive(null)
  }
  const m = safe(width, height)
  const sel = edit.selected ? view.items.find((o) => o.id === edit.selected) : null
  return (
    <>
      <canvas ref={ref} className="pointer-events-none absolute inset-0 z-[5] size-full" aria-hidden="true" />
      <div className="absolute inset-0 z-[6]" onPointerDown={down} onPointerMove={move} onPointerUp={up} onPointerCancel={up}
           onDoubleClick={(e) => { const p = local(e as unknown as React.PointerEvent); const b = hit(p.x, p.y); if (b) { e.stopPropagation(); edit.onOpen(b.id) } }}
           onClick={(e) => { if (drag || selBox) e.stopPropagation() }}>
        {drag && (
          <div className="pointer-events-none absolute border border-dashed border-white/25"
               style={{ left: m.l, top: m.t, right: m.r, bottom: m.b }} />
        )}
        {guides?.v && <div className="pointer-events-none absolute inset-y-0 left-1/2 w-px bg-accent/80" />}
        {guides?.h && <div className="pointer-events-none absolute inset-x-0 top-1/2 h-px bg-accent/80" />}
        {selBox && (
          <div className="pointer-events-none absolute rounded-sm outline outline-1 outline-accent"
               style={{ left: selBox.x - 4, top: selBox.y - 4, width: selBox.w + 8, height: selBox.h + 8 }}>
            {(['-left-1.5 -top-1.5', '-right-1.5 -top-1.5', '-left-1.5 -bottom-1.5', '-right-1.5 -bottom-1.5'] as const).map((c) => (
              <i key={c} className={`absolute block size-2.5 rounded-sm border border-accent bg-zinc-900 ${c}`} />
            ))}
          </div>
        )}
        {selBox && sel && !drag && (
          <div className="absolute flex gap-1 text-[10px]"
               style={{ left: Math.min(Math.max(4, selBox.x), width - 230), top: selBox.y > 34 ? selBox.y - 30 : selBox.y + selBox.h + 8 }}
               onPointerDown={(e) => e.stopPropagation()}>
            {sel.kind === 'caption' && (
              <button type="button" onClick={(e) => { e.stopPropagation(); edit.onPlaceAll(placeOf(sel.id)) }}
                      className="rounded bg-zinc-900/90 px-2 py-1 text-zinc-100 ring-1 ring-line hover:bg-zinc-800">Same place for all captions</button>
            )}
            {sel.place && (
              <button type="button" onClick={(e) => { e.stopPropagation(); edit.onPlace(sel.id, null) }}
                      className="rounded bg-zinc-900/90 px-2 py-1 text-zinc-300 ring-1 ring-line hover:bg-zinc-800">Reset</button>
            )}
          </div>
        )}
      </div>
    </>
  )
}

import { useEffect, useRef, useState } from 'react'
import { drawOverlays, ensureFonts, type OverlayBox, type Part } from '../overlayDraw'
import { phStore } from '../transport'
import { multiline, typable, wordsOf, wordsPatch } from '../captionWords'
import type { Overlay, OverlayPlace, OverlayStyle } from '../types'

export type OverlayView = { items: Overlay[]; style: OverlayStyle; parts: Part[] }

// Moving words by hand on the picture: pick one, drag it, drag a corner to
// size it. Each drop is one undoable edit; export draws the same place.
// Clicking a picked caption again types into it right there (sarah,
// 2026-10-18: edit the words on screen, not in the side panel).
export type OverlayEdit = {
  selected: string | null
  onSelect: (id: string | null) => void
  onPlace: (id: string, place: OverlayPlace | null) => void
  onPlaceAll: (place: OverlayPlace) => void
  onOpen: (id: string) => void
  onWords: (id: string, patch: { text?: string; sub?: string }) => void
}

const SNAP = 0.02   // pulls onto the centre lines within 2% of the frame
type Drag = { id: string; mode: 'move' | 'scale'; x0: number; y0: number; start: OverlayPlace; d0: number; moved: boolean; again: boolean }
// the box being typed into: where the caption was drawn when typing began
type Typing = { id: string; box: OverlayBox; value: string; size: number }
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
  const [typing, setTyping] = useState<Typing | null>(null)
  // read by the box's blur, which can come after Enter already saved it
  const typingRef = useRef<Typing | null>(null)
  typingRef.current = typing
  const placed: OverlayView = live
    ? { ...view, items: view.items.map((o) => (o.id === live.id ? { ...o, place: live.place } : o)) }
    : view
  // the words being typed stand in for the drawn ones until they're saved
  const shown: OverlayView = typing ? { ...placed, items: placed.items.filter((o) => o.id !== typing.id) } : placed
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

  // A fresh edit from the server (the music being picked polls the session
  // every 1.5 s) must not snap a caption back from under the pointer, nor
  // lose the drop: only a finished drag lets the server's place take over.
  const dragging = useRef(false)
  const lastPlace = useRef<OverlayPlace | null>(null)
  useEffect(() => { if (!dragging.current) setLive(null) }, [view])

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
  // which corner handle (0 tl, 1 tr, 2 bl, 3 br) is under the pointer, or -1;
  // the handles are drawn 4 px outside the box
  const cornerAt = (x: number, y: number) => !selBox ? -1
    : [[selBox.x - 4, selBox.y - 4], [selBox.x + selBox.w + 4, selBox.y - 4], [selBox.x - 4, selBox.y + selBox.h + 4],
      [selBox.x + selBox.w + 4, selBox.y + selBox.h + 4]]
      .findIndex(([cx, cy]) => Math.abs(x - cx) <= 10 && Math.abs(y - cy) <= 10)
  const onCorner = (x: number, y: number) => cornerAt(x, y) >= 0

  // a different caption picked (or none) ends typing without saving
  useEffect(() => { if (typing && edit?.selected !== typing.id) setTyping(null) }, [edit?.selected]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!edit) return <canvas ref={ref} className="pointer-events-none absolute inset-0 z-[5] size-full" aria-hidden="true" />

  const startTyping = (id: string) => {
    const o = view.items.find((x) => x.id === id)
    const b = boxes.current.find((x) => x.id === id)
    if (!o || !b || !typable(o)) return
    const value = wordsOf(o)
    // letters about as big as the drawn ones, read off the drawn box's height
    const size = Math.round(Math.min(44, Math.max(15, (b.h / value.split('\n').length) * 0.62)))
    setTyping({ id, box: b, value, size })
  }
  const stopTyping = (save: boolean) => {
    const t = typingRef.current
    if (!t) return
    typingRef.current = null
    const o = view.items.find((x) => x.id === t.id)
    const patch = save && o ? wordsPatch(o, t.value) : null
    setTyping(null)
    if (patch) edit.onWords(t.id, patch)
  }

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
    dragging.current = true
    lastPlace.current = null
    setDrag({ id: b.id, mode: scaling ? 'scale' : 'move', x0: p.x, y0: p.y, start, d0: Math.max(8, Math.hypot(p.x - cx, p.y - cy)), moved: false,
      again: !scaling && edit.selected === b.id && typing?.id !== b.id })
  }
  const move = (e: React.PointerEvent) => {
    if (!drag) {
      const p = local(e)
      const k = cornerAt(p.x, p.y)
      ;(e.currentTarget as HTMLElement).style.cursor = k === 0 || k === 3 ? 'nwse-resize' : k > 0 ? 'nesw-resize'
        : hit(p.x, p.y) ? 'move' : 'default'
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
    lastPlace.current = place
    setLive({ id: drag.id, place })
  }
  const up = () => {
    dragging.current = false
    if (drag?.moved && lastPlace.current) edit.onPlace(drag.id, lastPlace.current)
    setDrag(null)
    setGuides(null)
    // keep showing the dropped place until the edit comes back
    if (!drag?.moved) setLive(null)
    // a click (no drag) on the caption already picked: type into it
    if (drag && !drag.moved && drag.again) startTyping(drag.id)
  }
  const sel = edit.selected ? view.items.find((o) => o.id === edit.selected) : null
  return (
    <>
      <canvas ref={ref} className="pointer-events-none absolute inset-0 z-[5] size-full" aria-hidden="true" />
      <div className="absolute inset-0 z-[6]" onPointerDown={down} onPointerMove={move} onPointerUp={up} onPointerCancel={up}
           onDoubleClick={(e) => { const p = local(e as unknown as React.PointerEvent); const b = hit(p.x, p.y); if (b) { e.stopPropagation(); edit.onOpen(b.id); startTyping(b.id) } }}
           onClick={(e) => { if (drag || selBox) e.stopPropagation() }}>
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
        {typing && <TypeBox typing={typing} lines={!!sel && multiline(sel)} width={width}
                            onChange={(value) => setTyping({ ...typing, value })} onDone={stopTyping} />}
        {selBox && sel && !drag && !typing && (
          <div className="absolute flex flex-wrap gap-1 whitespace-nowrap text-[10px]"
               // on a narrow (vertical) frame the buttons wrap rather than run off it
               style={{ left: Math.max(4, Math.min(selBox.x, width - 290)), maxWidth: width - 8,
                 ...(selBox.y > 64 ? { bottom: height - selBox.y + 8 } : { top: selBox.y + selBox.h + 8 }) }}
               onPointerDown={(e) => e.stopPropagation()}>
            {typable(sel) && (
              <button type="button" onClick={(e) => { e.stopPropagation(); startTyping(sel.id) }}
                      className="rounded bg-zinc-900/90 px-2 py-1 text-zinc-100 ring-1 ring-line hover:bg-zinc-800">Edit words</button>
            )}
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

// Typing on the picture: a box where the caption was, its lines as they read
// there. Enter starts a new line where there can be one; clicking away or
// Cmd/Ctrl+Enter saves (one undoable edit), Escape leaves the words as they were.
function TypeBox({ typing, lines, width, onChange, onDone }: {
  typing: Typing; lines: boolean; width: number; onChange: (v: string) => void; onDone: (save: boolean) => void
}) {
  const ref = useRef<HTMLTextAreaElement>(null)
  useEffect(() => { const t = ref.current; if (t) { t.focus(); t.select() } }, [])
  const { box, size } = typing
  const n = Math.max(1, typing.value.split('\n').length)
  const w = Math.min(width - 8, Math.max(box.w + 40, 220))
  const left = Math.min(width - 4 - w, Math.max(4, box.x + box.w / 2 - w / 2))
  return (
    <textarea ref={ref} value={typing.value} maxLength={200} aria-label="Caption words" rows={n} spellCheck={false}
              onChange={(e) => onChange(e.target.value)}
              onBlur={() => onDone(true)}
              onPointerDown={(e) => e.stopPropagation()} onClick={(e) => e.stopPropagation()} onDoubleClick={(e) => e.stopPropagation()}
              onKeyDown={(e) => {
                e.stopPropagation()   // typing must not split shots or play the video
                if (e.key === 'Enter' && (!lines || e.metaKey || e.ctrlKey)) { e.preventDefault(); onDone(true) }
                if (e.key === 'Escape') { e.preventDefault(); onDone(false) }
              }}
              className="absolute resize-none overflow-hidden rounded-md bg-black/45 px-2 py-1 text-center font-semibold leading-tight text-white caret-white outline outline-2 outline-accent [text-shadow:0_1px_3px_rgba(0,0,0,.8)]"
              style={{ left, top: box.y + box.h / 2 - (n * size * 1.25 + 8) / 2, width: w, fontSize: size }} />
  )
}


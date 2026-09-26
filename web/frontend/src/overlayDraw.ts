// Words on screen, drawn. One function draws a frame of overlays at time t
// onto any canvas: the live preview over the player and the export renderer
// both call it, so what the creator watches is what gets exported.
//
// Everything is sized from the frame's short side and placed inside a safe
// area, so a preview canvas 400 px wide and a 1080×1920 export frame draw the
// same composition. Nothing here reads the clock or animates with CSS: the
// state at t is computed, never accumulated, which is what lets the export
// render any frame in any order.

import type { Overlay, OverlayKind, OverlayStyle } from './types'

export type Part = { id: string; title: string; start: number; end: number }

export const KIND_META: Record<OverlayKind, { label: string; icon: string; color: string; hint: string }> = {
  title: { label: 'Title', icon: 'T', color: '#b9d9eb', hint: 'Big words that open the video' },
  part: { label: 'Part label', icon: '§', color: '#a7c4a0', hint: 'Names a part or a place as it begins' },
  name: { label: 'Name tag', icon: '◧', color: '#e8c39e', hint: 'Who is speaking, with a handle or role' },
  caption: { label: 'Caption', icon: '❝', color: '#d8d8de', hint: 'A spoken line or short remark' },
  date: { label: 'Date', icon: '◷', color: '#c4b5fd', hint: 'When it was filmed' },
  end: { label: 'End card', icon: '■', color: '#f0a8a8', hint: 'The last words, over the last seconds' },
  chapters: { label: 'Chapter bar', icon: '▭', color: '#9fb4c7', hint: 'Shows which part of the video you are in' },
}

// ---- timing ---------------------------------------------------------------

const clamp01 = (x: number) => Math.max(0, Math.min(1, x))
const easeOut = (x: number) => 1 - (1 - x) ** 3

/** Intro and outro lengths. The outro finishes *before* the overlay's end so
 *  it never vanishes on a hard cut -- and a short overlay doesn't spend most
 *  of its life animating. (The fade-before-end idea is Overlay Studio's.) */
export function envelope(o: Pick<Overlay, 'start' | 'shown_end'>): { inS: number; outS: number } {
  const d = Math.max(0, o.shown_end - o.start)
  return { inS: Math.min(0.5, d * 0.3), outS: Math.min(0.3, d * 0.25) }
}

/** How far in (0→1) and how far from gone (1→0) an overlay is at t. */
export function phase(o: Pick<Overlay, 'start' | 'shown_end'>, t: number): { on: boolean; pin: number; pout: number } {
  if (t < o.start || t >= o.shown_end) return { on: false, pin: 0, pout: 0 }
  const { inS, outS } = envelope(o)
  return {
    on: true,
    pin: inS > 0 ? clamp01((t - o.start) / inS) : 1,
    pout: outS > 0 ? clamp01((o.shown_end - t) / outS) : 1,
  }
}

export function partAt(parts: Part[], t: number): number {
  for (let i = parts.length - 1; i >= 0; i--) if (parts[i].start <= t) return i
  return 0
}

/** Identical keys draw identical pixels. The exporter sends one frame per
 *  run of equal keys -- a title holding still is one PNG with a duration. */
export function frameKey(items: Overlay[], parts: Part[], t: number): string {
  const out: string[] = []
  for (const o of items) {
    const p = phase(o, t)
    if (!p.on) continue
    out.push(`${o.id}:${Math.round(p.pin * 1000)}:${Math.round(p.pout * 1000)}${o.kind === 'chapters' ? `:${partAt(parts, t)}` : ''}`)
  }
  return out.join('|')
}

/** Which frames of the edit have anything on screen (frame numbers). */
export function busyFrames(items: Overlay[], fps: number, total: number): number[] {
  const set = new Set<number>()
  const last = Math.round(total * fps)
  for (const o of items) {
    const a = Math.max(0, Math.floor(o.start * fps))
    const z = Math.min(last, Math.ceil(o.shown_end * fps))
    for (let f = a; f < z; f++) set.add(f)
  }
  return [...set].sort((x, y) => x - y)
}

// ---- type -----------------------------------------------------------------

const FAMILY: Record<OverlayStyle['font'], string> = {
  Clean: 'system-ui, -apple-system, "Helvetica Neue", "PingFang SC", "Hiragino Sans", sans-serif',
  Editorial: '"EB Garamond", "Songti SC", "Hiragino Mincho ProN", serif',
  Rounded: '"Nunito", "PingFang SC", "Hiragino Maru Gothic ProN", sans-serif',
}
const WEIGHT: Record<OverlayStyle['font'], { bold: number; regular: number }> = {
  Clean: { bold: 700, regular: 500 }, Editorial: { bold: 600, regular: 500 }, Rounded: { bold: 800, regular: 600 },
}
export const fontCss = (style: OverlayStyle, px: number, bold: boolean) =>
  `${bold ? WEIGHT[style.font].bold : WEIGHT[style.font].regular} ${Math.round(px)}px ${FAMILY[style.font]}`

/** Web fonts must be loaded before a canvas can draw them. */
export async function ensureFonts(style: OverlayStyle): Promise<void> {
  if (typeof document === 'undefined' || !document.fonts) return
  await Promise.all([fontCss(style, 40, true), fontCss(style, 40, false)].map((f) => document.fonts.load(f).catch(() => [])))
}

const SIZE = { S: 0.78, M: 1, L: 1.4 }

// ---- layout ---------------------------------------------------------------

type Line = { text: string; px: number; bold: boolean; color: string; track?: number; upper?: boolean }

function safe(W: number, H: number) {
  const portrait = H > W
  // Vertical video is watched in apps whose buttons sit bottom and right.
  return { l: W * 0.07, r: W * (portrait ? 0.14 : 0.07), t: H * (portrait ? 0.09 : 0.08), b: H * (portrait ? 0.2 : 0.09) }
}


export function wrap(measure: (s: string) => number, text: string, maxW: number, maxLines = 3): string[] {
  const tokens = text.match(/[぀-ヿ㐀-鿿가-힯][，。！？、,.!?」』]?|[^\s぀-ヿ㐀-鿿가-힯]+|\s+/g) ?? []
  const lines: string[] = []
  let cur = ''
  for (const tok of tokens) {
    const next = cur + tok
    if (cur.trim() && measure(next.trimEnd()) > maxW) {
      lines.push(cur.trimEnd())
      cur = tok.trimStart()
    } else cur = next
  }
  if (cur.trim()) lines.push(cur.trim())
  if (lines.length > maxLines) {
    const kept = lines.slice(0, maxLines)
    kept[maxLines - 1] = kept[maxLines - 1].replace(/\s*\S?$/, '') + '…'
    return kept
  }
  return lines
}

function linesFor(o: Overlay, style: OverlayStyle, u: number, chars: number): Line[] {
  const s = SIZE[o.size]
  const text = chars < o.text.length ? o.text.slice(0, chars) : o.text
  const ink = style.color
  switch (o.kind) {
    case 'title':
      return [{ text, px: 0.09 * u * s, bold: true, color: ink },
        ...(o.sub ? [{ text: o.sub, px: 0.034 * u * s, bold: false, color: ink }] : [])]
    case 'end':
      return [{ text, px: 0.07 * u * s, bold: true, color: ink },
        ...(o.sub ? [{ text: o.sub, px: 0.032 * u * s, bold: false, color: style.accent }] : [])]
    case 'part':
      return [...(o.sub ? [{ text: o.sub, px: 0.024 * u * s, bold: true, color: style.accent, track: 0.18, upper: true }] : []),
        { text, px: 0.058 * u * s, bold: true, color: ink }]
    case 'name':
      return [{ text, px: 0.05 * u * s, bold: true, color: ink },
        ...(o.sub ? [{ text: o.sub, px: 0.03 * u * s, bold: false, color: style.accent }] : [])]
    case 'caption':
      return [{ text, px: 0.046 * u * s, bold: false, color: ink }]
    case 'date':
      return [{ text, px: 0.03 * u * s, bold: true, color: ink, track: 0.12, upper: true }]
    default:
      return []
  }
}

type Anchor = { x: number; align: CanvasTextAlign; v: 'top' | 'middle' | 'bottom'; y: number }

function anchorFor(pos: Overlay['pos'], W: number, H: number): Anchor {
  const m = safe(W, H)
  const [row, col] = pos === 'center' ? ['middle', 'center'] : pos.includes('-')
    ? pos.split('-') as [string, string]
    : pos === 'top' || pos === 'bottom' ? [pos, 'center'] : ['middle', pos]
  const x = col === 'left' ? m.l : col === 'right' ? W - m.r : W / 2
  const align: CanvasTextAlign = col === 'left' ? 'left' : col === 'right' ? 'right' : 'center'
  const v = row === 'top' ? 'top' : row === 'bottom' ? 'bottom' : 'middle'
  const y = v === 'top' ? m.t : v === 'bottom' ? H - m.b : H / 2
  return { x, align, v, y }
}

// ---- draw -----------------------------------------------------------------

export function drawOverlays(ctx: CanvasRenderingContext2D | OffscreenCanvasRenderingContext2D, W: number, H: number,
  items: Overlay[], style: OverlayStyle, parts: Part[], t: number): void {
  ctx.clearRect(0, 0, W, H)
  const u = Math.min(W, H)
  for (const o of items) {
    const p = phase(o, t)
    if (!p.on) continue
    if (o.kind === 'chapters') { drawChapters(ctx, W, H, u, style, parts, t, easeOut(p.pin) * p.pout); continue }
    const e = easeOut(p.pin)
    const typing = o.anim === 'type'
    const chars = typing ? Math.ceil(o.text.length * clamp01(p.pin * 1.6)) : o.text.length
    const alpha = (typing ? Math.min(1, p.pin * 4) : e) * p.pout
    if (alpha <= 0.001) continue
    const pos = o.kind === 'caption' ? (style.captions === 'center' ? 'center' : 'bottom') : o.pos
    const a = anchorFor(pos, W, H)
    const dx = o.anim === 'slide' ? (1 - e) * 0.05 * u * (a.align === 'right' ? 1 : -1) : 0
    const dy = o.anim === 'rise' ? (1 - e) * 0.035 * u : 0
    drawBlock(ctx, W, H, u, linesFor(o, style, u, chars), o, style, a, dx, dy, alpha)
  }
}

function drawBlock(ctx: CanvasRenderingContext2D | OffscreenCanvasRenderingContext2D, W: number, H: number, u: number,
  lines: Line[], o: Overlay, style: OverlayStyle, a: Anchor, dx: number, dy: number, alpha: number) {
  const m = safe(W, H)
  const maxW = (a.align === 'center' ? W - m.l - m.r : (W - m.l - m.r) * 0.72)
  // measure and wrap
  type Row = { text: string; line: Line; w: number; h: number }
  const rows: Row[] = []
  for (const ln of lines) {
    ctx.font = fontCss(style, ln.px, ln.bold)
    setTracking(ctx, ln.track ? ln.track * ln.px : 0)
    const text = ln.upper ? ln.text.toUpperCase() : ln.text
    const max = o.kind === 'caption' ? 3 : o.kind === 'title' || o.kind === 'end' ? 3 : 2
    for (const r of wrap((s) => ctx.measureText(s).width, text, maxW, max)) {
      rows.push({ text: r, line: ln, w: ctx.measureText(r).width, h: ln.px * 1.18 })
    }
  }
  if (!rows.length) return
  const gap = 0.012 * u
  const blockH = rows.reduce((n, r) => n + r.h, 0) + gap * (new Set(rows.map((r) => r.line)).size - 1)
  const blockW = Math.max(...rows.map((r) => r.w))
  let y = (a.v === 'top' ? a.y : a.v === 'bottom' ? a.y - blockH : a.y - blockH / 2) + dy
  const x = a.x + dx

  ctx.save()
  ctx.globalAlpha = alpha
  if (style.backing === 'box' || o.kind === 'name') {
    const pad = 0.022 * u
    const left = a.align === 'left' ? x - pad : a.align === 'right' ? x - blockW - pad : x - blockW / 2 - pad
    ctx.fillStyle = style.backing === 'none' ? 'rgba(0,0,0,0)' : 'rgba(10,10,12,0.55)'
    roundRect(ctx, left, y - pad * 0.7, blockW + 2 * pad, blockH + pad * 1.4, pad * 0.6)
    ctx.fill()
    if (o.kind === 'name' || o.kind === 'part') {
      ctx.fillStyle = style.accent
      const bx = a.align === 'right' ? left + blockW + 2 * pad - 0.006 * u : left
      ctx.fillRect(bx, y - pad * 0.7, 0.006 * u, blockH + pad * 1.4)
    }
  } else if (o.kind === 'part') {
    // a short rule in the accent colour anchors the label without a box
    ctx.fillStyle = style.accent
    const w = 0.05 * u
    const lx = a.align === 'left' ? x : a.align === 'right' ? x - w : x - w / 2
    ctx.fillRect(lx, y + blockH + 0.014 * u, w, Math.max(2, 0.004 * u))
  }
  if (style.backing === 'shadow') {
    ctx.shadowColor = 'rgba(0,0,0,0.6)'
    ctx.shadowBlur = 0.018 * u
    ctx.shadowOffsetY = 0.003 * u
  }
  ctx.textAlign = a.align
  ctx.textBaseline = 'top'
  let prev: Line | null = null
  for (const r of rows) {
    if (prev && prev !== r.line) y += gap
    ctx.font = fontCss(style, r.line.px, r.line.bold)
    setTracking(ctx, r.line.track ? r.line.track * r.line.px : 0)
    ctx.fillStyle = r.line.color
    // letter-spacing adds trailing space; shift so tracked text stays aligned
    const shift = r.line.track && a.align !== 'left' ? (r.line.track * r.line.px) / (a.align === 'center' ? 2 : 1) : 0
    ctx.fillText(r.text, x + shift, y + (r.h - r.line.px) / 2)
    y += r.h
    prev = r.line
  }
  ctx.restore()
  setTracking(ctx, 0)
}

function drawChapters(ctx: CanvasRenderingContext2D | OffscreenCanvasRenderingContext2D, W: number, H: number, u: number,
  style: OverlayStyle, parts: Part[], t: number, alpha: number) {
  if (parts.length < 2 || alpha <= 0.001) return
  const m = safe(W, H)
  const total = parts[parts.length - 1].end - parts[0].start
  const x0 = m.l
  const width = W - m.l - m.r
  const y = m.t * 0.55
  const gap = 0.008 * u
  const h = Math.max(3, 0.007 * u)
  const cur = partAt(parts, t)
  ctx.save()
  ctx.globalAlpha = alpha
  let x = x0
  const room = width - gap * (parts.length - 1)
  parts.forEach((p, i) => {
    const w = room * ((p.end - p.start) / total)
    ctx.fillStyle = i === cur ? style.accent : i < cur ? 'rgba(255,255,255,0.7)' : 'rgba(255,255,255,0.28)'
    roundRect(ctx, x, y, w, h, h / 2)
    ctx.fill()
    if (i === cur) {
      ctx.font = fontCss(style, 0.024 * u, true)
      ctx.fillStyle = style.color
      ctx.textBaseline = 'top'
      ctx.textAlign = 'left'
      ctx.shadowColor = 'rgba(0,0,0,0.6)'
      ctx.shadowBlur = 0.012 * u
      const label = p.title.length > 40 ? p.title.slice(0, 39) + '…' : p.title
      const tw = ctx.measureText(label).width
      ctx.fillText(label, Math.min(Math.max(x, x0), x0 + width - tw), y + h + 0.012 * u)
      ctx.shadowBlur = 0
    }
    x += w + gap
  })
  ctx.restore()
}

function roundRect(ctx: CanvasRenderingContext2D | OffscreenCanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  ctx.beginPath()
  ctx.roundRect(x, y, w, h, r)
}

function setTracking(ctx: CanvasRenderingContext2D | OffscreenCanvasRenderingContext2D, px: number) {
  if ('letterSpacing' in ctx) (ctx as { letterSpacing: string }).letterSpacing = `${px}px`
}

// ---- export ---------------------------------------------------------------

export type ScheduleEntry = { frame: number | null; start: number; end: number }

/** Render every distinct overlay frame of the edit, hand each PNG to
 *  `upload`, and return when each frame is on screen. Equal keys -> one
 *  frame; frames nothing is on are left out (transparent). */
export async function renderSchedule(opts: {
  items: Overlay[]; style: OverlayStyle; parts: Part[]; fps: number; total: number; w: number; h: number
  upload: (n: number, png: Blob) => Promise<void>
  onProgress?: (done: number, of: number) => void
  cancelled?: () => boolean
}): Promise<ScheduleEntry[]> {
  const { items, style, parts, fps, total, w, h } = opts
  await ensureFonts(style)
  const frames = busyFrames(items, fps, total)
  const canvas = new OffscreenCanvas(w, h)
  const ctx = canvas.getContext('2d')!
  const schedule: ScheduleEntry[] = []
  const seen = new Map<string, number>()
  const pending = new Set<Promise<void>>()
  let n = 0
  let prevF = -2
  let prevKey = ''
  for (let i = 0; i < frames.length; i++) {
    if (opts.cancelled?.()) throw new Error('cancelled')
    const f = frames[i]
    const t = f / fps
    const key = frameKey(items, parts, t)
    if (!key) { prevF = f; prevKey = ''; continue }
    if (key === prevKey && f === prevF + 1) {
      schedule[schedule.length - 1].end = (f + 1) / fps
    } else {
      let id = seen.get(key)
      if (id == null) {
        id = n++
        seen.set(key, id)
        drawOverlays(ctx, w, h, items, style, parts, t)
        const blob = await canvas.convertToBlob({ type: 'image/png' })
        const p: Promise<void> = opts.upload(id, blob).finally(() => pending.delete(p))
        pending.add(p)
        if (pending.size >= 4) await Promise.race(pending)
      }
      schedule.push({ frame: id, start: f / fps, end: (f + 1) / fps })
    }
    prevF = f
    prevKey = key
    if (i % 10 === 0) opts.onProgress?.(i, frames.length)
  }
  await Promise.all(pending)
  opts.onProgress?.(frames.length, frames.length)
  return schedule
}

/** The parts of the edit in sequence time, from the timeline's items. */
export function partsOf(items: { beat_id: string; beat_title: string; seq_start: number; seq_end: number }[]): Part[] {
  const out: Part[] = []
  for (const it of items) {
    const last = out[out.length - 1]
    if (last && last.id === it.beat_id) last.end = it.seq_end
    else out.push({ id: it.beat_id, title: it.beat_title, start: it.seq_start, end: it.seq_end })
  }
  return out
}

// Words on screen, drawn. One function draws a frame of overlays at time t
// onto any canvas: the live preview over the player and the export renderer
// both call it, so what the creator watches is what gets exported.
//
// Everything is sized from the frame's short side and placed inside a safe
// area, so a preview canvas 400 px wide and a 1080×1920 export frame draw the
// same composition. Nothing here reads the clock or animates with CSS: the
// state at t is computed, never accumulated, which is what lets the export
// render any frame in any order.

import type { Motion, Overlay, OverlayKind, OverlayStyle } from './types'

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

/** CSS cubic-bezier(x1, y1, x2, y2) as a function of progress 0..1. y may
 *  overshoot past 1 (a back-out curve), which is how Playful bounces. */
export function bezier([x1, y1, x2, y2]: [number, number, number, number]): (x: number) => number {
  const at = (a: number, b: number, t: number) => 3 * a * t * (1 - t) ** 2 + 3 * b * t * t * (1 - t) + t ** 3
  return (x: number) => {
    if (x <= 0) return 0
    if (x >= 1) return 1
    let lo = 0, hi = 1, t = x
    for (let i = 0; i < 40; i++) {   // x(t) is monotone for 0<=x1,x2<=1: bisect
      t = (lo + hi) / 2
      if (at(x1, x2, t) < x) lo = t
      else hi = t
    }
    return at(y1, y2, t)
  }
}

/** Intro and outro lengths. The outro finishes *before* the overlay's end so
 *  it never vanishes on a hard cut -- and a short overlay doesn't spend most
 *  of its life animating. (The fade-before-end idea is Overlay Studio's.)
 *  A look sets the intro; exits mirror it at 0.6× (spec §4.4). */
export function envelope(o: Pick<Overlay, 'start' | 'shown_end'>, motion?: Motion | null): { inS: number; outS: number } {
  const d = Math.max(0, o.shown_end - o.start)
  if (!motion) return { inS: Math.min(0.5, d * 0.3), outS: Math.min(0.3, d * 0.25) }
  const inS = Math.min(motion.in_s, d * 0.35)
  return { inS, outS: Math.min(inS * 0.6, d * 0.25) }
}

/** How far in (0→1) and how far from gone (1→0) an overlay is at t. A look
 *  that steps (Cozy's 12 fps paper card, Film's 8 fps) holds each step. */
export function phase(o: Pick<Overlay, 'start' | 'shown_end'>, t: number, motion?: Motion | null): { on: boolean; pin: number; pout: number } {
  if (t < o.start || t >= o.shown_end) return { on: false, pin: 0, pout: 0 }
  const { inS, outS } = envelope(o, motion)
  let el = t - o.start
  if (motion && motion.step_fps > 0 && el < inS) el = Math.floor(el * motion.step_fps + 1e-6) / motion.step_fps
  return {
    on: true,
    pin: inS > 0 ? clamp01(el / inS) : 1,
    pout: outS > 0 ? clamp01((o.shown_end - t) / outS) : 1,
  }
}

/** How one line group of a block looks at intro progress `pin` (0..1): the
 *  look's curve, its stagger between groups, and its entrance. */
export type Pose = { dx: number; dy: number; alpha: number; scale: number; rot: number }
export function pose(o: Pick<Overlay, 'anim' | 'kind' | 'start' | 'shown_end'>, pin: number, pout: number, group: number,
  u: number, align: CanvasTextAlign, motion?: Motion | null): Pose {
  const ease = motion ? bezier(motion.curve) : easeOut
  const { inS } = envelope(o, motion)
  const lag = motion && inS > 0 ? (group * motion.stagger_s) / inS : 0
  const p = clamp01((pin - lag) / Math.max(1e-6, 1 - Math.min(lag, 0.9)))
  const e = ease(p)
  const big = o.kind === 'title' || o.kind === 'end' || o.kind === 'part'
  const typing = o.anim === 'type'
  let alpha = (typing ? Math.min(1, p * 4) : clamp01(e)) * pout
  let dx = 0, dy = 0, scale = 1, rot = 0
  if (big && motion?.enter === 'slam') {            // Hype: in from 1.5×, fast
    scale = 1.5 - 0.5 * e
    alpha = Math.min(1, p * 3) * pout
  } else if (big && motion?.enter === 'card') {     // Cozy: the measured paper-card path
    dy = (1 - e) * 0.024 * u
    rot = ((5 - 7 * e) * Math.PI) / 180
    scale = 0.88 + 0.12 * e
  } else {
    dx = o.anim === 'slide' ? (1 - e) * 0.05 * u * (align === 'right' ? 1 : -1) : 0
    dy = o.anim === 'rise' ? (1 - e) * 0.035 * u : 0
  }
  return { dx, dy, alpha, scale, rot }
}

export function partAt(parts: Part[], t: number): number {
  for (let i = parts.length - 1; i >= 0; i--) if (parts[i].start <= t) return i
  return 0
}

/** Identical keys draw identical pixels. The exporter sends one frame per
 *  run of equal keys -- a title holding still is one PNG with a duration. */
export function frameKey(items: Overlay[], parts: Part[], t: number, motion?: Motion | null): string {
  const out: string[] = []
  for (const o of items) {
    const p = phase(o, t, motion)
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
  // Film's typewriter and Hype's condensed caps, from fonts every Mac has
  Mono: '"Courier Prime", "Courier New", ui-monospace, Menlo, "PingFang SC", monospace',
  Condensed: '"Anton", Impact, "Arial Narrow", "Helvetica Neue", "PingFang SC", sans-serif',
}
const WEIGHT: Record<OverlayStyle['font'], { bold: number; regular: number }> = {
  Clean: { bold: 700, regular: 500 }, Editorial: { bold: 600, regular: 500 }, Rounded: { bold: 800, regular: 600 },
  Mono: { bold: 700, regular: 400 }, Condensed: { bold: 400, regular: 400 },
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

export function safe(W: number, H: number) {
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
  const lines = baseLines(o, style, u, chars)
  const m = style.motion
  if (!m || o.kind === 'date') return lines
  // the look's case and tracking, on every line (a date keeps its own)
  return lines.map((ln) => ({
    ...ln,
    text: m.case === 'lower' ? ln.text.toLowerCase() : ln.text,
    upper: ln.upper || m.case === 'upper',
    track: (ln.track ?? 0) + (o.kind === 'caption' ? 0 : m.track),
  }))
}

function baseLines(o: Overlay, style: OverlayStyle, u: number, chars: number): Line[] {
  const s = SIZE[o.size]
  const text = chars < o.text.length ? o.text.slice(0, chars) : o.text
  const ink = o.ink ?? style.color
  style = o.ink2 ? { ...style, accent: o.ink2 } : style
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
      // a describing caption names the place where a new one starts, small, above the line
      return [...(o.sub ? [{ text: o.sub, px: 0.026 * u * s, bold: true, color: style.accent, track: 0.12, upper: true }] : []),
        { text, px: 0.046 * u * s, bold: false, color: ink }]
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
  const motion = style.motion ?? null
  for (const o of items) {
    const p = phase(o, t, motion)
    if (!p.on) continue
    if (o.kind === 'chapters') { drawChapters(ctx, W, H, u, style, parts, t, easeOut(p.pin) * p.pout); continue }
    const typing = o.anim === 'type'
    const chars = typing ? Math.ceil(o.text.length * clamp01(p.pin * 1.6)) : o.text.length
    const pos = o.kind === 'caption' ? (style.captions === 'center' ? 'center' : 'bottom') : o.pos
    const a = anchorFor(pos, W, H)
    const at = (g: number) => pose(o, p.pin, p.pout, g, u, a.align, motion)
    if (at(0).alpha <= 0.001 && at(1).alpha <= 0.001) continue
    drawBlock(ctx, W, H, u, linesFor(o, style, u, chars), o, style, a, at)
  }
}

function drawBlock(ctx: CanvasRenderingContext2D | OffscreenCanvasRenderingContext2D, W: number, H: number, u: number,
  lines: Line[], o: Overlay, style: OverlayStyle, a: Anchor, at: (group: number) => Pose) {
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
  const p0 = at(0)
  let y = (a.v === 'top' ? a.y : a.v === 'bottom' ? a.y - blockH : a.y - blockH / 2) + p0.dy
  const x = a.x + p0.dx
  // A scaled entrance (Hype's slam) may never push words out of the safe
  // area: the block's own room caps how big it can start.
  const roomW = W - m.l - m.r, roomH = H - m.t - m.b
  const fit = Math.max(1, Math.min(roomW / Math.max(1, blockW), roomH / Math.max(1, blockH)))
  const cx = a.align === 'left' ? x + blockW / 2 : a.align === 'right' ? x - blockW / 2 : x
  const cy = y + blockH / 2
  // Scale about the block's centre, then pull it back inside the safe area
  // if the grown block would cross it on either side.
  const place = (pz: Pose) => {
    // the box a rotated block actually covers (Cozy's card tilts); a block
    // that fills the width shrinks a hair rather than tilt past the edge
    const c = Math.abs(Math.cos(pz.rot)), sn = Math.abs(Math.sin(pz.rot))
    const tilted = Math.min(roomW / (blockW * c + blockH * sn), roomH / (blockW * sn + blockH * c))
    const sc = Math.min(pz.scale, fit, pz.rot ? tilted : Infinity)
    const hw = ((blockW * c + blockH * sn) * sc) / 2, hh = ((blockW * sn + blockH * c) * sc) / 2
    const ox = Math.min(0, W - m.r - (cx + hw)) + Math.max(0, m.l - (cx - hw))
    const oy = Math.min(0, H - m.b - (cy + hh)) + Math.max(0, m.t - (cy - hh))
    return { sc, ox, oy }
  }

  ctx.save()
  const pl0 = place(p0)
  ctx.translate(cx + pl0.ox, cy + pl0.oy)
  ctx.rotate(p0.rot)
  ctx.scale(pl0.sc, pl0.sc)
  ctx.translate(-cx, -cy)
  ctx.globalAlpha = p0.alpha
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
  if (o.halo) {
    // nothing in the palette stands out from this frame enough on its own
    ctx.shadowColor = o.halo
    ctx.shadowBlur = 0.022 * u
    ctx.shadowOffsetY = 0.002 * u
  } else if (style.backing === 'shadow') {
    ctx.shadowColor = 'rgba(0,0,0,0.6)'
    ctx.shadowBlur = 0.018 * u
    ctx.shadowOffsetY = 0.003 * u
  }
  ctx.textAlign = a.align
  ctx.textBaseline = 'top'
  let prev: Line | null = null
  let group = 0
  for (const r of rows) {
    if (prev && prev !== r.line) { y += gap; group++ }
    ctx.font = fontCss(style, r.line.px, r.line.bold)
    setTracking(ctx, r.line.track ? r.line.track * r.line.px : 0)
    ctx.fillStyle = r.line.color
    // later lines fade in a stagger behind the first (the look's rhythm);
    // they move with the block, so nothing leaves the safe area mid-entrance
    ctx.globalAlpha = group ? at(group).alpha : p0.alpha
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
    const key = frameKey(items, parts, t, style.motion)
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

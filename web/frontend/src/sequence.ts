// The edit as a sequence of spans, and the arithmetic of time on it.

export type SeqItem = {
  key: string
  kind: 'shot' | 'gap'
  shot_id: string | null
  clip_id: string | null
  src_start: number
  src_end: number
  src_min?: number   // how far the ends can be dragged: the whole shot as filmed
  src_max?: number
  seq_start: number
  seq_end: number
  beat_id: string
  beat_title: string
  n: number | null
}

/** Index of the item under t (binary search). The very end belongs to the
 *  last item, so the playhead parked at the end still has a context. */
export function locate(items: SeqItem[], t: number): number {
  if (!items.length) return -1
  let lo = 0
  let hi = items.length - 1
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1
    if (items[mid].seq_start <= t) lo = mid
    else hi = mid - 1
  }
  return lo
}

/** Source time inside the item under t. */
export function toSource(item: SeqItem, t: number): number {
  return item.src_start + (t - item.seq_start)
}

/** "21.3", "0:21.3", "1:02:03.5", or SMPTE "00:00:21:09" -> seconds.
 *  Four colon-separated fields are hh:mm:ss:ff at the sequence frame rate. */
export function parseTimecode(input: string, fps: number): number | null {
  const s = input.trim()
  if (!s) return null
  const parts = s.split(':')
  if (parts.some((p) => !/^\d+(\.\d+)?$/.test(p))) return null
  const n = parts.map(Number)
  if (parts.length === 4) {
    if (parts.slice(0, 4).some((p) => p.includes('.')) || n[3] >= fps || n[2] >= 60 || n[1] >= 60) return null
    return n[0] * 3600 + n[1] * 60 + n[2] + n[3] / fps
  }
  if (parts.length > 3) return null
  if (parts.slice(0, -1).some((p) => p.includes('.'))) return null
  if (parts.length >= 2 && n[n.length - 1] >= 60) return null
  if (parts.length === 3 && n[1] >= 60) return null
  return n.reduce((acc, v) => acc * 60 + v, 0)
}

/** 0:21.30 -- minutes, seconds, hundredths. */
export function clock(t: number): string {
  const neg = t < 0
  t = Math.abs(t)
  const h = Math.floor(t / 3600)
  const m = Math.floor((t % 3600) / 60)
  const s = (t % 60).toFixed(2).padStart(5, '0')
  return (neg ? '-' : '') + (h ? `${h}:${String(m).padStart(2, '0')}:${s}` : `${m}:${s}`)
}

/** 00:00:21:09 at the sequence frame rate. */
export function smpte(t: number, fps: number): string {
  const f = Math.round(Math.max(0, t) * fps)
  const ff = f % fps
  const secs = Math.floor(f / fps)
  const p = (x: number) => String(x).padStart(2, '0')
  return `${p(Math.floor(secs / 3600))}:${p(Math.floor((secs % 3600) / 60))}:${p(secs % 60)}:${p(ff)}`
}

export type Grid = { bpm: number; phase: number } | null

/** Which beat of the music is at t, if a track with a tempo is under the edit. */
export function beatAt(grid: Grid, t: number): { beat: number; bar: number } | null {
  if (!grid) return null
  const period = 60 / grid.bpm
  const k = Math.floor((t - grid.phase) / period + 1e-6)
  if (k < 0) return null
  return { beat: (k % 4) + 1, bar: Math.floor(k / 4) + 1 }
}

/** "Shot 12 · 2.1s in · 0:21.30 · beat 3 of 4" */
export function readout(items: SeqItem[], grid: Grid, t: number): string {
  const k = locate(items, t)
  if (k < 0) return clock(t)
  const it = items[k]
  const parts = [
    it.kind === 'gap' ? 'Gap' : `Shot ${it.n}`,
    `${(t - it.seq_start).toFixed(1)}s in`,
    clock(t),
  ]
  const b = beatAt(grid, t)
  if (b) parts.push(`beat ${b.beat} of 4`)
  return parts.join(' · ')
}

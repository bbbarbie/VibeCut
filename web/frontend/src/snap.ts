// Magnetic playhead: pull a raw position to a meaningful moment nearby.
//
// Targets come sorted by time from the backend (timeline.py). Lookups are a
// binary search plus a scan of the few targets inside the snap window --
// never a pass over the whole list, because this runs on every pointer move
// and every frame, against thousands of targets.

export type TargetType = 'shot' | 'silence' | 'beat' | 'motion' | 'word'
export type Target = { t: number; type: TargetType; label: string }

// How hard each kind pulls, as a multiple of the base threshold. A cut
// between shots is the edit point people aim for most, so it reaches
// furthest; motion onsets are only as precise as the index (±0.5s), so they
// pull least.
export const WEIGHT: Record<TargetType, number> = { shot: 1.5, silence: 1.0, word: 1.0, beat: 0.9, motion: 0.6 }
const MAX_WEIGHT = 1.5

export type SnapOptions = {
  pxPerSec: number       // current zoom where the playhead is
  thresholdPx?: number   // how close, on screen, counts as "near"
  disabled?: boolean     // Alt held: exactly where the pointer is
}
export type SnapResult = { t: number; target: Target | null }

export const DEFAULT_THRESHOLD_PX = 8

/** First index whose time is >= t. */
export function lowerBound(ts: Target[], t: number): number {
  let lo = 0
  let hi = ts.length
  while (lo < hi) {
    const mid = (lo + hi) >> 1
    if (ts[mid].t < t) lo = mid + 1
    else hi = mid
  }
  return lo
}

/** The threshold is fixed in pixels, so in seconds it shrinks as you zoom
 *  in: strong snapping zoomed out, fine control zoomed in. */
export function thresholdSeconds(opts: SnapOptions): number {
  return (opts.thresholdPx ?? DEFAULT_THRESHOLD_PX) / Math.max(opts.pxPerSec, 1e-6)
}

function best(ts: Target[], raw: number, base: number, scale: number): Target | null {
  const reach = base * MAX_WEIGHT * scale
  let pick: Target | null = null
  let score = Infinity
  for (let i = lowerBound(ts, raw - reach); i < ts.length && ts[i].t <= raw + reach; i++) {
    const w = WEIGHT[ts[i].type]
    const d = Math.abs(ts[i].t - raw)
    if (d <= base * w * scale && d / w < score) {
      pick = ts[i]
      score = d / w
    }
  }
  return pick
}

export function snap(ts: Target[], raw: number, opts: SnapOptions): SnapResult {
  if (opts.disabled || ts.length === 0) return { t: raw, target: null }
  const hit = best(ts, raw, thresholdSeconds(opts), 1)
  return hit ? { t: hit.t, target: hit } : { t: raw, target: null }
}

/** The target the playhead is closing in on, before it snaps -- shown so
 *  the snap is never a surprise. */
export function approaching(ts: Target[], raw: number, opts: SnapOptions, factor = 3): Target | null {
  if (opts.disabled || ts.length === 0) return null
  return best(ts, raw, thresholdSeconds(opts), factor)
}

/** Next target strictly after t (dir 1) or before it (dir -1). */
export function step(ts: Target[], t: number, dir: 1 | -1, only?: TargetType, eps = 1e-3): Target | null {
  if (dir === 1) {
    for (let i = lowerBound(ts, t + eps); i < ts.length; i++) if (!only || ts[i].type === only) return ts[i]
  } else {
    for (let i = lowerBound(ts, t - eps) - 1; i >= 0; i--) if (!only || ts[i].type === only) return ts[i]
  }
  return null
}

/** A cut tapped during playback lands on the nearest target, allowing for
 *  reaction time: people press a little late, rarely early. Outside the
 *  window it stays where it was tapped. */
export function cutWhilePlaying(ts: Target[], tapped: number,
  { lag = 0.12, before = 0.6, after = 0.25 } = {}): SnapResult {
  const aim = tapped - lag
  let pick: Target | null = null
  let score = Infinity
  for (let i = lowerBound(ts, tapped - before); i < ts.length && ts[i].t <= tapped + after; i++) {
    const s = Math.abs(ts[i].t - aim) / WEIGHT[ts[i].type]
    if (s < score) { pick = ts[i]; score = s }
  }
  return pick ? { t: pick.t, target: pick } : { t: tapped, target: null }
}

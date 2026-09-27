// What the picture does at each join, so the player shows what the export
// will have. The plan comes from the backend (export.plan_transitions, the
// same code that renders the file): per shot, frames of handle for a
// dissolve, and any dip to black or flash to white at its edges. Pure
// functions of the sequence time -- the transport applies them each frame.

import type { SeqItem } from './sequence'

export type Trans = { key: string; head: number; tail: number; fade_in: [number, string] | null; fade_out: [number, string] | null }
export type TransMap = Map<string, Trans>

export const byKey = (list: Trans[] | undefined | null): TransMap => new Map((list ?? []).map((t) => [t.key, t]))

/** A dip or flash veil over the picture at t: {colour, opacity}, or null.
 *  Export fades the shot's own frames linearly to the colour; a veil of the
 *  same colour at the same opacity is the same picture. */
export function veilAt(items: SeqItem[], k: number, tr: TransMap, t: number, fps: number): { color: string; alpha: number } | null {
  const it = items[k]
  const p = it && tr.get(it.key)
  if (!it || !p) return null
  if (p.fade_in) {
    const d = p.fade_in[0] / fps
    if (t < it.seq_start + d) return { color: p.fade_in[1], alpha: 1 - Math.max(0, t - it.seq_start) / d }
  }
  if (p.fade_out) {
    const d = p.fade_out[0] / fps
    if (t > it.seq_end - d) return { color: p.fade_out[1], alpha: Math.min(1, (t - (it.seq_end - d)) / d) }
  }
  return null
}

/** The dissolve at the cut after item k: its window in sequence time and
 *  where the incoming shot starts playing (its source time at window start).
 *  Export overlaps the two shots over [cut - head, cut + tail], mixing
 *  linearly; null when that cut is a plain cut. */
export function dissolveAfter(items: SeqItem[], k: number, tr: TransMap, fps: number):
  { from: number; cut: number; to: number; inFrom: number } | null {
  const a = items[k], b = items[k + 1]
  if (!a || !b || a.kind !== 'shot' || b.kind !== 'shot') return null
  const tail = (tr.get(a.key)?.tail ?? 0) / fps, head = (tr.get(b.key)?.head ?? 0) / fps
  if (tail <= 0 && head <= 0) return null
  const cut = a.seq_end
  return { from: cut - head, cut, to: cut + tail, inFrom: b.src_start - head }
}

/** How much of the incoming shot shows at t inside a dissolve window (0..1). */
export function mixAt(d: { from: number; to: number }, t: number): number {
  return d.to > d.from ? Math.max(0, Math.min(1, (t - d.from) / (d.to - d.from))) : 1
}

/** Where to have the next shot waiting before its cut: its first source
 *  second, or earlier by its dissolve handle. */
export function preloadAt(items: SeqItem[], k: number, tr: TransMap, fps: number): { clip: string; t: number } | null {
  const b = items[k + 1]
  if (!b || b.kind !== 'shot' || !b.clip_id) return null
  const head = (tr.get(b.key)?.head ?? 0) / fps
  return { clip: b.clip_id, t: Math.max(0, b.src_start - head) }
}

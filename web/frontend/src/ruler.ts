// The ruler along the top of the timeline, copied from CapCut / Final Cut /
// Premiere: labelled times with small unlabelled ticks between them, and a
// step that follows the zoom: minutes when the whole edit is in view, then
// seconds, then half seconds and single frames ("15f") zoomed all the way
// in. Labels stay about a thumb apart; ticks never closer than a few pixels.
export const LABEL_GAP_PX = 64
export const TICK_GAP_PX = 7

// Candidate steps in frames, finest first.
function steps(fps: number): number[] {
  const f = [1, 2, 5, 10]
  if (fps % 2 === 0) f.push(fps / 2)
  for (const s of [1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 1200]) f.push(s * fps)
  return [...new Set(f.filter((x) => x <= fps * 1200))].sort((a, b) => a - b)
}

export const rulerFps = (fps: number) => Math.max(1, Math.round(fps) || 30)

/** The labelled step and the small-tick step, both in frames (minor 0 = none). */
export function rulerScale(pxPerSec: number, fps: number): { major: number; minor: number } {
  fps = rulerFps(fps)
  const pxPerFrame = pxPerSec / fps
  const all = steps(fps)
  const major = all.find((s) => s * pxPerFrame >= LABEL_GAP_PX) ?? all[all.length - 1]
  const minor = all.find((s) => s < major && major % s === 0 && s * pxPerFrame >= TICK_GAP_PX) ?? 0
  return { major, minor }
}

// "5s" under a minute, then "1:05"; between whole seconds, the frame: "15f".
export function rulerLabel(frame: number, fps: number): string {
  fps = rulerFps(fps)
  const f = Math.round(frame)
  if (f % fps) return `${f % fps}f`
  const s = f / fps
  if (s < 60) return `${s}s`
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

/** Every step (in frames) from `from` to `to` seconds, inclusive. */
export function rulerMarks(from: number, to: number, step: number, fps: number): number[] {
  fps = rulerFps(fps)
  if (step <= 0) return []
  const out: number[] = []
  const end = Math.floor((to * fps + 1e-6) / step)
  for (let k = Math.max(0, Math.ceil((from * fps - 1e-6) / step)); k <= end; k++) out.push(k * step)
  return out
}

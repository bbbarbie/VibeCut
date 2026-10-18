// The time labels along the top of the timeline, as in CapCut / iMovie:
// "5s, 10s, 15s" so the length of the edit can be read at a glance. The step
// follows the zoom, so labels stay about a thumb apart: whole seconds when
// zoomed in, half minutes or minutes when the whole edit is in view.
const STEPS = [1, 2, 5, 10, 15, 30, 60, 120, 300, 600]
export const LABEL_GAP_PX = 64

export function rulerStep(pxPerSec: number, gap = LABEL_GAP_PX): number {
  for (const s of STEPS) if (s * pxPerSec >= gap) return s
  return STEPS[STEPS.length - 1]
}

// "5s" under a minute, then "1:05", "2:00".
export function rulerLabel(t: number): string {
  const s = Math.round(t)
  if (s < 60) return `${s}s`
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

// Every step from the start to the end of the edit.
export function rulerMarks(total: number, step: number): number[] {
  const out: number[] = []
  for (let k = 0; k * step <= total + 1e-6; k++) out.push(k * step)
  return out
}

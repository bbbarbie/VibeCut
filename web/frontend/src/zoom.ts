// Timeline zoom, as in CapCut / iMovie on a Mac: ⌘ or Ctrl + scroll wheel,
// or a trackpad pinch (which the browser reports as a wheel with Ctrl
// held), zooms around the pointer. A pinch sends many small steps, a mouse
// wheel few big ones, so each step is turned into a factor smoothly and
// capped, so one wheel notch is a comfortable jump, never a leap.
export const ZOOM_MIN = 1
export const ZOOM_MAX = 40

const LINE_PX = 16
const PAGE_PX = 400
const PER_PX = 0.008
const STEP_CAP = 60

export const clampZoom = (z: number) => Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, z))

// WheelEvent.deltaMode: 0 pixels, 1 lines (Firefox with a mouse), 2 pages.
export function wheelFactor(deltaY: number, deltaMode = 0): number {
  const px = deltaY * (deltaMode === 1 ? LINE_PX : deltaMode === 2 ? PAGE_PX : 1)
  return Math.exp(-Math.max(-STEP_CAP, Math.min(STEP_CAP, px)) * PER_PX)
}

// The slider moves along a log scale, so going from "whole edit" to "two
// shots" takes the same hand movement as from "two shots" to "frames".
export const toSlider = (z: number) => Math.log(clampZoom(z)) / Math.log(ZOOM_MAX)
export const fromSlider = (v: number) => clampZoom(Math.exp(v * Math.log(ZOOM_MAX)))

// Where the content should scroll to so that the moment at `x` (content
// pixels) sits `offset` pixels from the timeline's left edge again.
export const anchoredScroll = (x: number, offset: number, viewW: number, contentW: number) =>
  Math.max(0, Math.min(Math.max(0, contentW - viewW), x - offset))

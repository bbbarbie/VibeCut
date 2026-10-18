// A shot's effect (Shake, Glitch, VHS...) as the preview draws it: the same
// numbers, at the same moment of the shot, as the export's ffmpeg chain
// (backend effects.py). Pure: given the time into the shot it says what CSS
// to put on the picture, and what to lay over it.

export const EFFECTS: [string, string][] = [
  ['shake', 'Shake'], ['zoom_in', 'Zoom in'], ['zoom_out', 'Zoom out'], ['pulse', 'Pulse'],
  ['flash', 'Flash'], ['strobe', 'Strobe'], ['blur_in', 'Blur in'], ['glow', 'Glow'],
  ['vhs', 'VHS'], ['glitch', 'Glitch'], ['grain', 'Film grain'], ['old_film', 'Old film'],
  ['vignette', 'Vignette'], ['disco', 'Disco'],
]
export const effectName = (k: string | null | undefined) => EFFECTS.find(([id]) => id === k)?.[1] ?? 'No effect'
export const AMOUNT = [0.25, 2] as const

// [priors] -- the same as effects.py
const SHAKE = 0.06, GLITCH = 0.08, GLITCH_RATE = 8, ZOOM = 0.15, PULSE = 0.07, PULSE_EVERY = 0.5
const FLASH_S = 0.4, STROBE_HZ = 6, BLUR_IN_S = 0.7, BLUR = 0.02, GLOW = 0.025, SPLIT = 0.004, HUE_SPEED = 120

export type FxLook = {
  /** goes in front of the shot's own turn and mirror */
  transform: string
  filter: string
  /** layers laid over the picture (white flashes, dark corners, scanlines) */
  tint: string
  /** film grain over the picture, 0..1 */
  grain: number
  /** the SVG filters' settings, when `filter` uses them */
  glow: { std: number; k: number } | null
  split: number | null
}

export const NO_FX: FxLook = { transform: '', filter: '', tint: '', grain: 0, glow: null, split: null }

const clamp01 = (x: number) => Math.max(0, Math.min(1, x))
const frac = (x: number) => x - Math.floor(x)
const pct = (x: number) => `${(x * 100).toFixed(3)}%`

function wander(m: number, kx: number, ky: number): string {
  return `translate(${pct((-m / 2) * kx / (1 - m))}, ${pct((-m / 2) * ky / (1 - m))}) scale(${(1 / (1 - m)).toFixed(4)})`
}

export function vignette(a: number): string {
  const alpha = Math.min(0.95, 0.6 * a)
  return `radial-gradient(ellipse at center, rgba(0,0,0,0) 38%, rgba(0,0,0,${alpha.toFixed(3)}) 100%)`
}
const white = (k: number) => `linear-gradient(rgba(255,255,255,${k.toFixed(3)}), rgba(255,255,255,${k.toFixed(3)}))`

/**
 * The effect `kind` at `u` seconds into a shot `d` seconds long, on a
 * picture `w` x `h` px as shown. `svg` names the SVG filters to use
 * (Player's hidden defs, or a tile's own).
 */
export function effectAt(kind: string | null | undefined, amount: number | undefined, u: number, d: number,
  w: number, h: number, svg = 'vcfx'): FxLook {
  if (!kind) return NO_FX
  const a = Math.max(AMOUNT[0], Math.min(AMOUNT[1], amount ?? 1))
  const fx: FxLook = { ...NO_FX }
  switch (kind) {
    case 'shake':
      fx.transform = wander(SHAKE * a, 0.9 * Math.sin(29 * u) * Math.sin(7.3 * u + 1), 0.9 * Math.cos(23 * u) * Math.sin(5.1 * u))
      break
    case 'glitch': {
      const step = Math.floor(u * GLITCH_RATE)
      const on = frac(Math.abs(Math.sin(step * 12.9898) * 43758.5)) > 0.7 ? 1 : 0
      const side = Math.sin(step * 78.233) > 0 ? 1 : -1
      fx.transform = wander(GLITCH * a, 0.9 * on * side, 0)
      fx.split = Math.max(1, SPLIT * a * 2 * w)
      fx.filter = `url(#${svg}-split)`
      break
    }
    case 'zoom_in': fx.transform = `scale(${(1 + ZOOM * a * clamp01(u / d)).toFixed(4)})`; break
    case 'zoom_out': fx.transform = `scale(${(1 + ZOOM * a * (1 - clamp01(u / d))).toFixed(4)})`; break
    case 'pulse': {
      const p = Math.max(u, 0) % PULSE_EVERY
      fx.transform = `scale(${(1 + PULSE * a * Math.exp(-p * 8)).toFixed(4)})`
      break
    }
    case 'flash': {
      const k = Math.min(1, 0.9 * a) * clamp01(1 - u / FLASH_S)
      if (k > 0) fx.tint = white(k)
      break
    }
    case 'strobe':
      if (Math.sin(2 * Math.PI * STROBE_HZ * u) > 0.5) fx.tint = white(Math.min(0.9, 0.55 * a))
      break
    case 'blur_in': {
      const r = BLUR * a * w * clamp01(1 - u / BLUR_IN_S)
      if (r > 0.05) fx.filter = `blur(${r.toFixed(2)}px)`
      break
    }
    case 'glow':
      fx.glow = { std: Math.max(0.5, GLOW * w), k: Math.min(1, 0.5 * a) }
      fx.filter = `url(#${svg}-glow)`
      break
    case 'vhs': {
      fx.split = Math.max(0.5, SPLIT * a * w)
      fx.filter = `saturate(0.8) contrast(1.08) url(#${svg}-split)`
      const line = Math.max(1, (h / 1080) * 4)   // every 4 rows of the export
      const alpha = Math.min(0.6, 0.3 * a)
      fx.tint = `repeating-linear-gradient(to bottom, rgba(0,0,0,${alpha.toFixed(2)}) 0 ${(line / 4).toFixed(2)}px, rgba(0,0,0,0) ${(line / 4).toFixed(2)}px ${line.toFixed(2)}px)`
      fx.grain = Math.min(0.5, 0.1 * a)
      break
    }
    case 'grain': fx.grain = Math.min(0.6, 0.15 * a); break
    case 'old_film':
      fx.filter = `sepia(${Math.min(1, 0.8 * a).toFixed(2)}) brightness(${(1 + 0.06 * a * Math.sin(50 * u)).toFixed(3)})`
      fx.grain = Math.min(0.6, 0.12 * a)
      fx.tint = vignette(a)
      break
    case 'vignette': fx.tint = vignette(a); break
    case 'disco': fx.filter = `hue-rotate(${(HUE_SPEED * a * u).toFixed(1)}deg)`; break
  }
  return fx
}

/** Set an SVG filter's settings (Player's defs, or a tile's). */
export function tuneSvg(fx: FxLook, svg = 'vcfx', root: ParentNode = document) {
  if (fx.glow) {
    root.querySelector(`#${svg}-glow feGaussianBlur`)?.setAttribute('stdDeviation', fx.glow.std.toFixed(2))
    const c = root.querySelector(`#${svg}-glow feComposite`)
    c?.setAttribute('k2', fx.glow.k.toFixed(3))
    c?.setAttribute('k3', (1 - fx.glow.k).toFixed(3))
  }
  if (fx.split != null) {
    const offs = root.querySelectorAll(`#${svg}-split feOffset`)
    offs[0]?.setAttribute('dx', (-fx.split).toFixed(2))
    offs[1]?.setAttribute('dx', fx.split.toFixed(2))
  }
}

let noiseUrl: string | null = null
/** A tile of grey noise, made once, for film grain. */
export function noise(): string {
  if (noiseUrl) return noiseUrl
  try {
    const c = document.createElement('canvas')
    c.width = c.height = 128
    const ctx = c.getContext('2d')!
    const img = ctx.createImageData(128, 128)
    for (let i = 0; i < img.data.length; i += 4) {
      const v = Math.random() * 255
      img.data[i] = img.data[i + 1] = img.data[i + 2] = v
      img.data[i + 3] = 255
    }
    ctx.putImageData(img, 0, 0)
    noiseUrl = c.toDataURL()
  } catch { noiseUrl = '' }
  return noiseUrl
}

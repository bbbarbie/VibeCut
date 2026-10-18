import { useEffect, useRef, useState } from 'react'
import { AMOUNT, EFFECTS, effectAt, effectName, noise, tuneSvg } from '../effectView'
import { cx } from '../ui'
import { Chip, Slider } from './Inspector'

// Video effects on a shot (sarah, 2026-10-18: the popular ones, in the app).
// Each tile plays its effect round and round on the shot's own picture,
// drawn by the same effectView the preview uses, and the export draws it
// with the same numbers (effects.py). One tap is one undoable turn; nothing
// is on until something is picked.

/** The SVG filters an effect may use (glow, colour split), under ids `${id}-glow` / `${id}-split`. */
export function FxDefs({ id }: { id: string }) {
  return (
    <svg width="0" height="0" aria-hidden className="pointer-events-none absolute">
      <filter id={`${id}-glow`} x="0" y="0" width="100%" height="100%" colorInterpolationFilters="sRGB">
        <feGaussianBlur in="SourceGraphic" stdDeviation="8" result="soft" />
        <feBlend in="SourceGraphic" in2="soft" mode="screen" result="lit" />
        <feComposite in="lit" in2="SourceGraphic" operator="arithmetic" k1="0" k2="0.5" k3="0.5" k4="0" />
      </filter>
      <filter id={`${id}-split`} x="0" y="0" width="100%" height="100%" colorInterpolationFilters="sRGB">
        <feColorMatrix in="SourceGraphic" type="matrix" values="1 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 1 0" result="r" />
        <feOffset in="r" dx="-2" result="ro" />
        <feColorMatrix in="SourceGraphic" type="matrix" values="0 0 0 0 0  0 1 0 0 0  0 0 0 0 0  0 0 0 1 0" result="g" />
        <feColorMatrix in="SourceGraphic" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 1 0 0  0 0 0 1 0" result="b" />
        <feOffset in="b" dx="2" result="bo" />
        <feBlend in="ro" in2="g" mode="screen" result="rg" />
        <feBlend in="rg" in2="bo" mode="screen" />
      </filter>
    </svg>
  )
}

const TILE_W = 112, TILE_H = 76, LOOP = 2.4

/** Seconds into a LOOP-long pretend shot, round and round while mounted. */
function useClock(): number {
  const [u, setU] = useState(0)
  useEffect(() => {
    let raf = 0
    const t0 = performance.now()
    const tick = (now: number) => { setU(((now - t0) / 1000) % LOOP); raf = requestAnimationFrame(tick) }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [])
  return u
}

function Sample({ kind, amount, thumb, u }: { kind: string | null; amount: number; thumb: string | null; u: number }) {
  const svg = `vcfx-tile-${kind}`
  const box = useRef<HTMLSpanElement>(null)
  const fx = effectAt(kind, amount, u, LOOP, TILE_W, TILE_H, svg)
  useEffect(() => { if (box.current) tuneSvg(fx, svg, box.current) })
  const pic = thumb ? { backgroundImage: `url(${thumb})`, backgroundSize: 'cover', backgroundPosition: 'center' } : { background: '#6b7f8e' }
  return (
    <span ref={box} className="absolute inset-0 overflow-hidden">
      {(fx.glow || fx.split != null) && <FxDefs id={svg} />}
      <span className="absolute inset-0" style={{ ...pic, transform: fx.transform, filter: fx.filter }} />
      {fx.tint && <span className="absolute inset-0" style={{ background: fx.tint }} />}
      {fx.grain > 0 && <span className="absolute inset-0 mix-blend-overlay"
                             style={{ backgroundImage: `url(${noise()})`, opacity: fx.grain,
                                      backgroundPosition: `${Math.floor(u * 997) % 128}px ${Math.floor(u * 571) % 128}px` }} />}
    </span>
  )
}

function Tile({ on, label, onClick, children }: { on: boolean; label: string; onClick: () => void; children: React.ReactNode }) {
  return (
    <button type="button" onClick={onClick} aria-pressed={on} className="flex shrink-0 flex-col items-center gap-1 font-serif text-[15px] text-zinc-100">
      <span className={cx('relative block overflow-hidden rounded-lg border-[3px] bg-black',
        on ? 'border-accent' : 'border-transparent hover:border-zinc-500')} style={{ width: TILE_W, height: TILE_H }}>
        {children}
      </span>
      {label}
    </button>
  )
}

const GRID = 'grid grid-cols-[repeat(auto-fill,minmax(112px,1fr))] justify-items-center gap-x-2 gap-y-3'

/**
 * The effects. With a shot clicked (`n`) a tile changes that shot; with
 * none, every shot, shown on the first one.
 */
export function EffectTiles({ n, effect, amount, thumb, onPick, onAll }: {
  /** the clicked shot's number, or null for every shot */
  n: number | null
  effect: string | null
  amount: number
  thumb: string | null
  onPick: (patch: { effect?: string | null; effect_amount?: number }, label: string) => void
  /** "Use for every shot", with a shot clicked */
  onAll: () => void
}) {
  const u = useClock()
  const where = n != null ? `shot ${n}` : 'every shot'
  return (
    <div className="flex flex-col gap-3">
      <div className={GRID}>
        <Tile on={!effect} label="None" onClick={() => effect && onPick({ effect: null }, `You took the effect off ${where}`)}>
          <Sample kind={null} amount={1} thumb={thumb} u={u} />
        </Tile>
        {EFFECTS.map(([id, name]) => (
          <Tile key={id} on={effect === id} label={name}
                onClick={() => effect !== id && onPick({ effect: id }, `You put ${name} on ${where}`)}>
            <Sample kind={id} amount={amount} thumb={thumb} u={u} />
          </Tile>
        ))}
      </div>
      <Slider label="Strength" value={Math.round(amount * 100)} min={AMOUNT[0] * 100} max={AMOUNT[1] * 100} step={5} unit="%" disabled={!effect}
              onCommit={(v) => effect && onPick({ effect, effect_amount: v / 100 }, `${effectName(effect)} on ${where} at ${v}%`)} />
      {n != null && effect && <div className="flex flex-wrap gap-2">
        <Chip onClick={onAll}>Use for every shot</Chip>
      </div>}
    </div>
  )
}

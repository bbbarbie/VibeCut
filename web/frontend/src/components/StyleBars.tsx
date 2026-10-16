import { useEffect, useRef, useState } from 'react'
import { blendLook } from '../joinView'
import { drawOverlays } from '../overlayDraw'
import type { CaptionEnter, CaptionTemplate, JoinInfo, Overlay, OverlayStyle } from '../types'
import { cx } from '../ui'
import { Chip, Slider } from './ShotBar'

// The bottom bar for a clicked caption (its Style and Animation) and for a
// clicked cut between two shots (its Transition). Every choice is a tile
// that moves the way the result will, drawn by the same code as the preview
// and the export (overlayDraw.drawOverlays, joinView.blendLook), and one tap
// is one undoable turn. Nothing here is on by default: a video keeps its
// look's own captions and cuts until something is picked (sarah, 2026-10-14).

export const TEMPLATE_NAMES: Record<CaptionTemplate, string> = {
  outlined: 'Outlined', bold: 'Big & bold', label: 'Label', highlight: 'Highlighter',
  handwritten: 'Handwritten', tape: 'Typed tape', pop: 'Pop colour', quiet: 'Quiet',
}
const ENTER_NAMES: Record<CaptionEnter, string> = {
  fade: 'Fade up', pop: 'Pop', slide: 'Slide in', stamp: 'Stamp', type: 'Typewriter', word: 'Word by word',
}
export const TRANSITION_NAMES: Record<string, string> = {
  cut: 'Cut', dissolve: 'Fade', dip_black: 'Dip to black', flash: 'Flash',
  zoom: 'Zoom through', slide_up: 'Slide up', blur: 'Blur', light_leak: 'Light leak', swipe: 'Swipe',
}

/** 0..1, round and round every `period` seconds while mounted. */
export function useLoop(period: number): number {
  const [m, setM] = useState(0)
  useEffect(() => {
    let raf = 0
    const t0 = performance.now()
    const tick = (now: number) => { setM(((now - t0) / 1000 / period) % 1); raf = requestAnimationFrame(tick) }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [period])
  return m
}

const TILE_W = 112, TILE_H = 76

export function Tile({ on, label, onClick, children }: { on: boolean; label: string; onClick: () => void; children: React.ReactNode }) {
  return (
    <button type="button" onClick={onClick} className="flex shrink-0 flex-col items-center gap-1 font-serif text-[15px] text-zinc-100">
      <span className={cx('relative block overflow-hidden rounded-lg border-[3px] bg-black',
        on ? 'border-accent' : 'border-transparent hover:border-zinc-500')} style={{ width: TILE_W, height: TILE_H }}>
        {children}
      </span>
      {label}
    </button>
  )
}

/** A caption drawn on a tile exactly as drawOverlays will draw it in the video. */
export function CaptionSample({ style, text, t, scale = 3 }: { style: OverlayStyle; text: string; t: number; scale?: number }) {
  const ref = useRef<HTMLCanvasElement>(null)
  useEffect(() => {
    const c = ref.current
    const ctx = c?.getContext('2d')
    if (!c || !ctx) return
    const o: Overlay = { id: 'tile', kind: 'caption', text, sub: '', pos: 'bottom', size: 'L', anim: 'fade', dur: 3,
      anchor: { to: 'edit' }, at: 0, start: 0, end: 3, shown_end: 3, place: { x: 0.5, y: 0.5, scale } }
    drawOverlays(ctx, c.width, c.height, [o], style, [], t)
  }, [style, text, t, scale])
  return <canvas ref={ref} width={TILE_W * 2} height={TILE_H * 2} className="absolute inset-0 size-full" />
}

export function CaptionBar({ style, thumb, sample, tab, onTab, onPick }: {
  style: OverlayStyle
  /** which tab is open: kept by the caller, so a pick (a new session) doesn't flip it back */
  tab: 'style' | 'anim'
  onTab: (tab: 'style' | 'anim') => void
  /** the picture under the caption, behind every tile */
  thumb: string | null
  sample: string
  onPick: (patch: { template?: CaptionTemplate | null; enter?: CaptionEnter | null }, label: string) => void
}) {
  const m = useLoop(2.2)
  const bg = thumb ? { backgroundImage: `url(${thumb})`, backgroundSize: 'cover', backgroundPosition: 'center' } : undefined
  const held = 2.0   // the caption fully in, for the Style tiles
  const tabs = [{ id: 'style' as const, icon: 'Aa', label: 'Style' }, { id: 'anim' as const, icon: '✦', label: 'Animation' }]
  return (
    <div className="shrink-0 border-t border-line bg-panel px-3 pb-3 pt-2">
      <div className="flex gap-1.5">
        {tabs.map((x) => (
          <button key={x.id} type="button" onClick={() => onTab(x.id)}
                  className={cx('flex flex-1 flex-col items-center gap-0.5 rounded-xl py-1.5 font-serif text-[15px]',
                    tab === x.id ? 'bg-accent text-accent-ink' : 'text-zinc-100 hover:bg-raised')}>
            <span className="text-[18px] leading-none">{x.icon}</span>{x.label}
          </button>
        ))}
      </div>
      <div className="mt-2 flex items-start gap-3 overflow-x-auto rounded-xl border border-line bg-raised/40 px-4 py-3">
        {tab === 'style' ? <>
          <Tile on={!style.template} label="The look's own" onClick={() => style.template && onPick({ template: null }, 'Captions back to the look\'s own')}>
            <span className="absolute inset-0" style={bg} />
            <CaptionSample style={{ ...style, template: null, enter: null }} text="Aa" t={held} />
          </Tile>
          {(Object.keys(TEMPLATE_NAMES) as CaptionTemplate[]).map((id) => (
            <Tile key={id} on={style.template === id} label={TEMPLATE_NAMES[id]}
                  onClick={() => style.template !== id && onPick({ template: id }, `Every caption is now ${TEMPLATE_NAMES[id]}`)}>
              <span className="absolute inset-0" style={bg} />
              <CaptionSample style={{ ...style, template: id, enter: null }} text="Aa" t={held} />
            </Tile>
          ))}
        </> : <>
          <Tile on={!style.enter} label="The look's own" onClick={() => style.enter && onPick({ enter: null }, 'Captions come in the look\'s own way')}>
            <span className="absolute inset-0" style={bg} />
            <CaptionSample style={{ ...style, enter: null }} text={sample} t={m * 2.2} scale={2} />
          </Tile>
          {(Object.keys(ENTER_NAMES) as CaptionEnter[]).map((id) => (
            <Tile key={id} on={style.enter === id} label={ENTER_NAMES[id]}
                  onClick={() => style.enter !== id && onPick({ enter: id }, `Captions now come in: ${ENTER_NAMES[id]}`)}>
              <span className="absolute inset-0" style={bg} />
              <CaptionSample style={{ ...style, enter: id }} text={sample} t={m * 2.2} scale={2} />
            </Tile>
          ))}
        </>}
      </div>
    </div>
  )
}

/** Two pictures joined the way `kind` joins them, playing round and round. */
export function JoinSample({ kind, from, to, m }: { kind: string; from: string | null; to: string | null; m: number }) {
  // hold the outgoing shot, run the join through the middle half, hold the next
  const k = Math.max(0, Math.min(1, (m - 0.25) / 0.5))
  const pic = (src: string | null) => src ? { backgroundImage: `url(${src})`, backgroundSize: 'cover', backgroundPosition: 'center' } : { background: '#444' }
  if (kind === 'cut' || kind === 'dip_black' || kind === 'flash') {
    const veil = kind === 'cut' ? 0 : 1 - Math.abs(k - 0.5) * 2
    return <>
      <span className="absolute inset-0" style={pic(k < 0.5 ? from : to)} />
      <span className="absolute inset-0" style={{ background: kind === 'flash' ? 'white' : 'black', opacity: veil }} />
    </>
  }
  const look = blendLook(kind, k)
  const css = (p: typeof look.out) => ({ opacity: p.opacity, translate: p.translate, scale: p.scale,
    filter: p.filter.replace(/([\d.]+)px/, (_, n) => `${(Number(n) / 3).toFixed(1)}px`) })
  return <>
    <span className="absolute inset-0" style={{ ...pic(from), ...css(look.out) }} />
    <span className="absolute inset-0" style={{ ...pic(to), ...css(look.in) }} />
    {look.glow && <span className="absolute inset-0" style={{ background: look.glow.background, opacity: look.glow.alpha }} />}
  </>
}

export function JoinBar({ join, before, after, from, to, onPick }: {
  join: JoinInfo
  before: number | null
  after: number | null
  from: string | null
  to: string | null
  onPick: (op: { kind: string; dur?: number; all?: boolean }, label: string) => void
}) {
  const m = useLoop(1.8)
  const picked = join.picked ?? null
  const dur = join.picked_dur ?? 0.5
  const where = before != null && after != null ? `the cut from shot ${before} to shot ${after}` : 'this cut'
  // a blend picked here that the footage can't give (no film past the cut) plays as a cut
  const short = !!picked && picked !== 'cut' && picked !== join.picture && !['dip_black', 'flash'].includes(picked)
  return (
    <div className="shrink-0 border-t border-line bg-panel px-3 pb-3 pt-2">
      <div className="px-1 pb-1 font-serif text-[16px] text-zinc-100">✦ How the picture changes at {where}</div>
      <div className="flex items-start gap-3 overflow-x-auto rounded-xl border border-line bg-raised/40 px-4 py-3">
        {Object.entries(TRANSITION_NAMES).map(([id, name]) => (
          <Tile key={id} on={(picked ?? join.picture) === id} label={name}
                onClick={() => onPick({ kind: id, dur }, `${name} at ${where}`)}>
            <JoinSample kind={id} from={from} to={to} m={m} />
          </Tile>
        ))}
      </div>
      {short && <div className="px-1 pt-2 font-serif text-[15px] text-zinc-100">
        These shots weren't filmed long enough past the cut to blend, so this one stays a cut.</div>}
      <div className="mt-2 flex items-center gap-4 rounded-xl border border-line bg-raised/40 px-4 py-2.5">
        <Slider label="Length" value={dur} min={0.2} max={1.5} step={0.1} unit=" s" disabled={!picked || picked === 'cut'}
                onCommit={(v) => picked && onPick({ kind: picked, dur: v }, `The ${TRANSITION_NAMES[picked].toLowerCase()} now takes ${v} s`)} />
        <Chip onClick={() => onPick({ kind: picked ?? join.picture, dur, all: true },
          `Every cut is now a ${TRANSITION_NAMES[picked ?? join.picture].toLowerCase()}`)}>Use for every cut</Chip>
        {picked && <Chip onClick={() => join.picked_all
          ? onPick({ kind: 'auto', all: true }, 'Every cut is back to the look\'s own')
          : onPick({ kind: 'auto' }, `${where[0].toUpperCase()}${where.slice(1)} is back to the look's own`)}>
          Back to the look's own</Chip>}
      </div>
    </div>
  )
}

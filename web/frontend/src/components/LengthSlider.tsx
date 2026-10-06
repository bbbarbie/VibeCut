import { lengthLabel } from '../brief'
import type { LengthSlider as Slider } from '../types'
import { cx } from '../ui'

// How long the video should be, as a slider over the footage there is
// (sarah, 2026-10-06: "fast is under a minute, 3 minutes or full length"
// meant nothing once the shoot was bigger). The marks are read from the
// footage and the kind of video; the suggested one says why. The same
// control sits in the questions popup and in Frames.
export function LengthSlider({ slider, value, onChange, onCommit, compact }: {
  slider: Slider
  value: number
  onChange: (seconds: number) => void
  /** released (Frames applies it then; the popup just keeps it) */
  onCommit?: (seconds: number) => void
  compact?: boolean
}) {
  const { min, max } = slider
  const span = Math.max(1, max - min)
  const at = (s: number) => `${((Math.min(max, Math.max(min, s)) - min) / span) * 100}%`
  const step = max - min > 600 ? 5 : 1
  return (
    <div className={cx('select-none', 'w-full')}>
      <div className="flex items-baseline gap-2">
        <span className={cx('font-serif tabular-nums text-zinc-100', compact ? 'text-[18px]' : 'text-[28px]')}>About {lengthLabel(value)}</span>
        <span className="text-[11px] text-muted">of {lengthLabel(max)} good footage</span>
      </div>
      <div className="relative mt-3 h-9">
        <input type="range" min={min} max={max} step={step} value={Math.round(value)} aria-label="Length of the video"
               onChange={(e) => onChange(Number(e.target.value))}
               onPointerUp={(e) => onCommit?.(Number((e.target as HTMLInputElement).value))}
               onKeyUp={(e) => { if (e.key.startsWith('Arrow') || e.key === 'Home' || e.key === 'End') onCommit?.(Number((e.target as HTMLInputElement).value)) }}
               className="absolute inset-x-0 top-0 h-4 w-full cursor-pointer accent-[var(--color-accent)]" />
        {slider.marks.map((m) => (
          <button key={m.key} type="button" onClick={() => { onChange(m.seconds); onCommit?.(m.seconds) }}
                  style={{ left: at(m.seconds) }}
                  className={cx('absolute top-5 whitespace-nowrap rounded px-1 text-[10px] leading-tight',
                    // the ends hang inward so they stay inside the card
                    (m.seconds - min) / span > 0.88 ? '-translate-x-full text-right' : (m.seconds - min) / span < 0.12 ? 'text-left' : '-translate-x-1/2 text-center',
                    Math.abs(value - m.seconds) <= step ? 'text-accent' : 'text-muted hover:text-zinc-200')}>
            <span className="block font-medium">{m.label}{m.key === slider.suggest ? ' ★' : ''}</span>
            <span className="block tabular-nums">{lengthLabel(m.seconds)}</span>
          </button>
        ))}
      </div>
      <p className={cx('text-muted', compact ? 'mt-3 text-[11px]' : 'mt-4 text-[12px]')}>★ {slider.why}</p>
    </div>
  )
}

import { useState } from 'react'
import type { SeqItem } from '../sequence'
import type { SoundStrip } from '../types'
import { cx } from '../ui'

// The tools for what's selected on the timeline, along the bottom (sarah,
// 2026-10-14: one click to a tool, then a slider to drag -- not a menu that
// steps the volume 25% at a time). A shot gets Split, Sound, Speed, Turn &
// crop, Swap and Delete; a sound strip gets its own Sound tools. Every
// change is one undoable turn (board.set_shot / edit_audio), sent when a
// slider is let go, not while it moves.

type Patch = Record<string, unknown>
type Tab = 'sound' | 'speed' | 'turn'

export function ShotBar({ item, extracted, onFix, onSplit, onSwap, onDelete, onExtract }: {
  item: SeqItem
  /** its sound is on its own strip below */
  extracted: boolean
  onFix: (patch: Patch, label: string) => void
  onSplit: () => void
  onSwap: () => void
  onDelete: () => void
  onExtract: () => void
}) {
  const [tab, setTab] = useState<Tab | null>(null)
  const n = item.n ?? ''
  const tools: { id: Tab | 'split' | 'swap' | 'delete'; icon: string; label: string; danger?: boolean }[] = [
    { id: 'split', icon: '✂︎', label: 'Split' },
    { id: 'sound', icon: '🔊', label: 'Sound' },
    { id: 'speed', icon: '⏩', label: 'Speed' },
    { id: 'turn', icon: '⟳', label: 'Turn & crop' },
    { id: 'swap', icon: '⇄', label: 'Swap' },
    { id: 'delete', icon: '🗑', label: 'Delete', danger: true },
  ]
  const press = (id: typeof tools[number]['id']) => {
    if (id === 'split') onSplit()
    else if (id === 'swap') onSwap()
    else if (id === 'delete') onDelete()
    else setTab(tab === id ? null : id)
  }

  return (
    <div className="shrink-0 border-t border-line bg-panel px-3 pb-3 pt-2">
      <div className="flex gap-1.5">
        {tools.map((t) => (
          <button key={t.id} type="button" onClick={() => press(t.id)}
                  className={cx('flex flex-1 flex-col items-center gap-0.5 rounded-xl py-1.5 font-serif text-[15px]',
                    tab === t.id ? 'bg-accent text-accent-ink' : t.danger ? 'text-rose-200 hover:bg-rose-500/10' : 'text-zinc-100 hover:bg-raised')}>
            <span className="text-[18px] leading-none">{t.icon}</span>{t.label}
          </button>
        ))}
      </div>
      {tab === 'sound' && (extracted
        ? <Row><span className="font-serif text-[15px] text-zinc-200">This shot's sound is on its own strip under the picture. Click the strip to change it.</span></Row>
        : <SoundRow gain={item.gain ?? 1} mute={!!item.mute} fadeIn={item.fade_in ?? 0} fadeOut={item.fade_out ?? 0}
                    onFix={(p, what) => onFix(p, `You ${what} on shot ${n}`)}
                    extra={<Chip onClick={onExtract}>Take the sound off</Chip>} />)}
      {tab === 'speed' && <SpeedRow speed={item.speed ?? 1} onFix={(x) => onFix({ speed: x }, x === 1 ? `You put shot ${n} back to normal speed` : `You set shot ${n} to ${x}×`)} />}
      {tab === 'turn' && (() => {
        const r = item.rotate ?? 0
        const changed = !!(r || item.fill || item.mirror)
        return (
          <Row>
            <Chip onClick={() => onFix({ rotate: (r + 270) % 360 }, `You turned shot ${n} left`)}>↺ Turn left</Chip>
            <Chip onClick={() => onFix({ rotate: (r + 90) % 360 }, `You turned shot ${n} right`)}>↻ Turn right</Chip>
            <Chip on={!!item.mirror} onClick={() => onFix({ mirror: !item.mirror }, `You ${item.mirror ? 'unmirrored' : 'mirrored'} shot ${n}`)}>⇋ Mirror</Chip>
            <Chip on={!!item.fill} onClick={() => !item.fill && onFix({ fill: true }, `Shot ${n} fills the frame`)}>Fill the frame</Chip>
            <Chip on={!item.fill} onClick={() => item.fill && onFix({ fill: false }, `Shot ${n} shows its whole picture`)}>Show it all</Chip>
            <span className="flex-1" />
            {changed && <Chip onClick={() => onFix({ rotate: 0, fill: false, mirror: false }, `You put shot ${n} back as filmed`)}>Back to as filmed</Chip>}
          </Row>
        )
      })()}
    </div>
  )
}

/** A sound strip (extract audio): the same Sound tools, plus Delete. */
export function StripBar({ strip, onEdit, onDelete }: {
  strip: SoundStrip
  onEdit: (patch: Patch, label: string) => void
  onDelete: () => void
}) {
  const name = `the sound of shot ${strip.n ?? ''}`.trim()
  return (
    <div className="shrink-0 border-t border-line bg-panel px-3 pb-3 pt-2">
      <div className="px-1 pb-1 font-serif text-[16px] text-zinc-100">🔊 Sound of shot {strip.n ?? ''} · drag it on the timeline to move it</div>
      <SoundRow gain={strip.gain} mute={strip.mute} fadeIn={strip.fade_in ?? 0} fadeOut={strip.fade_out ?? 0}
                onFix={(p, what) => onEdit(p, `You ${what} on ${name}`)}
                extra={<Chip danger onClick={onDelete}>Delete this sound</Chip>} />
    </div>
  )
}

function SoundRow({ gain, mute, fadeIn, fadeOut, onFix, extra }: {
  gain: number; mute: boolean; fadeIn: number; fadeOut: number
  onFix: (patch: Patch, what: string) => void
  extra?: React.ReactNode
}) {
  return (
    <Row>
      <Slider label="Volume" value={Math.round(gain * 100)} min={0} max={200} step={5} unit="%" disabled={mute}
              onCommit={(v) => onFix({ gain: v / 100 }, `set the volume to ${v}%`)} />
      <Slider label="Fade in" value={fadeIn} min={0} max={3} step={0.1} unit=" s"
              onCommit={(v) => onFix({ fade_in: v }, v ? `faded the sound in over ${v}s` : 'took the fade in off')} />
      <Slider label="Fade out" value={fadeOut} min={0} max={3} step={0.1} unit=" s"
              onCommit={(v) => onFix({ fade_out: v }, v ? `faded the sound out over ${v}s` : 'took the fade out off')} />
      <Chip on={mute} onClick={() => onFix({ mute: !mute }, mute ? 'unmuted the sound' : 'muted the sound')}>{mute ? 'Unmute' : 'Mute'}</Chip>
      {extra}
    </Row>
  )
}

// Speed on a doubling scale: the middle of the slider is 1×, each quarter
// of the way doubles or halves it.
const PRESETS = [0.5, 1, 2, 4]
function SpeedRow({ speed, onFix }: { speed: number; onFix: (x: number) => void }) {
  const [drag, setDrag] = useState<number | null>(null)   // while the slider moves; the shot's own value otherwise
  const v = drag ?? Math.log2(speed)
  const shown = Math.round(2 ** v * 100) / 100
  const commit = () => { setDrag(null); if (Math.abs(shown - speed) > 1e-3) onFix(shown) }
  return (
    <Row>
      <label className="flex min-w-0 flex-[2] flex-col gap-1 font-serif text-[15px] text-zinc-100">
        <span className="flex justify-between"><span>Speed</span><span className="tabular-nums">{shown}×</span></span>
        <input type="range" min={-2} max={2} step={0.05} value={v} className="w-full accent-[#1f5f8b]"
               onChange={(e) => setDrag(Number(e.target.value))} onPointerUp={commit} onKeyUp={commit} />
      </label>
      {PRESETS.map((x) => <Chip key={x} on={Math.abs(speed - x) < 1e-3} onClick={() => onFix(x)}>{x}×</Chip>)}
    </Row>
  )
}

export function Slider({ label, value, min, max, step, unit, disabled, onCommit }: {
  label: string; value: number; min: number; max: number; step: number; unit: string; disabled?: boolean
  onCommit: (v: number) => void
}) {
  const [drag, setDrag] = useState<number | null>(null)
  const v = drag ?? value
  const commit = () => {
    setDrag(null)
    const r = Math.round(v / step) * step
    const x = Math.round(r * 100) / 100
    if (Math.abs(x - value) > 1e-6) onCommit(x)
  }
  return (
    <label className={cx('flex min-w-0 flex-1 flex-col gap-1 font-serif text-[15px] text-zinc-100', disabled && 'opacity-40')}>
      <span className="flex justify-between"><span>{label}</span><span className="tabular-nums">{Math.round(v * 100) / 100}{unit}</span></span>
      <input type="range" min={min} max={max} step={step} value={v} disabled={disabled} className="w-full accent-[#1f5f8b]"
             onChange={(e) => setDrag(Number(e.target.value))} onPointerUp={commit} onKeyUp={commit} />
    </label>
  )
}

export function Row({ children }: { children: React.ReactNode }) {
  return <div className="mt-2 flex items-center gap-4 rounded-xl border border-line bg-raised/40 px-4 py-2.5">{children}</div>
}

export function Chip({ children, onClick, on, danger }: { children: React.ReactNode; onClick: () => void; on?: boolean; danger?: boolean }) {
  return (
    <button type="button" onClick={onClick}
            className={cx('shrink-0 whitespace-nowrap rounded-lg border px-3 py-1.5 font-serif text-[15px]',
              on ? 'border-accent bg-accent text-accent-ink' : danger ? 'border-rose-200/40 text-rose-200 hover:bg-rose-500/10'
                : 'border-line bg-panel text-zinc-100 hover:bg-raised')}>
      {children}
    </button>
  )
}

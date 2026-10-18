import { useEffect, useRef, useState } from 'react'
import { phStore, snapStore, transport, transportStore, useStore } from '../transport'
import { Icon } from './icons'

const mss = (t: number) => `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, '0')}`

// Under the edit screen's preview, on black as in her reference picture
// (sarah, 2026-10-16): play, where you are of how long, a bar to drag through
// the edit, the frame the video is for (click it for the three to choose
// from, sarah 2026-10-18; it used to step through them), full screen.
// It subscribes to the playhead itself, so the rest of the screen doesn't
// redraw thirty times a second.
export function PreviewBar({ total, clip, onPlay, onBack, frames, frame, onFrame, onFull }: {
  total: number
  /** a clip from Media playing on its own, by name; null when the edit is shown */
  clip: string | null
  onPlay: () => void
  onBack: () => void
  /** the frames to choose from, in order, and the one the video is in now */
  frames: FrameChoice[]
  frame: string
  onFrame: (key: string) => void
  onFull: () => void
}) {
  const ph = useStore(phStore)
  const tr = useStore(transportStore)
  const btn = 'grid size-9 shrink-0 place-items-center rounded-lg text-white/90 hover:bg-white/10'
  return (
    <div className="flex h-14 shrink-0 items-center gap-3 px-5 text-white/85">
      {clip ? <>
        <span className="min-w-0 flex-1 truncate font-serif text-[16px]">Playing the clip {clip}</span>
        <button type="button" onClick={onBack}
                className="shrink-0 rounded-lg border border-white/25 px-3 py-1.5 font-serif text-[15px] text-white hover:bg-white/10">Back to the edit</button>
      </> : <>
        <button type="button" onClick={onPlay} aria-label={tr.playing ? 'Pause' : 'Play'} title={tr.playing ? 'Pause (Space)' : 'Play (Space)'} className={btn}>
          <Icon name={tr.playing ? 'pause' : 'play'} size={22} />
        </button>
        <span className="shrink-0 font-serif text-[16px] tabular-nums">{mss(ph)} / {mss(total)}</span>
        <input type="range" min={0} max={Math.max(total, 0.01)} step={0.01} value={Math.min(ph, total)} aria-label="Where in the video"
               onPointerDown={() => { if (transportStore.get().playing) transport.stop() }}
               onChange={(e) => { transport.seek(Number(e.target.value)); snapStore.set(null) }}
               className="min-w-0 flex-1 accent-[#7fb4dc]" />
      </>}
      <FramePicker frames={frames} current={frame} onPick={onFrame} />
      <button type="button" onClick={onFull} aria-label="Full screen" title="Full screen" className={btn}><Icon name="full" size={20} /></button>
    </div>
  )
}

export type FrameChoice = { key: string; name: string; ratio: string; about: string; wide: boolean }

// The frame as a dropdown, like CapCut's ratio menu: the button says what the
// video is now, a click opens the choices above it (the bar is at the bottom
// of the preview), each with the shape drawn, a pick closes it.
function FramePicker({ frames, current, onPick }: { frames: FrameChoice[]; current: string; onPick: (key: string) => void }) {
  const [open, setOpen] = useState(false)
  const box = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const away = (e: PointerEvent) => { if (box.current && !box.current.contains(e.target as Node)) setOpen(false) }
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    window.addEventListener('pointerdown', away)
    window.addEventListener('keydown', esc)
    return () => { window.removeEventListener('pointerdown', away); window.removeEventListener('keydown', esc) }
  }, [open])
  const now = frames.find((f) => f.key === current) ?? frames[0]
  return (
    <div ref={box} className="relative shrink-0">
      <button type="button" onClick={() => setOpen((o) => !o)} aria-haspopup="menu" aria-expanded={open}
              title="The shape of the video. The export follows it."
              className={`flex h-9 items-center gap-1.5 rounded-lg px-2 font-serif text-[15px] text-white/90 hover:bg-white/10 ${open ? 'bg-white/10' : ''}`}>
        <Icon name={now.wide ? 'wide' : 'frame'} size={18} />{now.name} {now.ratio}
        <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden className={`ml-0.5 transition-transform ${open ? '' : 'rotate-180'}`}>
          <path d="M2.5 4.5 6 8l3.5-3.5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>
      {open && (
        <div role="menu" className="absolute bottom-full right-0 z-40 mb-2 w-72 rounded-xl border border-line bg-panel p-1.5 shadow-2xl shadow-black/40">
          {frames.map((f) => {
            const on = f.key === now.key
            return (
              <button key={f.key} type="button" role="menuitemradio" aria-checked={on}
                      onClick={() => { setOpen(false); if (!on) onPick(f.key) }}
                      className={`flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-left hover:bg-raised ${on ? 'bg-raised' : ''}`}>
                <span className="grid size-9 shrink-0 place-items-center">
                  <span className={`block rounded-[3px] border-2 ${on ? 'border-accent' : 'border-zinc-400'} ${f.wide ? 'h-[18px] w-8' : 'h-8 w-[18px]'}`} />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block font-serif text-[16px] text-zinc-100">{f.name} <span className="text-zinc-400">{f.ratio}</span></span>
                  <span className="block font-serif text-[14px] text-zinc-300">{f.about}</span>
                </span>
                {on && <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden className="shrink-0 text-accent">
                  <path d="M3 8.5 6.5 12 13 4.5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                </svg>}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}

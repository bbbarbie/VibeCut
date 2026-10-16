import { phStore, snapStore, transport, transportStore, useStore } from '../transport'
import { Icon } from './icons'

const mss = (t: number) => `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, '0')}`

// Under the edit screen's preview, on black as in her reference picture
// (sarah, 2026-10-16): play, where you are of how long, a bar to drag through
// the edit, the frame the video is for (click to change it), full screen.
// It subscribes to the playhead itself, so the rest of the screen doesn't
// redraw thirty times a second.
export function PreviewBar({ total, clip, onPlay, onBack, frame, onFrame, onFull }: {
  total: number
  /** a clip from Media playing on its own, by name; null when the edit is shown */
  clip: string | null
  onPlay: () => void
  onBack: () => void
  frame: { label: string; ratio: string; wide: boolean }
  onFrame: () => void
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
      <button type="button" onClick={onFrame} title={`${frame.label}: click for the next frame. The export follows it.`}
              className="flex h-9 shrink-0 items-center gap-1.5 rounded-lg px-2 font-serif text-[15px] text-white/90 hover:bg-white/10">
        <Icon name={frame.wide ? 'wide' : 'frame'} size={18} />{frame.ratio}
      </button>
      <button type="button" onClick={onFull} aria-label="Full screen" title="Full screen" className={btn}><Icon name="full" size={20} /></button>
    </div>
  )
}

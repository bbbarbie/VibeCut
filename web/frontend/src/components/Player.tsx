import { useEffect, useRef, type RefObject } from 'react'
import type { Segment } from '../types'
import { dur } from '../format'

// One <video> element. Two drivers share it: a preview (a span or a queue
// of spans from the shelf or a storyboard card, via `segment`) and the
// timeline transport, which drives the element directly through `videoRef`.
// With no segment, this component leaves the element alone.
export function Player({ videoRef, segment, label, gap, onTime, onEnd, onPlayingChange }: {
  videoRef: RefObject<HTMLVideoElement | null>
  segment: Segment | null
  label: string
  gap: boolean
  onTime: (t: number) => void
  onEnd: () => void
  onPlayingChange: (playing: boolean) => void
}) {
  const seg = useRef<Segment | null>(null)

  useEffect(() => {
    const el = videoRef.current
    seg.current = segment
    if (!el || !segment) return
    const src = `/api/video/${segment.clipId}`
    const go = () => {
      el.currentTime = segment.start
      if (segment.autoplay) el.play().catch(() => {})
    }
    if (el.getAttribute('src') !== src) {
      el.setAttribute('src', src)
      el.addEventListener('loadedmetadata', go, { once: true })
      el.load()
    } else {
      go()
    }
  }, [segment, videoRef])

  return (
    <div className="flex min-h-0 flex-1 flex-col bg-black">
      <div className="relative min-h-0 flex-1">
        <video
          ref={videoRef}
          className={`absolute inset-0 size-full object-contain ${gap ? 'invisible' : ''}`}
          playsInline
          onTimeUpdate={(e) => {
            const s = seg.current
            if (!s) return
            const t = e.currentTarget.currentTime
            onTime(Math.max(0, t - s.start))
            if (t >= s.end - 0.04) {
              e.currentTarget.pause()
              onEnd()
            }
          }}
          onPlay={() => onPlayingChange(true)}
          onPause={() => onPlayingChange(false)}
        />
        {gap && <div className="absolute inset-0 grid place-items-center text-[11px] text-zinc-700">gap</div>}
      </div>
      <div className="flex h-7 shrink-0 items-center justify-between border-t border-line bg-panel px-3 text-[11px] text-muted">
        <span className="truncate">{label}</span>
        {segment && <span className="tabular-nums">{dur(segment.end - segment.start)}</span>}
      </div>
    </div>
  )
}

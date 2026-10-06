import type { Brief as BriefData } from '../types'
import { Button, Notice } from '../ui'

// Between the footage and the rough cut. There used to be a "What's this
// video about?" box here; sarah (2026-10-06) found it a step she didn't need,
// so what the video is gets read from the clips (pitch.guess) and the style
// questions open by themselves. This page is only what's behind the popup:
// a way back into it if it was closed, and on to the rough cut once answered.
export function Brief({ brief, busy, onStart, onContinue }: {
  brief: BriefData | null
  busy: boolean
  onStart: () => void
  onContinue: () => void
}) {
  return (
    <div className="grid min-h-0 flex-1 place-items-center p-8">
      <div className="w-full max-w-md text-center">
        <h2 className="font-serif text-[26px] text-zinc-100">A few quick questions</h2>
        <p className="mt-2 font-serif text-[17px] text-zinc-200">How long, how fast, and what goes on screen.</p>
        {brief ? (
          <Notice tone="ok" className="mt-6 flex items-center gap-3 text-left">
            <span className="min-w-0 flex-1 font-serif text-[16px]">{brief.said || 'Answered.'}</span>
            <Button size="sm" variant="primary" onClick={onContinue}>Rough cut →</Button>
          </Notice>
        ) : (
          <Button variant="primary" size="lg" className="mt-6" disabled={busy} onClick={onStart}>Start</Button>
        )}
      </div>
    </div>
  )
}

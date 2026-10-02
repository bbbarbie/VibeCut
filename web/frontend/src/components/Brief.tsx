import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Brief as BriefData, Capabilities, Clip, Session } from '../types'
import { Button, Notice, inputCls } from '../ui'
import { Voiceover } from './Voiceover'

// The brief: what the video is, in one line. The style questions follow
// (StyleQuestions.tsx), then the rough cut. Two opt-in side doors live
// here because they change what the story is built from: the creator's own
// narration, and talking-to-camera mode.

// Shown only if the footage can't be read for suggestions (pitch.py).
const EXAMPLES = ['A weekend in Tokyo, mostly the food', 'My sister’s wedding day', 'A day at the beach with friends']

export function Brief({ clips, brief, asking, caps, voiceover, onAsk, onVoiceover, onTalk, onContinue }: {
  clips: Clip[]
  brief: BriefData | null
  asking: boolean
  caps: Capabilities
  voiceover: Session['voiceover']
  onAsk: (text: string) => void
  onVoiceover: (text: string) => Promise<void>
  onTalk: () => void
  onContinue: () => void
}) {
  const [text, setText] = useState(brief?.message ?? '')
  const shots = clips.flatMap((c) => c.shots.map((s) => ({ ...s, clip: c })))
  const go = (t: string) => { if (t.trim() && !asking) onAsk(t.trim()) }
  // Three lines read from these clips, so a click can replace typing.
  const [ideas, setIdeas] = useState<string[] | null>(null)
  const clipKey = clips.map((c) => c.id).join(',')
  useEffect(() => {
    if (!clipKey) return
    let live = true
    api.suggestions()
      .then((r) => { if (live) setIdeas(r.suggestions.length ? r.suggestions : EXAMPLES) })
      .catch(() => { if (live) setIdeas(EXAMPLES) })
    return () => { live = false }
  }, [clipKey])
  return (
    <div className="min-h-0 flex-1 overflow-y-auto p-8">
      <div className="mx-auto max-w-2xl">
        <p className="text-[12px] text-muted">{clips.length} clip{clips.length === 1 ? '' : 's'} read</p>
        <h2 className="mt-1 font-serif text-[26px] text-zinc-100">What’s this video about?</h2>
        <p className="mt-1 text-[13px] text-zinc-400">One line is enough. Then a few quick questions about the style, and you’ll see what the rough cut leaves out before anything is built.</p>
        <form className="mt-4 flex gap-2" onSubmit={(e) => { e.preventDefault(); go(text) }}>
          <input autoFocus value={text} onChange={(e) => setText(e.target.value)} disabled={asking}
                 placeholder="e.g. a weekend in Tokyo, mostly the food" className={inputCls + ' text-[14px]'} />
          <Button variant="primary" size="lg" type="submit" disabled={asking || !text.trim()}>{asking ? 'Thinking…' : 'Next'}</Button>
        </form>
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          {ideas === null ? (
            <span className="text-[11px] text-muted"><span className="mr-1.5 inline-block size-1.5 animate-pulse rounded-full bg-accent" />Reading your clips for ideas…</span>
          ) : ideas.map((x) => (
            <button key={x} type="button" disabled={asking} onClick={() => { setText(x); go(x) }}
                    title="Use this and go on"
                    className="rounded-full border border-line px-2.5 py-1 text-[12px] text-zinc-300 hover:border-zinc-500 hover:text-zinc-100 disabled:opacity-40">{x}</button>
          ))}
        </div>

        {brief && (
          <Notice tone="ok" className="mt-4 flex items-center gap-3">
            <span className="min-w-0 flex-1">Brief written: “{brief.message}”{brief.said ? ` — ${brief.said}` : ''}</span>
            <Button size="sm" variant="primary" onClick={onContinue}>Rough cut →</Button>
          </Notice>
        )}

        <div className="mt-6 flex flex-wrap items-start gap-2">
          <Voiceover current={voiceover} busy={asking} onSubmit={onVoiceover} />
          <button type="button" onClick={caps.speech ? onTalk : undefined} disabled={!caps.speech}
                  title={caps.speech ? 'Transcribe on this Mac, cut pauses and retakes, add subtitles' : 'Transcribing runs on-device and needs macOS 26 with the Xcode command-line tools'}
                  className="rounded-lg border border-line px-3 py-1.5 text-left text-[12px] text-zinc-300 hover:bg-raised disabled:cursor-default disabled:opacity-50 disabled:hover:bg-transparent">
            Talking to camera? Cut it by what you said…
            {!caps.speech && <span className="block text-[10px] text-muted">needs macOS 26</span>}
          </button>
        </div>

        <div className="mt-8 grid grid-cols-6 gap-1.5">
          {shots.slice(0, 24).map((s) => <img key={s.id} src={s.thumb} alt="" className="aspect-video w-full rounded object-cover" />)}
        </div>
      </div>
    </div>
  )
}

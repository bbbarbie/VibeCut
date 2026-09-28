import { useEffect, useRef, useState } from 'react'
import { api, type RemixJob } from '../api'

// Remix: paste the reels you want yours to feel like, press one button, and
// the shelf becomes a finished short in their style -- then it lands on the
// storyboard so it can be edited like any other cut. The heavy lifting
// (learning the references, choosing shots, finding music and its drop,
// rendering) happens on the server; this only asks, waits and shows.
export function Remix({ onClose, onDone, canLinks = true }: { onClose: () => void; onDone: () => Promise<void> | void; canLinks?: boolean }) {
  const [links, setLinks] = useState('')
  const [title, setTitle] = useState('a day in my life')
  const [sub, setSub] = useState('')
  const [job, setJob] = useState<RemixJob | null>(null)
  const [error, setError] = useState<string | null>(null)
  const timer = useRef<number | null>(null)
  const busy = !!job && job.stage !== 'done' && job.stage !== 'error'

  useEffect(() => {
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape' && !busy) onClose() }
    window.addEventListener('keydown', esc)
    return () => { window.removeEventListener('keydown', esc); if (timer.current) window.clearTimeout(timer.current) }
  }, [busy, onClose])

  const go = async () => {
    setError(null)
    const refs = links.split(/\s+/).map((s) => s.trim()).filter(Boolean)
    if (!refs.length) { setError('Paste at least one link (TikTok, Reels, Shorts, or a file on this Mac).'); return }
    try {
      let s = await api.remixStart({ refs, title: title.trim() || undefined, sub: sub.trim() || undefined })
      setJob(s)
      while (s.stage !== 'done' && s.stage !== 'error') {
        await new Promise((r) => { timer.current = window.setTimeout(r, 700) })
        s = await api.remixStatus(s.id)
        setJob(s)
      }
      if (s.stage === 'done') await onDone()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  const stageText = job ? ({
    queued: 'Starting…', references: 'Watching your references…', choosing: 'Choosing the moments…',
    music: 'Finding music and its drop…', rendering: 'Rendering…', done: 'Done', error: 'Failed',
  } as const)[job.stage] : ''

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/60" onClick={() => { if (!busy) onClose() }}>
      <div className="w-[560px] max-w-[94vw] rounded-2xl border border-line bg-panel p-5 shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="mb-1 font-serif text-[24px] text-zinc-100">Build a short from reference reels</div>
        <p className="mb-3 text-[12px] leading-snug text-zinc-400">
          Paste one to three reels you want yours to feel like. VibeCut picks the moments from your clips, finds free music with a drop,
          and renders a finished short — which then becomes your story, editable like any other. Nothing of theirs ends up in your video:
          only their pace, their length, how they hold the first shot, and the kind of music they build on.
        </p>
        {!canLinks && <p className="mb-3 rounded-lg border border-amber-300/30 bg-amber-300/10 px-3 py-2 text-[12px] text-amber-100">
          Links can’t be fetched on this computer (no yt-dlp). Give the paths of reference files saved here instead, or install yt-dlp.
        </p>}

        {!job || job.stage === 'error' ? (
          <>
            <label className="block text-[11px] uppercase tracking-wide text-muted">Reference links</label>
            <textarea value={links} onChange={(e) => setLinks(e.target.value)} rows={3} spellCheck={false}
                      placeholder={'https://www.youtube.com/shorts/…\nhttps://www.instagram.com/reel/…'}
                      className="mt-1 w-full resize-none rounded-lg border border-line bg-ink px-3 py-2 font-mono text-[12px] text-zinc-200 outline-none focus:border-accent/60" />
            <div className="mt-3 grid grid-cols-2 gap-3">
              <div>
                <label className="block text-[11px] uppercase tracking-wide text-muted">Title over the opening</label>
                <input value={title} onChange={(e) => setTitle(e.target.value)}
                       className="mt-1 w-full rounded-lg border border-line bg-ink px-3 py-1.5 text-[13px] text-zinc-200 outline-none focus:border-accent/60" />
              </div>
              <div>
                <label className="block text-[11px] uppercase tracking-wide text-muted">A line under it (optional)</label>
                <input value={sub} onChange={(e) => setSub(e.target.value)} placeholder="as a columbia student"
                       className="mt-1 w-full rounded-lg border border-line bg-ink px-3 py-1.5 text-[13px] text-zinc-200 outline-none focus:border-accent/60" />
              </div>
            </div>
            {(error || job?.error) && <div className="mt-3 rounded-lg border border-red-500/40 bg-red-500/10 px-3 py-2 text-[12px] text-red-200">{error ?? job?.error}</div>}
            <div className="mt-4 flex items-center justify-end gap-2">
              <button type="button" onClick={onClose} className="rounded-lg px-3 py-1.5 text-[12px] text-muted hover:text-zinc-200">Cancel</button>
              <button type="button" onClick={go} className="rounded-lg bg-accent px-4 py-1.5 text-[13px] font-medium text-accent-ink hover:brightness-110">Make it</button>
            </div>
          </>
        ) : job.stage !== 'done' ? (
          <div>
            <div className="mb-2 flex items-center justify-between text-[12px]">
              <span className="text-zinc-200">{stageText}</span>
              <span className="text-muted">{Math.round(job.progress * 100)}% · {Math.round(job.elapsed)} s</span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-raised">
              <div className="h-full bg-accent transition-[width]" style={{ width: `${Math.round(job.progress * 100)}%` }} />
            </div>
            <ul className="mt-3 space-y-0.5 font-mono text-[11px] text-muted">
              {job.lines.map((l, i) => <li key={i} className="truncate">{l}</li>)}
            </ul>
            <p className="mt-3 text-[11px] text-muted">The first time takes a minute or two: references are downloaded and read, and a few tracks are fetched. After that it's seconds.</p>
          </div>
        ) : (
          <div>
            <video src={`/api/remix/${job.id}/file`} controls autoPlay playsInline className="mx-auto max-h-[52vh] rounded-lg bg-black" />
            <div className="mt-3 text-[12px] text-zinc-200">
              {job.shots} shots · {job.seconds}s to make{job.music ? <> · music: <span className="text-zinc-100">{job.music.title}</span> ({Math.round(job.music.bpm)} BPM)</> : ' · no usable track found online'}
            </div>
            {job.fingerprint && <div className="mt-1 text-[11px] text-muted">Style: {job.fingerprint}</div>}
            {job.music && (
              <div className="mt-2 rounded-lg border border-line bg-ink px-3 py-2 text-[11px] text-muted">
                Paste this in your post's caption — the music's licence asks for it:
                <div className="mt-1 select-all font-mono text-zinc-300">Music: {job.music.credit}</div>
              </div>
            )}
            <div className="mt-4 flex items-center justify-end gap-2">
              <a href={`/api/remix/${job.id}/file`} download className="rounded-lg border border-line px-3 py-1.5 text-[12px] text-zinc-200 hover:bg-raised">Download</a>
              <button type="button" onClick={() => { setJob(null) }} className="rounded-lg border border-line px-3 py-1.5 text-[12px] text-zinc-200 hover:bg-raised">Try other references</button>
              <button type="button" onClick={onClose} className="rounded-lg bg-accent px-4 py-1.5 text-[13px] font-medium text-accent-ink hover:brightness-110">Edit this cut</button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

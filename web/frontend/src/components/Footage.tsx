import { useRef } from 'react'
import type { Clip, ImportError, Shot } from '../types'
import { dur, when } from '../format'
import { Button, Notice, Progress, cx } from '../ui'

// The footage stage: what's in the project, how the reading is going, what
// couldn't be read (with a retry), and the one way forward. Every clip is
// only read; nothing is copied, moved or changed.

export type Importing = { text: string; frac: number | null } | null

export function Footage({ clips, importing, errors, vision, onPick, onRetry, onPreview, onNext, canContinue, briefDone }: {
  clips: Clip[]
  importing: Importing
  errors: ImportError[]
  vision: string
  onPick: (files: FileList) => void
  onRetry: (paths: string[]) => void
  onPreview: (clip: Clip, shot: Shot) => void
  onNext: () => void
  canContinue: boolean
  briefDone: boolean
}) {
  const folder = useRef<HTMLInputElement>(null)
  const files = useRef<HTMLInputElement>(null)
  const nShots = clips.reduce((n, c) => n + c.shots.length, 0)
  const total = clips.reduce((n, c) => n + c.duration, 0)
  const leftOut = clips.filter((c) => c.cut?.rejected).length
  const retryable = errors.map((e) => e.path).filter((p): p is string => !!p)

  const inputs = (
    <>
      {/* @ts-expect-error -- non-standard but supported everywhere that matters */}
      <input ref={folder} type="file" className="hidden" webkitdirectory="" multiple
             onChange={(e) => { if (e.target.files) onPick(e.target.files); e.target.value = '' }} />
      <input ref={files} type="file" className="hidden" multiple accept=".mp4,.mov,video/mp4,video/quicktime"
             onChange={(e) => { if (e.target.files) onPick(e.target.files); e.target.value = '' }} />
    </>
  )

  if (!clips.length && !importing && !errors.length) {
    return (
      <div className="grid min-h-0 flex-1 place-items-center p-8">
        {inputs}
        <div className="w-full max-w-xl rounded-2xl border border-dashed border-zinc-700 p-10 text-center">
          <h2 className="font-serif text-[26px] text-zinc-100">Start with your clips</h2>
          <p className="mt-2 text-[13px] text-zinc-400">Drag a folder of videos anywhere onto this window, or choose one. Every clip is read once, on this computer.</p>
          <div className="mt-6 flex justify-center gap-2">
            <Button variant="primary" size="lg" onClick={() => folder.current?.click()}>Choose a folder</Button>
            <Button size="lg" onClick={() => files.current?.click()}>Choose some clips</Button>
          </div>
          <p className="mt-4 text-[11px] text-muted">.mp4 and .mov · nothing is uploaded or changed</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {inputs}
      <div className="min-h-0 flex-1 overflow-y-auto p-5 pb-24">
        <div className="flex flex-wrap items-end gap-3">
          <div className="min-w-0">
            <h2 className="font-serif text-[24px] leading-tight text-zinc-100">Footage</h2>
            <p className="mt-0.5 text-[12px] text-zinc-400">
              {clips.length ? <>{clips.length} clip{clips.length === 1 ? '' : 's'} · {nShots} shot{nShots === 1 ? '' : 's'} · {dur(total)}{leftOut ? ` · ${leftOut} left out by the rough cut` : ''}</> : 'Nothing read yet'}
            </p>
          </div>
          <div className="ml-auto flex gap-2">
            <Button disabled={!!importing} onClick={() => files.current?.click()}>Add clips</Button>
            <Button disabled={!!importing} onClick={() => folder.current?.click()}>Add a folder</Button>
          </div>
        </div>

        {importing && (
          <div className="mt-4 rounded-xl border border-line bg-raised px-4 py-3" aria-live="polite">
            <Progress frac={importing.frac ?? 0.05} />
            <p className="mt-1.5 text-[12px] text-zinc-300">{importing.text}</p>
          </div>
        )}

        {errors.length > 0 && (
          <Notice tone="bad" className="mt-4">
            <div className="flex items-start gap-3">
              <div className="min-w-0 flex-1">
                <div className="font-medium">{errors.length} file{errors.length === 1 ? '' : 's'} couldn’t be read</div>
                <ul className="mt-1 space-y-0.5 text-[11px] text-rose-100/80">
                  {errors.map((e, i) => <li key={i} className="truncate" title={e.path ?? ''}>{e.path ? e.path.split('/').pop() : 'The import'} — {e.error}</li>)}
                </ul>
              </div>
              {retryable.length > 0 && <Button size="sm" disabled={!!importing} onClick={() => onRetry(retryable)}>Try again</Button>}
            </div>
          </Notice>
        )}

        {vision !== 'ready' && clips.length > 0 && (
          <p className="mt-3 text-[11px] text-muted">
            {vision === 'building' ? 'Building the on-device helper that names what’s in each shot…'
              : 'On-device labels (what’s in each shot, faces) need macOS — shots are grouped by colour instead, so “subject by subject” is cruder.'}
          </p>
        )}

        <div className="mt-5 grid grid-cols-[repeat(auto-fill,minmax(220px,1fr))] gap-3">
          {clips.map((c) => <ClipCard key={c.id} clip={c} onPreview={(s) => onPreview(c, s)} />)}
        </div>
      </div>

      <div className="absolute inset-x-0 bottom-0 flex items-center gap-4 border-t border-line bg-panel/95 px-5 py-3 backdrop-blur">
        <div className="min-w-0 text-[12px] text-zinc-400">
          {importing ? 'Reading your clips…'
            : !clips.length ? 'Add some clips to begin.'
              : briefDone ? 'The brief is written. Go on to the rough cut.' : 'Next, say what this video is — one line is enough.'}
        </div>
        <Button variant="primary" size="lg" className="ml-auto" disabled={!canContinue} onClick={onNext}>
          {briefDone ? 'Rough cut →' : 'What’s this video? →'}
        </Button>
      </div>
    </div>
  )
}

function ClipCard({ clip, onPreview }: { clip: Clip; onPreview: (s: Shot) => void }) {
  const first = clip.shots[0]
  const thrown = clip.cut?.rejected
  const portrait = clip.height > clip.width
  const labels = Array.from(new Set(clip.shots.flatMap((s) => s.labels.slice(0, 2).map(([l]) => l.replace(/_/g, ' '))))).slice(0, 3)
  return (
    <div className={cx('rounded-xl border border-line bg-raised/60 p-2', thrown && 'opacity-70')}>
      <button type="button" onClick={() => first && onPreview(first)} title="Watch" className="relative block aspect-video w-full overflow-hidden rounded-lg bg-black">
        {first && <img src={first.thumb} alt="" loading="lazy" draggable={false} className={cx('size-full', portrait ? 'object-contain' : 'object-cover', thrown && 'grayscale')} />}
        <span className="absolute bottom-1 right-1 rounded bg-black/70 px-1 text-[10px] tabular-nums text-zinc-200">{dur(clip.duration)}</span>
        {clip.shots.length > 1 && <span className="absolute left-1 top-1 rounded bg-black/70 px-1 text-[10px] text-zinc-200">{clip.shots.length} shots</span>}
      </button>
      {clip.shots.length > 1 && (
        <div className="mt-1.5 flex gap-0.5 overflow-hidden">
          {clip.shots.slice(0, 8).map((s) => (
            <button key={s.id} type="button" onClick={() => onPreview(s)} className="h-7 w-11 shrink-0 overflow-hidden rounded-sm bg-black hover:ring-1 hover:ring-accent">
              <img src={s.thumb} alt="" loading="lazy" className="size-full object-cover" />
            </button>
          ))}
        </div>
      )}
      <div className="mt-1.5 truncate px-0.5 text-[12px] text-zinc-200" title={clip.name}>{clip.name}</div>
      <div className="truncate px-0.5 text-[10px] text-muted">{when(clip.capture_time) || 'no date'}{clip.gps ? ' · GPS' : ''}{labels.length ? ` · ${labels.join(', ')}` : ''}</div>
      {thrown && (
        <div className="mt-1.5 rounded bg-rose-500/10 px-1.5 py-1 text-[10px] leading-snug text-rose-200">
          Rough cut leaves it out: {clip.cut!.override === 'reject' ? 'you threw it away' : clip.cut!.en}
        </div>
      )}
    </div>
  )
}

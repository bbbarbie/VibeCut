import { useRef } from 'react'
import type { Clip, Shot } from '../types'
import { dur, when } from '../format'

export const SHOT_MIME = 'application/x-vibecut-shot'

export function Shelf({ clips, activeShot, onPreview, onAdd, onPick, busy, onUseRejected }: {
  clips: Clip[]
  activeShot: string | null
  onPreview: (clip: Clip, shot: Shot) => void
  onAdd: (clip: Clip, shot: Shot) => void
  onPick: (files: FileList) => void
  busy: boolean
  onUseRejected?: (clip: Clip) => void
}) {
  const folderInput = useRef<HTMLInputElement>(null)
  const fileInput = useRef<HTMLInputElement>(null)
  const nShots = clips.reduce((n, c) => n + c.shots.length, 0)
  const total = clips.reduce((n, c) => n + c.duration, 0)

  return (
    <section className="flex min-h-0 min-w-0 flex-1 flex-col border-r border-line bg-panel">
      <header className="flex h-10 shrink-0 items-center gap-3 border-b border-line px-4">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-muted">Media</span>
        {clips.length > 0 && (
          <span className="text-[11px] text-zinc-500">
            {clips.length} clips · {nShots} shots · {dur(total)}
          </span>
        )}
        <div className="flex-1" />
        <button
          type="button"
          disabled={busy}
          onClick={() => fileInput.current?.click()}
          className="rounded-md border border-line px-2.5 py-1 text-[12px] text-zinc-300 hover:bg-raised disabled:opacity-40"
          title="Add individual clips to this session — already-indexed clips aren't redone"
        >
          Add clips
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => folderInput.current?.click()}
          className="rounded-md border border-line px-2.5 py-1 text-[12px] text-zinc-300 hover:bg-raised disabled:opacity-40"
        >
          Import folder
        </button>
        <input
          ref={fileInput}
          type="file"
          className="hidden"
          multiple
          accept=".mp4,.mov,video/mp4,video/quicktime"
          onChange={(e) => { if (e.target.files) onPick(e.target.files); e.target.value = '' }}
        />
        <input
          ref={folderInput}
          type="file"
          className="hidden"
          // @ts-expect-error -- non-standard but supported everywhere that matters
          webkitdirectory=""
          multiple
          onChange={(e) => { if (e.target.files) onPick(e.target.files); e.target.value = '' }}
        />
      </header>

      {clips.length === 0 ? (
        <button
          type="button"
          onClick={() => folderInput.current?.click()}
          className="m-4 grid flex-1 place-items-center rounded-xl border border-dashed border-zinc-700 text-center hover:border-zinc-500"
        >
          <div>
            <div className="text-[15px] text-zinc-200">Drop a folder or clips here</div>
            <div className="mt-1 text-[12px] text-muted">.mp4 and .mov · they stay on this Mac, nothing is uploaded</div>
          </div>
        </button>
      ) : (
        <div className="grid min-h-0 flex-1 auto-rows-min grid-cols-[repeat(auto-fill,minmax(148px,1fr))] gap-3 overflow-y-auto p-4">
          {clips.flatMap((c) => c.shots.map((s) => (
            <ShotCard
              key={s.id}
              clip={c}
              shot={s}
              active={activeShot === s.id}
              onPreview={() => onPreview(c, s)}
              onAdd={() => onAdd(c, s)}
              onUseRejected={onUseRejected ? () => onUseRejected(c) : undefined}
            />
          )))}
        </div>
      )}
    </section>
  )
}

function ShotCard({ clip, shot, active, onPreview, onAdd, onUseRejected }: {
  clip: Clip; shot: Shot; active: boolean; onPreview: () => void; onAdd: () => void; onUseRejected?: () => void
}) {
  const thrown = clip.cut?.rejected
  const w = clip.cut?.windows[shot.id]
  const q = shot.quality
  const portrait = clip.height > clip.width
  return (
    <div
      draggable
      onDragStart={(e) => {
        e.dataTransfer.setData(SHOT_MIME, shot.id)
        e.dataTransfer.effectAllowed = 'copy'
      }}
      onClick={onPreview}
      className={`group cursor-pointer select-none rounded-lg p-1 ${active ? 'bg-raised ring-1 ring-accent' : 'hover:bg-raised'} ${thrown ? 'opacity-60' : ''}`}
      title={shot.labels.map(([l]) => l.replace(/_/g, ' ')).join(', ')}
    >
      <div className="relative aspect-video overflow-hidden rounded-md bg-black">
        <img
          src={shot.thumb}
          loading="lazy"
          draggable={false}
          className={`size-full ${portrait ? 'object-contain' : 'object-cover'}`}
        />
        <span className="absolute bottom-1 right-1 rounded bg-black/70 px-1 text-[10px] tabular-nums text-zinc-200">
          {dur(shot.end - shot.start)}
        </span>
        <span
          className="absolute left-1 top-1 h-1 w-8 overflow-hidden rounded-full bg-black/60"
          title={`quality ${q.toFixed(2)}${shot.aesthetic != null ? ` · aesthetic ${shot.aesthetic.toFixed(2)}` : ''}`}
        >
          <span className={`block h-full ${q > 0.6 ? 'bg-emerald-400' : q > 0.4 ? 'bg-amber-300' : 'bg-rose-400'}`}
                style={{ width: `${Math.round(q * 100)}%` }} />
        </span>
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onAdd() }}
          className="absolute right-1 top-1 hidden size-6 place-items-center rounded-md bg-accent text-[15px] font-bold leading-none text-accent-ink group-hover:grid"
          title="Add to timeline"
        >
          +
        </button>
      </div>
      <div className="mt-1 truncate px-0.5 text-[11px] text-zinc-300">
        {clip.name}{clip.shots.length > 1 && <span className="text-muted"> · {shot.index + 1}/{clip.shots.length}</span>}
      </div>
      <div className="truncate px-0.5 text-[10px] text-muted">{when(clip.capture_time) || 'no date'}{clip.gps ? ' · GPS' : ''}</div>
      {thrown ? (
        <div className="mt-1 rounded bg-rose-500/10 px-1.5 py-1 text-[10px] leading-snug text-rose-200" title={clip.cut!.en}>
          Left out: {clip.cut!.override === 'reject' ? 'you threw this away' : clip.cut!.en}
          {onUseRejected && <button type="button" onClick={(e) => { e.stopPropagation(); onUseRejected() }}
                                    className="ml-1 underline">Use it</button>}
        </div>
      ) : w && (w[1] - w[0]) < (shot.end - shot.start) - 0.5 ? (
        <div className="px-0.5 text-[10px] text-zinc-500">keeps {(w[1] - w[0]).toFixed(0)}s of {(shot.end - shot.start).toFixed(0)}s</div>
      ) : null}
    </div>
  )
}

import { useEffect, useState } from 'react'
import { api } from '../api'
import { applyAll, learnRef } from '../borrow'
import { fromDataTransfer } from '../drop'
import type { LookFit, RefCard, RefSummary, RefTrait, Session } from '../types'
import { Button, Dialog, Field, inputCls, Notice, Pills, Progress, cx } from '../ui'

// Reference: learn a video's style (pace, transitions, cutting to the beat,
// colour, frame, music feel) and apply the parts the creator ticks, as one
// undoable turn. Only measurements are kept; the reference's frames and
// sound never go into the creator's video.

type Phase = { kind: 'pick' } | { kind: 'learning'; text: string; frac: number } | { kind: 'card'; card: RefCard }

const EVIDENCE: Record<string, string> = { meta: 'file info', still: 'still frames', motion: 'every frame', audio: 'the sound' }

export function BorrowStyle({ onClose, onApplied, onRemix }: { onClose: () => void; onApplied: (s: Session) => void; onRemix?: () => void }) {
  const [phase, setPhase] = useState<Phase>({ kind: 'pick' })
  const [source, setSource] = useState('')
  const [library, setLibrary] = useState<RefSummary[]>([])
  const [links, setLinks] = useState(true)
  const [error, setError] = useState('')
  const [dragging, setDragging] = useState(false)
  const busy = phase.kind === 'learning'

  useEffect(() => {
    api.refLibrary().then((r) => { setLibrary(r.references); setLinks(r.links) }).catch(() => {})
  }, [])

  const open = async (rid: string) => {
    setError('')
    try { setPhase({ kind: 'card', card: await api.refCard(rid) }) } catch (e) { setError((e as Error).message) }
  }

  // Paste and go: learn it, apply everything that fits, back to the editor.
  // The card only shows up when something needs a decision.
  const learn = async (src: string) => {
    setError('')
    let rid: string | null = null
    const progress = (text: string, frac: number) => setPhase({ kind: 'learning', text, frac })
    try {
      rid = await learnRef(src, progress)
      onApplied(await applyAll(rid, progress))
    } catch (e) {
      setError((e as Error).message)
      if (rid) await open(rid)
      else setPhase({ kind: 'pick' })
    }
  }

  const dropped = async (dt: DataTransfer) => {
    setDragging(false)
    const picked = await fromDataTransfer(dt)
    if (!picked.length) { setError('Drop one .mp4 or .mov file.'); return }
    const p = picked[0]
    try {
      const loc = await api.locate([{ name: p.file.name, size: p.file.size, mtime: p.file.lastModified, relpath: p.relpath }])
      const path = loc.resolved[p.relpath] ?? (await api.upload(p.file, p.relpath, 'references')).path
      await learn(path)
    } catch (e) { setError((e as Error).message) }
  }

  const forget = async (rid: string) => {
    const r = await api.refForget(rid)
    setLibrary(r.references)
  }

  return (
    <Dialog title="Make it feel like a video you love" width={620} busy={busy} onClose={onClose} id="borrow-title"
            sub="VibeCut measures the craft of a reference — how long shots are held, how one becomes the next, whether cuts land on the beat, the colour, the frame — and gives your footage the same feel. Nothing of theirs is copied into your video.">
      {phase.kind === 'pick' && (
        <div className="space-y-3">
          <form onSubmit={(e) => { e.preventDefault(); if (source.trim()) void learn(source) }} className="flex items-end gap-2">
            <div className="min-w-0 flex-1">
              <Field label={links ? 'A link, or a file path on this computer' : 'A file path on this computer (install yt-dlp for links)'}>
                <input value={source} onChange={(e) => { setSource(e.target.value); setError('') }} className={inputCls}
                       placeholder={links ? 'https://… or ~/Movies/a-vlog-i-love.mp4' : '~/Movies/a-vlog-i-love.mp4'} />
              </Field>
            </div>
            <Button variant="primary" type="submit" size="lg" disabled={!source.trim()}>Make mine feel like this</Button>
          </form>
          <div className={cx('rounded-xl border border-dashed px-3 py-4 text-center text-[12px]', dragging ? 'border-accent text-zinc-100' : 'border-zinc-700 text-muted')}
               onDragOver={(e) => { e.preventDefault(); setDragging(true) }} onDragLeave={() => setDragging(false)}
               onDrop={(e) => { e.preventDefault(); void dropped(e.dataTransfer) }}>
            …or drop the video file here
          </div>
          {links && <p className="text-[11px] text-muted">Links are fetched with yt-dlp and read on this computer only. Only use videos you’re allowed to download.</p>}
          {error && <Notice tone="bad">{error}</Notice>}
          {library.length > 0 && (
            <div className="rounded-xl border border-line bg-raised p-2">
              <div className="px-1 text-[11px] font-semibold uppercase tracking-wider text-muted">Styles you’ve learnt</div>
              {library.map((r) => (
                <div key={r.rid} className="mt-1 flex items-center gap-2">
                  <button type="button" title="Open to choose what to borrow" onClick={() => void open(r.rid)}
                          className="min-w-0 flex-1 rounded-md px-2 py-1.5 text-left hover:bg-zinc-800">
                    <span className="block truncate text-[13px] text-zinc-100">{r.title}</span>
                    <span className="block truncate text-[11px] text-muted">{r.summary.slice(0, 2).map((l) => l.replace(/^\w+\s+/, '')).join(' · ')}</span>
                  </button>
                  <button type="button" aria-label={`Forget ${r.title}`} title="Forget this style (and delete a downloaded copy)" onClick={() => void forget(r.rid)}
                          className="grid size-7 place-items-center rounded-md text-muted hover:bg-zinc-800 hover:text-zinc-100">✕</button>
                </div>
              ))}
            </div>
          )}
          {onRemix && (
            <p className="border-t border-line pt-3 text-[12px] text-zinc-400">
              Want a whole short built from reference reels instead — moments picked, free music with a drop, rendered?{' '}
              <button type="button" className="text-accent hover:underline" onClick={onRemix}>Build a short from reels…</button>
            </p>
          )}
        </div>
      )}

      {phase.kind === 'learning' && (
        <div aria-live="polite">
          <p className="text-[13px] text-zinc-300">{phase.text}</p>
          <Progress frac={Math.max(0.04, phase.frac)} className="mt-2" />
          <p className="mt-2 text-[11px] text-muted">Every frame is read once at a tiny size; that’s all the learning needs.</p>
        </div>
      )}

      {phase.kind === 'card' && error && <Notice tone="bad" className="mb-3">{error}</Notice>}
      {phase.kind === 'card' && <Card card={phase.card} onBack={() => setPhase({ kind: 'pick' })} onApplied={onApplied}
                                      onReload={() => void open(phase.card.reference.rid)} />}
    </Dialog>
  )
}

function Card({ card, onBack, onApplied, onReload }: { card: RefCard; onBack: () => void; onApplied: (s: Session) => void; onReload: () => void }) {
  const ref = card.reference
  const [on, setOn] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(card.traits.map((t) => [t.key, t.available && t.on])))
  const [strength, setStrength] = useState<'subtle' | 'full'>('full')
  const [look, setLook] = useState<LookFit | null>(null)
  const [lookError, setLookError] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const picked = card.traits.filter((t) => t.available && on[t.key]).map((t) => t.key)
  const hasLook = card.traits.some((t) => t.key === 'look' && t.available)

  useEffect(() => {
    if (!hasLook || !on.look || !card.has_story) return
    let live = true
    setLookError('')
    api.refLook(ref.rid, strength).then((l) => { if (live) setLook(l) }).catch((e) => { if (live) setLookError((e as Error).message) })
    return () => { live = false }
  }, [ref.rid, strength, on.look, hasLook, card.has_story])

  const apply = async () => {
    setBusy(true); setError('')
    try { onApplied(await api.refApply(ref.rid, picked, strength)) }
    catch (e) { setError((e as Error).message); setBusy(false) }
  }

  const pickTrack = async (id: string) => {
    try { await api.useTrack(id); onReload() } catch (e) { setError((e as Error).message) }
  }

  return (
    <div className="space-y-3">
      <div className="flex items-start gap-3 rounded-xl border border-line bg-raised px-3 py-2.5">
        <div className="min-w-0 flex-1">
          <div className="truncate text-[14px] text-zinc-100">{ref.title}</div>
          <div className="text-[11px] text-muted">{[ref.uploader, ref.url ? 'from a link' : 'from a file',
            ref.duration > ref.learnt_from_s + 1 ? `learnt from the first ${Math.round(ref.learnt_from_s / 60)} min` : null].filter(Boolean).join(' · ')}</div>
        </div>
        <Button size="sm" variant="ghost" onClick={onBack}>Another video</Button>
      </div>
      {!card.has_story && <Notice tone="warn"><strong>No story yet.</strong> A style is applied to an edit: pick one of the proposals first. This style stays saved under “Styles you’ve learnt”.</Notice>}
      <ul className="space-y-2">
        {card.traits.map((t) => <Trait key={t.key} t={t} on={!!on[t.key]} onToggle={(v) => setOn({ ...on, [t.key]: v })}>
          {t.key === 'look' && t.available && on.look && card.has_story && (
            <div className="mt-2 space-y-2">
              <div className="flex items-center gap-2 text-[12px] text-zinc-300">Strength <Pills values={['Subtle', 'Full']} selected={[strength === 'subtle' ? 'Subtle' : 'Full']} onPick={(v) => setStrength(v === 'Subtle' ? 'subtle' : 'full')} /></div>
              {lookError && <Notice tone="bad">{lookError}</Notice>}
              {look && <>
                <div className="flex gap-2 overflow-x-auto">{look.previews.map((p) => (
                  <figure key={p.after} className="flex shrink-0 gap-0.5">
                    <img src={p.before} alt="Your shot as filmed" className="h-16 rounded-l-md" /><img src={p.after} alt="Your shot with the borrowed look" className="h-16 rounded-r-md" />
                  </figure>
                ))}</div>
                <p className="text-[11px] text-muted">Before · after, on your own shots. {look.look_words.length ? `Yours would read: ${look.look_words.join(', ')}.` : ''} Colour shifts are capped, so the reference’s subject matter doesn’t tint your footage.</p>
              </>}
            </div>
          )}
          {t.key === 'music' && (
            <div className="mt-2 text-[11px] text-muted">
              {!card.music_folder ? <span>Choose your music folder under <b>Music</b> in the editor to find tracks of yours with this feel.</span>
                : card.music.length === 0 ? <span>Nothing in your music folder to compare yet.</span>
                  : card.music.map((m) => (
                    <div key={m.id} className="mt-1 flex flex-wrap items-center gap-2">
                      <span className="min-w-0 flex-1 truncate text-[12px] text-zinc-200">{m.title}<span className="block text-[10px] text-muted">{m.reason || 'closest of your tracks, loosely'}</span></span>
                      <audio controls preload="none" src={m.audio} className="h-7 max-w-[180px]" />
                      <Button size="sm" onClick={() => void pickTrack(m.id)}>Use under my edit</Button>
                    </div>
                  ))}
            </div>
          )}
        </Trait>)}
      </ul>
      {error && <Notice tone="bad">{error}</Notice>}
      <div className="flex flex-wrap items-center gap-3 border-t border-line pt-3">
        <p className="min-w-0 flex-1 text-[11px] text-muted">One change in your edit history — Undo takes all of it back. Transitions and bars show as you play; the grade appears in the export.</p>
        <Button variant="primary" disabled={busy || !picked.length || !card.has_story} onClick={() => void apply()}>
          {busy ? 'Applying…' : !card.has_story ? 'Your edit is still being made'
            : picked.length ? `Borrow ${picked.length === 1 ? 'this' : `these ${picked.length}`}` : 'Tick something to borrow'}
        </Button>
      </div>
    </div>
  )
}

function Trait({ t, on, onToggle, children }: { t: RefTrait; on: boolean; onToggle: (v: boolean) => void; children?: React.ReactNode }) {
  const can = t.available
  return (
    <li className={cx('rounded-xl border border-line px-3 py-2', !can && 'opacity-60')}>
      <label className="flex items-center gap-2">
        {t.how || t.why_not ? <input type="checkbox" checked={can && on} disabled={!can} onChange={(e) => onToggle(e.target.checked)} className="accent-[#1f5f8b]" />
          : <span className="size-2 rounded-full bg-zinc-600" />}
        <span className="text-[13px] text-zinc-100">{t.title}</span>
        <span className="flex flex-wrap gap-1">{t.words.map((w) => <span key={w} className="rounded-full border border-line px-1.5 text-[10px] text-zinc-300">{w}</span>)}</span>
      </label>
      {can && t.how && <p className="mt-1 text-[12px] text-zinc-400">{t.how}</p>}
      {t.why_not && <p className="mt-1 text-[12px] text-amber-200/80">{t.why_not}</p>}
      <p className="mt-0.5 text-[10px] text-muted">measured from {t.evidence.map((e) => EVIDENCE[e] ?? e).join(' + ')}</p>
      {children}
    </li>
  )
}

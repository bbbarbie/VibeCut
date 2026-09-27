import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { applyAll, learnRef } from '../borrow'
import { fromDataTransfer } from '../drop'
import type { LookFit, RefCard, RefSummary, RefTrait, Session } from '../types'

// Borrow a feeling: learn a reference video's style (pace, transitions,
// cutting to the beat, colour, frame, music feel) and apply the parts the
// creator ticks, as one undoable turn. Only measurements are kept; the
// reference's frames and sound never go into the creator's video.

type Phase = { kind: 'pick' } | { kind: 'learning'; text: string; frac: number } | { kind: 'card'; card: RefCard }

const EVIDENCE: Record<string, string> = { meta: 'file info', still: 'still frames', motion: 'every frame', audio: 'the sound' }

export function BorrowStyle({ onClose, onApplied }: { onClose: () => void; onApplied: (s: Session) => void }) {
  const dialog = useRef<HTMLDialogElement>(null)
  const [phase, setPhase] = useState<Phase>({ kind: 'pick' })
  const [source, setSource] = useState('')
  const [library, setLibrary] = useState<RefSummary[]>([])
  const [links, setLinks] = useState(true)
  const [error, setError] = useState('')
  const [dragging, setDragging] = useState(false)

  useEffect(() => { dialog.current?.showModal() }, [])
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

  return <dialog ref={dialog} className="tool-dialog borrow" aria-labelledby="borrow-title" onCancel={(e) => { e.preventDefault(); onClose() }}>
    <div className="tool-dialog-heading">
      <div><p className="creator-eyebrow">LEARN FROM A REFERENCE</p><h2 id="borrow-title">Borrow a feeling</h2></div>
      <button type="button" aria-label="Close" onClick={onClose}>✕</button>
    </div>

    {phase.kind === 'pick' && <div className="borrow-body">
      <p className="tool-description">Show VibeCut a video whose editing you love. It measures the craft — how long shots are held, how one becomes the next, whether cuts land on the beat, the colour, the frame — and gives <em>your</em> footage the same feel. Nothing of theirs is copied into your video.</p>
      <form onSubmit={(e) => { e.preventDefault(); if (source.trim()) void learn(source) }} className="borrow-source">
        <label className="creator-field"><span>{links ? 'A link, or a file path' : 'A file path (install yt-dlp for links)'}</span>
          <input value={source} onChange={(e) => { setSource(e.target.value); setError('') }}
                 placeholder={links ? 'https://… or ~/Movies/a-vlog-i-love.mp4' : '~/Movies/a-vlog-i-love.mp4'} />
        </label>
        <button type="submit" className="creator-primary" disabled={!source.trim()}>Make mine feel like this</button>
      </form>
      <div className={`borrow-drop ${dragging ? 'borrow-drop-on' : ''}`}
           onDragOver={(e) => { e.preventDefault(); setDragging(true) }} onDragLeave={() => setDragging(false)}
           onDrop={(e) => { e.preventDefault(); void dropped(e.dataTransfer) }}>
        …or drop the video file here
      </div>
      {links && <p className="borrow-fine">Links are fetched with yt-dlp for analysis on this Mac only. Only use videos you’re allowed to download.</p>}
      {error && <p className="creator-error" role="alert">{error}</p>}
      {library.length > 0 && <div className="borrow-lib">
        <strong>Styles you’ve learnt</strong>
        {library.map((r) => <div key={r.rid} className="borrow-lib-row">
          <button type="button" title="Open to choose what to borrow" onClick={() => void open(r.rid)}>
            <span>{r.title}</span>
            <small>{r.summary.slice(0, 2).map((l) => l.replace(/^\w+\s+/, '')).join(' · ')}</small>
          </button>
          <button type="button" aria-label={`Forget ${r.title}`} title="Forget this style (and delete a downloaded copy)" onClick={() => void forget(r.rid)}>✕</button>
        </div>)}
      </div>}
    </div>}

    {phase.kind === 'learning' && <div className="borrow-body" aria-live="polite">
      <p className="tool-description">{phase.text}</p>
      <div className="borrow-bar"><div style={{ width: `${Math.max(4, phase.frac * 100)}%` }} /></div>
      <p className="borrow-fine">Every frame is read once at a tiny size; that’s all the learning needs.</p>
    </div>}

    {phase.kind === 'card' && error && <p className="creator-error" role="alert">{error}</p>}
    {phase.kind === 'card' && <Card card={phase.card} onBack={() => setPhase({ kind: 'pick' })} onApplied={onApplied}
                                    onReload={() => void open(phase.card.reference.rid)} />}
  </dialog>
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

  const useTrack = async (id: string) => {
    try { await api.useTrack(id); onReload() } catch (e) { setError((e as Error).message) }
  }

  return <div className="borrow-body">
    <div className="borrow-ref">
      <strong>{ref.title}</strong>
      <small>{[ref.uploader, ref.url ? 'from a link' : 'from a file',
               ref.duration > ref.learnt_from_s + 1 ? `learnt from the first ${Math.round(ref.learnt_from_s / 60)} min` : null]
        .filter(Boolean).join(' · ')}</small>
      <button type="button" onClick={onBack}>Another video</button>
    </div>
    {!card.has_story && <p className="tool-style borrow-nostory"><strong>No story yet.</strong> A style is applied to an edit: go back to the editor, drop your footage, say what the video is and pick one of the three stories. Then come back here — this style stays saved under “Styles you’ve learnt”.</p>}
    <ul className="borrow-traits">
      {card.traits.map((t) => <Trait key={t.key} t={t} on={!!on[t.key]} onToggle={(v) => setOn({ ...on, [t.key]: v })}>
        {t.key === 'look' && t.available && on.look && card.has_story && <div className="borrow-look">
          <fieldset className="creator-choice"><legend>Strength</legend><div>
            {(['subtle', 'full'] as const).map((s) => <button type="button" key={s} aria-pressed={strength === s} onClick={() => setStrength(s)}>
              {s === 'subtle' ? 'Subtle' : 'Full'}</button>)}
          </div></fieldset>
          {lookError && <p className="creator-error">{lookError}</p>}
          {look && <>
            <div className="borrow-previews">{look.previews.map((p) => <figure key={p.after}>
              <img src={p.before} alt="Your shot as filmed" /><img src={p.after} alt="Your shot with the borrowed look" />
            </figure>)}</div>
            <small>Before · after, on your own shots. {look.look_words.length ? `Yours would read: ${look.look_words.join(', ')}.` : ''} Colour shifts are capped, so the reference’s subject matter (a blue sea, a sunset) doesn’t tint your footage.</small>
          </>}
        </div>}
        {t.key === 'music' && <div className="borrow-music">
          {!card.music_folder ? <small>Choose your music folder under <b>Music</b> in the editor to find tracks of yours with this feel.</small>
            : card.music.length === 0 ? <small>Nothing in your music folder to compare yet.</small>
              : card.music.map((m) => <div key={m.id} className="borrow-track">
                <div><span>{m.title}</span><small>{m.reason || 'closest of your tracks, loosely'}</small></div>
                <audio controls preload="none" src={m.audio} />
                <button type="button" onClick={() => void useTrack(m.id)}>Use under my edit</button>
              </div>)}
        </div>}
      </Trait>)}
    </ul>
    {error && <p className="creator-error" role="alert">{error}</p>}
    <div className="tool-actions tool-actions-live">
      <p className="borrow-fine">One change in your edit history — Undo takes all of it back. Transitions and bars show as you play; the grade appears in the export.</p>
      <button type="button" className={`creator-primary ${busy ? '' : 'borrow-blocked'}`} disabled={busy || !picked.length || !card.has_story}
              onClick={() => void apply()}>
        {busy ? 'Applying…' : !card.has_story ? 'Choose a story first'
          : picked.length ? `Borrow ${picked.length === 1 ? 'this' : `these ${picked.length}`}` : 'Tick something to borrow'}
      </button>
    </div>
  </div>
}

function Trait({ t, on, onToggle, children }: { t: RefTrait; on: boolean; onToggle: (v: boolean) => void; children?: React.ReactNode }) {
  const can = t.available
  return <li className={`borrow-trait ${can ? '' : 'borrow-trait-off'}`}>
    <label>
      {t.how || t.why_not ? <input type="checkbox" checked={can && on} disabled={!can} onChange={(e) => onToggle(e.target.checked)} /> : <span className="borrow-dot" />}
      <span className="borrow-trait-title">{t.title}</span>
      <span className="borrow-chips">{t.words.map((w) => <span key={w}>{w}</span>)}</span>
    </label>
    {can && t.how && <p>{t.how}</p>}
    {t.why_not && <p className="borrow-why">{t.why_not}</p>}
    <small className="borrow-evidence">measured from {t.evidence.map((e) => EVIDENCE[e] ?? e).join(' + ')}</small>
    {children}
  </li>
}

import { useEffect, useRef, useState } from 'react'
import { CREATIVE_TOOLS, LIVE_TOOL_IDS, REFERENCE_TOOL_ID, TITLES_TOOL_ID, makeBrief, readBriefs, storeBrief, type CreativeTool, type FeatureBrief } from '../creativeTools'
import type { Session } from '../types'
import { BorrowStyle } from './BorrowStyle'
import { emptyProfile, loadProfile } from '../profile'
import './CreatorProfile.css'
import './CreativeTools.css'

export function CreativeTools({ onClose, onProfile, onApplyPlan, onApplyTitles, onStyled }: {
  onClose: () => void
  onProfile: () => void
  onApplyPlan: (brief: FeatureBrief) => Promise<void>
  onApplyTitles: (brief: FeatureBrief) => Promise<void>
  onStyled: (s: Session) => void
}) {
  const [selected, setSelected] = useState<CreativeTool | null>(null)
  const [initial] = useState(() => {
    try { return { briefs: readBriefs(window.localStorage), error: '' } }
    catch { return { briefs: {}, error: 'Saved briefs could not be read. You can still configure and download a brief; existing data will not be overwritten.' } }
  })
  const [briefs, setBriefs] = useState<Record<string, FeatureBrief>>(initial.briefs)
  const storageError = initial.error
  return <main className="creator-page">
    <header className="creator-topbar"><button type="button" onClick={onClose}>← Back to editor</button>
      <span className="creator-wordmark">Vibe<span>Cut</span></span><button type="button" onClick={onProfile}>Creator profile ↗</button></header>
    <div className="creator-body">
      <div className="creator-heading"><div><p className="creator-eyebrow">YOUR CREATIVE TOOLBOX</p>
        <h1>More ways to <em>tell it.</em></h1><p>Start with your footage and tell VibeCut the story you want.</p></div><span className="creator-badge">3 live · 4 coming soon</span></div>
      <p className="tools-notice"><strong>Plan my edit</strong>, <strong>Titles &amp; motion</strong> and <strong>Borrow a feeling</strong> work now: they change your storyboard through VibeCut’s editing engine, show what changed, and keep it undoable. The other tools are clearly marked until their pipelines are built.</p>
      {storageError && <p role="alert" className="creator-error">{storageError}</p>}
      <div className="tools-grid">{CREATIVE_TOOLS.map((tool) => {
        const live = LIVE_TOOL_IDS.includes(tool.id)
        return <button type="button" key={tool.id} className={`tool-card ${live ? 'tool-card-live' : 'tool-card-soon'}`} disabled={!live} onClick={() => setSelected(tool)}>
          <div className="tool-card-top"><span className="tool-icon" aria-hidden="true">{tool.icon}</span><span>{live ? 'AVAILABLE NOW' : 'COMING SOON'}</span></div>
          <h2>{tool.title}</h2><p>{tool.subtitle}</p><div className="tool-card-bottom"><span>{live ? (tool.id === REFERENCE_TOOL_ID ? 'Learn from a video' : briefs[tool.id] ? 'Edit again' : tool.id === TITLES_TOOL_ID ? 'Add words on screen' : 'Edit my footage') : 'Not available yet'}</span>{live && <span aria-hidden="true">↗</span>}</div>
        </button>
      })}</div>
      <p className="tools-footnote">Live tools use the same local footage, operation log, diff and Undo controls as chat editing. No new provider is called; words on screen are drawn on this Mac, and reference videos are analysed on this Mac.</p>
    </div>
    {selected?.id === REFERENCE_TOOL_ID && <BorrowStyle onClose={() => setSelected(null)} onApplied={(s) => { setSelected(null); onStyled(s); onClose() }} />}
    {selected && selected.id !== REFERENCE_TOOL_ID && <ToolDialog key={selected.id} tool={selected} saved={briefs[selected.id]} onClose={() => setSelected(null)} onApplied={onClose}
      onApplyPlan={selected.id === TITLES_TOOL_ID ? onApplyTitles : onApplyPlan} onSaved={setBriefs} />}
  </main>
}

function ToolDialog({ tool, saved, onClose, onApplied, onApplyPlan, onSaved }: {
  tool: CreativeTool
  saved?: FeatureBrief
  onClose: () => void
  onApplied: () => void
  onApplyPlan: (brief: FeatureBrief) => Promise<void>
  onSaved: (b: Record<string, FeatureBrief>) => void
}) {
  const dialog = useRef<HTMLDialogElement>(null)
  const [option, setOption] = useState<string>(saved?.option ?? tool.options[0])
  const [request, setRequest] = useState(saved?.request ?? '')
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')
  const [applying, setApplying] = useState(false)
  const [discard, setDiscard] = useState(false)
  const [baseline, setBaseline] = useState(JSON.stringify([option, request]))
  const dirty = baseline !== JSON.stringify([option, request])
  const [creator] = useState(() => {
    try { return loadProfile(window.localStorage) }
    catch { return { profile: emptyProfile(), error: 'Saved profile unavailable; default style will be attached.' } }
  })
  useEffect(() => { dialog.current?.showModal() }, [])
  useEffect(() => {
    const warn = (e: BeforeUnloadEvent) => { if (dirty) e.preventDefault() }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [dirty])
  const close = () => dirty ? setDiscard(true) : onClose()
  const changed = () => { setStatus(''); setError(''); setDiscard(false) }
  const titles = tool.id === TITLES_TOOL_ID
  const apply = async () => {
    try {
      const brief = makeBrief(tool, option, request, '', creator.profile)
      setApplying(true); setError(''); setStatus(titles ? 'Adding words on screen to your storyboard…' : 'VibeCut is reading your storyboard and applying reversible changes…')
      await onApplyPlan(brief)
      try { onSaved(storeBrief(window.localStorage, brief)) } catch { /* the edit succeeded; local convenience storage is optional */ }
      setBaseline(JSON.stringify([option, request]))
      setApplying(false)
      onApplied()
    } catch (e) {
      setError((e as Error).message)
      setStatus('')
      setApplying(false)
    }
  }
  return <dialog ref={dialog} className="tool-dialog" aria-labelledby="tool-title" onCancel={e => { e.preventDefault(); close() }}>
    <div className="tool-dialog-heading"><div><p className="creator-eyebrow">{titles ? 'WORDS ON SCREEN' : 'EDIT WITH AI'}</p><h2 id="tool-title">{tool.title}</h2></div><button type="button" aria-label="Close feature" disabled={applying} onClick={close}>✕</button></div>
    <form onSubmit={e => { e.preventDefault(); void apply() }}>
      <p className="tool-description">{tool.subtitle}</p>
      <fieldset className="creator-choice"><legend>Choose a direction</legend><div>{tool.options.map(o => <button type="button" key={o} aria-pressed={option === o} onClick={() => { setOption(o); changed() }}>{o}</button>)}</div></fieldset>
      <label className="creator-field"><span>{tool.input}</span><textarea rows={4} value={request} maxLength={2000} placeholder={tool.placeholder} onChange={e => { setRequest(e.target.value); changed() }} /></label>
      {titles ? <>
        <div className="tool-style"><strong>Your style is used</strong><p>{creator.profile.font} font · <span style={{ color: creator.profile.color }}>●</span> {creator.profile.color} accent · captions {creator.profile.captionPosition.toLowerCase()}{creator.profile.name ? ` · name tag “${creator.profile.name}”` : ''}</p><small>One font and colour for the whole video. Change them any time under Words on screen.</small>{creator.error && <p className="creator-error">{creator.error}</p>}</div>
        <div className="tool-future tool-live-note"><strong>What happens next</strong><ul><li>Only what’s missing is added — nothing you placed is replaced.</li><li>Words come from your parts, filming dates, voiceover and profile; nothing is invented.</li><li>Each one hangs off a part or shot and moves with it. Edit, drag, or Undo them in the editor; Export renders them.</li></ul><p>You need a chosen story first. If something can’t be added (no voiceover for captions, one filming day for dates), VibeCut says so.</p></div>
      </> : <>
      <div className="tool-style"><strong>Creator direction included</strong><p>{creator.profile.name || 'Your creator profile'} · {creator.profile.pace.toLowerCase()} pacing{creator.profile.avoid ? ` · avoid ${creator.profile.avoid}` : ''}</p><small>The editing engine receives this direction with your request.</small>{creator.error && <p className="creator-error">{creator.error}</p>}</div>
      <div className="tool-future tool-live-note"><strong>What happens next</strong><ul><li>VibeCut reads the current storyboard—not your raw video pixels.</li><li>It applies the smallest valid set of editing operations.</li><li>The editor shows exactly what changed, with Undo.</li></ul><p>If your footage needs the rough-cut approval first, or AI editing is not configured, VibeCut will tell you here.</p></div>
      </>}
      {error && <p className="creator-error" role="alert">{error}</p>}
      <p role="status" className="tool-status">{status}</p>
      {discard && <div className="tool-discard" role="alert"><p>Leave without applying this direction?</p><button type="button" onClick={() => setDiscard(false)}>Keep editing</button><button type="button" onClick={onClose}>Discard changes</button></div>}
      <div className="tool-actions tool-actions-live"><button type="submit" disabled={applying} className="creator-primary">{applying ? 'Applying…' : titles ? 'Add to my video' : 'Apply to storyboard'}</button></div>
    </form>
  </dialog>
}

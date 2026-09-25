import { useEffect, useRef, useState } from 'react'
import { CREATIVE_TOOLS, LIVE_TOOL_ID, makeBrief, readBriefs, storeBrief, type CreativeTool, type FeatureBrief } from '../creativeTools'
import { emptyProfile, loadProfile } from '../profile'
import './CreatorProfile.css'
import './CreativeTools.css'

export function CreativeTools({ onClose, onProfile, onApplyPlan }: {
  onClose: () => void
  onProfile: () => void
  onApplyPlan: (brief: FeatureBrief) => Promise<void>
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
        <h1>More ways to <em>tell it.</em></h1><p>Start with your footage and tell VibeCut the story you want.</p></div><span className="creator-badge">1 live · 6 coming soon</span></div>
      <p className="tools-notice"><strong>Plan my edit works now:</strong> it sends your direction through VibeCut’s existing editing engine, records the changes in chat, and keeps them undoable. The other tools are clearly marked until their generation pipelines are built.</p>
      {storageError && <p role="alert" className="creator-error">{storageError}</p>}
      <div className="tools-grid">{CREATIVE_TOOLS.map((tool) => {
        const live = tool.id === LIVE_TOOL_ID
        return <button type="button" key={tool.id} className={`tool-card ${live ? 'tool-card-live' : 'tool-card-soon'}`} disabled={!live} onClick={() => setSelected(tool)}>
          <div className="tool-card-top"><span className="tool-icon" aria-hidden="true">{tool.icon}</span><span>{live ? 'AVAILABLE NOW' : 'COMING SOON'}</span></div>
          <h2>{tool.title}</h2><p>{tool.subtitle}</p><div className="tool-card-bottom"><span>{live ? (briefs[tool.id] ? 'Edit again' : 'Edit my footage') : 'Not available yet'}</span>{live && <span aria-hidden="true">↗</span>}</div>
        </button>
      })}</div>
      <p className="tools-footnote">The live tool uses the same local footage, operation log, diff and Undo controls as chat editing. No new provider is called.</p>
    </div>
    {selected && <ToolDialog key={selected.id} tool={selected} saved={briefs[selected.id]} onClose={() => setSelected(null)} onApplied={onClose} onApplyPlan={onApplyPlan} onSaved={setBriefs} />}
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
  const apply = async () => {
    try {
      const brief = makeBrief(tool, option, request, '', creator.profile)
      setApplying(true); setError(''); setStatus('VibeCut is reading your storyboard and applying reversible changes…')
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
    <div className="tool-dialog-heading"><div><p className="creator-eyebrow">EDIT WITH AI</p><h2 id="tool-title">{tool.title}</h2></div><button type="button" aria-label="Close feature" disabled={applying} onClick={close}>✕</button></div>
    <form onSubmit={e => { e.preventDefault(); void apply() }}>
      <p className="tool-description">{tool.subtitle}</p>
      <fieldset className="creator-choice"><legend>Choose a direction</legend><div>{tool.options.map(o => <button type="button" key={o} aria-pressed={option === o} onClick={() => { setOption(o); changed() }}>{o}</button>)}</div></fieldset>
      <label className="creator-field"><span>{tool.input}</span><textarea rows={4} value={request} maxLength={2000} placeholder={tool.placeholder} onChange={e => { setRequest(e.target.value); changed() }} /></label>
      <div className="tool-style"><strong>Creator direction included</strong><p>{creator.profile.name || 'Your creator profile'} · {creator.profile.pace.toLowerCase()} pacing{creator.profile.avoid ? ` · avoid ${creator.profile.avoid}` : ''}</p><small>The editing engine receives this direction with your request.</small>{creator.error && <p className="creator-error">{creator.error}</p>}</div>
      <div className="tool-future tool-live-note"><strong>What happens next</strong><ul><li>VibeCut reads the current storyboard—not your raw video pixels.</li><li>It applies the smallest valid set of editing operations.</li><li>The editor shows exactly what changed, with Undo.</li></ul><p>If your footage needs the rough-cut approval first, or AI editing is not configured, VibeCut will tell you here.</p></div>
      {error && <p className="creator-error" role="alert">{error}</p>}
      <p role="status" className="tool-status">{status}</p>
      {discard && <div className="tool-discard" role="alert"><p>Leave without applying this direction?</p><button type="button" onClick={() => setDiscard(false)}>Keep editing</button><button type="button" onClick={onClose}>Discard changes</button></div>}
      <div className="tool-actions tool-actions-live"><button type="submit" disabled={applying} className="creator-primary">{applying ? 'Applying…' : 'Apply to storyboard'}</button></div>
    </form>
  </dialog>
}

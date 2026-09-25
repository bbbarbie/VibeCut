import { useEffect, useRef, useState } from 'react'
import { CREATIVE_TOOLS, makeBrief, readBriefs, storeBrief, type CreativeTool, type FeatureBrief } from '../creativeTools'
import { emptyProfile, loadProfile, safeReference } from '../profile'
import './CreatorProfile.css'
import './CreativeTools.css'

export function CreativeTools({ onClose, onProfile }: { onClose: () => void; onProfile: () => void }) {
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
        <h1>More ways to <em>tell it.</em></h1><p>Start with an idea. Choose a feature and shape a brief around your own style.</p></div><span className="creator-badge">Feature previews</span></div>
      <p className="tools-notice">These buttons configure and save briefs. Video generation, reference analysis and rendering are not connected yet. Your editor and original footage stay unchanged.</p>
      {storageError && <p role="alert" className="creator-error">{storageError}</p>}
      <div className="tools-grid">{CREATIVE_TOOLS.map((tool, i) => <button type="button" key={tool.id} className="tool-card" onClick={() => setSelected(tool)}>
        <div className="tool-card-top"><span className="tool-icon" aria-hidden="true">{tool.icon}</span><span>0{i + 1} / PLAN</span></div>
        <h2>{tool.title}</h2><p>{tool.subtitle}</p><div className="tool-card-bottom"><span>{briefs[tool.id] ? 'Edit saved brief' : 'Create a brief'}</span><span aria-hidden="true">↗</span></div>
      </button>)}</div>
      <p className="tools-footnote">Inspired by the seven video workflows we reviewed. No third-party plugins are installed or called by these buttons.</p>
    </div>
    {selected && <ToolDialog key={selected.id} tool={selected} saved={briefs[selected.id]} onClose={() => setSelected(null)} onSaved={setBriefs} />}
  </main>
}

function ToolDialog({ tool, saved, onClose, onSaved }: { tool: CreativeTool; saved?: FeatureBrief; onClose: () => void; onSaved: (b: Record<string, FeatureBrief>) => void }) {
  const dialog = useRef<HTMLDialogElement>(null)
  const [option, setOption] = useState<string>(saved?.option ?? tool.options[0])
  const [request, setRequest] = useState(saved?.request ?? '')
  const [reference, setReference] = useState(saved?.reference ?? '')
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')
  const [discard, setDiscard] = useState(false)
  const [baseline, setBaseline] = useState(JSON.stringify([option, request, reference]))
  const dirty = baseline !== JSON.stringify([option, request, reference])
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
  const build = () => {
    if (reference.trim() && !safeReference(reference.trim())) throw new Error('Use a full http:// or https:// reference link, or leave it empty.')
    return makeBrief(tool, option, request, reference, creator.profile)
  }
  const save = () => {
    try {
      const brief = build()
      onSaved(storeBrief(window.localStorage, brief))
      setBaseline(JSON.stringify([option, request, reference])); setStatus('Brief saved in this browser. No video has been generated.'); setError(''); setDiscard(false)
    } catch (e) { setError(`Could not save: ${(e as Error).message}`) }
  }
  const download = () => {
    try {
      const brief = build()
      const objectUrl = URL.createObjectURL(new Blob([JSON.stringify(brief, null, 2)], { type: 'application/json' }))
      const a = document.createElement('a'); a.href = objectUrl; a.download = `vibecut-${tool.id}-brief.json`; a.click()
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000)
      setError(''); setStatus('Brief downloaded as JSON. This is an editing plan, not a rendered video.')
    } catch (e) { setError((e as Error).message) }
  }
  return <dialog ref={dialog} className="tool-dialog" aria-labelledby="tool-title" onCancel={e => { e.preventDefault(); close() }}>
    <div className="tool-dialog-heading"><div><p className="creator-eyebrow">CONFIGURE A BRIEF</p><h2 id="tool-title">{tool.title}</h2></div><button type="button" aria-label="Close feature" onClick={close}>✕</button></div>
    <form onSubmit={e => { e.preventDefault(); save() }}>
      <p className="tool-description">{tool.subtitle}</p>
      <fieldset className="creator-choice"><legend>Choose a direction</legend><div>{tool.options.map(o => <button type="button" key={o} aria-pressed={option === o} onClick={() => { setOption(o); changed() }}>{o}</button>)}</div></fieldset>
      <label className="creator-field"><span>{tool.input}</span><textarea rows={4} value={request} maxLength={2000} placeholder={tool.placeholder} onChange={e => { setRequest(e.target.value); changed() }} /></label>
      <label className="creator-field"><span>Reference link · optional</span><input value={reference} inputMode="url" maxLength={2048} placeholder="https://…" onChange={e => { setReference(e.target.value); changed() }} /></label>
      {creator.profile.references.length > 0 && <label className="creator-field"><span>Or choose from your profile</span><select value="" onChange={e => { setReference(e.target.value); changed() }}><option value="">Choose a saved reference…</option>{creator.profile.references.map(r => <option key={r.url} value={r.url}>{r.note || r.url}</option>)}</select></label>}
      <div className="tool-style"><strong>Style attached to your brief</strong><p>{creator.profile.name || 'Your creator profile'} · {creator.profile.font} captions · {creator.profile.color} · {creator.profile.pace.toLowerCase()} pacing</p><small>Your saved profile is captured when you open this feature.</small>{creator.error && <p className="creator-error">{creator.error}</p>}</div>
      <div className="tool-future"><strong>When connected, this feature will produce</strong><ul>{tool.outputs.map(o => <li key={o}>{o}</li>)}</ul><p>{tool.note}</p><details><summary>Implementation status</summary><p>Not connected: {tool.needs}</p><p>Research source: {tool.source}.</p></details></div>
      {error && <p className="creator-error" role="alert">{error}</p>}
      <p role="status" className="tool-status">{status}</p>
      {discard && <div className="tool-discard" role="alert"><p>Leave without saving this brief?</p><button type="button" onClick={() => setDiscard(false)}>Keep editing</button><button type="button" onClick={onClose}>Discard changes</button></div>}
      <div className="tool-actions"><button type="button" className="creator-secondary" onClick={download}>Download brief</button><button type="submit" className="creator-primary">Save brief</button></div>
    </form>
  </dialog>
}

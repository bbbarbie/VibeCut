import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react'
import { emptyProfile, FONTS, loadProfile, PACES, PLATFORMS, safeReference, saveProfile, VIBES, type CreatorProfile as Profile } from '../profile'
import './CreatorProfile.css'

export function CreatorProfile({ onClose, onTools }: { onClose: () => void; onTools: () => void }) {
  const [initial] = useState(() => {
    try { return loadProfile(window.localStorage) }
    catch { return { profile: emptyProfile(), error: 'Browser storage is unavailable. You can explore your style, but it cannot be saved here.' } }
  })
  const [profile, setProfile] = useState(initial.profile)
  const [saved, setSaved] = useState(initial.profile)
  const [error, setError] = useState<string | null>(initial.error)
  const [message, setMessage] = useState('')
  const [leaving, setLeaving] = useState(false)
  const [url, setUrl] = useState('')
  const [referenceNote, setReferenceNote] = useState('')
  const [referenceError, setReferenceError] = useState('')
  const heading = useRef<HTMLHeadingElement>(null)
  const leaveDialog = useRef<HTMLDialogElement>(null)
  const exitAction = useRef(onClose)
  const dirty = JSON.stringify(profile) !== JSON.stringify(saved)
  const pendingReference = !!(url.trim() || referenceNote.trim())
  const unsaved = dirty || pendingReference
  useEffect(() => { heading.current?.focus() }, [])
  useEffect(() => { if (leaving) leaveDialog.current?.showModal() }, [leaving])
  useEffect(() => {
    const warn = (e: BeforeUnloadEvent) => { if (unsaved) e.preventDefault() }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [unsaved])
  const update = <K extends keyof Profile>(key: K, value: Profile[K]) => {
    setProfile(p => ({ ...p, [key]: value }))
    setMessage('')
  }
  const toggle = (key: 'platforms' | 'vibes', value: string) => update(key,
    profile[key].includes(value) ? profile[key].filter(v => v !== value) : [...profile[key], value])
  const store = () => {
    if (pendingReference) {
      setReferenceError('Add your reference below, or clear its fields before saving.')
      return
    }
    try {
      const next = saveProfile(window.localStorage, profile)
      setProfile(next); setSaved(next); setError(null); setMessage('Profile saved in this browser.'); setLeaving(false)
    } catch { setError('Could not save. Your changes are still here. Check browser storage permissions and try again.') }
  }
  const addReference = () => {
    const link = url.trim()
    if (!safeReference(link)) { setReferenceError('Enter a full link starting with https:// or http://.'); return }
    if (profile.references.some(r => r.url === link)) { setReferenceError('This reference is already saved.'); return }
    if (profile.references.length >= 10) { setReferenceError('You can save up to 10 references.'); return }
    update('references', [...profile.references, { url: link, note: referenceNote.trim() }])
    setUrl(''); setReferenceNote(''); setReferenceError('')
  }

  return <main className="creator-page">
    <header className="creator-topbar">
      <button type="button" onClick={() => { exitAction.current = onClose; if (unsaved) setLeaving(true); else onClose() }}>← Back to editor</button>
      <span className="creator-wordmark">Vibe<span>Cut</span></span>
      <button type="button" onClick={() => { exitAction.current = onTools; if (unsaved) setLeaving(true); else onTools() }}>Creative tools ↗</button>
    </header>
    <div className="creator-body">
      <div className="creator-heading">
        <div><p className="creator-eyebrow">YOUR CREATIVE HOME</p>
          <h1 ref={heading} tabIndex={-1}>A little more <em>you.</em></h1>
          <p>Give your videos a common thread. Start with the things that feel like you.</p></div>
        <span className="creator-badge">Creator profile</span>
      </div>
      <div className="creator-layout">
        <form id="creator-form" onSubmit={e => { e.preventDefault(); store() }} className="creator-fields">
          <Section number="01" title="The person behind the camera" description="A few words about you and what you love to make.">
            <div className="creator-pair">
              <Field label="Your name"><input value={profile.name} maxLength={80} autoComplete="given-name" placeholder="What should we call you?" onChange={e => update('name', e.target.value)} /></Field>
              <Field label="Creator handle"><input value={profile.handle} maxLength={80} placeholder="@yourname" autoCapitalize="none" onChange={e => update('handle', e.target.value)} /></Field>
            </div>
            <Field label="What do you make?"><textarea value={profile.about} rows={2} maxLength={1000} placeholder="Little moments, weekend adventures, and places worth sharing…" onChange={e => update('about', e.target.value)} /></Field>
            <Field label="What would you like help with?"><textarea value={profile.goal} rows={2} maxLength={1000} placeholder="Turn my camera roll into a weekly vlog that still feels like me." onChange={e => update('goal', e.target.value)} /></Field>
            <Choice label="Where you share" values={PLATFORMS} selected={profile.platforms} onPick={v => toggle('platforms', v)} />
          </Section>
          <Section number="02" title="Your signature style" description="Choose a starting point. You can always change your mind.">
            <Choice label="The feeling · pick a few" values={VIBES} selected={profile.vibes} onPick={v => toggle('vibes', v)} />
            <Choice label="Pacing" values={PACES} selected={[profile.pace]} onPick={v => update('pace', v as Profile['pace'])} />
            <Choice label="Caption font" values={FONTS} selected={[profile.font]} onPick={v => update('font', v as Profile['font'])} />
            <div className="creator-pair">
              <Field label="Signature color"><div className="creator-color"><input type="color" aria-label="Signature color" value={profile.color} onChange={e => update('color', e.target.value)} /><span>{profile.color.toUpperCase()}</span></div></Field>
              <Field label="Caption placement"><select value={profile.captionPosition} onChange={e => update('captionPosition', e.target.value as Profile['captionPosition'])}><option>Lower</option><option>Middle</option></select></Field>
            </div>
            <Field label="Things to avoid"><textarea value={profile.avoid} rows={2} maxLength={1000} placeholder="No heavy filters. Keep natural sound. Go easy on zooms." onChange={e => update('avoid', e.target.value)} /></Field>
          </Section>
          <Section number="03" title="Keep your inspiration close" description="Save a video link and tell us what you like about it. Links are bookmarks for now; videos aren’t analyzed.">
            {profile.references.length > 0 && <ul className="creator-references">{profile.references.map((r, i) => <li key={r.url}>
              <div><a href={r.url} target="_blank" rel="noopener noreferrer">{new URL(r.url).hostname} ↗</a><p>{r.note || r.url}</p></div>
              <button type="button" aria-label={`Remove reference ${i + 1}`} onClick={() => update('references', profile.references.filter((_, index) => index !== i))}>Remove</button>
            </li>)}</ul>}
            <Field label="Reference video link"><input type="text" inputMode="url" value={url} maxLength={2048} placeholder="https://…" onChange={e => { setUrl(e.target.value); setReferenceError(''); setMessage('') }} /></Field>
            <Field label="What do you like about it?"><input value={referenceNote} maxLength={500} placeholder="The quiet opening and handwritten captions, not the transitions." onChange={e => { setReferenceNote(e.target.value); setMessage('') }} /></Field>
            {referenceError && <p className="creator-error" role="alert">{referenceError}</p>}
            <button type="button" className="creator-secondary" onClick={addReference} disabled={profile.references.length >= 10}>+ Add reference <span>{profile.references.length}/10</span></button>
          </Section>
        </form>
        <aside className="creator-preview">
          <p className="creator-eyebrow">YOUR STYLE, AT A GLANCE</p>
          <div className="creator-sample" style={{ '--signature': profile.color } as CSSProperties}>
            <span className="creator-sample-tag">STYLE PREVIEW</span>
            <div className="creator-sample-art" aria-hidden="true"><i /><i /><i /></div>
            <div className={`creator-caption ${profile.captionPosition.toLowerCase()} ${profile.font.toLowerCase()}`}><span>little moments,</span><br /><span>worth keeping.</span></div>
            <span className="creator-sample-credit">{profile.handle || 'your next story'}</span>
          </div>
          <div className="creator-person"><span className="creator-avatar">{profile.name.trim().slice(0, 1).toUpperCase() || 'Y'}</span><div><h2>{profile.name.trim() || 'Your creative world'}</h2><p>{profile.platforms.join(' · ') || 'A style that travels with you'}</p></div></div>
          <p className="creator-preview-about">{profile.about || 'Your everyday moments. Your way of telling them.'}</p>
          <div className="creator-tags">{profile.vibes.map(v => <span key={v}>{v}</span>)}</div>
          <dl className="creator-details"><div><dt>Pacing</dt><dd>{profile.pace}</dd></div><div><dt>Captions</dt><dd>{profile.font} · {profile.captionPosition.toLowerCase()}</dd></div><div><dt>References</dt><dd>{profile.references.length} added</dd></div></dl>
          <div className="creator-note"><strong>A starting point, saved.</strong><p>This profile stays here between editing sessions. Font, color and placement update this sample. Applying your style to edits comes next.</p></div>
        </aside>
      </div>
    </div>
    <footer className="creator-savebar">
      <div aria-live="polite">{error ? <span className="creator-error" role="alert">{error}</span> : message || (unsaved ? 'You have unsaved changes' : 'Only stored in this browser · no account needed')}</div>
      <button type="submit" form="creator-form" className="creator-primary">Save profile <span aria-hidden="true">↗</span></button>
    </footer>
    {leaving && <dialog ref={leaveDialog} className="creator-leave" aria-labelledby="leave-heading" onCancel={() => setLeaving(false)}>
      <h2 id="leave-heading">Keep your changes?</h2><p>Your latest changes haven’t been saved.</p>
      <button autoFocus type="button" onClick={() => setLeaving(false)}>Keep editing</button>
      <button type="button" onClick={() => exitAction.current()}>Discard changes & leave</button>
    </dialog>}
  </main>
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return <label className="creator-field"><span>{label}</span>{children}</label>
}
function Section({ number, title, description, children }: { number: string; title: string; description: string; children: ReactNode }) {
  return <section className="creator-section"><header><span>{number}</span><div><h2>{title}</h2><p>{description}</p></div></header><div className="creator-section-content">{children}</div></section>
}
function Choice({ label, values, selected, onPick }: { label: string; values: readonly string[]; selected: string[]; onPick: (v: string) => void }) {
  return <fieldset className="creator-choice"><legend>{label}</legend><div>{values.map(v => <button key={v} type="button" aria-pressed={selected.includes(v)} onClick={() => onPick(v)}>{v}</button>)}</div></fieldset>
}

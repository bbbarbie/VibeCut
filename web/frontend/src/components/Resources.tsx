import { useEffect, useRef, useState, type CSSProperties } from 'react'
import { api } from '../api'
import { fontById } from '../captionFonts'
import type { Resource, ResourceFolder, ResourceKind } from '../types'
import { Button, cx } from '../ui'
import { Icon, type IconName } from './icons'

// My resources (sarah, 2026-10-19: "a resources folder so i can save my own
// animations or templates forever", on the left rail, and in the profile).
// What the creator saved with a "Save to My resources" button where it was
// made, by kind; one click puts it on the video as one undoable turn. Signed
// out, the folder is a card that leads to signing in, and so is every Save.

const ICON: Record<ResourceKind, IconName> = {
  caption: 'text', animation: 'spark', transition: 'split', effect: 'spark', shot: 'adjust', song: 'music',
}
// where one goes when clicked, said once at the top of its section
const GOES: Record<ResourceKind, string> = {
  caption: 'For every caption',
  animation: 'How every caption arrives',
  transition: 'At the clicked cut, or every cut',
  effect: 'On the clicked shot, or every shot',
  shot: 'On the clicked shot',
  song: 'Under the whole video',
}

/** The folder on the left rail. `onUse` absent (the profile page): rename and delete only. */
export function Resources({ folder, error, onUse, onChange, onRetry }: {
  folder: ResourceFolder | null
  error?: string | null
  onUse?: (r: Resource) => void
  onChange: (items: Resource[]) => void
  onRetry?: () => void
}) {
  if (error) return (
    <div className="space-y-3 px-1 py-2">
      <p className="font-serif text-[16px] text-zinc-100">Your resources didn’t load: {error}</p>
      {onRetry && <Button onClick={onRetry}>Try again</Button>}
    </div>
  )
  if (!folder) return <p className="px-1 py-2 font-serif text-[16px] text-zinc-300">Opening your folder…</p>
  if (!folder.signed_in) return <SignIn url={folder.signin_url} />
  if (!folder.items.length) return (
    <div className="space-y-3 px-1 py-2">
      <p className="font-serif text-[17px] text-zinc-100">Nothing saved yet.</p>
      <p className="font-serif text-[15px] leading-snug text-zinc-300">
        When you like a caption look, an animation, a transition, an effect, a shot’s settings or a song, press
        <span className="whitespace-nowrap text-zinc-100"> <Icon name="resources" size={16} className="inline -mt-0.5" /> Save to My resources</span> where
        you changed it. It stays here for every video.
      </p>
    </div>
  )
  const kinds = folder.kinds.filter((k) => folder.items.some((x) => x.kind === k.id))
  return (
    <div className="space-y-5">
      {onUse && <p className="font-serif text-[15px] leading-snug text-zinc-300">Click one to put it on your video.</p>}
      {kinds.map((k) => (
        <section key={k.id} className="space-y-2">
          <header>
            <h3 className="font-serif text-[18px] font-medium text-zinc-100">{k.title}</h3>
            {onUse && <p className="font-serif text-[15px] text-zinc-300">{GOES[k.id]}</p>}
          </header>
          <ul className="space-y-1.5">
            {folder.items.filter((x) => x.kind === k.id).map((r) => (
              <Row key={r.id} r={r} onUse={onUse} onChange={onChange} />
            ))}
          </ul>
        </section>
      ))}
    </div>
  )
}

function SignIn({ url }: { url: string | null }) {
  const [soon, setSoon] = useState(false)
  return (
    <div className="flex flex-col items-center gap-3 rounded-2xl border border-line bg-raised px-5 py-6 text-center">
      <span className="grid size-14 place-items-center rounded-2xl bg-accent/12 text-accent"><Icon name="resources" size={30} /></span>
      <h3 className="font-serif text-[20px] leading-tight text-zinc-100">Sign in to keep your resources</h3>
      <p className="font-serif text-[15px] leading-snug text-zinc-300">
        Save your caption looks, animations, transitions, effects and songs, and use them on every video. They stay yours, in your own folder.
      </p>
      <Button variant="primary" size="lg" onClick={() => { if (url) window.location.href = url; else setSoon(true) }}>
        <Icon name="user" size={18} /> Sign in
      </Button>
      {soon && (
        <p className="font-serif text-[15px] leading-snug text-zinc-100" role="status">
          Accounts are coming soon. Until then, My resources works when VibeCut runs on your own computer.
        </p>
      )}
    </div>
  )
}

function Row({ r, onUse, onChange }: { r: Resource; onUse?: (r: Resource) => void; onChange: (items: Resource[]) => void }) {
  const [mode, setMode] = useState<'show' | 'rename' | 'delete'>('show')
  const [busy, setBusy] = useState(false)
  const [why, setWhy] = useState<string | null>(null)
  const act = async (f: () => Promise<{ items: Resource[] }>) => {
    setBusy(true); setWhy(null)
    try { onChange((await f()).items); setMode('show') } catch (e) { setWhy((e as Error).message) } finally { setBusy(false) }
  }
  const icon = (name: IconName, label: string, onClick: () => void) => (
    <button type="button" title={label} aria-label={`${label} ${r.name}`} onClick={onClick}
            className="grid size-9 shrink-0 place-items-center rounded-lg text-zinc-300 hover:bg-raised hover:text-zinc-100">
      <Icon name={name} size={18} />
    </button>
  )
  return (
    <li className="rounded-xl border border-line bg-panel">
      {mode === 'rename' ? (
        <Rename name={r.name} busy={busy} onDone={(name) => (name && name !== r.name ? act(() => api.renameResource(r.id, name)) : setMode('show'))} />
      ) : (
        <div className="flex items-center gap-1 pr-1">
          {onUse ? (
            <button type="button" onClick={() => onUse(r)} title={`Put “${r.name}” on your video`}
                    className="flex min-w-0 flex-1 items-center gap-3 rounded-l-xl px-2 py-2 text-left hover:bg-raised">
              <Tile r={r} /><span className="min-w-0 flex-1 truncate font-serif text-[16px] text-zinc-100">{r.name}</span>
            </button>
          ) : (
            <span className="flex min-w-0 flex-1 items-center gap-3 px-2 py-2">
              <Tile r={r} /><span className="min-w-0 flex-1 truncate font-serif text-[16px] text-zinc-100">{r.name}</span>
            </span>
          )}
          {icon('pencil', 'Rename', () => setMode('rename'))}
          {icon('trash', 'Delete', () => setMode('delete'))}
        </div>
      )}
      {mode === 'delete' && (
        <div className="flex flex-wrap items-center gap-2 border-t border-line px-3 py-2">
          <span className="min-w-0 flex-1 font-serif text-[15px] text-zinc-100">Delete it from your resources?</span>
          <Button size="sm" variant="danger" disabled={busy} onClick={() => act(() => api.deleteResource(r.id))}>Delete</Button>
          <Button size="sm" onClick={() => setMode('show')}>Keep</Button>
        </div>
      )}
      {why && <p className="border-t border-line px-3 py-2 font-serif text-[15px] text-rose-300">{why}</p>}
    </li>
  )
}

// No <form>: the profile page is one, and a form inside a form submits the outer one.
function Rename({ name, busy, onDone }: { name: string; busy: boolean; onDone: (name: string | null) => void }) {
  const [v, setV] = useState(name)
  const ref = useRef<HTMLInputElement>(null)
  useEffect(() => { ref.current?.select() }, [])
  return (
    <div className="flex items-center gap-2 p-2">
      <input ref={ref} value={v} maxLength={60} disabled={busy} aria-label="New name" onChange={(e) => setV(e.target.value)}
             onKeyDown={(e) => {
               if (e.key === 'Enter') { e.preventDefault(); onDone(v.trim()) }
               if (e.key === 'Escape') onDone(null)
             }}
             className="min-w-0 flex-1 rounded-lg border border-line bg-ink px-2.5 py-1.5 font-serif text-[16px] text-zinc-100 outline-none focus:border-accent/60" />
      <Button size="sm" variant="primary" disabled={busy || !v.trim()} onClick={() => onDone(v.trim())}>Save</Button>
      <Button size="sm" onClick={() => onDone(null)}>Cancel</Button>
    </div>
  )
}

// A caption look is shown in its own letters; everything else by what it is.
function Tile({ r }: { r: Resource }) {
  if (r.kind === 'caption') {
    const v = r.value as { typeface?: string; text_color?: string; outline?: { color: string; width: number } | null
      shadow?: { color: string; opacity: number } | null; backdrop?: { color: string; opacity: number } | null }
    const f = fontById(v.typeface)
    const style: CSSProperties = {
      fontFamily: f?.family, fontWeight: f?.weight ?? 600, color: v.text_color ?? '#ffffff',
      WebkitTextStroke: v.outline?.width ? `1.5px ${v.outline.color}` : undefined,
      textShadow: v.shadow?.opacity ? `1px 2px 3px ${v.shadow.color}` : undefined,
      background: v.backdrop?.opacity ? v.backdrop.color : undefined,
    }
    return (
      <span className="grid size-11 shrink-0 place-items-center rounded-lg bg-[#1d1d22]">
        <span className="rounded px-1 text-[19px] leading-none" style={style}>Aa</span>
      </span>
    )
  }
  return (
    <span className={cx('grid size-11 shrink-0 place-items-center rounded-lg bg-accent/10 text-accent')}>
      <Icon name={ICON[r.kind]} size={20} />
    </span>
  )
}

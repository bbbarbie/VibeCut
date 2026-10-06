import { useEffect, useState } from 'react'
import { api } from '../api'
import { dur } from '../format'
import { loadProfile } from '../profile'
import { go } from '../router'
import type { Capabilities, ProjectMeta } from '../types'
import { ago, Button, Confirm, Dialog, Field, inputCls, Notice, Wordmark } from '../ui'

// Home: every video you're making, and where each one stands. One primary
// action (New video). Everything else you'd do lives inside a project.

const STAGE_WORDS: Record<ProjectMeta['stage'], { label: string; next: string }> = {
  footage: { label: 'Footage', next: 'Add your clips' },
  brief: { label: 'Brief', next: 'Say what the video is' },
  cut: { label: 'Rough cut', next: 'Look over the rough cut' },
  story: { label: 'Story', next: 'Keep editing' },
  exported: { label: 'Exported', next: 'Open it' },
}

export function Projects() {
  const [list, setList] = useState<ProjectMeta[] | null>(null)
  const [caps, setCaps] = useState<Capabilities | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [rename, setRename] = useState<ProjectMeta | null>(null)
  const [remove, setRemove] = useState<ProjectMeta | null>(null)
  const initial = (() => { try { return loadProfile(window.localStorage).profile.name.trim().charAt(0).toUpperCase() || '☺' } catch { return '☺' } })()

  const load = () => api.projects().then((r) => { setList(r.projects); setCaps(r.capabilities); setError(null) })
    .catch((e) => setError((e as Error).message))
  useEffect(() => { load() }, [])

  const open = async (p: ProjectMeta) => {
    try { await api.openProject(p.id); go({ kind: 'project', id: p.id, view: 'story' }) }
    catch (e) { setError((e as Error).message) }
  }
  const create = async (name: string) => {
    try { const r = await api.createProject(name); go({ kind: 'project', id: r.project.id, view: 'story' }) }
    catch (e) { setError((e as Error).message) }
  }

  return (
    <div className="flex h-full flex-col overflow-hidden bg-ink">
      <header className="flex h-12 shrink-0 items-center gap-3 border-b border-line bg-ink px-4">
        <Wordmark />
        <div className="flex-1" />
        <Button variant="ghost" size="sm" onClick={() => go({ kind: 'polish' })}
                title="Already have a finished video? Point at a moment and say what to put there">Polish a finished video</Button>
        <span className="mx-1 h-5 w-px bg-line" aria-hidden />
        <button type="button" title="Your profile" aria-label="Your profile" onClick={() => go({ kind: 'profile' })}
                className="grid size-8 place-items-center rounded-full bg-zinc-700 font-serif text-[15px] font-semibold text-zinc-100 ring-1 ring-zinc-500/40 hover:ring-accent">{initial}</button>
      </header>

      <main className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto max-w-[1100px] px-6 py-8">
          <div className="flex flex-wrap items-end gap-4">
            <div>
              <h1 className="font-serif text-[30px] leading-tight text-zinc-100">Your videos</h1>
              <p className="mt-1 text-[13px] text-zinc-400">Each one starts from your clips and ends as one file. Nothing leaves this computer.</p>
            </div>
            {/* With no videos yet, the one in the middle is the only way in. */}
            {!!list?.length && <Button variant="primary" size="lg" className="ml-auto" onClick={() => create('')}>New video</Button>}
          </div>
          {error && <Notice tone="bad" className="mt-4">{error} <button type="button" className="underline" onClick={load}>Try again</button></Notice>}

          {list === null ? (
            <p className="mt-10 text-[13px] text-muted">Loading…</p>
          ) : list.length === 0 ? (
            <EmptyHome onNew={() => create('')} />
          ) : (
            <div className="mt-6 grid grid-cols-[repeat(auto-fill,minmax(260px,1fr))] gap-4">
              {list.map((p) => <Card key={p.id} p={p} onOpen={() => open(p)} onRename={() => setRename(p)} onDelete={() => setRemove(p)} />)}
            </div>
          )}

          {caps && <Machine caps={caps} />}
        </div>
      </main>

      {rename && <RenameProject p={rename} onClose={() => setRename(null)} onDone={() => { setRename(null); load() }} />}
      {remove && (
        <Confirm title={`Delete “${remove.name}”?`} action="Delete the project" danger onNo={() => setRemove(null)}
                 text={<>Only the project is removed: its story, its edits and its history. Your clips and any exported files stay exactly where they are.</>}
                 onYes={async () => { try { await api.deleteProject(remove.id); setRemove(null); load() } catch (e) { setError((e as Error).message); setRemove(null) } }} />
      )}
    </div>
  )
}

function Card({ p, onOpen, onRename, onDelete }: { p: ProjectMeta; onOpen: () => void; onRename: () => void; onDelete: () => void }) {
  const w = STAGE_WORDS[p.stage]
  const [menu, setMenu] = useState(false)
  return (
    <article className="group relative flex flex-col overflow-hidden rounded-xl border border-line bg-panel transition-colors hover:border-zinc-600">
      <button type="button" onClick={onOpen} className="block text-left">
        <div className="relative aspect-video w-full bg-black">
          {p.cover ? <img src={p.cover} alt="" className="size-full object-cover" />
            : <div className="grid size-full place-items-center text-[12px] text-zinc-600">No clips yet</div>}
          <span className="absolute left-2 top-2 rounded-md bg-black/70 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-zinc-200">{w.label}</span>
          {p.duration ? <span className="absolute bottom-2 right-2 rounded bg-black/70 px-1 text-[10px] tabular-nums text-zinc-200">{dur(p.duration)}</span> : null}
        </div>
        <div className="px-3 pb-3 pt-2.5">
          <h3 className="truncate font-serif text-[17px] text-zinc-100">{p.name}</h3>
          <p className="mt-0.5 truncate text-[11px] text-muted">
            {p.clips ? `${p.clips} clip${p.clips === 1 ? '' : 's'}` : 'Empty'}{p.board ? ` · ${p.board.parts} parts` : ''}{p.exports ? ` · exported ${p.exports}×` : ''} · {ago(p.updated)}
          </p>
          <p className="mt-2 text-[12px] text-accent">{w.next} →</p>
        </div>
      </button>
      <button type="button" aria-label="Project options" onClick={() => setMenu((m) => !m)}
              className="absolute right-2 top-2 grid size-7 place-items-center rounded-md bg-black/60 text-zinc-200 opacity-0 hover:bg-black/80 focus:opacity-100 group-hover:opacity-100">⋯</button>
      {menu && (
        <div className="absolute right-2 top-10 z-10 w-40 rounded-lg border border-line bg-panel p-1 shadow-xl" onMouseLeave={() => setMenu(false)}>
          <button type="button" onClick={() => { setMenu(false); onRename() }} className="block w-full rounded-md px-2.5 py-1.5 text-left text-[12px] text-zinc-100 hover:bg-raised">Rename</button>
          <button type="button" onClick={() => { setMenu(false); onDelete() }} className="block w-full rounded-md px-2.5 py-1.5 text-left text-[12px] text-rose-200 hover:bg-rose-500/10">Delete…</button>
        </div>
      )}
    </article>
  )
}

function EmptyHome({ onNew }: { onNew: () => void }) {
  return (
    <div className="mt-8 rounded-2xl border border-dashed border-zinc-700 p-10 text-center">
      <h2 className="font-serif text-[26px] text-zinc-100">Start with your clips</h2>
      <p className="mx-auto mt-2 max-w-md text-[13px] leading-relaxed text-zinc-400">
        Drop the clips from a trip or a day out. VibeCut reads them, throws away what a viewer would notice, proposes three ways to tell it, and you shape the rest by talking or by hand.
      </p>
      <ol className="mx-auto mt-6 grid max-w-2xl grid-cols-2 gap-x-6 gap-y-2 text-left text-[12px] text-zinc-400 sm:grid-cols-4">
        {[['1', 'Footage', 'your clips, read here'], ['2', 'Brief', 'one line about the video'], ['3', 'Rough cut', 'what to leave out, and why'], ['4', 'Story', 'edit, then export one file']]
          .map(([n, t, s]) => <li key={n}><span className="text-muted">{n} · </span><span className="text-zinc-200">{t}</span><span className="block text-[11px] text-muted">{s}</span></li>)}
      </ol>
      <Button variant="primary" size="lg" className="mt-6" onClick={onNew}>New video</Button>
    </div>
  )
}

// What this machine can do, in the creator's words. Nothing is promised that would then fail.
function Machine({ caps }: { caps: Capabilities }) {
  const mac = caps.platform === 'darwin'
  const rows: [string, boolean, string][] = [
    ['Cuts, stories, captions, sound and export', true, 'always on, all on this computer'],
    ['Typed edits (“the opening is too slow”)', caps.llm, caps.llm ? 'a language model is set up' : 'needs ANTHROPIC_API_KEY in web/.env — the storyboard’s text is sent, never footage'],
    ['What’s in each shot (on-device labels, faces)', caps.vision === 'ready', caps.vision === 'ready' ? 'on' : mac ? 'building the helper…' : 'macOS only — colour grouping is used instead'],
    ['Talking to camera (transcribe, cut pauses and retakes)', caps.speech, caps.speech ? 'on' : 'needs macOS 26 with the Xcode command-line tools'],
    ['Reference videos from a link', caps.links, caps.links ? 'yt-dlp found' : 'drop a file instead, or install yt-dlp'],
  ]
  return (
    <section className="mt-10 border-t border-line pt-5">
      <h2 className="text-[11px] font-semibold uppercase tracking-wider text-muted">On this computer</h2>
      <ul className="mt-2 grid gap-1.5 text-[12px] sm:grid-cols-2">
        {rows.map(([what, on, why]) => (
          <li key={what} className="flex items-start gap-2">
            <span className={on ? 'text-emerald-300' : 'text-zinc-500'} aria-hidden>{on ? '●' : '○'}</span>
            <span className={on ? 'text-zinc-200' : 'text-zinc-400'}>{what}<span className="block text-[11px] text-muted">{why}</span></span>
          </li>
        ))}
      </ul>
    </section>
  )
}

function RenameProject({ p, onClose, onDone }: { p: ProjectMeta; onClose: () => void; onDone: () => void }) {
  const [name, setName] = useState(p.name)
  const [error, setError] = useState('')
  const submit = async () => {
    try { await api.renameProject(p.id, name.trim()); onDone() } catch (e) { setError((e as Error).message) }
  }
  return (
    <Dialog title="Rename" onClose={onClose} width={420}
            footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button variant="primary" onClick={submit} disabled={!name.trim()}>Save</Button></>}>
      <form onSubmit={(e) => { e.preventDefault(); submit() }}>
        <Field label="Name"><input autoFocus value={name} onChange={(e) => setName(e.target.value)} maxLength={80} className={inputCls} /></Field>
        {error && <Notice tone="bad" className="mt-2">{error}</Notice>}
      </form>
    </Dialog>
  )
}

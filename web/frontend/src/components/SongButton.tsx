import { useEffect, useRef, useState } from 'react'
import { api, type Song, type Songs } from '../api'
import type { Session } from '../types'

// The song under the edit (songs.py). The app picks one as soon as the edit
// is there; tapping Song shows three others that fit, each put under the
// edit and played with it in one tap, plus the creator's own song or none.
// Every choice is one undoable turn.
export function SongButton({ boardKey, onDone, onHear }: {
  boardKey: string; onDone: (s: Session) => void; onHear: () => void
}) {
  const [open, setOpen] = useState(false)
  const [s, setS] = useState<Songs | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const box = useRef<HTMLDivElement>(null)
  const btn = useRef<HTMLButtonElement>(null)
  const file = useRef<HTMLInputElement>(null)
  const [pos, setPos] = useState<{ left: number; top: number } | null>(null)
  const autoAsked = useRef(false)

  // Read the list; while the free library is being searched, keep asking.
  // When it's ready and nothing was ever chosen, the app puts its pick under the edit.
  useEffect(() => {
    let stop = false
    let timer: number | undefined
    const load = async () => {
      try {
        const r = await api.songs()
        if (stop) return
        setS(r)
        if (r.status === 'searching') { timer = window.setTimeout(load, 2000); return }
        if (!r.chosen && !autoAsked.current && r.others.length) {
          autoAsked.current = true
          onDone(await api.songUse(null, true))
        }
      } catch { /* the edit isn't there yet */ }
    }
    load()
    return () => { stop = true; window.clearTimeout(timer) }
  }, [boardKey])  // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!open) return
    const r = btn.current?.getBoundingClientRect()
    if (r) setPos({ top: r.bottom + 6, left: Math.max(8, Math.min(r.right - 360, window.innerWidth - 368)) })
    const away = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) setOpen(false) }
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    window.addEventListener('mousedown', away)
    window.addEventListener('keydown', esc)
    return () => { window.removeEventListener('mousedown', away); window.removeEventListener('keydown', esc) }
  }, [open])

  const run = async (key: string, f: () => Promise<Session>, hear: boolean) => {
    if (busy) return
    setBusy(key); setErr(null)
    try { onDone(await f()); if (hear) onHear() } catch (e) { setErr((e as Error).message) } finally { setBusy(null) }
  }

  const cur = s?.current
  const label = cur ? `Song · ${cur.title}` : s?.status === 'searching' && !s.chosen ? 'Finding a song…' : 'Song'

  const row = (x: Song) => (
    <button key={x.id} type="button" disabled={!!busy} onClick={() => run(x.id, () => api.songUse(x.id), true)}
            className="block w-full rounded-lg border border-line px-3 py-2 text-left font-serif hover:bg-zinc-800 disabled:opacity-60">
      <span className="block truncate text-[15px] text-zinc-100">{busy === x.id ? 'Putting it under your edit…' : x.title}</span>
      {x.by && <span className="block truncate text-[15px] text-zinc-300">by {x.by}</span>}
      <span className="mt-0.5 block text-[15px] leading-snug text-zinc-300">{x.why}</span>
    </button>
  )

  return (
    <div ref={box} className="relative">
      <button ref={btn} type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open}
              title="The song under your edit"
              className="max-w-[220px] truncate whitespace-nowrap rounded-md border border-line px-2 py-1 text-[11px] text-zinc-300 hover:bg-raised">
        {label}
      </button>
      {open && pos && (
        <div className="fixed z-40 max-h-[80vh] w-[360px] overflow-y-auto rounded-xl border border-line bg-raised p-4 font-serif shadow-2xl" style={pos}>
          {cur ? <>
            <p className="text-[15px] text-zinc-300">Playing under your edit</p>
            <p className="mt-0.5 text-[17px] leading-snug text-zinc-100">{cur.title}{cur.by ? <span className="text-zinc-300"> by {cur.by}</span> : null}</p>
            <p className="mt-0.5 text-[15px] leading-snug text-zinc-200">{cur.why}</p>
          </> : (
            <p className="text-[15px] leading-snug text-zinc-200">
              {s?.status === 'searching' ? 'Finding songs that fit your edit…' : 'No song under your edit right now.'}
            </p>
          )}
          {s?.ducks && cur && <p className="mt-1 text-[15px] leading-snug text-zinc-200">It gets quieter wherever someone talks.</p>}

          {!!s?.others.length && <>
            <p className="mt-4 text-[15px] text-zinc-300">Or try one of these, it plays with your edit</p>
            <div className="mt-1.5 space-y-1.5">{s.others.map(row)}</div>
          </>}
          {s?.status === 'offline' && (
            <p className="mt-3 text-[15px] leading-snug text-zinc-200">The free music library can't be reached right now, so there's nothing new to suggest. Your own songs still work.</p>
          )}

          <div className="mt-4 flex gap-1.5">
            <button type="button" disabled={!!busy} onClick={() => file.current?.click()}
                    className="flex-1 rounded-md border border-line px-2 py-1.5 font-serif text-[15px] text-zinc-100 hover:bg-zinc-800">
              {busy === 'own' ? 'Reading your song…' : 'Add your own song'}
            </button>
            {cur && (
              <button type="button" disabled={!!busy} onClick={() => run('none', () => api.songUse(null), false)}
                      className="rounded-md border border-line px-3 py-1.5 font-serif text-[15px] text-zinc-300 hover:bg-zinc-800">
                No song
              </button>
            )}
          </div>
          <input ref={file} type="file" accept="audio/*,.mp3,.m4a,.wav,.flac" className="hidden"
                 onChange={(e) => {
                   const f = e.target.files?.[0]
                   e.target.value = ''
                   if (f) run('own', () => api.songUpload(f), true)
                 }} />
          {err && <p className="mt-2 text-[15px] text-rose-300">{err}</p>}
        </div>
      )}
    </div>
  )
}

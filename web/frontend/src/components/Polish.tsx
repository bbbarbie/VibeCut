import { useCallback, useEffect, useRef, useState } from 'react'
import { boomScale, drawCaptions, type PolishCaption, type PolishEffect, type PolishRecipe } from '../polishDraw'
import { fromInput } from '../drop'

// Polish: a finished edit, and the creator pointing at it.
//
// Click the picture -> a point in time and in the frame (the anchor). Say what
// you want there -> it happens as a change you can undo. Nothing here cuts,
// picks or renders: the edit is already made.

type Turn = { id: number; said: string; reply: string; lines: { kind: string; text: string }[]; skipped: string[]; undone: boolean; has_ops: boolean
  anchor: { t: number; x: number; y: number } | null }
type State = {
  job: 'none' | 'reading' | 'ready' | 'error'; error: string | null
  video: { name: string; url: string; duration?: number; fps?: number; width?: number; height?: number; cuts?: number[]; bpm?: number | null } | null
  faces: boolean; captions: PolishCaption[]; effects: PolishEffect[]; turns: Turn[]
  recipe: PolishRecipe; recipes: PolishRecipe[]; system_fonts: string[]; llm: boolean
}
type Here = { t: number; x: number; y: number }

async function call<T>(url: string, body?: unknown): Promise<T> {
  const r = await fetch(url, body === undefined ? undefined
    : { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) })
  if (!r.ok) {
    let msg = r.statusText
    try { msg = (await r.json()).detail ?? msg } catch { /* not json */ }
    throw new Error(msg)
  }
  return r.json()
}

const clock = (t: number) => `${Math.floor(t / 60)}:${(t % 60).toFixed(1).padStart(4, '0')}`

export function Polish() {
  const [st, setSt] = useState<State | null>(null)
  const [here, setHere] = useState<Here | null>(null)
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState<string | null>(null)
  const [now, setNow] = useState(0)
  const [playing, setPlaying] = useState(false)
  const video = useRef<HTMLVideoElement>(null)
  const canvas = useRef<HTMLCanvasElement>(null)
  const stage = useRef<HTMLDivElement>(null)
  const input = useRef<HTMLInputElement>(null)
  const file = useRef<HTMLInputElement>(null)
  const room = useRef<HTMLDivElement>(null)
  const [roomSize, setRoomSize] = useState({ w: 0, h: 0 })
  useEffect(() => {
    const el = room.current
    if (!el) return
    const ro = new ResizeObserver(() => setRoomSize({ w: el.clientWidth, h: el.clientHeight }))
    ro.observe(el)
    return () => ro.disconnect()
  }, [st?.video?.url])

  const load = useCallback(async () => setSt(await call<State>('/api/polish')), [])
  useEffect(() => { load().catch(() => {}) }, [load])
  useEffect(() => {        // while the video is being read
    if (st?.job !== 'reading') return
    const id = window.setInterval(() => { load().catch(() => {}) }, 700)
    return () => window.clearInterval(id)
  }, [st?.job, load])

  // the recipe's own font file, if it points at one on this Mac
  useEffect(() => {
    const r = st?.recipe
    if (!r?.font_file || typeof FontFace === 'undefined') return
    const f = new FontFace(r.family, `url(/api/polish/font?name=${encodeURIComponent(r.name)})`)
    f.load().then((ff) => { document.fonts.add(ff); setNow((n) => n + 1e-9) }).catch(() => setNote(`Couldn't load the font file for “${r.name}”.`))
  }, [st?.recipe])

  // draw captions and booms on every frame
  useEffect(() => {
    let raf = 0
    const tick = () => {
      const v = video.current, c = canvas.current
      if (v && c && st) {
        const t = v.currentTime
        const W = c.width, H = c.height
        const ctx = c.getContext('2d')
        if (ctx) drawCaptions(ctx, W, H, st.captions, t)
        const s = boomScale(st.effects, t)
        if (stage.current) stage.current.style.transform = s === 1 ? '' : `scale(${s})`
        setNow((n) => (Math.abs(n - t) > 0.05 ? t : n))   // the clock and scrubber, not 60 renders a second
      }
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [st])

  // ---- open a finished video ----------------------------------------------
  const open = async (files: FileList | null) => {
    const picked = files ? fromInput(files) : []
    if (!picked.length) { setNote('Choose an .mp4 or .mov file.'); return }
    setBusy(true); setNote(null)
    try {
      const f = picked[0]
      const loc = await call<{ resolved: Record<string, string>; missing: string[] }>('/api/locate',
        { files: [{ name: f.file.name, size: f.file.size, mtime: f.file.lastModified, relpath: f.relpath }] })
      let path = loc.resolved[f.relpath]
      if (!path) {
        const r = await fetch('/api/upload', { method: 'POST', body: f.file,
          headers: { 'x-relpath': encodeURIComponent(f.relpath), 'x-batch': 'polish' } })
        path = (await r.json()).path
      }
      setSt(await call<State>('/api/polish/open', { path }))
      setHere(null)
    } catch (e) { setNote((e as Error).message) } finally { setBusy(false) }
  }

  // ---- the one interaction ---------------------------------------------------
  const point = (e: React.MouseEvent) => {
    const v = video.current, pic = stage.current
    if (!v || !pic || !st?.video?.width) return
    v.pause()
    // the stage is exactly the picture, so this is a place in the frame, 0..1
    const r = pic.getBoundingClientRect()
    const x = (e.clientX - r.left) / r.width, y = (e.clientY - r.top) / r.height
    if (x < 0 || x > 1 || y < 0 || y > 1) return
    setHere({ t: v.currentTime, x, y })
    setNote(null)
    window.setTimeout(() => input.current?.focus(), 0)
  }

  const send = async () => {
    if (!here || !text.trim() || busy) return
    setBusy(true); setNote(null)
    try {
      const s = await call<State>('/api/polish/say', { ...here, text: text.trim() })
      setSt(s)
      setText('')
      const last = s.turns.at(-1)
      setNote(last ? [last.reply, ...last.lines.filter((l) => l.kind !== 'none').map((l) => l.text)].filter(Boolean).join(' · ') : null)
      if (video.current) video.current.currentTime = here.t + 0.001
    } catch (e) { setNote((e as Error).message) } finally { setBusy(false) }
  }

  const toggle = async (id: number) => setSt(await call<State>(`/api/polish/turns/${id}/toggle`, {}))
  const useRecipe = async (name: string) => setSt(await call<State>('/api/polish/recipe/use', { name }))
  const editRecipe = async (fields: Partial<PolishRecipe>) => {
    try { setSt(await call<State>('/api/polish/recipe/edit', { fields })) } catch (e) { setNote((e as Error).message) }
  }

  const v = st?.video
  // the picture's rectangle inside the room: contained, never stretched
  const vw = v?.width || 16, vh = v?.height || 9
  const fit = Math.min(roomSize.w / vw, roomSize.h / vh) || 0
  const pic = { w: vw * fit, h: vh * fit, left: (roomSize.w - vw * fit) / 2, top: (roomSize.h - vh * fit) / 2 }
  const hereCap = here && st ? st.captions.find((c) => here.t >= c.t && here.t < c.t + c.dur) : null

  return (
    <div className="flex h-full flex-col bg-panel text-zinc-200">
      <header className="flex h-12 shrink-0 items-center gap-3 border-b border-line px-4">
        <a href="#" className="font-serif text-[20px] text-zinc-100">VibeCut</a>
        <a href="#/" className="rounded-md px-1.5 py-0.5 text-[12px] text-muted hover:bg-raised hover:text-zinc-100">← Your videos</a>
        <span className="text-[12px] text-muted">Polish — point at a moment of a finished video, say what you want there</span>
        {v && <span className="ml-auto truncate text-[12px] text-zinc-400">{v.name}</span>}
        <button type="button" onClick={() => file.current?.click()}
                className={`${v ? '' : 'ml-auto'} rounded-lg border border-line px-3 py-1 text-[12px] hover:bg-raised`}>
          {v ? 'Open another' : 'Open a finished video'}
        </button>
        <input ref={file} type="file" accept=".mp4,.mov,video/mp4,video/quicktime" className="hidden"
               onChange={(e) => { open(e.target.files); e.target.value = '' }} />
      </header>

      {!v ? (
        <div className="grid flex-1 place-items-center p-8"
             onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); open(e.dataTransfer.files) }}>
          <div className="max-w-lg rounded-2xl border border-dashed border-zinc-700 p-10 text-center">
            <h2 className="font-serif text-[26px] text-zinc-100">Start from a video you've already cut</h2>
            <p className="mt-2 text-[13px] text-zinc-400">Drop it here or open it. Then click any moment and say what you want there —
              “这里写上「东京第一天」”, “这里加个 boom”, “这段字大一点”.</p>
            <button type="button" disabled={busy} onClick={() => file.current?.click()}
                    className="mt-5 rounded-lg bg-accent px-4 py-2 text-[13px] font-semibold text-accent-ink disabled:opacity-40">
              {busy ? 'Opening…' : 'Open a finished video'}
            </button>
            {note && <p className="mt-3 text-[12px] text-rose-300">{note}</p>}
          </div>
        </div>
      ) : (
        <div className="grid min-h-0 flex-1 grid-cols-[minmax(0,1fr)_320px]">
          <main className="flex min-h-0 flex-col gap-3 p-4">
            <div ref={room} className="relative min-h-0 flex-1 overflow-hidden rounded-xl bg-black">
              <div ref={stage} className="absolute cursor-crosshair" onClick={point} data-picture
                   style={{ left: pic.left, top: pic.top, width: pic.w, height: pic.h }}>
                <video ref={video} src={v.url} playsInline className="absolute inset-0 size-full"
                       onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} />
                <canvas ref={canvas} width={v.width ?? 1920} height={v.height ?? 1080}
                        className="pointer-events-none absolute inset-0 size-full" aria-hidden />
                {here && (
                  <span className="pointer-events-none absolute size-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-accent bg-accent/30"
                        style={{ left: `${here.x * 100}%`, top: `${here.y * 100}%` }} />
                )}
              </div>
              {st.job === 'reading' && <div className="absolute left-3 top-3 rounded bg-black/70 px-2 py-1 text-[11px]">Reading the video — cuts, movement, beat{st.faces ? '' : ''}…</div>}
            </div>

            {/* the sentence, at the anchor */}
            <div className="flex items-center gap-2">
              <button type="button" onClick={() => { const e = video.current; if (!e) return; if (e.paused) { setHere(null); e.play() } else e.pause() }}
                      className="w-16 rounded-lg border border-line py-1.5 text-[12px] hover:bg-raised">{playing ? 'Pause' : 'Play'}</button>
              <input type="range" min={0} max={v.duration ?? 0} step={0.01} value={now} className="min-w-0 flex-1"
                     onChange={(e) => { if (video.current) video.current.currentTime = +e.target.value }} />
              <span className="w-24 text-right text-[12px] tabular-nums text-muted">{clock(now)} / {clock(v.duration ?? 0)}</span>
            </div>
            <div className={`flex items-center gap-2 rounded-xl border px-3 py-2 ${here ? 'border-accent/60 bg-raised' : 'border-line'}`}>
              <span className="shrink-0 text-[12px] text-muted">
                {here ? <>Here: <b className="text-zinc-200">{clock(here.t)}</b>{hereCap ? ` · on “${hereCap.text}”` : ''}</> : 'Click the picture where you want something'}
              </span>
              <input ref={input} value={text} disabled={!here || busy} onChange={(e) => setText(e.target.value)}
                     onKeyDown={(e) => { if (e.key === 'Enter') send() }}
                     placeholder={here ? '这里写上「…」 · 这里加个 boom · 这段字大一点 · 用我的配方' : ''}
                     className="min-w-0 flex-1 bg-transparent text-[14px] text-zinc-100 outline-none placeholder:text-zinc-600" />
              <button type="button" onClick={send} disabled={!here || !text.trim() || busy}
                      className="rounded-lg bg-accent px-3 py-1 text-[12px] font-semibold text-accent-ink disabled:opacity-30">Do it</button>
            </div>
            {note && <p className="text-[12px] text-zinc-300">{note}</p>}
          </main>

          <aside className="flex min-h-0 flex-col gap-3 overflow-y-auto border-l border-line p-3">
            <RecipeCard st={st} onUse={useRecipe} onEdit={editRecipe} onSave={() => {
              if (!hereCap) { setNote('Click on a caption first, then save it as your recipe.'); return }
              setText('把这条字幕存成配方'); window.setTimeout(() => input.current?.focus(), 0)
            }} />
            {!st.faces && st.job === 'ready' && (
              <p className="rounded-md bg-amber-300/10 px-2 py-1.5 text-[11px] text-amber-200/90">
                Faces can't be looked for on this machine, so “don't cover a face” is not checked here.</p>
            )}
            <section>
              <h3 className="mb-1.5 text-[11px] uppercase tracking-wider text-muted">Changes</h3>
              {st.turns.length === 0 && <p className="text-[12px] text-zinc-500">Nothing yet.</p>}
              <ul className="space-y-2">
                {[...st.turns].reverse().map((t) => (
                  <li key={t.id} className={`rounded-lg border border-line px-2.5 py-2 text-[12px] ${t.undone ? 'opacity-40' : ''}`}>
                    <div className="flex items-start gap-2">
                      <span className="min-w-0 flex-1 text-zinc-200">{t.anchor ? <span className="text-muted">{clock(t.anchor.t)} · </span> : null}{t.said}</span>
                      {t.has_ops && <button type="button" onClick={() => toggle(t.id)} className="shrink-0 text-[10px] text-muted hover:text-zinc-200">{t.undone ? 'Redo' : 'Undo'}</button>}
                    </div>
                    {t.reply && <p className="mt-1 text-zinc-400">{t.reply}</p>}
                    {t.lines.filter((l) => l.kind !== 'none').map((l, i) => <p key={i} className="mt-1 text-zinc-400">{l.kind === 'added' ? '+ ' : l.kind === 'removed' ? '− ' : '~ '}{l.text}</p>)}
                    {t.skipped.map((s) => <p key={s} className="mt-1 text-amber-200/80">Skipped: {s}</p>)}
                  </li>
                ))}
              </ul>
            </section>
          </aside>
        </div>
      )}
    </div>
  )
}

function RecipeCard({ st, onUse, onEdit, onSave }: {
  st: State; onUse: (name: string) => void; onEdit: (f: Partial<PolishRecipe>) => void; onSave: () => void
}) {
  const r = st.recipe
  const [fontPath, setFontPath] = useState('')
  return (
    <section className="rounded-xl border border-line bg-raised/60 p-3">
      <div className="flex items-baseline gap-2">
        <h3 className="text-[11px] uppercase tracking-wider text-muted">My recipe</h3>
        <span className="ml-auto text-[12px] text-zinc-200">{r.name}</span>
      </div>
      <div className="mt-2 rounded-md bg-black/60 px-2 py-3 text-center"
           style={{ fontFamily: `"${r.family}", system-ui`, fontWeight: r.weight, color: r.color,
                    WebkitTextStroke: r.stroke_color ? `${Math.max(1, r.stroke_width * 8)}px ${r.stroke_color}` : undefined, fontSize: 20, paintOrder: 'stroke fill' }}>
        东京第一天
      </div>
      <p className="mt-1.5 text-[11px] text-zinc-400">{r.family}{r.font_file ? ' (your file)' : ''} · {Math.round(r.size * 1000) / 10}% · {r.position.replace('_', ' ')} · {r.enter}</p>
      <div className="mt-2 flex flex-wrap gap-1.5 text-[11px]">
        <button type="button" onClick={onSave} className="rounded-md border border-line px-2 py-1 hover:bg-zinc-800">Save a caption as my recipe</button>
        {(['lower_third', 'center', 'follow_speaker'] as const).map((p) => (
          <button key={p} type="button" onClick={() => onEdit({ position: p })}
                  className={`rounded-md border px-2 py-1 ${r.position === p ? 'border-accent text-accent' : 'border-line hover:bg-zinc-800'}`}>
            {p === 'lower_third' ? 'Lower third' : p === 'center' ? 'Centre' : 'Follow the speaker'}
          </button>
        ))}
      </div>
      <label className="mt-2 block text-[11px] text-muted">Font on this Mac
        <select value={r.font_file ? '' : r.family} onChange={(e) => e.target.value && onEdit({ family: e.target.value, font_file: null })}
                className="mt-1 block w-full rounded border border-line bg-panel px-1.5 py-1 text-[12px] text-zinc-200">
          {r.font_file && <option value="">{r.family} (your file)</option>}
          {st.system_fonts.map((f) => <option key={f} value={f}>{f}</option>)}
        </select>
      </label>
      <div className="mt-1.5 flex gap-1.5">
        <input value={fontPath} onChange={(e) => setFontPath(e.target.value)} placeholder="…or a font file: ~/Library/Fonts/My.otf"
               className="min-w-0 flex-1 rounded border border-line bg-panel px-1.5 py-1 text-[11px] text-zinc-200 outline-none" />
        <button type="button" disabled={!fontPath.trim()} onClick={() => onEdit({ font_file: fontPath.trim(), family: fontPath.trim().split('/').pop()!.replace(/\.\w+$/, '') })}
                className="rounded border border-line px-2 text-[11px] disabled:opacity-40">Use</button>
      </div>
      <p className="mt-1 text-[10px] leading-snug text-muted">Only fonts already on your computer. A font you recognise in someone else's video isn't one you may use.</p>
      {st.recipes.length > 1 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {st.recipes.slice(1).map((x) => (
            <button key={x.name} type="button" onClick={() => onUse(x.name)} className="rounded border border-line px-1.5 py-0.5 text-[11px] text-zinc-400 hover:text-zinc-200">
              Use “{x.name}”
            </button>
          ))}
        </div>
      )}
    </section>
  )
}

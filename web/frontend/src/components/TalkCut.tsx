import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { dur } from '../format'
import type { TalkItem, TalkPart, TalkState } from '../types'

// Talking-head cut: talking to camera, cut by what was said. A gate like the rough
// cut: the whole transcript, every cut struck through with its reason, and
// one click puts anything back. Nothing becomes the storyboard until "Use
// this cut" -- and that is one undoable turn.
export function TalkCut({ onApply, onWatch, onClose }: {
  onApply: (captions: boolean) => Promise<void>
  onWatch: (clipId: string, start: number, end: number, id: string) => void
  onClose: () => void
}) {
  const [st, setSt] = useState<TalkState | null>(null)
  const [locale, setLocale] = useState('zh-CN')
  const [script, setScript] = useState('')
  const [redo, setRedo] = useState(false)
  const [captions, setCaptions] = useState(true)
  const [err, setErr] = useState<string | null>(null)
  const [applying, setApplying] = useState(false)
  const timer = useRef<number | undefined>(undefined)

  const poll = async () => {
    const s = await api.talkState()
    setSt(s)
    if (s.job && (s.job.stage === 'transcribing' || s.job.stage === 'reviewing')) timer.current = window.setTimeout(poll, 600)
  }
  useEffect(() => {
    poll().catch(() => {})
    return () => window.clearTimeout(timer.current)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps -- poll once on open

  const start = async () => {
    setErr(null); setRedo(false)
    try { setSt(await api.talkStart({ locale, script })); timer.current = window.setTimeout(poll, 400) } catch (e) { setErr((e as Error).message) }
  }
  const toggle = async (id: string | null) => {
    if (!id) return
    try { setSt(await api.talkToggle(id)) } catch (e) { setErr((e as Error).message) }
  }
  const apply = async () => {
    setApplying(true); setErr(null)
    try { await onApply(captions) } catch (e) { setErr((e as Error).message) } finally { setApplying(false) }
  }

  const job = st?.job
  const running = job && (job.stage === 'transcribing' || job.stage === 'reviewing')
  const plan = st?.plan
  const showSetup = !running && (!plan || redo)

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto p-5 pb-28">
        <div className="flex items-baseline gap-3">
          <p className="text-[12px] text-muted">Talking to camera</p>
          <button type="button" onClick={onClose} className="ml-auto text-[12px] text-accent hover:underline">Back to the story</button>
        </div>
        <h2 className="mt-1 font-serif text-[26px] text-zinc-100">Cut by what you said</h2>
        <p className="mt-1 max-w-2xl text-[13px] text-zinc-400">
          Your clips are transcribed on this Mac. Pauses are cut down to a breath, a sentence you said twice keeps its last take,
          stumbles and filler sounds go — and you see every cut before anything changes.
        </p>

        {showSetup && (
          <div className="mt-4 max-w-2xl space-y-3 rounded-xl border border-line bg-raised px-4 py-3">
            <div className="flex items-center gap-2 text-[12px]">
              <span className="w-24 text-muted">Language</span>
              <div className="flex rounded-md border border-line bg-panel p-px">
                {[['zh-CN', 'Chinese'], ['en-US', 'English']].map(([k, n]) => (
                  <button key={k} type="button" aria-pressed={locale === k} onClick={() => setLocale(k)}
                          className={`rounded px-2.5 py-0.5 ${locale === k ? 'bg-zinc-700 text-zinc-100' : 'text-muted hover:text-zinc-200'}`}>{n}</button>
                ))}
              </div>
            </div>
            <label className="block text-[12px]">
              <span className="text-muted">Your script <span className="text-zinc-600">(optional)</span></span>
              <textarea value={script} onChange={(e) => setScript(e.target.value)} rows={5}
                        placeholder={'Hi everyone, today I want to talk about…\n\nWith a script, takes of the same line are compared and the most complete one stays; lines you never said are listed.'}
                        className="mt-1 block w-full resize-y rounded-lg border border-line bg-panel px-3 py-2 text-[13px] text-zinc-100 outline-none placeholder:text-zinc-600 focus:border-zinc-500" />
            </label>
            <p className="text-[11px] leading-snug text-muted">
              {st?.llm
                ? 'The transcript’s text (not the audio) goes to Claude to judge retakes and false starts; simple rules are the fallback.'
                : 'No language model is set up, so simple rules judge retakes. Add ANTHROPIC_API_KEY to web/.env for a second opinion.'}
              {' '}The first time, macOS downloads its speech model for the language.
            </p>
            <div className="flex gap-2">
              <button type="button" onClick={start} className="rounded-lg bg-accent px-4 py-1.5 text-[13px] font-semibold text-accent-ink">Transcribe & cut</button>
              {plan && <button type="button" onClick={() => setRedo(false)} className="rounded-lg px-3 text-[12px] text-muted hover:text-zinc-200">Cancel</button>}
            </div>
          </div>
        )}

        {running && (
          <div className="mt-4 max-w-2xl rounded-xl border border-line bg-raised px-4 py-3">
            <div className="h-1.5 overflow-hidden rounded-full bg-zinc-800">
              <div className="h-full rounded-full bg-accent transition-[width]" style={{ width: `${job.stage === 'reviewing' ? 100 : (job.done / Math.max(1, job.total)) * 100}%` }} />
            </div>
            <p className="mt-1.5 text-[12px] text-muted">
              {job.stage === 'reviewing' ? (st?.llm ? 'Reading the sentences for retakes…' : 'Finding pauses and retakes…')
                : `Transcribing ${job.done + 1 > job.total ? job.total : job.done + 1} of ${job.total} · ${job.current}`}
            </p>
          </div>
        )}
        {job?.stage === 'error' && <p className="mt-3 text-[13px] text-rose-300">{job.error}</p>}
        {err && <p className="mt-3 text-[13px] text-rose-300">{err}</p>}

        {plan && !showSetup && !running && <>
          <div className="mt-4 rounded-xl border border-line bg-raised px-4 py-3">
            <div className="font-serif text-[22px] text-zinc-100">{plan.summary.line_en}</div>
            {plan.agent_note && <p className="mt-1.5 text-[12px] text-zinc-300">{plan.source === 'agent' ? '✦ ' : ''}{plan.agent_note}</p>}
            <button type="button" onClick={() => setRedo(true)} className="mt-1.5 text-[11px] text-muted hover:text-zinc-200">Transcribe again (other language or script)…</button>
          </div>
          {plan.unsaid.length > 0 && (
            <div className="mt-3 rounded-xl border border-amber-500/30 px-4 py-2.5 text-[12px]">
              <div className="text-amber-200">Script lines you didn’t say</div>
              <ol className="mt-1 space-y-0.5 text-zinc-300">{plan.unsaid.map((u) => <li key={u.line}>{u.line}. {u.text}</li>)}</ol>
            </div>
          )}
          {(job?.silent.length ?? 0) > 0 && (
            <p className="mt-2 text-[11px] text-muted">No speech found in {job!.silent.length} clip(s): {job!.silent.slice(0, 6).join(', ')}{job!.silent.length > 6 ? '…' : ''}</p>
          )}
          <p className="mt-4 text-[11px] text-muted">Click a sentence to hear it. Struck-through words are cut — click them to put them back. ⏸ marks a pause.</p>
          <ol className="mt-2 max-w-3xl space-y-1">
            {plan.items.map((it) => <Row key={it.id} it={it} onToggle={toggle} onWatch={onWatch} />)}
          </ol>
        </>}
      </div>

      {plan && !showSetup && !running && (
        <div className="flex shrink-0 items-center gap-3 border-t border-line bg-panel px-5 py-3">
          <label className="flex items-center gap-2 text-[12px] text-zinc-200">
            <input type="checkbox" checked={captions} onChange={(e) => setCaptions(e.target.checked)} className="accent-[#b9d9eb]" />
            Add subtitles
          </label>
          <span className="text-[11px] text-muted">{dur(plan.summary.raw)} → {dur(plan.summary.cut)}</span>
          <button type="button" onClick={apply} disabled={applying}
                  className="ml-auto rounded-lg bg-accent px-4 py-1.5 text-[13px] font-semibold text-accent-ink disabled:opacity-40">
            {applying ? 'Building…' : 'Use this cut'}
          </button>
        </div>
      )}
    </div>
  )
}

function Row({ it, onToggle, onWatch }: {
  it: TalkItem
  onToggle: (id: string | null) => void
  onWatch: (clipId: string, start: number, end: number, id: string) => void
}) {
  if (it.kind === 'pause') {
    return (
      <li>
        <button type="button" onClick={() => onToggle(it.id)} title={it.cut ? 'Keep this pause whole' : 'Cut it down to a breath'}
                className={`ml-14 rounded px-1.5 text-[11px] tabular-nums ${it.cut ? 'text-zinc-500 hover:text-zinc-300' : 'bg-amber-500/10 text-amber-200'}`}>
          ⏸ {it.len.toFixed(1)}s {it.cut ? `→ ${it.keeps.toFixed(2)}s` : 'kept'}
        </button>
      </li>
    )
  }
  return (
    <li className={`group flex gap-3 rounded-lg px-2 py-1.5 ${it.removed ? 'bg-rose-500/5' : 'hover:bg-raised'}`}>
      <button type="button" onClick={() => onWatch(it.clip, Math.max(0, it.start - 0.2), it.end + 0.3, it.id)}
              title={`${it.clip_name} · ${it.start.toFixed(1)}s — play it`}
              className="w-12 shrink-0 pt-0.5 text-left text-[10px] tabular-nums text-muted hover:text-zinc-200">▶ {Math.floor(it.start / 60)}:{String(Math.floor(it.start % 60)).padStart(2, '0')}</button>
      <div className="min-w-0 flex-1">
        <p className={`font-serif text-[16px] leading-snug ${it.removed ? 'text-zinc-500 line-through decoration-rose-400/70' : 'text-zinc-100'}`}>
          {it.parts.map((p, k) => <Part key={k} p={p} sentenceGone={it.removed} onToggle={onToggle} />)}
        </p>
        {(it.code || it.removed) && (
          <p className="mt-0.5 text-[11px]">
            {it.en && <span className={`mr-1.5 rounded px-1 ${it.removed ? 'bg-rose-500/15 text-rose-200' : 'bg-amber-500/15 text-amber-200'}`}>{it.en}</span>}
            <span className="text-muted">{it.removed && !it.auto ? 'you cut this' : it.why}{it.override && it.auto && !it.removed ? ' — you kept it' : ''}</span>
          </p>
        )}
        {it.script_line && <p className="text-[10px] text-zinc-600">script line {it.script_line}</p>}
      </div>
      <button type="button" onClick={() => onToggle(it.id)}
              className={`h-6 shrink-0 self-start rounded-md px-2 text-[11px] ${it.removed ? 'bg-zinc-700 text-zinc-100' : 'text-muted opacity-0 hover:text-rose-300 group-hover:opacity-100'}`}>
        {it.removed ? 'Put back' : 'Cut'}
      </button>
    </li>
  )
}

function Part({ p, sentenceGone, onToggle }: { p: TalkPart; sentenceGone: boolean; onToggle: (id: string | null) => void }) {
  if (p.kind === 'pause') {
    return (
      <button type="button" onClick={() => onToggle(p.id)} title={p.cut ? `${p.len.toFixed(1)}s pause, cut to a breath — click to keep it` : 'Kept whole — click to cut it'}
              className={`mx-0.5 rounded px-1 align-middle font-sans text-[10px] no-underline ${p.cut ? 'text-zinc-500' : 'bg-amber-500/10 text-amber-200'}`}>
        ⏸{p.len.toFixed(1)}
      </button>
    )
  }
  if (!p.code) return <span>{p.text}</span>
  return (
    <button type="button" disabled={sentenceGone} onClick={() => onToggle(p.id)}
            title={p.removed ? `${p.en} — click to keep it` : `${p.en} — kept; click to cut`}
            className={p.removed && !sentenceGone ? 'text-rose-300/80 line-through decoration-rose-400' : 'underline decoration-amber-300/60 decoration-dotted'}>
      {p.text}
    </button>
  )
}

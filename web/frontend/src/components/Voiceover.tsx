import { useRef, useState } from 'react'
import type { Session } from '../types'
import { dur } from '../format'

// Opt-in: the creator's own narration becomes the spine of one proposal.
// Subtitles give each line its time; a plain script only estimates it.

export function Voiceover({ current, busy, onSubmit }: {
  current: Session['voiceover']
  busy: boolean
  onSubmit: (text: string) => Promise<void>
}) {
  const [open, setOpen] = useState(false)
  const [text, setText] = useState('')
  const [error, setError] = useState<string | null>(null)
  const file = useRef<HTMLInputElement>(null)

  const go = async () => {
    if (!text.trim() || busy) return
    setError(null)
    try { await onSubmit(text); setOpen(false); setText('') } catch (e) { setError((e as Error).message) }
  }

  if (!open) {
    return (
      <button type="button" onClick={() => setOpen(true)}
              className="rounded-lg border border-line px-3 py-1.5 text-[12px] text-zinc-300 hover:bg-raised"
              title="Paste your subtitles or script — one proposal will follow it line by line">
        {current
          ? `Voiceover: ${current.lines} lines, ${dur(current.total)}${current.timing === 'text_only' ? ' (estimated from the words)' : ''} — change`
          : 'Follow my voiceover…'}
      </button>
    )
  }
  return (
    <div className="w-full rounded-xl border border-line bg-raised p-3">
      <p className="text-[12px] text-zinc-300">
        Paste the subtitles of your voiceover (.srt), or just the script. One proposal will follow it line by line:
        what each line says decides what’s shown, and for how long.
      </p>
      <p className="mt-1 text-[11px] text-muted">
        Lines that nothing you filmed shows are left empty and listed — not covered with something unrelated.
      </p>
      <textarea rows={5} value={text} onChange={(e) => setText(e.target.value)} disabled={busy}
                placeholder={'1\n00:00:00,000 --> 00:00:03,500\nWe started the morning at the market.\n\n— or just the script —'}
                className="mt-2 block w-full resize-y rounded-lg border border-line bg-panel px-3 py-2 font-mono text-[12px] text-zinc-100 outline-none placeholder:text-zinc-600 focus:border-zinc-500" />
      {error && <p className="mt-1.5 text-[11px] text-rose-300">{error}</p>}
      <div className="mt-2 flex items-center gap-2">
        <button type="button" onClick={() => file.current?.click()} disabled={busy}
                className="rounded-lg border border-line px-3 py-1.5 text-[12px] text-zinc-300 hover:bg-zinc-800">Open a subtitle file</button>
        <input ref={file} type="file" className="hidden" accept=".srt,.vtt,.txt,text/plain"
               onChange={async (e) => { const f = e.target.files?.[0]; if (f) setText(await f.text()); e.target.value = '' }} />
        <button type="button" onClick={() => setOpen(false)} className="ml-auto px-2 text-[12px] text-muted hover:text-zinc-200">Cancel</button>
        <button type="button" onClick={go} disabled={busy || !text.trim()}
                className="rounded-lg bg-accent px-3 py-1.5 text-[12px] font-semibold text-accent-ink disabled:opacity-30">
          {busy ? 'Working…' : 'Follow it'}
        </button>
      </div>
    </div>
  )
}

import { useEffect, useRef, useState } from 'react'
import type { AIEstimate, AIState } from '../api'
import { Button, Dialog } from '../ui'
import { AISwitch } from './AISwitch'

// The two picks before anything is cut (plan of 2026-10-10, step 2): the
// frame the video is for, and the look of the whole thing. Everything else
// is read from the footage. Defaults come from the server; one button.
export type SetupData = {
  format: string; suggested?: string; portrait_share: number
  remembered?: { format?: string; look?: string; music?: string; vibe?: string }   // what was picked last time (defaults.py)
  music?: boolean
  // "Cut it like": the library's vibes and your own learnt reels (vibes.py)
  vibes?: { id: string; name: string; line: string; kind: 'library' | 'reference' }[]
  vibe?: string | null
  formats: { key: string; label: string; seconds: number }[]
  look: string; looks: { id: string; name: string; line: string; font: string; palette: string[]; status: string }[]
  about: string
}

const GLYPH: Record<string, string> = { short: 'h-7 w-4', tall: 'h-7 w-4', wide: 'h-4 w-7' }

export function Setup({ data, busy, progress, onDone, onCancel, ai, estimate, onAI }: {
  data: SetupData | null
  ai?: AIState | null; estimate?: AIEstimate | null   // the AI switch, and what this edit would cost with it on
  onAI?: (on: boolean) => void
  busy: boolean
  progress?: { line: string; done: number; total: number; elapsed: number } | null   // where the making is
  onDone: (format: string, look: string, music: boolean, vibe: string | null, aiCost: number | null) => void   // aiCost: the price shown, null = no AI
  onCancel: () => void
}) {
  const [format, setFormat] = useState<string | null>(null)
  const [look, setLook] = useState<string | null>(null)
  const [music, setMusic] = useState<boolean | null>(null)
  const withMusic = music ?? data?.music ?? true
  const [vibe, setVibe] = useState<string | null | undefined>(undefined)   // undefined = not touched
  const chosenVibe = vibe === undefined ? (data?.vibe ?? null) : vibe
  const last = data?.remembered
  const first = useRef<HTMLButtonElement>(null)
  const fmt = format ?? data?.format ?? 'tall'
  const lk = look ?? data?.look ?? 'cozy'
  useEffect(() => { first.current?.focus() }, [data])
  // a chosen vibe sets the cut itself, so the AI doesn't plan it (and nothing is spent)
  const aiOn = !!ai?.available && !!ai?.on && !chosenVibe
  const cost = aiOn && estimate?.on ? estimate.dollars : null
  const usd = (d: number) => d < 0.01 ? 'under 1¢' : `$${d.toFixed(2)}`
  const say = (s: number) => s < 60 ? `${s} s` : `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`

  return (
    <Dialog title="Two picks, then your video" sub={data ? `From the clips: ${data.about}. Length, pace and captions are read from the footage; change any of it in Frames.` : 'Reading your clips…'}
            onClose={onCancel} busy={busy} width={560}
            footer={<>
              {busy && progress && (
                <span className="mr-auto self-center text-[12px] text-muted">
                  {progress.line}{progress.total ? ` ${progress.done}/${progress.total}` : ''} · {Math.round(progress.elapsed)} s
                </span>
              )}
              <Button variant="ghost" onClick={onCancel} disabled={busy}>Not yet</Button>
              <Button variant="primary" onClick={() => onDone(fmt, lk, withMusic, chosenVibe, cost)} disabled={!data || busy || (aiOn && cost == null)}>
                {busy ? 'Making it…' : cost != null ? `Make my video · ${usd(cost)}` : 'Make my video'}
              </Button>
            </>}>
      <div className="space-y-4">
        {ai && onAI && (
          // what this edit will cost with AI, before anything is spent
          <div className="flex items-center gap-3 rounded-xl border border-line px-3 py-2.5">
            <AISwitch ai={ai} onToggle={onAI} busy={busy} />
            <p className="font-serif text-[15px] leading-snug text-zinc-200">
              {!ai.available ? 'No AI key on this Mac, so the usual rules make the edit.'
                : ai.on && chosenVibe ? 'Cutting it like a vibe follows that vibe, so AI doesn’t plan this one. Free.'
                : !aiOn ? 'Off: the usual rules make the edit, free.'
                : cost == null ? 'Working out what this edit costs…'
                : <>AI plans this edit into chapters: about <b>{usd(cost)}</b> ({estimate!.moments} moments, {estimate!.model}). Nothing is spent until you press Make.</>}
            </p>
          </div>
        )}
        <div>
          <div className="mb-1.5 flex items-baseline gap-2 text-[11px] font-semibold uppercase tracking-wider text-muted">Which frame?
            {last?.format && format === null && <span className="font-normal normal-case tracking-normal">as last time{data?.suggested && data.suggested !== last.format ? ` · the footage suggests ${data.suggested}` : ''}</span>}
          </div>
          <div className="grid grid-cols-3 gap-2" role="radiogroup" aria-label="Frame">
            {(data?.formats ?? []).map((f, i) => (
              <button key={f.key} type="button" role="radio" aria-checked={fmt === f.key} ref={i === 0 ? first : undefined}
                      onClick={() => setFormat(f.key)}
                      className={`flex flex-col items-center gap-2 rounded-xl border px-2 py-3 text-center ${fmt === f.key ? 'border-accent bg-raised text-zinc-100' : 'border-line text-zinc-400 hover:text-zinc-200'}`}>
                <span className={`block rounded-[3px] border-2 ${fmt === f.key ? 'border-accent' : 'border-zinc-500'} ${GLYPH[f.key] ?? 'h-5 w-5'}`} aria-hidden />
                <span className="font-serif text-[14px] leading-tight">{f.label.split(' · ')[0]}</span>
                <span className="text-[10px] leading-tight text-muted">{f.label.split(' · ')[1]} · about {say(f.seconds)}</span>
              </button>
            ))}
          </div>
          {data && data.portrait_share > 0 && data.portrait_share < 1 && (
            <p className="mt-1 text-[10px] text-muted">{Math.round(data.portrait_share * 100)}% of your footage is upright; the rest gets black bars in a vertical frame, and the other way round.</p>
          )}
        </div>
        <div>
          <div className="mb-1.5 flex items-baseline gap-2 text-[11px] font-semibold uppercase tracking-wider text-muted">Which look?
            {last?.look && look === null && <span className="font-normal normal-case tracking-normal">as last time</span>}
          </div>
          <div className="flex flex-wrap gap-1.5" role="radiogroup" aria-label="Look">
            {(data?.looks ?? []).map((l) => (
              <button key={l.id} type="button" role="radio" aria-checked={lk === l.id} onClick={() => setLook(l.id)} title={l.line}
                      className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[12px] ${lk === l.id ? 'border-accent bg-raised text-zinc-100' : 'border-line text-zinc-400 hover:text-zinc-200'}`}>
                <span className="flex" aria-hidden>{l.palette.slice(0, 3).map((c) => <i key={c} className="block size-2.5 rounded-full ring-1 ring-black/40" style={{ background: c }} />)}</span>
                {l.name}
              </button>
            ))}
          </div>
          {data && <p className="mt-1 font-serif text-[13px] text-zinc-300">{data.looks.find((l) => l.id === lk)?.line}</p>}
          <p className="mt-0.5 text-[10px] text-muted">A look sets the words, the colour, how parts join and the music's feel. Change it later under Captions.</p>
        </div>
        {data && (data.vibes?.length ?? 0) > 0 && (
          <div>
            <div className="mb-1.5 flex items-baseline gap-2 text-[11px] font-semibold uppercase tracking-wider text-muted">Cut it like
              {last?.vibe && vibe === undefined && <span className="font-normal normal-case tracking-normal">as last time</span>}
            </div>
            <div className="flex flex-wrap gap-1.5" role="radiogroup" aria-label="Cut it like">
              <button type="button" role="radio" aria-checked={chosenVibe === null} onClick={() => setVibe(null)}
                      className={`rounded-full border px-2.5 py-1 text-[12px] ${chosenVibe === null ? 'border-accent bg-raised text-zinc-100' : 'border-line text-zinc-400 hover:text-zinc-200'}`}>
                This frame's own pace
              </button>
              {data.vibes!.map((v) => (
                <button key={v.id} type="button" role="radio" aria-checked={chosenVibe === v.id} onClick={() => setVibe(v.id)} title={v.line}
                        className={`rounded-full border px-2.5 py-1 text-[12px] ${chosenVibe === v.id ? 'border-accent bg-raised text-zinc-100' : 'border-line text-zinc-400 hover:text-zinc-200'}`}>
                  {v.kind === 'library' ? '✦ ' : ''}{v.name}
                </button>
              ))}
            </div>
            <p className="mt-1 font-serif text-[13px] text-zinc-300">{data.vibes!.find((v) => v.id === chosenVibe)?.line ?? 'Shot length, hook and words set by the frame you picked.'}</p>
          </div>
        )}
        <label className="flex items-center gap-2 text-[12px] text-zinc-300">
          <input type="checkbox" checked={withMusic} onChange={(e) => setMusic(e.target.checked)} />
          Music under it{last?.music && music === null ? <span className="text-muted"> · as last time</span> : null}
        </label>
      </div>
    </Dialog>
  )
}

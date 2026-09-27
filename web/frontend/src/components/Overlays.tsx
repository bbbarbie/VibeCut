import { useEffect, useRef, useState } from 'react'
import { KIND_META } from '../overlayDraw'
import { clock, type SeqItem } from '../sequence'
import type { Overlay, OverlayFinding, OverlayKind, OverlayPos, Overlays as OverlayData } from '../types'

type Ops = (ops: Record<string, unknown>[], label: string) => Promise<unknown>

const ADDABLE: OverlayKind[] = ['title', 'part', 'name', 'caption', 'date', 'end', 'chapters']
const GRID: OverlayPos[] = ['top-left', 'top', 'top-right', 'left', 'center', 'right', 'bottom-left', 'bottom', 'bottom-right']
const ANIMS = [['fade', 'Fade'], ['rise', 'Rise'], ['slide', 'Slide'], ['type', 'Type on']] as const
const r2 = (x: number) => Math.round(x * 100) / 100

// Words on screen: titles, part labels, name tags, captions, dates, an end
// card. Same panel at both levels -- Story says where in parts ("Start of
// “Market”"), Frames in times. Every change is an operation in the same log
// as a cut, with the same Undo.
export function Overlays({ data, items, level, selected, busy, onSelect, onRun, onSuggest, onWatch, newAt }: {
  data: OverlayData
  items: SeqItem[]
  level: 'story' | 'frames'
  selected: string | null
  busy: boolean
  onSelect: (id: string | null) => void
  onRun: Ops
  onSuggest: () => Promise<void>
  onWatch: (o: Overlay) => void
  newAt: (kind: OverlayKind) => Record<string, unknown>   // where a new one goes, and its first words
}) {
  const [adding, setAdding] = useState(false)
  const [suggesting, setSuggesting] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const { items: list, style, findings } = data
  const byOverlay = new Map<string, OverlayFinding[]>()
  for (const f of findings) byOverlay.set(f.overlay, [...(byOverlay.get(f.overlay) ?? []), f])
  const issues = findings.filter((f) => f.verdict === 'bad' || f.verdict === 'warn').length

  const where = (o: Overlay): string => {
    if (level === 'frames') return `${clock(o.start)} – ${clock(o.shown_end)}`
    const a = o.anchor
    if (a.to === 'end') return `Last ${r2(o.shown_end - o.start)}s of the video`
    if (a.to === 'edit') return o.at < 0.5 ? 'Start of the video' : o.kind === 'chapters' ? 'Whole video' : `${r2(o.at)}s in`
    if (a.to === 'beat') {
      const it = items.find((x) => x.beat_id === a.id)
      return o.dur == null ? `Throughout “${it?.beat_title ?? 'a part'}”` : `Start of “${it?.beat_title ?? 'a part'}”`
    }
    const it = items.find((x) => x.key === a.id)
    return it ? `On shot ${it.n} in “${it.beat_title}”` : 'On a shot'
  }

  const suggest = async () => {
    setSuggesting(true); setErr(null)
    try { await onSuggest() } catch (e) { setErr((e as Error).message) } finally { setSuggesting(false) }
  }
  const style1 = (patch: Record<string, string>, what: string) => onRun([{ op: 'overlay_style', ...patch }], `You changed the ${what} of all words on screen`)

  return (
    <section className="rounded-xl border border-line bg-raised px-3 py-2.5">
      <div className="flex items-baseline gap-2">
        <h4 className="font-serif text-[15px] text-zinc-100">Words on screen</h4>
        {issues > 0 && <span className="text-[10px] text-amber-300" title="Things a viewer would notice — see each item">{issues} to look at</span>}
        <button type="button" onClick={suggest} disabled={busy || suggesting}
                title="Add a title, part labels, dates, captions from your voiceover, a name tag and an end card — only where the edit already knows the words. Nothing you added is replaced."
                className="ml-auto rounded-md bg-accent px-2 py-0.5 text-[11px] font-semibold text-accent-ink disabled:opacity-40">
          {suggesting ? 'Adding…' : list.length ? '✦ Fill in the rest' : '✦ Add titles for me'}
        </button>
      </div>
      {err && <p className="mt-1.5 text-[11px] text-rose-300">{err}</p>}

      {/* one look for the whole video */}
      <div className="mt-2.5 space-y-1.5 border-t border-line pt-2 text-[11px]">
        {data.look && (
          <>
            <Row label="Look">
              <div className="flex flex-wrap gap-1">
                {data.look.all.map((l) => (
                  <button key={l.id} type="button" title={`${l.line} (${l.status === 'prior' ? 'first guess' : 'calibrated'})`}
                          onClick={() => onRun([{ op: 'set_look', look: data.look!.id === l.id ? null : l.id }],
                            data.look!.id === l.id ? 'You took the look off' : `You chose the ${l.name} look`)}
                          className={`flex items-center gap-1 rounded-md border px-1.5 py-0.5 ${data.look!.id === l.id ? 'border-accent text-zinc-100' : 'border-line text-zinc-400 hover:text-zinc-200'}`}>
                    <span className="flex">{l.palette.slice(0, 2).map((c) => <i key={c} className="block size-2 rounded-full" style={{ background: c }} />)}</span>
                    {l.name}
                  </button>
                ))}
              </div>
            </Row>
            {data.look.id && data.look.overrides.length > 0 && (
              <p className="pl-16 text-[10px] text-amber-200/80">
                Your {data.look.overrides.join(' and ')} differ{data.look.overrides.length === 1 ? 's' : ''} from the look.{' '}
                <button type="button" className="underline" onClick={() => onRun([{ op: 'set_look', look: data.look!.id, reset: true }], 'You went back to the look’s own style')}>
                  Use the look’s
                </button>
              </p>
            )}
          </>
        )}
        <Row label="Font">
          <Seg value={style.font} options={[['Clean', 'Clean'], ['Editorial', 'Editorial'], ['Rounded', 'Rounded'], ['Mono', 'Typewriter'], ['Condensed', 'Condensed']]}
               onChange={(v) => style1({ font: v }, 'font')} fonts />
        </Row>
        <Row label="Colour">
          <Swatch key={'c' + style.color} value={style.color} title="Text colour" onChange={(v) => style1({ color: v }, 'text colour')} />
          <Swatch key={'a' + style.accent} value={style.accent} title="Accent (labels, handles, the chapter bar)" onChange={(v) => style1({ accent: v }, 'accent colour')} />
          <span className="ml-1 text-[10px] text-muted">text · accent</span>
        </Row>
        <Row label="Backing">
          <Seg value={style.backing} options={[['shadow', 'Shadow'], ['box', 'Box'], ['none', 'None']]}
               onChange={(v) => style1({ backing: v }, 'backing')} />
        </Row>
        <Row label="Captions">
          <Seg value={style.captions} options={[['bottom', 'Bottom'], ['center', 'Middle']]}
               onChange={(v) => style1({ captions: v }, 'caption position')} />
        </Row>
        <p className="text-[10px] leading-snug text-muted">One font, one colour and one caption position for the whole video — mixing them is an amateur tell.</p>
      </div>

      <div className="mt-2 border-t border-line pt-2">
        {list.length === 0 && (
          <p className="text-[11px] leading-snug text-muted">
            Nothing on screen yet. <b className="font-medium text-zinc-300">Add titles for me</b> fills in what the edit already knows — part names, dates, your voiceover’s lines — or add one yourself.
          </p>
        )}
        <ol className="space-y-1">
          {list.map((o) => (
            <Item key={o.id} o={o} where={where(o)} open={selected === o.id} findings={byOverlay.get(o.id) ?? []} level={level}
                  onToggle={() => onSelect(selected === o.id ? null : o.id)} onRun={onRun} onWatch={() => onWatch(o)} />
          ))}
        </ol>
        <div className="relative mt-2">
          <button type="button" onClick={() => setAdding((a) => !a)} disabled={busy}
                  className="w-full rounded-lg border border-dashed border-line px-2 py-1.5 text-left text-[11px] text-muted hover:text-zinc-200 disabled:opacity-40">
            + Add {level === 'frames' ? 'at the playhead' : 'words'}…
          </button>
          {adding && (
            <div className="mt-1 grid grid-cols-2 gap-1">
              {ADDABLE.map((k) => (
                <button key={k} type="button" title={KIND_META[k].hint}
                        onClick={async () => {
                          setAdding(false)
                          await onRun([{ op: 'add_overlay', kind: k, ...newAt(k) }], `You added a ${KIND_META[k].label.toLowerCase()}`)
                        }}
                        className="flex items-center gap-1.5 rounded-md bg-panel px-2 py-1 text-left text-[11px] text-zinc-200 hover:bg-zinc-800">
                  <span className="w-3 text-center" style={{ color: KIND_META[k].color }}>{KIND_META[k].icon}</span>{KIND_META[k].label}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </section>
  )
}

function Item({ o, where, open, findings, level, onToggle, onRun, onWatch }: {
  o: Overlay; where: string; open: boolean; findings: OverlayFinding[]; level: 'story' | 'frames'
  onToggle: () => void; onRun: Ops; onWatch: () => void
}) {
  const meta = KIND_META[o.kind]
  const worst = findings.some((f) => f.verdict === 'bad') ? 'bad' : findings.length ? 'warn' : null
  const ref = useRef<HTMLLIElement>(null)
  useEffect(() => { if (open) ref.current?.scrollIntoView({ block: 'nearest' }) }, [open])
  const edit = (patch: Record<string, unknown>, what: string) =>
    onRun([{ op: 'edit_overlay', overlay: o.id, ...patch }], `You changed the ${what} of the ${meta.label.toLowerCase()}`)
  const length = r2(o.end - o.start)
  const fills = o.dur == null
  return (
    <li ref={ref} className={`rounded-lg ${open ? 'bg-panel ring-1 ring-zinc-700' : 'hover:bg-panel/60'}`}>
      <button type="button" onClick={onToggle} className="flex w-full items-start gap-2 px-2 py-1.5 text-left">
        <span className="mt-px w-3 shrink-0 text-center text-[12px]" style={{ color: meta.color }} title={meta.label}>{meta.icon}</span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-[12px] text-zinc-100">{o.kind === 'chapters' ? 'Chapter bar' : o.text}</span>
          <span className="block truncate text-[10px] text-muted">{meta.label} · {where}</span>
        </span>
        {worst && <span className={`mt-0.5 text-[10px] ${worst === 'bad' ? 'text-rose-300' : 'text-amber-300'}`}
                        title={findings.map((f) => f.message).join('\n')}>{worst === 'bad' ? '●' : '▲'}</span>}
      </button>
      {open && (
        <div className="space-y-2 px-2 pb-2.5 pl-7 text-[11px]">
          {findings.map((f) => (
            <p key={f.rule} className={`leading-snug ${f.verdict === 'bad' ? 'text-rose-300' : 'text-amber-200'}`}>{f.message}</p>
          ))}
          {o.kind !== 'chapters' && <>
            <Words key={'t' + o.text} label="Words" value={o.text} onCommit={(v) => v.trim() && edit({ text: v }, 'words')} />
            {!['caption', 'date'].includes(o.kind) && (
              <Words key={'s' + o.sub} label={o.kind === 'part' ? 'Small line above' : o.kind === 'name' ? 'Handle or role' : 'Second line'} value={o.sub}
                     onCommit={(v) => edit({ sub: v }, 'second line')} />
            )}
          </>}
          {!['caption', 'chapters'].includes(o.kind) && (
            <Row label="Place">
              <div className="grid grid-cols-3 gap-0.5" role="radiogroup" aria-label="Position on screen">
                {GRID.map((p) => (
                  <button key={p} type="button" role="radio" aria-checked={o.pos === p} title={p.replace('-', ' ')}
                          onClick={() => o.pos !== p && edit({ pos: p }, 'place')}
                          className={`h-3.5 w-5 rounded-[3px] ${o.pos === p ? 'bg-accent' : 'bg-zinc-700 hover:bg-zinc-500'}`} />
                ))}
              </div>
              <Seg value={o.size} options={[['S', 'S'], ['M', 'M'], ['L', 'L']]} onChange={(v) => edit({ size: v }, 'size')} />
            </Row>
          )}
          {o.kind !== 'chapters' && (
            <Row label="Comes in">
              <Seg value={o.anim} options={ANIMS.map(([k, n]) => [k, n])} onChange={(v) => edit({ anim: v }, 'animation')} />
            </Row>
          )}
          <Row label="Length">
            <Stepper value={length} disabled={fills}
                     onChange={(v) => edit({ dur: Math.max(0.5, r2(v)) }, 'length')} />
            {(o.anchor.to === 'beat' || o.anchor.to === 'shot') && (
              <label className="flex items-center gap-1 text-[10px] text-muted">
                <input type="checkbox" checked={fills} onChange={() => edit({ dur: fills ? length : null }, 'length')} className="accent-[#b9d9eb]" />
                whole {o.anchor.to === 'beat' ? 'part' : 'shot'}
              </label>
            )}
          </Row>
          {o.anchor.to !== 'end' && o.kind !== 'chapters' && (
            <Row label="Starts">
              <button type="button" onClick={() => edit({ start: Math.max(0, r2(o.start - 0.5)) }, 'timing')}
                      className="rounded bg-zinc-800 px-1.5 py-0.5 text-zinc-200 hover:bg-zinc-700">½s earlier</button>
              <button type="button" onClick={() => edit({ start: r2(o.start + 0.5) }, 'timing')}
                      className="rounded bg-zinc-800 px-1.5 py-0.5 text-zinc-200 hover:bg-zinc-700">½s later</button>
              {level === 'frames' && <span className="text-[10px] text-muted">or drag it on the timeline</span>}
            </Row>
          )}
          <div className="flex gap-2 pt-1">
            <button type="button" onClick={onWatch} className="rounded-md border border-line px-2 py-0.5 text-zinc-200 hover:bg-zinc-800">▶ See it in the video</button>
            <button type="button" onClick={() => onRun([{ op: 'drop_overlay', overlay: o.id }], `You removed the ${meta.label.toLowerCase()}`)}
                    className="rounded-md px-2 py-0.5 text-rose-300 hover:bg-rose-500/10">Remove</button>
          </div>
        </div>
      )}
    </li>
  )
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2">
      <span className="w-14 shrink-0 text-[10px] uppercase tracking-wider text-muted">{label}</span>
      <div className="flex min-w-0 flex-wrap items-center gap-1.5">{children}</div>
    </div>
  )
}

function Seg<T extends string>({ value, options, onChange, fonts }: {
  value: T; options: readonly (readonly [T | string, string])[]; onChange: (v: T) => void; fonts?: boolean
}) {
  const family = (k: string) => (!fonts ? undefined : k === 'Editorial' ? 'var(--font-serif)' : k === 'Rounded' ? 'Nunito, sans-serif'
    : k === 'Mono' ? '"Courier New", ui-monospace, monospace' : k === 'Condensed' ? 'Impact, "Arial Narrow", sans-serif' : undefined)
  return (
    <div className="flex rounded-md border border-line bg-panel p-px">
      {options.map(([k, name]) => (
        <button key={k} type="button" aria-pressed={value === k} onClick={() => value !== k && onChange(k as T)}
                style={{ fontFamily: family(k) }}
                className={`rounded px-1.5 py-px text-[11px] ${value === k ? 'bg-zinc-700 text-zinc-100' : 'text-muted hover:text-zinc-200'}`}>
          {name}
        </button>
      ))}
    </div>
  )
}

function Swatch({ value, title, onChange }: { value: string; title: string; onChange: (v: string) => void }) {
  const [v, setV] = useState(value)   // keyed on value by the caller: a new value remounts
  return (
    <label title={title} className="relative size-5 cursor-pointer overflow-hidden rounded-md ring-1 ring-zinc-600" style={{ background: v }}>
      <input type="color" value={v} onChange={(e) => setV(e.target.value)}
             onBlur={() => v !== value && onChange(v)} className="absolute inset-0 cursor-pointer opacity-0" />
    </label>
  )
}

function Words({ label, value, onCommit }: { label: string; value: string; onCommit: (v: string) => void }) {
  const [v, setV] = useState(value)   // keyed on value by the caller: a new value remounts
  const commit = () => { if (v !== value) onCommit(v) }
  return (
    <label className="block">
      <span className="text-[10px] uppercase tracking-wider text-muted">{label}</span>
      <input value={v} maxLength={140} onChange={(e) => setV(e.target.value)} onBlur={commit}
             onKeyDown={(e) => { e.stopPropagation(); if (e.key === 'Enter') (e.target as HTMLInputElement).blur(); if (e.key === 'Escape') { setV(value); (e.target as HTMLInputElement).blur() } }}
             className="mt-0.5 block w-full rounded-md border border-line bg-ink px-2 py-1 text-[12px] text-zinc-100 outline-none focus:border-zinc-500" />
    </label>
  )
}

function Stepper({ value, onChange, disabled }: { value: number; onChange: (v: number) => void; disabled?: boolean }) {
  return (
    <div className={`flex items-center rounded-md border border-line bg-panel ${disabled ? 'opacity-40' : ''}`}>
      <button type="button" disabled={disabled} onClick={() => onChange(value - 0.5)} className="px-1.5 text-zinc-300 hover:text-white">−</button>
      <span className="w-12 text-center tabular-nums text-zinc-100">{value.toFixed(1)}s</span>
      <button type="button" disabled={disabled} onClick={() => onChange(value + 0.5)} className="px-1.5 text-zinc-300 hover:text-white">+</button>
    </div>
  )
}

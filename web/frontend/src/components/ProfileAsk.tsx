import { useEffect, useRef, useState, type ReactNode } from 'react'
import { api, type CreatorHabits } from '../api'
import { Button, cx, Dialog, inputCls } from '../ui'

// Asked once, right after the first export (profile.py): the email names
// the profile, everything else is a tap on a picture. What this video
// used is already picked, so most people only type their email. Kept on
// this Mac; the next video starts from it, and it keeps up with what's
// changed in Frames.

type Pick = { key: string; label: string; art: ReactNode }

const KINDS: Pick[] = [
  { key: 'vlog', label: 'Vlogs', art: <Strip /> },
  { key: 'lesson', label: 'Lessons', art: <Board /> },
]
const PACES: Pick[] = [
  { key: 'fast', label: 'Quick', art: <Beats n={9} /> },
  { key: 'balanced', label: 'Steady', art: <Beats n={5} /> },
  { key: 'calm', label: 'Calm', art: <Beats n={3} /> },
]
const JOINS: Pick[] = [
  { key: 'cut', label: 'Straight cut', art: <Join mid="none" /> },
  { key: 'soft', label: 'Soft fade', art: <Join mid="blend" /> },
  { key: 'dip', label: 'Fade to black', art: <Join mid="#111" /> },
  { key: 'flash', label: 'Quick flash', art: <Join mid="#fff" /> },
]
const CAPTIONS: Pick[] = [
  { key: 'bold', label: 'Big & bold', art: <Word font='"Anton", Impact, "Arial Narrow", sans-serif' weight={400} upper color="#fff" shadow /> },
  { key: 'clean', label: 'Clean', art: <Word font='system-ui, -apple-system, "Helvetica Neue", sans-serif' weight={700} color="#fff" shadow /> },
  { key: 'cozy', label: 'Cozy', art: <Word font='"EB Garamond", serif' weight={500} italic lower color="#f6ebd9" /> },
  { key: 'quiet', label: 'Quiet', art: <Word font='"EB Garamond", serif' weight={500} italic color="#efe8dd" small /> },
  { key: 'playful', label: 'Bright', art: <Word font='"Nunito", system-ui, sans-serif' weight={800} color="#ffd84d" box /> },
  { key: 'none', label: 'No captions', art: <Word none /> },
]

// what this video used, so the popup opens on it (looks/*.json)
const LOOK_CAPTIONS: Record<string, string> = { hype: 'bold', clean: 'clean', cozy: 'cozy', quiet: 'quiet', playful: 'playful' }
const LOOK_JOINS: Record<string, string> = { cinematic: 'cut', clean: 'cut', hype: 'cut', cozy: 'soft', film: 'soft', quiet: 'dip', playful: 'flash' }
const EMAIL = /^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$/

export function ProfileAsk({ current, onDone }: {
  current: { pace?: string; look?: string | null; joins?: string; captions?: boolean }
  onDone: (p: CreatorHabits | null) => void
}) {
  const [email, setEmail] = useState('')
  const [kind, setKind] = useState<string | null>('vlog')
  const [pace, setPace] = useState<string | null>(current.pace ?? null)
  const [joins, setJoins] = useState<string | null>(current.joins ?? (current.look ? LOOK_JOINS[current.look] ?? null : null))
  const [captions, setCaptions] = useState<string | null>(current.captions === false ? 'none' : current.look ? LOOK_CAPTIONS[current.look] ?? null : null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const field = useRef<HTMLInputElement>(null)
  useEffect(() => { field.current?.focus() }, [])
  const ok = EMAIL.test(email.trim())

  const skip = () => { if (!busy) api.profileSkip().catch(() => {}).finally(() => onDone(null)) }
  const save = async () => {
    if (!ok) { setError('That doesn’t look like an email address yet.'); return }
    setBusy(true); setError(null)
    try { onDone(await api.profileSave({ email: email.trim(), kind, pace, joins, captions })) }
    catch (e) { setError((e as Error).message); setBusy(false) }
  }

  return (
    <Dialog title="Your first video is done! 🎉" width={640} busy={busy} onClose={skip} id="profile-title"
            sub={<span className="font-serif text-[15px] text-zinc-300">Tell VibeCut how you like your videos, and the next one starts that way. It stays on this Mac.</span>}
            footer={<>
              <Button variant="ghost" onClick={skip} disabled={busy}>Skip</Button>
              <Button variant="primary" onClick={save} disabled={busy || !ok}>{busy ? 'Saving…' : 'Save my profile'}</Button>
            </>}>
      <form className="space-y-3.5" onSubmit={(e) => { e.preventDefault(); save() }}>
        <label className="block">
          <span className="mb-1.5 block font-serif text-[17px] text-zinc-100">Your email</span>
          <input ref={field} type="email" autoComplete="email" value={email} placeholder="you@example.com"
                 onChange={(e) => { setEmail(e.target.value); setError(null) }} className={cx(inputCls, 'text-[15px]')} />
          <span className="mt-1 block font-serif text-[14px] text-zinc-300">It only names your profile. Nothing is sent anywhere.</span>
          {error && <span className="mt-1 block text-[14px] text-rose-300">{error}</span>}
        </label>
        <Row title="What do you make?" picks={KINDS} value={kind} onPick={setKind} />
        <Row title="How fast do you like the cuts?" picks={PACES} value={pace} onPick={setPace} />
        <Row title="How should one shot flow into the next?" picks={JOINS} value={joins} onPick={setJoins} />
        <Row title="Your captions" picks={CAPTIONS} value={captions} onPick={setCaptions} />
        <p className="font-serif text-[14px] text-zinc-300">We picked what this video used. Whatever you change in your next edits, VibeCut keeps up.</p>
      </form>
    </Dialog>
  )
}

function Row({ title, picks, value, onPick }: { title: string; picks: Pick[]; value: string | null; onPick: (k: string) => void }) {
  return (
    <div>
      <div className="mb-1 font-serif text-[17px] text-zinc-100">{title}</div>
      <div className="flex flex-wrap gap-2" role="radiogroup" aria-label={title}>
        {picks.map((p) => (
          <button key={p.key} type="button" role="radio" aria-checked={value === p.key} onClick={() => onPick(p.key)}
                  className={cx('flex w-[92px] flex-col items-center gap-1 rounded-xl border p-1.5 text-center transition-colors',
                    value === p.key ? 'border-accent bg-raised text-zinc-100 ring-1 ring-accent' : 'border-line text-zinc-300 hover:bg-raised')}>
            <span className="grid h-10 w-full place-items-center overflow-hidden rounded-lg" aria-hidden>{p.art}</span>
            <span className="font-serif text-[14px] leading-tight">{p.label}</span>
          </button>
        ))}
      </div>
    </div>
  )
}

// ---- the little pictures ----------------------------------------------------

const SKY = ['#f4a261', '#8ecae6', '#90be6d', '#e76f51']

function Strip() {
  return <span className="flex gap-1">{SKY.slice(0, 3).map((c) => <i key={c} className="block h-8 w-5 rounded-[4px]" style={{ background: `linear-gradient(${c}, #2a3440)` }} />)}</span>
}

function Board() {
  return (
    <span className="relative block h-9 w-16 rounded-[4px] bg-[#2f4f3f] p-1.5">
      {[40, 32, 24].map((w) => <i key={w} className="mb-1 block h-[3px] rounded bg-white/80" style={{ width: w }} />)}
      <i className="absolute -right-1 bottom-0 block size-3 rounded-full bg-[#f4a261]" />
    </span>
  )
}

function Beats({ n }: { n: number }) {
  return (
    <span className="flex h-7 w-[72px] gap-[2px]">
      {Array.from({ length: n }, (_, i) => <i key={i} className="block h-full flex-1 rounded-[3px]" style={{ background: SKY[i % SKY.length] }} />)}
    </span>
  )
}

function Join({ mid }: { mid: string }) {
  const a = SKY[0], b = SKY[1]
  const bg = mid === 'none' ? `linear-gradient(90deg, ${a} 50%, ${b} 50%)`
    : mid === 'blend' ? `linear-gradient(90deg, ${a} 25%, ${b} 75%)`
      : `linear-gradient(90deg, ${a} 25%, ${mid} 45%, ${mid} 55%, ${b} 75%)`
  return <span className="block h-7 w-[72px] rounded-[4px]" style={{ background: bg }} />
}

function Word({ font, weight, color, upper, lower, italic, shadow, box, small, none }: {
  font?: string; weight?: number; color?: string; upper?: boolean; lower?: boolean; italic?: boolean
  shadow?: boolean; box?: boolean; small?: boolean; none?: boolean
}) {
  return (
    <span className="grid h-full w-full place-items-center" style={{ background: 'linear-gradient(160deg, #6b8fa8, #3a4a3f)' }}>
      {!none && (
        <span style={{
          fontFamily: font, fontWeight: weight, color, fontStyle: italic ? 'italic' : undefined, fontSize: small ? 15 : 19, lineHeight: 1,
          textTransform: upper ? 'uppercase' : lower ? 'lowercase' : undefined, letterSpacing: upper ? '0.02em' : undefined,
          textShadow: shadow ? '0 1px 3px rgba(0,0,0,.7)' : undefined,
          ...(box ? { background: '#ff6fa8', color: '#fff', padding: '2px 5px', borderRadius: 4 } : {}),
        }}>Lunch</span>
      )}
    </span>
  )
}

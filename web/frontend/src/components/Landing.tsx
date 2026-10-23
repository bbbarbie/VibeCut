import { useEffect, useRef, useState, type ReactNode } from 'react'
import { go } from '../router'
import { cx, Wordmark } from '../ui'

// The page that sells the product: what it is, what it can do, how it works,
// what it fixes, what it costs, and the honest limits. 2026-10-23, the user:
// "less words, more straight to the point, and a carousel of animations that
// we can do". So every section says one thing, and the carousel (Moves) plays
// the app's own caption entrances, transitions and effects, by their menu names. It lives at #/welcome so the app's
// own home stays as bare as it is (sarah, 2026-10-06).
//
// 2026-10-23, the user: "be cute, match the vibe of current YC companies'
// landing pages". So: a floating pill nav, an announcement pill, a big rounded
// headline with one Garamond italic word, a product window, a marquee, a bento
// grid, pastel tiles and a plain mark (no mascot). The app's paper and
// blue stay underneath so opening the app still feels like the same place.
// No logos, quotes or backers we don't have. The copy keeps to the promise in
// CLAUDE.md: "no amateur tells", never "beautiful".

const NAV = [
  ['moves', 'What it can do'],
  ['how', 'How it works'],
  ['pricing', 'Pricing'],
  ['faq', 'FAQ'],
] as const

// Pastels for the tiles. Written as hex rather than Tailwind's palette
// because the app flips zinc / rose / amber etc. for its paper theme.
const P = {
  pink: '#ffe0e8', butter: '#fff3c4', mint: '#d6f2e3', lilac: '#e8e2ff', sky: '#dcecfb', cream: '#fffdf9',
}
// The app's own faces (index.css): EB Garamond for words people read and for
// the wordmark, the system sans for labels. Nunito stays only inside the drawn
// captions, because it is the face the app draws captions in.
const display = 'font-serif font-medium tracking-[-0.015em]'
const ink = 'text-[#1d1a17]'
const soft = 'text-[#5d5650]'

export function Landing() {
  const [scrolled, setScrolled] = useState(false)
  useEffect(() => { document.title = 'VibeCut — a hundred clips in, one video out' }, [])
  const openApp = () => go({ kind: 'projects' })
  return (
    <div className={cx('lc relative h-full overflow-y-auto overflow-x-hidden scroll-smooth bg-[#fbf8f2] font-sans', ink)}
         onScroll={(e) => setScrolled(e.currentTarget.scrollTop > 8)}>
      <style>{CSS}</style>
      <div aria-hidden className="lc-dots pointer-events-none absolute inset-x-0 top-0 h-[900px]" />

      <header className="sticky top-3 z-30 px-4">
        <div className={cx('mx-auto flex h-14 max-w-[980px] items-center gap-5 rounded-full border px-3 pl-5 transition-all',
          scrolled ? 'border-[#e8e2d8] bg-white/85 shadow-[0_8px_30px_-12px_rgba(29,26,23,0.25)] backdrop-blur' : 'border-transparent bg-transparent')}>
          <a href="#/welcome" className="flex shrink-0 items-center gap-2" onClick={(e) => { e.preventDefault(); jumpTop() }}>
            <Mark className="size-7" />
            <Wordmark className="text-[22px] text-[#1d1a17]" />
          </a>
          <nav className={cx('hidden flex-1 items-center justify-center gap-1 text-[14px] font-medium md:flex', soft)}>
            {NAV.map(([id, label]) => (
              <a key={id} href={`#/welcome#${id}`} onClick={(e) => { e.preventDefault(); jump(id) }}
                 className="rounded-full px-3 py-1.5 transition-colors hover:bg-[#1d1a17]/5 hover:text-[#1d1a17]">{label}</a>
            ))}
          </nav>
          <div className="flex-1 md:hidden" />
          <Pill onClick={openApp} small>Open VibeCut</Pill>
        </div>
      </header>

      <main className="relative">
        <Hero onStart={openApp} />
        <Marquee />
        <Moves />
        <How onStart={openApp} />
        <Promise />
        <Fixes />
        <Pricing onStart={openApp} />
        <Faq />
        <Closing onStart={openApp} />
      </main>

      <footer className="px-6 pb-10">
        <div className={cx('mx-auto flex max-w-[1080px] flex-wrap items-center gap-x-6 gap-y-3 border-t border-[#e8e2d8] pt-8 text-[14px]', soft)}>
          <span className="flex items-center gap-2"><Mark className="size-5" /><Wordmark className="text-[18px] text-[#1d1a17]" /></span>
          <span>For people who'd rather film than edit.</span>
          <span className="flex-1" />
          <a href="#/welcome" onClick={(e) => { e.preventDefault(); jump('faq') }} className="hover:text-[#1d1a17]">FAQ</a>
          <a href="#/profile" className="hover:text-[#1d1a17]">Your profile</a>
          <span>© {new Date().getFullYear()} VibeCut</span>
        </div>
      </footer>
    </div>
  )
}

function jump(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}
function jumpTop() {
  document.querySelector('.lc')?.scrollTo({ top: 0, behavior: 'smooth' })
}

/* ---------- small parts ---------- */

/** The one button shape on this page: a pill, dark or white. */
function Pill({ children, onClick, light, small, className }: {
  children: ReactNode; onClick: () => void; light?: boolean; small?: boolean; className?: string
}) {
  return (
    <button type="button" onClick={onClick}
            className={cx('group inline-flex shrink-0 items-center justify-center gap-2 rounded-full font-semibold transition-all active:scale-[0.97]',
              small ? 'h-10 px-4 text-[14px]' : 'h-12 px-6 text-[16px]',
              light ? 'border border-[#e2dcd2] bg-white text-[#1d1a17] shadow-sm hover:border-[#cfc7bb]'
                    : 'bg-[#1d1a17] text-white shadow-[0_6px_20px_-6px_rgba(29,26,23,0.5)] hover:-translate-y-px hover:bg-[#2c2824]',
              className)}>
      {children}
      {!light && <span aria-hidden className="transition-transform group-hover:translate-x-0.5">→</span>}
    </button>
  )
}

/** VibeCut's mark: one frame cut in two on a diagonal, the second shot a
    shade lighter. Plain on purpose (the user, 2026-10-23: the clapperboard
    mascot was "too cartoonish"); the same drawing is public/favicon.svg. */
function Mark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={cx('shrink-0', className)} aria-hidden>
      <defs><clipPath id="vc-mark-frame"><rect x="6.5" y="9" width="19" height="14" rx="2.5" /></clipPath></defs>
      <rect width="32" height="32" rx="9" fill="#1f5f8b" />
      <g clipPath="url(#vc-mark-frame)">
        <path d="M0 0 H18.5 L10.5 32 H0 Z" fill="#fff" />
        <path d="M20.7 0 H32 V32 H12.7 Z" fill="#fff" fillOpacity="0.6" />
      </g>
    </svg>
  )
}

function Kicker({ children, className }: { children: ReactNode; className?: string }) {
  return <span className={cx('inline-flex items-center gap-1.5 rounded-full border border-[#e2dcd2] bg-white px-3 py-1 text-[12px] font-semibold uppercase tracking-[0.08em] text-accent', className)}>{children}</span>
}

function H2({ children, className }: { children: ReactNode; className?: string }) {
  return <h2 className={cx(display, 'mt-4 text-[40px] leading-[1.08] sm:text-[54px]', className)}>{children}</h2>
}

/** The Garamond italic word every one of these pages has, plus a squiggle. */
function Em({ children, squiggle }: { children: ReactNode; squiggle?: boolean }) {
  return (
    <span className="relative inline-block whitespace-nowrap">
      <span className="font-serif font-medium italic tracking-normal text-accent">{children}</span>
      {squiggle && (
        <svg viewBox="0 0 200 12" preserveAspectRatio="none" className="lc-draw absolute -bottom-1 left-0 h-3 w-full" aria-hidden>
          <path d="M2 8 C 30 2, 50 12, 80 6 S 130 2, 160 7 S 190 5, 198 4" stroke="#ff9fb4" strokeWidth="4" fill="none" strokeLinecap="round" />
        </svg>
      )}
    </span>
  )
}

/* ---------- hero ---------- */

function Hero({ onStart }: { onStart: () => void }) {
  return (
    <section className="relative mx-auto max-w-[1080px] px-6 pt-16 pb-10 text-center sm:pt-24">
      <button type="button" onClick={() => jump('how')}
              className="lc-rise mx-auto inline-flex items-center gap-2 rounded-full border border-[#e2dcd2] bg-white py-1 pr-3 pl-1 text-[13px] font-medium shadow-sm transition-colors hover:border-[#cfc7bb]">
        <span className="rounded-full px-2 py-0.5 text-[12px] font-bold text-[#1d1a17]" style={{ background: P.butter }}>New</span>
        <span className={soft}>Cut your day like a reel you love</span>
        <span className="text-accent">→</span>
      </button>

      <h1 className={cx(display, 'lc-rise mx-auto mt-7 max-w-[860px] text-[50px] leading-[1.02] sm:text-[84px]')} style={{ animationDelay: '60ms' }}>
        A hundred clips in.<br />One video <Em squiggle>you'd post.</Em>
      </h1>
      <p className={cx('lc-rise mx-auto mt-6 max-w-[560px] text-[18px] leading-relaxed sm:text-[20px]', soft)} style={{ animationDelay: '120ms' }}>
        Drop your clips. Get a video with <b className="font-semibold text-[#1d1a17]">no amateur tells</b>.
      </p>
      <div className="lc-rise mt-8 flex flex-wrap items-center justify-center gap-3" style={{ animationDelay: '180ms' }}>
        <Pill onClick={onStart}>Start with your clips</Pill>
        <Pill light onClick={() => jump('moves')}>See what it can do</Pill>
      </div>
      <p className={cx('lc-rise mt-5 flex flex-wrap items-center justify-center gap-x-4 gap-y-1 text-[13px]', soft)} style={{ animationDelay: '220ms' }}>
        <span>🔒 Runs on your Mac</span><span>📵 No upload</span><span>🎁 Free in early access</span>
      </p>

      <div className="lc-rise relative mx-auto mt-14 max-w-[880px]" style={{ animationDelay: '280ms' }}>
        <Sticker className="-top-6 -left-10 rotate-[-8deg]" bg={P.pink} delay={0}>😵‍💫 shaky</Sticker>
        <Sticker className="top-24 -left-16 rotate-[6deg]" bg={P.butter} delay={1.2}>🌚 too dark</Sticker>
        <Sticker className="-top-8 -right-6 rotate-[7deg]" bg={P.mint} delay={0.6}>🎵 on the beat</Sticker>
        <Sticker className="top-40 -right-16 rotate-[-5deg]" bg={P.lilac} delay={1.8}>☕ 7:42 am</Sticker>
        <BeforeAfter />
      </div>
    </section>
  )
}

function Sticker({ children, className, bg, delay }: { children: ReactNode; className: string; bg: string; delay: number }) {
  return (
    <div className={cx('absolute z-10 hidden lg:block', className)}>
      <span className="lc-float block rounded-2xl border-2 border-white px-3 py-1.5 text-[14px] font-bold whitespace-nowrap shadow-[0_10px_24px_-10px_rgba(29,26,23,0.35)]"
            style={{ background: bg, animationDelay: `${delay}s` }}>{children}</span>
    </div>
  )
}

/** The promise as a picture: the shoot as it arrives, then the video. Both
    drawn rather than photographed, because real screenshots show real faces.
    It flips by itself until the visitor picks a side (never with reduced motion). */
function BeforeAfter() {
  const [side, setSide] = useState<'before' | 'after'>('before')
  const [held, setHeld] = useState(() => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false)
  useEffect(() => {
    if (held) return
    const t = window.setInterval(() => setSide((s) => (s === 'before' ? 'after' : 'before')), 3800)
    return () => window.clearInterval(t)
  }, [held])
  const pick = (s: typeof side) => { setHeld(true); setSide(s) }
  return (
    <div className="relative">
      <div aria-hidden className="absolute -inset-x-10 -top-6 -bottom-10 -z-10 rounded-[48px] opacity-80 blur-3xl"
           style={{ background: `radial-gradient(40% 50% at 25% 40%, ${P.pink}, transparent), radial-gradient(40% 50% at 75% 50%, ${P.sky}, transparent), radial-gradient(40% 40% at 50% 90%, ${P.butter}, transparent)` }} />
      <div className="overflow-hidden rounded-[22px] border border-[#e2dcd2] bg-white p-1.5 shadow-[0_30px_80px_-30px_rgba(29,26,23,0.35)]">
        <div className="flex h-10 items-center gap-1.5 px-3">
          <span className="size-3 rounded-full bg-[#ff8fa3]" /><span className="size-3 rounded-full bg-[#ffd166]" /><span className="size-3 rounded-full bg-[#7bd389]" />
          <span className="flex-1" />
          <div role="tablist" aria-label="Before and after" className="inline-flex rounded-full bg-[#f3efe8] p-0.5 text-[13px] font-semibold">
            {([['before', 'Your clips'], ['after', 'Your video']] as const).map(([s, label]) => (
              <button key={s} type="button" role="tab" aria-selected={side === s} onClick={() => pick(s)}
                      className={cx('rounded-full px-3.5 py-1 whitespace-nowrap transition-all', side === s ? 'bg-white text-[#1d1a17] shadow-sm' : 'text-[#8a827a] hover:text-[#1d1a17]')}>{label}</button>
            ))}
          </div>
          <span className="flex-1" />
          <span className="hidden w-[54px] sm:block" />
        </div>
        <div className="grid overflow-hidden rounded-2xl text-left">
          <div aria-hidden={side !== 'before'} className={cx('[grid-area:1/1] transition-all duration-500', side === 'before' ? 'opacity-100' : 'pointer-events-none scale-[0.98] opacity-0')}><Pile /></div>
          <div aria-hidden={side !== 'after'} className={cx('[grid-area:1/1] transition-all duration-500', side === 'after' ? 'opacity-100' : 'pointer-events-none scale-[0.98] opacity-0')}><Mock /></div>
        </div>
      </div>
    </div>
  )
}

const TINTS = ['#7d9cc0', '#c79b84', '#86b394', '#d8c27a', '#a493c4', '#79b5b5', '#c98a99', '#a1ad7c', '#8597c4', '#c4a98f']

/** A day's footage as it comes off the phone, with the tells VibeCut catches. */
function Pile() {
  const tells: Record<number, string> = { 2: 'too dark', 9: 'shaky', 13: 'same shot', 14: 'same shot', 19: 'wind', 22: 'too bright', 27: '0.6 s', 30: 'shaky' }
  return (
    <div className="flex h-full flex-col bg-black">
      <div className="flex items-center gap-2 px-4 pt-3 text-[13px] text-zinc-300">
        <span className="font-semibold text-zinc-100">Sep 22 · 104 clips</span><span className="flex-1" /><span className="hidden text-muted sm:inline">4:12 of footage</span>
      </div>
      <div className="grid flex-1 grid-cols-8 content-center gap-2 p-4">
        {Array.from({ length: 32 }).map((_, i) => {
          const tell = tells[i]
          const dark = tell === 'too dark', bright = tell === 'too bright'
          return (
            <div key={i} className="relative aspect-[4/3] overflow-hidden rounded-md"
                 style={{ background: TINTS[(i * 7) % TINTS.length], filter: dark ? 'brightness(0.35)' : bright ? 'brightness(1.6) saturate(0.5)' : tell === 'shaky' ? 'blur(1.2px)' : undefined, transform: `rotate(${((i * 37) % 7) - 3}deg)` }}>
              {tell && <span className="absolute inset-x-0.5 bottom-0.5 rounded bg-[#ff5c7a] px-0.5 text-center text-[9px] leading-[14px] font-semibold text-white">{tell}</span>}
            </div>
          )
        })}
      </div>
      <div className="flex items-center gap-2 px-4 pb-3 text-[13px] text-zinc-300">
        <span className="font-semibold text-[#ff8fa3]">8 tells</span><span className="text-muted">·</span><span>+69 more clips</span><span className="flex-1" /><span className="text-muted">nothing cut yet</span>
      </div>
    </div>
  )
}

/** The editor: a shot sequence sitting on the beat, a caption lane, a music strip. */
function Mock() {
  const shots = [9, 5, 4, 7, 4, 6, 3, 7, 5, 8]
  return (
    <div className="bg-black">
      <div className="flex items-center gap-2 px-4 pt-3 text-[13px] text-zinc-300">
        <span className="truncate font-semibold text-zinc-100">Sep 22 · Short 9:16</span><span className="flex-1" />
        <span className="hidden whitespace-nowrap text-[#7bd389] sm:inline">✓ Draft saved</span>
        <span className="rounded-full bg-white px-2.5 py-0.5 text-[12px] font-bold text-[#1d1a17]">Export</span>
      </div>
      <div className="p-4">
        <div className="mx-auto flex aspect-[9/16] w-[22%] min-w-[120px] flex-col justify-end overflow-hidden rounded-xl"
             style={{ background: 'linear-gradient(160deg, #7d9cc0 0%, #c79b84 55%, #2a2622 100%)' }}>
          <div className="m-3 self-start rounded-lg bg-white px-2 py-1 font-['Nunito'] text-[12px] font-extrabold" style={{ color: '#1a1a1a' }}>
            7:42 am · coffee run ☕
          </div>
          <div className="mb-3 flex items-center gap-2 px-3 text-[11px] text-zinc-300">
            <span>▶</span><span>0:04 / 0:25</span>
            <span className="h-1 flex-1 rounded-full bg-white/30"><span className="block h-1 w-[18%] rounded-full bg-white" /></span>
          </div>
        </div>
      </div>
      <div className="space-y-1.5 px-4 pb-4">
        <div className="flex h-5 items-end gap-[3px]">
          {Array.from({ length: 32 }).map((_, i) => <span key={i} className={cx('flex-1 rounded-sm', i % 4 === 0 ? 'h-3.5 bg-[#ffd166]' : 'h-1.5 bg-white/20')} />)}
        </div>
        <div className="flex gap-[3px]">
          {shots.map((w, i) => (
            <div key={i} className="relative h-12 rounded-md" style={{ flex: w, background: TINTS[i] }}>
              {i === 0 && <span className="absolute top-1 left-1.5 text-[10px] font-bold text-white">Hook</span>}
              <span className="absolute right-1.5 bottom-1 hidden text-[10px] text-white/85 sm:inline">{(w * 0.4).toFixed(1)}s</span>
            </div>
          ))}
        </div>
        <div className="flex gap-[3px]">
          <span className="h-4 truncate rounded bg-[#7bd389]/30 px-1.5 text-[10px] leading-4 text-[#bff0cc]" style={{ flex: 12 }}>T A day in the city</span>
          <span style={{ flex: 14 }} />
          <span className="h-4 truncate rounded bg-[#7bd389]/30 px-1.5 text-[10px] leading-4 text-[#bff0cc]" style={{ flex: 18 }}>§ 11:49 am · look up</span>
          <span style={{ flex: 14 }} />
        </div>
        <div className="h-4 truncate rounded bg-[#8fc3ff]/25 px-1.5 text-[10px] leading-4 text-[#cfe5ff]">♪ Kara Square — Super Power Pop Rock · on the beat</div>
      </div>
    </div>
  )
}

/* ---------- the tells, scrolling ---------- */

function Marquee() {
  const tells = ['exposure jumps', 'cuts off the beat', 'a caption over a face', 'the same shot twice', 'wind in the mic', 'a 0.6 s flash of nothing', 'music drowning your voice', 'five fonts in one video', 'shaky openers', 'dark words on a dark coat', 'a chat that runs 14 s']
  const row = tells.map((t, i) => (
    <span key={i} className="flex shrink-0 items-center gap-3 pr-3">
      <span className="rounded-full border border-[#e2dcd2] bg-white px-4 py-1.5 text-[15px] font-semibold text-[#8a827a] line-through decoration-[#ff8fa3] decoration-2">{t}</span>
      <span className="text-[#ff9fb4]">✿</span>
    </span>
  ))
  return (
    <section className="mt-20 py-6" aria-label="Amateur tells VibeCut catches">
      <p className={cx('mb-5 text-center text-[13px] font-semibold uppercase tracking-[0.1em]', soft)}>Tells it catches</p>
      <div className="lc-fade overflow-hidden">
        <div className="lc-marquee flex w-max">{row}{row}</div>
      </div>
    </section>
  )
}

/* ---------- what it can do: a carousel of moves ---------- */

type MoveKind = 'Captions' | 'Transitions' | 'Effects' | 'On the beat'
type Move = { kind: MoveKind; name: string; fx: string }

// Every card is a move the editor really has, under its menu name
// (overlays.ENTERS, transitions.KINDS, effects.KINDS, make.punches).
const MOVES: Move[] = [
  { kind: 'On the beat', name: 'Cut on the beat', fx: 'cuts' },
  { kind: 'Captions', name: 'Pop', fx: 'pop' },
  { kind: 'Transitions', name: 'Swipe', fx: 'whip' },
  { kind: 'Effects', name: 'Glitch', fx: 'glitch' },
  { kind: 'Captions', name: 'Typewriter', fx: 'type' },
  { kind: 'Transitions', name: 'Zoom through', fx: 'zoom' },
  { kind: 'Effects', name: 'VHS', fx: 'vhs' },
  { kind: 'On the beat', name: 'Punch in', fx: 'punch' },
  { kind: 'Captions', name: 'Stamp', fx: 'stamp' },
  { kind: 'Transitions', name: 'Light leak', fx: 'leak' },
  { kind: 'Effects', name: 'Shake', fx: 'shake' },
  { kind: 'Captions', name: 'Word by word', fx: 'word' },
  { kind: 'Transitions', name: 'Flash', fx: 'flash' },
  { kind: 'Effects', name: 'Disco', fx: 'disco' },
  { kind: 'Captions', name: 'Slide in', fx: 'slide' },
  { kind: 'Transitions', name: 'Slide up', fx: 'up' },
  { kind: 'Effects', name: 'Old film', fx: 'old' },
  { kind: 'Captions', name: 'Fade up', fx: 'fade' },
  { kind: 'Transitions', name: 'Fade', fx: 'dissolve' },
  { kind: 'Effects', name: 'Zoom in', fx: 'zoomin' },
  { kind: 'Transitions', name: 'Dip to black', fx: 'dip' },
  { kind: 'Effects', name: 'Glow', fx: 'glow' },
  { kind: 'Transitions', name: 'Blur', fx: 'blur' },
  { kind: 'Effects', name: 'Pulse', fx: 'pulse' },
  { kind: 'Effects', name: 'Film grain', fx: 'grain' },
  { kind: 'Effects', name: 'Strobe', fx: 'strobe' },
  { kind: 'Effects', name: 'Blur in', fx: 'blurin' },
  { kind: 'Effects', name: 'Vignette', fx: 'vignette' },
  { kind: 'Effects', name: 'Zoom out', fx: 'zoomout' },
]
const KINDS = ['All', 'Captions', 'Transitions', 'Effects', 'On the beat'] as const

function Moves() {
  const [kind, setKind] = useState<(typeof KINDS)[number]>('All')
  const [auto, setAuto] = useState(() => !(window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false))
  const [hover, setHover] = useState(false)
  const track = useRef<HTMLDivElement>(null)
  const list = kind === 'All' ? MOVES : MOVES.filter((m) => m.kind === kind)

  const step = (dir: 1 | -1) => {
    const el = track.current
    if (!el) return
    const card = el.querySelector('figure')
    const w = (card?.getBoundingClientRect().width ?? 180) + 16
    if (dir === 1 && el.scrollLeft + el.clientWidth >= el.scrollWidth - 4) el.scrollTo({ left: 0, behavior: 'smooth' })
    else if (dir === -1 && el.scrollLeft <= 4) el.scrollTo({ left: el.scrollWidth, behavior: 'smooth' })
    else el.scrollBy({ left: dir * w, behavior: 'smooth' })
  }
  // It moves along by itself until someone touches it, and waits while hovered.
  useEffect(() => {
    if (!auto || hover) return
    const t = window.setInterval(() => step(1), 2600)
    return () => window.clearInterval(t)
  }, [auto, hover, kind])
  useEffect(() => { track.current?.scrollTo({ left: 0 }) }, [kind])
  const pad = { paddingInline: 'max(24px, calc((100% - 1032px) / 2))', scrollPaddingInline: 'max(24px, calc((100% - 1032px) / 2))' }

  return (
    <section id="moves" aria-roledescription="carousel" aria-label="What VibeCut can do" className="scroll-mt-24 py-16">
      <div className="mx-auto flex max-w-[1080px] flex-wrap items-end gap-6 px-6">
        <div className="flex-1">
          <Kicker>What it can do</Kicker>
          <H2>Every move, <Em squiggle>built in.</Em></H2>
        </div>
        <div className="flex gap-2">
          {([[-1, '←', 'Previous'], [1, '→', 'Next']] as const).map(([d, a, label]) => (
            <button key={d} type="button" aria-label={label} onClick={() => { setAuto(false); step(d) }}
                    className="grid size-12 place-items-center rounded-full border border-[#e2dcd2] bg-white text-[18px] font-bold shadow-sm transition-all hover:border-[#cfc7bb] active:scale-95">{a}</button>
          ))}
        </div>
      </div>
      <div role="tablist" aria-label="Kind of move" className="mx-auto mt-6 flex max-w-[1080px] flex-wrap gap-2 px-6">
        {KINDS.map((k) => (
          <button key={k} type="button" role="tab" aria-selected={kind === k} onClick={() => setKind(k)}
                  className={cx('rounded-full px-4 py-1.5 text-[14px] font-semibold transition-colors',
                    kind === k ? 'bg-[#1d1a17] text-white' : 'bg-white text-[#5d5650] shadow-sm hover:text-[#1d1a17]')}>
            {k}{k !== 'All' && <span className="ml-1.5 opacity-50">{MOVES.filter((m) => m.kind === k).length}</span>}
          </button>
        ))}
      </div>
      <div ref={track} style={pad}
           className="lc-track mt-8 flex snap-x snap-mandatory gap-4 overflow-x-auto pb-4"
           onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
           onPointerDown={() => setAuto(false)} onWheel={(e) => { if (Math.abs(e.deltaX) > Math.abs(e.deltaY)) setAuto(false) }}>
        {list.map((m, i) => (
          <figure key={m.kind + m.name} className="w-[168px] shrink-0 snap-start sm:w-[184px]">
            {/* each card starts its loop at a different point, so a row never plays in lockstep */}
            <div className="lc-card relative aspect-[9/16] overflow-hidden rounded-[22px] border-4 border-white bg-black shadow-[0_18px_40px_-20px_rgba(29,26,23,0.5)]"
                 style={{ '--lc-d': `-${((i * 0.9) % 2.4).toFixed(2)}s` } as React.CSSProperties}>
              <MoveArt m={m} i={i} />
            </div>
            <figcaption className="mt-3 px-1">
              <div className="text-[15px] font-bold">{m.name}</div>
              <div className="text-[12px] text-[#8a827a]">{m.kind}</div>
            </figcaption>
          </figure>
        ))}
      </div>
    </section>
  )
}

// Three made-up places, drawn, so no card shows anyone's face.
const SCENES = [
  { sky: 'linear-gradient(180deg,#ffb38a,#ff7a9c 75%)', sun: '#fff3c4', far: '#b0608f', near: '#4b3566' },
  { sky: 'linear-gradient(180deg,#7cc6ec,#d8f0fb 75%)', sun: '#ffffff', far: '#6fb894', near: '#2f7158' },
  { sky: 'linear-gradient(180deg,#26295a,#8a5aa0 85%)', sun: '#ffe9a8', far: '#3d3670', near: '#17152e' },
]

function Scene({ v = 0, className, style }: { v?: number; className?: string; style?: React.CSSProperties }) {
  const s = SCENES[v % SCENES.length]
  return (
    <div className={cx('absolute inset-0 overflow-hidden', className)} style={{ background: s.sky, ...style }}>
      <span className="absolute top-[18%] left-[52%] aspect-square w-[34%] rounded-full" style={{ background: s.sun }} />
      <span className="absolute top-[52%] -left-[30%] h-[70%] w-[110%] rounded-[50%]" style={{ background: s.far }} />
      <span className="absolute top-[64%] -right-[35%] h-[70%] w-[120%] rounded-[50%]" style={{ background: s.near }} />
    </div>
  )
}

function Cap({ children, className, style }: { children: ReactNode; className?: string; style?: React.CSSProperties }) {
  return (
    <span className={cx("inline-block rounded-lg bg-white px-2.5 py-1 font-['Nunito'] text-[14px] font-extrabold whitespace-nowrap text-[#1a1a1a] shadow-md", className)} style={style}>
      {children}
    </span>
  )
}

function MoveArt({ m, i }: { m: Move; i: number }) {
  const { kind, fx } = m
  if (kind === 'Captions') {
    return (
      <>
        <Scene v={0} />
        <div className="absolute inset-x-2 top-[60%] flex justify-center gap-1">
          {fx === 'word'
            ? ['coffee', 'run', '☕'].map((w, i) => <Cap key={w} className="lc-c-word" style={{ animationDelay: `calc(var(--lc-d) + ${i * 0.22}s)` }}>{w}</Cap>)
            : <Cap className={`lc-c-${fx}`}>7:42 am · coffee ☕</Cap>}
        </div>
      </>
    )
  }
  if (kind === 'Transitions') {
    const veil = fx === 'dip' ? '#000' : fx === 'flash' ? '#fff' : fx === 'leak'
      ? 'radial-gradient(60% 50% at 50% 50%, rgba(255,190,90,0.95), rgba(255,90,120,0.6) 55%, transparent 80%)' : null
    return (
      <>
        <Scene v={i} className={`lc-tr lc-ta-${fx}`} />
        <Scene v={i + 1} className={`lc-tr lc-tb-${fx}`} />
        {veil && <div className="lc-tr lc-veil absolute inset-0" style={{ background: veil, mixBlendMode: fx === 'leak' ? 'screen' : undefined }} />}
      </>
    )
  }
  if (kind === 'On the beat') {
    return (
      <>
        {fx === 'cuts'
          ? [0, 1, 2].map((v) => <Scene key={v} v={v} className="lc-b-cycle" style={{ animationDelay: `calc(var(--lc-d) + ${[0, -1.6, -0.8][v]}s)` }} />)
          : <div className="lc-b-punch absolute inset-0"><Scene v={2} /></div>}
        <div className="absolute inset-x-0 bottom-3 flex justify-center gap-1.5">
          {(fx === 'cuts' ? [0, 1, 2] : [0]).map((v) => (
            <span key={v} className={cx('size-2.5 rounded-full bg-white', fx === 'cuts' ? 'lc-b-dot' : 'lc-b-tick')}
                  style={{ animationDelay: fx === 'cuts' ? `calc(var(--lc-d) + ${[0, -1.6, -0.8][v]}s)` : undefined }} />
          ))}
        </div>
      </>
    )
  }
  // Effects: the picture moves inside a slightly larger frame so a shake never shows an edge.
  const v = ['vhs', 'glitch', 'disco', 'glow', 'strobe', 'pulse'].includes(fx) ? 2 : fx === 'old' || fx === 'grain' ? 1 : 0
  return (
    <>
      <div className={cx('absolute -inset-[6%]', `lc-e-${fx}`)}><Scene v={v} /></div>
      {fx === 'glow' && <div className="lc-o-glow absolute -inset-[6%]"><Scene v={v} /></div>}
      {fx === 'glitch' && <div className="lc-o-glitch absolute -inset-[6%]"><Scene v={v} /></div>}
      {(fx === 'grain' || fx === 'old') && <div className="lc-o-grain absolute -inset-[20%]" />}
      {fx === 'old' && <span className="lc-o-scratch absolute inset-y-0 w-px bg-white/70" />}
      {fx === 'vhs' && <div className="lc-o-vhs absolute inset-0" />}
      {fx === 'vignette' && <div className="lc-o-vignette absolute inset-0" />}
    </>
  )
}

/* ---------- how it works ---------- */

function How({ onStart }: { onStart: () => void }) {
  const steps: { n: string; title: string; text: string; bg: string; art: ReactNode }[] = [
    { n: '1', title: 'Drop your clips', bg: P.sky, text: 'A folder, or a hundred files.', art: <ArtDrop /> },
    { n: '2', title: 'Make two picks', bg: P.butter, text: 'Frame and look. That’s it.', art: <ArtPicks /> },
    { n: '3', title: 'Watch, then post', bg: P.pink, text: 'Tweak in one tap. Save to Photos.', art: <ArtWatch /> },
  ]
  return (
    <section id="how" className="mx-auto max-w-[1080px] scroll-mt-24 px-6 py-16">
      <div className="text-center">
        <Kicker>How it works</Kicker>
        <H2>Three steps. <Em squiggle>That’s it.</Em></H2>
      </div>
      <div className="mt-12 grid gap-5 md:grid-cols-3">
        {steps.map((s) => (
          <div key={s.n} className="group rounded-[28px] p-2 transition-transform hover:-translate-y-1" style={{ background: s.bg }}>
            <div className="grid h-[170px] place-items-center overflow-hidden rounded-[22px] bg-white/60">{s.art}</div>
            <div className="px-4 pt-5 pb-5">
              <span className="text-[13px] font-semibold text-[#1d1a17]/45">Step {s.n}</span>
              <h3 className={cx(display, 'mt-1 text-[26px]')}>{s.title}</h3>
              <p className="mt-1 text-[15px] text-[#4a443e]">{s.text}</p>
            </div>
          </div>
        ))}
      </div>
      <div className="mt-5 flex flex-wrap items-center gap-x-8 gap-y-4 rounded-[28px] p-6 sm:p-8" style={{ background: P.lilac }}>
        <span className="grid size-14 shrink-0 place-items-center rounded-2xl bg-white text-[28px] shadow-sm">🔗</span>
        <div className="min-w-0 flex-1 basis-[300px]">
          <h3 className={cx(display, 'text-[24px]')}>Or paste a reel you love.</h3>
          <p className="mt-1 text-[15px] text-[#4a443e]">Your day, cut to its rhythm. Never its frames.</p>
        </div>
        <Pill onClick={onStart}>Try it with a reel</Pill>
      </div>
    </section>
  )
}

/* ---------- the promise ---------- */

function Promise() {
  const rows = [
    { share: 40, what: 'Hard constraints', bg: '#1f5f8b', fg: '#fff' },
    { share: 30, what: 'Editing grammar', bg: '#9ed8b8', fg: '#1d1a17' },
    { share: 20, what: 'Consistency', bg: '#ffd97a', fg: '#1d1a17' },
    { share: 10, what: 'Taste', bg: '#ff9fb4', fg: '#1d1a17' },
  ]
  return (
    <section className="mx-auto max-w-[1080px] px-6 py-16">
      <div className="rounded-[32px] border border-[#ece6dc] bg-white p-8 shadow-[0_20px_60px_-40px_rgba(29,26,23,0.4)] sm:p-12">
        <div className="grid gap-10 lg:grid-cols-2 lg:items-center">
          <div>
            <Kicker>The promise</Kicker>
            <H2>Not “beautiful”.<br /><Em>No amateur tells.</Em></H2>
            <p className={cx('mt-4 text-[17px]', soft)}>We fix the craft. The taste stays yours.</p>
          </div>
          <div>
            <div className="flex h-16 overflow-hidden rounded-2xl">
              {rows.map((r) => (
                <div key={r.what} className="flex items-center justify-center text-[18px] font-extrabold" style={{ flex: r.share, background: r.bg, color: r.fg }}>
                  {r.share}%{r.what === 'Taste' && <span className="ml-0.5">♥</span>}
                </div>
              ))}
            </div>
            <div className="mt-2 flex text-[12px] font-semibold">
              <span className="border-t-2 border-accent/40 pt-1 text-accent" style={{ flex: 90 }}>VibeCut does this</span>
              <span className="ml-1 border-t-2 border-[#ff9fb4] pt-1 text-center text-[#d4567a]" style={{ flex: 10 }}>you</span>
            </div>
            <div className="mt-5 flex flex-wrap gap-x-5 gap-y-2 text-[14px] font-semibold">
              {rows.map((r) => (
                <span key={r.what} className="flex items-center gap-2"><span className="size-3 rounded-full" style={{ background: r.bg }} />{r.what}</span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

function ArtDrop() {
  return (
    <div className="relative h-[120px] w-[200px]">
      <div className="absolute inset-x-6 bottom-0 h-[70px] rounded-2xl border-2 border-dashed border-[#1f5f8b]/40 bg-white" />
      {[0, 1, 2, 3].map((i) => (
        <div key={i} className="absolute top-0" style={{ left: 40 + i * 30, transform: `rotate(${(i - 1.5) * 9}deg)` }}>
          <div className="lc-drop h-12 w-9 rounded-lg border-2 border-white shadow-md" style={{ background: TINTS[i * 2], animationDelay: `${i * 0.25}s` }} />
        </div>
      ))}
    </div>
  )
}

function ArtPicks() {
  return (
    <div className="flex flex-col items-center gap-3">
      <div className="flex gap-2">
        {['Short', 'Tall', 'Wide'].map((x, i) => (
          <span key={x} className={cx('rounded-full px-3 py-1 text-[13px] font-bold', i === 0 ? 'bg-[#1d1a17] text-white' : 'bg-white text-[#5d5650] shadow-sm')}>{x}</span>
        ))}
      </div>
      <div className="flex gap-2">
        {[['Cozy', '#e8b48a'], ['Film', '#b8a184'], ['Hype', '#ff7a9c']].map(([x, c], i) => (
          <span key={x} className={cx('flex items-center gap-1.5 rounded-full bg-white px-3 py-1 text-[13px] font-bold shadow-sm', i === 0 && 'ring-2 ring-[#1d1a17]')}>
            <span className="size-2.5 rounded-full" style={{ background: c }} />{x}
          </span>
        ))}
      </div>
    </div>
  )
}

function ArtWatch() {
  return (
    <div className="flex items-center gap-4">
      <div className="relative grid h-[120px] w-[68px] place-items-center rounded-xl shadow-md" style={{ background: 'linear-gradient(160deg, #a493c4, #c98a99 60%, #2a2622)' }}>
        <span className="grid size-8 place-items-center rounded-full bg-white/90 pl-0.5 text-[12px]">▶</span>
      </div>
      <div className="flex flex-col gap-1.5">
        {['🎵 Music', '⏱ 0:25', '🎨 Cozy', '💬 Words'].map((x) => (
          <span key={x} className="rounded-full bg-white px-3 py-1 text-[12px] font-bold shadow-sm">{x}</span>
        ))}
      </div>
    </div>
  )
}

/* ---------- what it fixes: a bento ---------- */

function Tile({ title, text, bg, className, children }: { title: string; text: string; bg: string; className?: string; children?: ReactNode }) {
  return (
    <div className={cx('flex flex-col overflow-hidden rounded-[28px] p-6 transition-transform hover:-translate-y-0.5', className)} style={{ background: bg }}>
      {children && <div className="mb-5 flex flex-1 items-center">{children}</div>}
      <h3 className={cx(display, 'text-[22px]')}>{title}</h3>
      <p className="mt-1.5 text-[14px] leading-relaxed text-[#4a443e]">{text}</p>
    </div>
  )
}

function Fixes() {
  return (
    <section id="fixes" className="mx-auto max-w-[1080px] scroll-mt-24 px-6 py-20">
      <div className="text-center">
        <Kicker>What it fixes</Kicker>
        <H2>Amateur tells, <Em>handled.</Em></H2>
      </div>
      <div className="mt-12 grid auto-rows-[minmax(200px,auto)] gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Tile className="sm:col-span-2 lg:row-span-2" bg={P.sky} title="Cuts on the beat"
              text="The drop lands right after the hook.">
          <div className="w-full space-y-2">
            <div className="flex h-20 items-end gap-1.5">
              {Array.from({ length: 24 }).map((_, i) => (
                <span key={i} className="lc-beat flex-1 rounded-full" style={{ height: i % 4 === 0 ? 80 : 24 + ((i * 7) % 20), background: i % 4 === 0 ? '#1f5f8b' : '#1f5f8b44', animationDelay: `${(i % 4) * 0.12}s` }} />
              ))}
            </div>
            <div className="flex gap-1">
              {[4, 4, 8, 4, 4].map((w, i) => (
                <div key={i} className="h-28 rounded-2xl border-[3px] border-white shadow-sm" style={{ flex: w, background: TINTS[i + 3] }} />
              ))}
            </div>
            <div className="flex justify-between px-1 text-[11px] font-bold text-[#1f5f8b]/70"><span>♩ 1</span><span>2</span><span>3</span><span>4</span><span>drop ✦</span></div>
          </div>
        </Tile>
        <Tile bg={P.butter} title="One look, end to end" text="Seven looks, fitted to your footage.">
          <div className="flex -space-x-2">
            {['#e8b48a', '#b8a184', '#ff7a9c', '#a9b8c4', '#ffd166', '#2a2622', '#d9d2c5'].map((c) => <span key={c} className="size-9 rounded-full border-[3px] border-white" style={{ background: c }} />)}
          </div>
        </Tile>
        <Tile bg={P.pink} title="Captions that read" text="Time and place, always readable.">
          <div className="rounded-xl px-3 py-6" style={{ background: 'linear-gradient(135deg, #2a2622, #c98a99)' }}>
            <span className="rounded-md bg-white px-2 py-1 font-['Nunito'] text-[13px] font-extrabold text-[#1a1a1a]">11:49 am · look up ✨</span>
          </div>
        </Tile>
        <Tile bg={P.mint} title="Your voice stays up" text="Music ducks when you talk.">
          <svg viewBox="0 0 200 50" className="w-full" aria-hidden>
            <path d="M0 25 Q10 5 20 25 T40 25 T60 25 T80 25 T100 25 T120 25 T140 25 T160 25 T180 25 T200 25" stroke="#1f8b5f" strokeWidth="3" fill="none" />
            <path d="M0 40 L60 40 L70 46 L140 46 L150 40 L200 40" stroke="#ff9fb4" strokeWidth="3" fill="none" strokeLinecap="round" />
          </svg>
        </Tile>
        <Tile bg={P.lilac} title="No shot twice" text="Look-alikes collapse to the best.">
          <div className="flex items-center gap-2">
            <div className="h-14 w-10 rounded-lg border-2 border-white shadow-sm" style={{ background: TINTS[4] }} />
            <div className="relative h-14 w-10 rounded-lg border-2 border-white opacity-50 shadow-sm" style={{ background: TINTS[4] }}>
              <span className="absolute inset-0 grid place-items-center text-[22px] font-black text-[#d4567a]">×</span>
            </div>
          </div>
        </Tile>
        <Tile bg={P.cream} className="border border-[#ece6dc]" title="Every cut checked" text="Light, colour and sound at every join.">
          <div className="flex items-center gap-1.5">
            {['✓', '✓', '!', '✓'].map((m, i) => (
              <span key={i} className="flex items-center gap-1.5">
                <span className="h-10 w-8 rounded-md" style={{ background: TINTS[i + 5] }} />
                {i < 3 && <span className={cx('grid size-5 place-items-center rounded-full text-[11px] font-black text-white', m === '!' ? 'bg-[#ff8fa3]' : 'bg-[#7bd389]')}>{m}</span>}
              </span>
            ))}
          </div>
        </Tile>
        <Tile bg={P.sky} title="Cut like a vlog" text="Wide, medium, close, every stop.">
          <div className="flex items-end gap-2">
            {[['wide', 56], ['medium', 44], ['close', 32]].map(([l, s]) => (
              <span key={l as string} className="flex flex-col items-center gap-1 text-[11px] font-bold text-[#1f5f8b]">
                <span className="rounded-lg border-2 border-white bg-[#7d9cc0]" style={{ width: s as number, height: s as number }} />{l}
              </span>
            ))}
          </div>
        </Tile>
        <Tile bg={P.butter} className="sm:col-span-2" title="Your footage stays home"
              text="Read on your Mac. Every frame is one you filmed.">
          <div className="flex flex-wrap gap-2">
            {['🔒 On-device', '🎞 Only your frames', '📵 No account', '↩ Every change undoable'].map((x) => (
              <span key={x} className="rounded-full bg-white px-3 py-1.5 text-[13px] font-bold shadow-sm">{x}</span>
            ))}
          </div>
        </Tile>
      </div>
    </section>
  )
}

/* ---------- pricing ---------- */

function Pricing({ onStart }: { onStart: () => void }) {
  const inc = ['Unlimited videos', 'Music, captions, looks, effects', 'Cut like any reel', 'Straight to Photos']
  return (
    <section id="pricing" className="mx-auto max-w-[1080px] scroll-mt-24 px-6 py-16">
      <div className="text-center">
        <Kicker>Pricing</Kicker>
        <H2>Free in <Em squiggle>early access.</Em></H2>
      </div>
      <div className="mx-auto mt-12 grid max-w-[860px] gap-5 md:grid-cols-[1.15fr_1fr]">
        <div className="relative rounded-[28px] bg-[#1d1a17] p-8 text-white shadow-[0_30px_60px_-30px_rgba(29,26,23,0.6)]">
          <span className="absolute -top-3 right-6 rotate-[4deg] rounded-full px-3 py-1 text-[12px] font-extrabold text-[#1d1a17]" style={{ background: P.butter }}>Now ✦</span>
          <h3 className={cx(display, 'text-[22px] text-white/70')}>Early access</h3>
          <div className={cx(display, 'mt-2 text-[56px] leading-none text-white')}>$0</div>
          <p className="mt-3 text-[15px] text-white/70">Everything, on your Mac.</p>
          <ul className="mt-6 space-y-2.5 text-[15px]">
            {inc.map((x) => <li key={x} className="flex items-center gap-2.5"><span className="grid size-5 place-items-center rounded-full bg-[#7bd389] text-[11px] font-black text-[#1d1a17]">✓</span>{x}</li>)}
          </ul>
          <button type="button" onClick={onStart}
                  className="mt-8 h-12 w-full rounded-full bg-white text-[16px] font-bold text-[#1d1a17] transition-transform hover:-translate-y-px active:scale-[0.98]">
            Start with your clips →
          </button>
        </div>
        <div className="rounded-[28px] border border-[#ece6dc] bg-white p-8">
          <h3 className={cx(display, 'text-[22px] text-[#8a827a]')}>Creator</h3>
          <div className={cx(display, 'mt-2 text-[32px] leading-tight')}>Coming later</div>
          <p className={cx('mt-3 text-[15px]', soft)}>For one person posting every week.</p>
          <ul className={cx('mt-6 space-y-2.5 text-[15px]', soft)}>
            {['Everything in early access', 'Smarter picks, no key needed', 'Your taste on every Mac'].map((x) => (
              <li key={x} className="flex items-center gap-2.5"><span className="grid size-5 place-items-center rounded-full text-[11px]" style={{ background: P.lilac }}>✦</span>{x}</li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  )
}

/* ---------- FAQ ---------- */

function Faq() {
  const qs = [
    ['Will it make my video beautiful?', 'It removes the amateur tells. The taste is yours.'],
    ['Does it generate video?', 'Never. Every frame is one you filmed.'],
    ['Where does my footage go?', 'Nowhere. It is read on your Mac. With your own Claude key, a few small frames are sent to pick moments, and you can turn that off.'],
    ['Can I still edit by hand?', 'Yes. One tap opens the full editor, and every change undoes.'],
    ['Windows?', 'Not yet. Mac only for now.'],
  ]
  const [open, setOpen] = useState<number | null>(0)
  return (
    <section id="faq" className="mx-auto max-w-[780px] scroll-mt-24 px-6 py-16">
      <div className="text-center">
        <Kicker>Questions</Kicker>
        <H2><Em>Honest</Em> answers.</H2>
      </div>
      <div className="mt-10 space-y-3">
        {qs.map(([q, a], i) => (
          <div key={q} className={cx('rounded-[22px] border transition-colors', open === i ? 'border-[#ece6dc] bg-white shadow-sm' : 'border-transparent bg-[#f3efe8] hover:bg-[#efe9e0]')}>
            <button type="button" aria-expanded={open === i} onClick={() => setOpen(open === i ? null : i)}
                    className="flex w-full items-center justify-between gap-4 px-6 py-4 text-left text-[17px] font-bold">
              {q}
              <span className={cx('grid size-7 shrink-0 place-items-center rounded-full text-[16px] transition-transform', open === i ? 'rotate-45 bg-[#1d1a17] text-white' : 'bg-white')}>+</span>
            </button>
            {open === i && <p className={cx('px-6 pb-5 text-[15px]', soft)}>{a}</p>}
          </div>
        ))}
      </div>
    </section>
  )
}

/* ---------- closing ---------- */

function Closing({ onStart }: { onStart: () => void }) {
  return (
    <section className="mx-auto max-w-[1080px] px-6 pt-10 pb-20">
      <div className="relative overflow-hidden rounded-[36px] px-8 py-16 text-center sm:py-20"
           style={{ background: `linear-gradient(135deg, ${P.pink}, ${P.lilac} 50%, ${P.sky})` }}>
        <div aria-hidden className="lc-dots absolute inset-0 opacity-60" />
        <div className="relative">
          <h2 className={cx(display, 'mx-auto max-w-[680px] text-[40px] leading-[1.08] sm:text-[58px]')}>
            Your video is <Em>one drop away.</Em>
          </h2>
          <div className="mt-8 flex justify-center"><Pill onClick={onStart}>Start with your clips</Pill></div>
          <p className={cx('mt-4 text-[14px]', soft)}>No account. No upload.</p>
        </div>
      </div>
    </section>
  )
}

/* ---------- motion ---------- */

// Kept here rather than in index.css: nothing else in the app moves like this.
const CSS = `
.lc-dots { background-image: radial-gradient(rgba(29,26,23,0.09) 1px, transparent 1px); background-size: 22px 22px;
  -webkit-mask-image: linear-gradient(to bottom, black, transparent 85%); mask-image: linear-gradient(to bottom, black, transparent 85%); }
.lc-fade { -webkit-mask-image: linear-gradient(to right, transparent, black 10%, black 90%, transparent); mask-image: linear-gradient(to right, transparent, black 10%, black 90%, transparent); }
@keyframes lc-rise { from { opacity: 0; transform: translateY(14px) } to { opacity: 1; transform: none } }
.lc-rise { animation: lc-rise .7s cubic-bezier(.2,.7,.2,1) both; }
@keyframes lc-float { 0%,100% { transform: translateY(0) } 50% { transform: translateY(-8px) } }
.lc-float { animation: lc-float 4.5s ease-in-out infinite; }
@keyframes lc-marquee { to { transform: translateX(-50%) } }
.lc-marquee { animation: lc-marquee 40s linear infinite; }
.lc-marquee:hover { animation-play-state: paused; }
@keyframes lc-beat { 0%,100% { transform: scaleY(1) } 50% { transform: scaleY(.55) } }
.lc-beat { transform-origin: bottom; animation: lc-beat .5s ease-in-out infinite; }
@keyframes lc-drop { 0% { transform: translateY(-6px) } 50% { transform: translateY(26px) } 100% { transform: translateY(-6px) } }
.lc-drop { animation: lc-drop 2.4s ease-in-out infinite; }
@keyframes lc-draw { from { stroke-dashoffset: 260 } to { stroke-dashoffset: 0 } }
.lc-draw path { stroke-dasharray: 260; animation: lc-draw 1.2s .5s ease-out both; }
/* the moves carousel: every loop is short so a card says what it does in a glance */
.lc-track { scrollbar-width: none; } .lc-track::-webkit-scrollbar { display: none; }
@keyframes lc-c-fade { 0%,10% { opacity:0; transform:translateY(8px) } 32%,84% { opacity:1; transform:none } 100% { opacity:0 } }
@keyframes lc-c-pop { 0%,10% { opacity:0; transform:scale(.3) } 22% { opacity:1; transform:scale(1.18) } 30%,84% { opacity:1; transform:scale(1) } 100% { opacity:0; transform:scale(1) } }
@keyframes lc-c-slide { 0%,10% { opacity:0; transform:translateX(-40px) } 32%,84% { opacity:1; transform:none } 100% { opacity:0; transform:none } }
@keyframes lc-c-stamp { 0%,10% { opacity:0; transform:scale(2.6) rotate(-10deg) } 19% { opacity:1; transform:scale(.9) rotate(-3deg) } 25%,84% { opacity:1; transform:scale(1) rotate(-3deg) } 100% { opacity:0; transform:scale(1) rotate(-3deg) } }
@keyframes lc-c-type { 0%,10% { clip-path:inset(0 100% 0 0) } 50%,84% { clip-path:inset(0 0 0 0); opacity:1 } 100% { clip-path:inset(0 0 0 0); opacity:0 } }
.lc-c-fade { animation: lc-c-fade 2.8s ease-out infinite; }
.lc-c-pop, .lc-c-word { animation: lc-c-pop 2.8s ease-out infinite; }
.lc-c-slide { animation: lc-c-slide 2.8s cubic-bezier(.2,.8,.2,1) infinite; }
.lc-c-stamp { animation: lc-c-stamp 2.8s ease-out infinite; }
.lc-c-type { animation: lc-c-type 2.8s steps(14) infinite; }

.lc-tr { animation-duration: 2.4s; animation-iteration-count: infinite; animation-direction: alternate; animation-timing-function: ease-in-out; }
@keyframes lc-t-in { 0%,35% { opacity:0 } 65%,100% { opacity:1 } }
@keyframes lc-t-cut { 0%,50% { opacity:0 } 50.01%,100% { opacity:1 } }
@keyframes lc-t-veil { 0%,35% { opacity:0 } 50% { opacity:1 } 65%,100% { opacity:0 } }
@keyframes lc-t-zoom-a { 0%,35% { transform:scale(1); opacity:1 } 55%,100% { transform:scale(2.4); opacity:0 } }
@keyframes lc-t-zoom-b { 0%,45% { transform:scale(.5); opacity:0 } 65%,100% { transform:scale(1); opacity:1 } }
@keyframes lc-t-up { 0%,35% { transform:translateY(100%) } 65%,100% { transform:none } }
@keyframes lc-t-whip-a { 0%,35% { transform:none; filter:blur(0) } 50% { filter:blur(6px) } 65%,100% { transform:translateX(-100%); filter:blur(0) } }
@keyframes lc-t-whip-b { 0%,35% { transform:translateX(100%); filter:blur(0) } 50% { filter:blur(6px) } 65%,100% { transform:none; filter:blur(0) } }
@keyframes lc-t-blur-a { 0%,35% { filter:blur(0) } 50%,100% { filter:blur(12px) } }
@keyframes lc-t-blur-b { 0%,50% { opacity:0; filter:blur(12px) } 50.01% { opacity:1; filter:blur(12px) } 65%,100% { opacity:1; filter:blur(0) } }
@keyframes lc-t-leak { 0%,30% { opacity:0; transform:translateX(-60%) } 50% { opacity:1 } 70%,100% { opacity:0; transform:translateX(60%) } }
.lc-tb-dissolve { animation-name: lc-t-in; }
.lc-tb-dip, .lc-tb-flash, .lc-tb-leak { animation-name: lc-t-cut; }
.lc-veil { animation-name: lc-t-veil; }
.lc-tb-leak ~ .lc-veil { animation-name: lc-t-leak; }
.lc-ta-zoom { animation-name: lc-t-zoom-a; } .lc-tb-zoom { animation-name: lc-t-zoom-b; }
.lc-tb-up { animation-name: lc-t-up; }
.lc-ta-whip { animation-name: lc-t-whip-a; } .lc-tb-whip { animation-name: lc-t-whip-b; }
.lc-ta-blur { animation-name: lc-t-blur-a; } .lc-tb-blur { animation-name: lc-t-blur-b; }

@keyframes lc-b-cycle { 0%,33.3% { opacity:1 } 33.4%,100% { opacity:0 } }
.lc-b-cycle { animation: lc-b-cycle 2.4s linear infinite; }
@keyframes lc-b-dot { 0%,33.3% { opacity:1; transform:scale(1.3) } 33.4%,100% { opacity:.35; transform:none } }
.lc-b-dot { animation: lc-b-dot 2.4s linear infinite; }
@keyframes lc-b-punch { 0% { transform:scale(1.16) } 35%,100% { transform:scale(1) } }
.lc-b-punch { animation: lc-b-punch .8s cubic-bezier(.2,.8,.2,1) infinite; }
@keyframes lc-b-tick { 0% { opacity:1; transform:scale(1.5) } 35%,100% { opacity:.35; transform:none } }
.lc-b-tick { animation: lc-b-tick .8s ease-out infinite; }

@keyframes lc-e-shake { 0%,100% { transform:translate(0,0) } 20% { transform:translate(-3%,2%) rotate(-1deg) } 40% { transform:translate(3%,-2%) rotate(1deg) } 60% { transform:translate(-2%,-3%) } 80% { transform:translate(2%,3%) rotate(.5deg) } }
.lc-e-shake { animation: lc-e-shake .35s linear infinite; }
@keyframes lc-e-zoomin { from { transform:scale(1) } to { transform:scale(1.4) } }
.lc-e-zoomin { animation: lc-e-zoomin 2.8s ease-in-out infinite; }
.lc-e-zoomout { animation: lc-e-zoomin 2.8s ease-in-out infinite reverse; }
@keyframes lc-e-pulse { 0%,100% { transform:scale(1) } 12% { transform:scale(1.12) } 40% { transform:scale(1.02) } }
.lc-e-pulse { animation: lc-e-pulse .7s ease-out infinite; }
@keyframes lc-e-strobe { 0%,40% { filter:none } 45%,55% { filter:brightness(2.4) saturate(.3) } 60%,100% { filter:none } }
.lc-e-strobe { animation: lc-e-strobe .45s steps(1) infinite; }
@keyframes lc-e-blurin { 0% { filter:blur(14px); transform:scale(1.15) } 45%,100% { filter:blur(0); transform:scale(1) } }
.lc-e-blurin { animation: lc-e-blurin 2.8s ease-out infinite; }
@keyframes lc-e-disco { to { filter:hue-rotate(360deg) saturate(1.6) } }
.lc-e-disco { animation: lc-e-disco 1.6s linear infinite; }
@keyframes lc-e-old { 0%,100% { filter:sepia(.85) contrast(1.1) } 50% { filter:sepia(.85) contrast(1.1) brightness(.8) } }
.lc-e-old { animation: lc-e-old .3s steps(2) infinite; }
@keyframes lc-e-vhs { 0%,46%,54%,100% { transform:none } 50% { transform:skewX(-5deg) translateX(3%) } }
.lc-e-vhs { filter: saturate(1.6) contrast(1.1); animation: lc-e-vhs 1.4s linear infinite; }
@keyframes lc-o-glow { 0%,100% { opacity:.2 } 50% { opacity:.9 } }
.lc-o-glow { filter: blur(10px) brightness(1.5); mix-blend-mode: screen; animation: lc-o-glow 1.6s ease-in-out infinite; }
@keyframes lc-o-glitch { 0%,100% { clip-path:inset(0 0 100% 0); transform:none } 10% { clip-path:inset(20% 0 60% 0); transform:translateX(-9%) } 20% { clip-path:inset(55% 0 25% 0); transform:translateX(7%) } 30% { clip-path:inset(0 0 100% 0) } 60% { clip-path:inset(70% 0 12% 0); transform:translateX(-6%) } 70% { clip-path:inset(0 0 100% 0) } }
.lc-o-glitch { filter: hue-rotate(150deg) saturate(2); animation: lc-o-glitch 1.2s steps(1) infinite; }
@keyframes lc-o-grain { 0% { transform:translate(0,0) } 25% { transform:translate(-5%,4%) } 50% { transform:translate(4%,-3%) } 75% { transform:translate(-3%,-5%) } }
.lc-o-grain { opacity:.55; mix-blend-mode: overlay; animation: lc-o-grain .4s steps(1) infinite;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='140' height='140'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='2'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E"); }
@keyframes lc-o-scratch { 0%,100% { left:30%; opacity:.7 } 33% { left:62%; opacity:.2 } 66% { left:45%; opacity:.8 } }
.lc-o-scratch { animation: lc-o-scratch .5s steps(1) infinite; }
@keyframes lc-o-vhs { from { background-position: 0 0, 0 -40% } to { background-position: 0 4px, 0 140% } }
.lc-o-vhs { background: repeating-linear-gradient(0deg, rgba(0,0,0,.22) 0 1px, transparent 1px 4px), linear-gradient(transparent 0 45%, rgba(255,255,255,.18) 50%, transparent 55%);
  background-size: 100% 4px, 100% 100%; background-repeat: repeat, no-repeat; animation: lc-o-vhs 2.2s linear infinite; }
@keyframes lc-o-vignette { 0%,100% { opacity:.6 } 50% { opacity:1 } }
.lc-o-vignette { background: radial-gradient(ellipse at center, transparent 30%, rgba(0,0,0,.8) 80%); animation: lc-o-vignette 2.4s ease-in-out infinite; }
.lc .lc-card * { animation-delay: var(--lc-d, 0s); }
@media (prefers-reduced-motion: reduce) {
  .lc *, .lc *::before { animation: none !important; transition: none !important; }
}
`

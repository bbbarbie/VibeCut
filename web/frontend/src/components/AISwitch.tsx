import type { AIState } from '../api'

// The AI switch (sarah, 2026-10-18: "an ai button that turns on and off,
// when it's on, it calculates how much is spent for that edit before i
// proceed"). Off by default. On, every Make shows what that edit will cost
// first; nothing is spent until she presses Make. No key on this Mac: it
// says so instead of turning on.
export function AISwitch({ ai, onToggle, busy }: { ai: AIState | null; onToggle: (on: boolean) => void; busy?: boolean }) {
  if (!ai) return null
  const on = ai.available && ai.on
  return (
    <button type="button" role="switch" aria-checked={on} disabled={!ai.available || busy}
            onClick={() => onToggle(!on)}
            title={!ai.available ? 'No AI key on this Mac' : on ? `AI plans your edits (${ai.model}); each one shows its cost before you go` : 'Turn on to let AI plan your edit; you see the cost first'}
            className={`flex shrink-0 items-center gap-2 rounded-full border px-3 py-1.5 font-serif text-[15px] transition-colors disabled:opacity-40 ${on ? 'border-accent bg-accent/15 text-zinc-100' : 'border-line text-zinc-300 hover:bg-raised'}`}>
      <span className={`relative h-4 w-7 rounded-full transition-colors ${on ? 'bg-accent' : 'bg-zinc-600'}`} aria-hidden>
        <span className={`absolute top-0.5 size-3 rounded-full bg-white transition-all ${on ? 'left-3.5' : 'left-0.5'}`} />
      </span>
      AI {on ? 'on' : 'off'}
    </button>
  )
}

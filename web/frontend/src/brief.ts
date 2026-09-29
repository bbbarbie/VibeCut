import type { StyleAnswers, StyleQuestion } from './types.ts'

// What the creator picked in the style questions: choice keys per question,
// plus anything they typed under "Something else".
export type Picks = Record<string, { keys: string[]; other: string }>

const STYLE_IDS = ['length', 'pace', 'opening', 'captions'] as const

/** Picks -> the first chat message and the structured answers that shape
 * the proposals. Length, pace, opening and captions travel as `style`; focus and any
 * tailored question become plain words in the direction. */
export function composeBrief(text: string, questions: StyleQuestion[], picks: Picks, extra = ''):
  { message: string; style: StyleAnswers } {
  const style: StyleAnswers = {}
  const lines = [text.trim()]
  for (const q of questions) {
    const p = picks[q.id]
    if (!p) continue
    const other = p.other.trim()
    if ((STYLE_IDS as readonly string[]).includes(q.id)) {
      if (p.keys[0]) style[q.id as typeof STYLE_IDS[number]] = p.keys[0]
      if (other) lines.push(`${q.question} ${other}`)
    } else if (q.id === 'focus') {
      const words = [...p.keys, ...(other ? [other] : [])]
      if (words.length) lines.push(`Mostly about ${words.join(', ')}.`)
    } else {
      const said = [...q.choices.filter((c) => p.keys.includes(c.key)).map((c) => c.label), ...(other ? [other] : [])]
      if (said.length) lines.push(`${q.question} ${said.join(', ')}.`)
    }
  }
  if (extra.trim()) lines.push(extra.trim())
  return { message: lines.filter(Boolean).join('\n'), style }
}

/** A few words for the chat: "short, fast and punchy, opens on the best moment". */
export function sayPicks(questions: StyleQuestion[], picks: Picks): string {
  const bits: string[] = []
  for (const q of questions) {
    const labels = q.choices.filter((c) => picks[q.id]?.keys.includes(c.key)).map((c) => c.label.toLowerCase())
    if (labels.length) bits.push(labels.join(' + '))
  }
  return bits.join(', ')
}

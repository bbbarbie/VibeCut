import { decodeProfile, type CreatorProfile } from './profile.ts'

export const CREATIVE_TOOLS = [
  { id: 'camera-motion', icon: '↗', title: 'Camera motion', subtitle: 'Give a still moment a little movement.',
    source: 'Camera-motion demo', options: ['Push in', 'Pull out', 'Pan', 'Orbit', 'Handheld'],
    input: 'Describe the shot or image you want to animate', placeholder: 'A slow push toward the coffee cup. Keep the table and background steady.',
    outputs: ['A short preview before a full render', 'Camera direction and subject framing'],
    needs: 'Image-to-video generation and a preview renderer.', note: 'This creates new footage; it is an optional mode, separate from editing your original clips.' },
  { id: 'guided-edit', icon: '✦', title: 'Plan my edit', subtitle: 'Turn a direction into a clear editing brief.',
    source: 'Hypit agent workflow', options: ['Daily vlog', 'Travel diary', 'Product story', 'Talking head'],
    input: 'What story do you want to tell?', placeholder: 'A relaxed weekend in Boston, starting with the best moment and ending at the waterfront.',
    outputs: ['Story beats and a proposed shot order', 'A reversible list of edits to review'],
    needs: 'Connecting this brief to the existing storyboard operations.', note: 'The current editor already supports storyboards and reversible edits. This brief is not sent to that engine yet.' },
  { id: 'motion-graphics', icon: 'Aa', title: 'Titles & motion', subtitle: 'Make your words part of the story.',
    source: 'HyperFrames HTML/CSS-to-video', options: ['Opening title', 'Lower third', 'Statistic card', 'Animated captions'],
    input: 'What should the graphic say?', placeholder: 'Three hidden spots in Boston — a simple opening title with a soft fade.',
    outputs: ['Graphics using your saved font and color', 'Editable text, placement and animation'],
    needs: 'A deterministic graphics composition and export renderer.', note: 'Your profile supplies starting style preferences. No graphic is rendered by this panel yet.' },
  { id: 'reference-style', icon: '◈', title: 'Borrow a feeling', subtitle: 'Bring the details you love into your own video.',
    source: 'VidMuse reference packaging', options: ['Pacing', 'Captions & layout', 'Color & mood', 'Overall direction'],
    input: 'What do you like—and what should stay yours?', placeholder: 'I like the calm pacing and small captions. Keep my original sound and warmer colors.',
    outputs: ['An editable style card for approval', 'Style attributes adapted to your footage'],
    needs: 'Reference ingestion, transcription and visual style analysis.', note: 'References guide high-level style; their footage, logos and music are not copied.' },
  { id: 'video-variants', icon: '⑂', title: 'Try another version', subtitle: 'Explore a different hook without starting over.',
    source: 'Hypit reference-video variants', options: ['Different hooks', 'Shorter cut', 'Different pacing', 'Different language'],
    input: 'What should change between versions?', placeholder: 'Try a question, a surprising moment, and the result first. Keep the rest of the story consistent.',
    outputs: ['Alternate versions with controlled differences', 'A comparison of what changed'],
    needs: 'Reusable scene templates, transcript alignment and version rendering.', note: 'Variants should preserve your source project; this panel currently saves the request only.' },
  { id: 'ai-presenter', icon: '◉', title: 'My on-screen character', subtitle: 'Explore a presenter or a cartoon narrator.',
    source: 'Fish Audio + HeyGen + HyperFrames pipeline', options: ['Cartoon narrator', 'Digital presenter', 'Voiceover only'],
    input: 'Describe your character and what they should say', placeholder: 'A cartoon version of me introducing my weekly vlog in a friendly voice.',
    outputs: ['A presenter or narration preview', 'Captions and graphics matched to your style'],
    needs: 'Voice, avatar and composition providers; a cartoon-capable provider for cartoon mode.', note: 'Use your own likeness or an authorized character. Any face or voice cloning needs an explicit consent step before generation.' },
  { id: 'b-roll', icon: '▧', title: 'Find the supporting shots', subtitle: 'Show what you’re talking about.',
    source: 'Local video agent / automatic B-roll', options: ['My footage only', 'Licensed stock suggestions', 'Generated suggestions'],
    input: 'Which part of the story needs a visual?', placeholder: 'When I describe the café, show the storefront, the pastry counter, and a close-up of the drink.',
    outputs: ['Suggested shots with a reason and placement', 'An approval list before anything is inserted'],
    needs: 'Transcript/beat analysis, footage retrieval and optional licensed asset or generation services.', note: 'Start with your own footage. Stock and generated suggestions will require separate services.' },
] as const

export type CreativeTool = typeof CREATIVE_TOOLS[number]
export type FeatureBrief = { version: 1; tool: string; option: string; request: string; reference: string; creator: CreatorProfile; savedAt: string }
export const BRIEFS_KEY = 'vibecut.feature-briefs.v1'
export const LIVE_TOOL_ID = 'guided-edit'

export function guidedEditMessage(brief: FeatureBrief): string {
  if (brief.tool !== LIVE_TOOL_ID) throw new Error('Only Plan my edit can change the storyboard right now.')
  const preferences = [
    `${brief.creator.pace.toLowerCase()} pacing`,
    brief.creator.avoid.trim() ? `avoid ${brief.creator.avoid.trim()}` : '',
  ].filter(Boolean).join('; ')
  return [
    `Plan and apply a ${brief.option.toLowerCase()} edit to my current footage.`,
    `Story direction: ${brief.request}`,
    `Creator preferences: ${preferences}.`,
    'If there is no working storyboard yet, choose the proposal that best fits. Make only the smallest reversible storyboard changes needed, and ask one question instead of guessing when the direction is ambiguous.',
  ].join('\n')
}

export function makeBrief(tool: CreativeTool, option: string, request: string, reference: string, creator: CreatorProfile): FeatureBrief {
  if (!(tool.options as readonly string[]).includes(option)) throw new Error('Choose an available option.')
  if (!request.trim()) throw new Error('Add a short description before saving your brief.')
  return { version: 1, tool: tool.id, option, request: request.trim().slice(0, 2000), reference: reference.trim().slice(0, 2048),
    creator: decodeProfile(JSON.stringify(creator)), savedAt: new Date().toISOString() }
}

export function readBriefs(storage: Pick<Storage, 'getItem'>): Record<string, FeatureBrief> {
  const raw = storage.getItem(BRIEFS_KEY)
  if (!raw) return {}
  const value = JSON.parse(raw)
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('Invalid saved briefs')
  const result: Record<string, FeatureBrief> = {}
  for (const tool of CREATIVE_TOOLS) {
    const b = value[tool.id]
    if (!b) continue
    if (b.version !== 1 || b.tool !== tool.id || typeof b.request !== 'string' || typeof b.reference !== 'string'
      || typeof b.savedAt !== 'string' || !(tool.options as readonly string[]).includes(b.option)) throw new Error('Invalid saved brief')
    result[tool.id] = { ...makeBrief(tool, b.option, b.request, b.reference, b.creator), savedAt: b.savedAt }
  }
  return result
}

export function storeBrief(storage: Pick<Storage, 'getItem' | 'setItem'>, brief: FeatureBrief): Record<string, FeatureBrief> {
  const next = { ...readBriefs(storage), [brief.tool]: brief }
  storage.setItem(BRIEFS_KEY, JSON.stringify(next))
  return next
}

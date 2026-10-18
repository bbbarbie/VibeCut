// The caption fonts people reach for in CapCut, TikTok and Reels edits
// (sarah, 2026-10-18: "i want the popular ones to all be in our app").
// The apps' own faces are proprietary, so these are the openly licensed
// faces those edits use or that read the same way, shipped with the app in
// public/fonts (OFL 1.1 / Apache 2.0, licence beside each) so preview and
// export draw identical letters with no network. Their families carry a
// "VC " prefix so a Mac's own copy, or the looks' older names, never stand in.
// `size` evens out how big each face reads at the same pixel size.
export type CaptionFont = { id: string; name: string; family: string; weight: number; size: number }

const F = (id: string, name: string, weight: number, size = 1, fallback = 'sans-serif'): CaptionFont =>
  ({ id, name, family: `"VC ${name}", ${fallback}`, weight, size })

export const CAPTION_FONTS: CaptionFont[] = [
  F('tiktok-sans', 'TikTok Sans', 800),
  F('montserrat', 'Montserrat', 800, 0.95),
  F('poppins', 'Poppins', 700, 0.95),
  F('bebas-neue', 'Bebas Neue', 400, 1.25),
  F('anton', 'Anton', 400, 1.1),
  F('archivo-black', 'Archivo Black', 400, 0.92),
  F('luckiest-guy', 'Luckiest Guy', 400, 1, 'cursive'),
  F('bangers', 'Bangers', 400, 1.15, 'cursive'),
  F('fredoka', 'Fredoka', 600, 1.02),
  F('permanent-marker', 'Permanent Marker', 400, 1, 'cursive'),
  F('caveat', 'Caveat', 700, 1.3, 'cursive'),
  F('pacifico', 'Pacifico', 400, 0.95, 'cursive'),
  F('lobster', 'Lobster', 400, 1.08, 'cursive'),
  F('playfair-display', 'Playfair Display', 700, 1, 'serif'),
  F('courier-prime', 'Courier Prime', 400, 1, 'monospace'),
]

export const fontById = (id: string | null | undefined): CaptionFont | null =>
  (id && CAPTION_FONTS.find((f) => f.id === id)) || null

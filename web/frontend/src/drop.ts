// Turn a drop (files, folders, or both) into a flat list of video files.
export type Picked = { file: File; relpath: string }

const VIDEO = /\.(mp4|mov)$/i

function readAll(reader: FileSystemDirectoryReader): Promise<FileSystemEntry[]> {
  // readEntries hands back at most ~100 at a time; keep asking until empty.
  return new Promise((resolve, reject) => {
    const out: FileSystemEntry[] = []
    const next = () => reader.readEntries((batch) => {
      if (!batch.length) return resolve(out)
      out.push(...batch)
      next()
    }, reject)
    next()
  })
}

async function walk(entry: FileSystemEntry, into: Picked[]): Promise<void> {
  if (entry.name.startsWith('.')) return
  if (entry.isFile) {
    if (!VIDEO.test(entry.name)) return
    const file = await new Promise<File>((res, rej) => (entry as FileSystemFileEntry).file(res, rej))
    into.push({ file, relpath: entry.fullPath.replace(/^\//, '') })
  } else if (entry.isDirectory) {
    const kids = await readAll((entry as FileSystemDirectoryEntry).createReader())
    await Promise.all(kids.map((k) => walk(k, into)))
  }
}

export async function fromDataTransfer(dt: DataTransfer): Promise<Picked[]> {
  const entries = Array.from(dt.items)
    .filter((i) => i.kind === 'file')
    .map((i) => i.webkitGetAsEntry())
    .filter((e): e is FileSystemEntry => !!e)
  const out: Picked[] = []
  await Promise.all(entries.map((e) => walk(e, out)))
  return out.sort((a, b) => a.relpath.localeCompare(b.relpath))
}

export function fromInput(files: FileList): Picked[] {
  return Array.from(files)
    .filter((f) => VIDEO.test(f.name) && !f.name.startsWith('.'))
    .map((f) => ({ file: f, relpath: f.webkitRelativePath || f.name }))
}

// Clips picked on the home page before the video exists. Create makes the
// video, parks the clips here and opens it; the project reads them on open.
// Files can't travel in a URL, and nothing here outlives the tab.
let handoff: Picked[] | null = null
export function handOff(picked: Picked[]): void { handoff = picked }
export function takeHandoff(): Picked[] | null { const p = handoff; handoff = null; return p }

/** Same file picked twice (dropped again, or in a folder and on its own): once. */
export function mergePicked(have: Picked[], more: Picked[]): Picked[] {
  const key = (p: Picked) => `${p.file.name}|${p.file.size}|${p.file.lastModified}`
  const seen = new Set(have.map(key))
  return [...have, ...more.filter((p) => !seen.has(key(p)) && seen.add(key(p)))]
}

// The front door (plan step 4): reels pasted on the home page beside the
// clips. Create parks them here too; the project starts a Remix with them
// as soon as the clips are read.
let refs: string[] | null = null
export function handOffRefs(links: string[]): void { refs = links.length ? links : null }
export function takeRefs(): string[] | null { const r = refs; refs = null; return r }

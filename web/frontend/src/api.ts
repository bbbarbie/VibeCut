import type { CutData, Job, PrefClass, Project, Session } from './types'

async function j<T>(res: Promise<Response>): Promise<T> {
  const r = await res
  if (!r.ok) {
    let detail = r.statusText
    try { detail = (await r.json()).detail ?? detail } catch { /* not json */ }
    throw new Error(detail)
  }
  return r.json()
}

const post = (url: string, body: unknown) =>
  fetch(url, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) })

export const api = {
  project: () => j<Project>(fetch('/api/project')),
  clear: () => j<Project>(fetch('/api/project', { method: 'DELETE' })),
  locate: (files: { name: string; size: number; mtime: number; relpath: string }[]) =>
    j<{ resolved: Record<string, string>; missing: string[] }>(post('/api/locate', { files })),
  upload: (file: File, relpath: string, batch: string) =>
    j<{ path: string }>(fetch('/api/upload', {
      method: 'POST', body: file,
      headers: { 'x-relpath': encodeURIComponent(relpath), 'x-batch': batch },
    })),
  import: (paths: string[]) => j<Job>(post('/api/import', { paths })),
  job: (id: string) => j<Job>(fetch(`/api/jobs/${id}`)),
  session: () => j<Session>(fetch('/api/session')),
  cut: () => j<CutData>(fetch('/api/cut')),
  override: (target: string, action: string) => j<CutData>(post('/api/cut/override', { target, action })),
  approve: () => j<Session>(post('/api/cut/approve', {})),
  chat: (message: string) => j<Session>(post('/api/chat', { message })),
  ops: (ops: Record<string, unknown>[], label: string) => j<Session>(post('/api/ops', { ops, label })),
  toggle: (turn: number) => j<Session>(post(`/api/turns/${turn}/toggle`, {})),
  voiceover: (text: string) => j<Session>(post('/api/voiceover', { text })),
  classify: (req: { turn: number; klass: PrefClass; rule?: string; scope?: string; counter?: string; reason?: string }) =>
    j<Session>(post('/api/preferences/classify', req)),
  rule: (id: string, action: 'forget' | 'narrow') => j<Session>(post(`/api/preferences/${id}/${action}`, {})),
}

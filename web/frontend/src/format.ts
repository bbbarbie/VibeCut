export function dur(s: number): string {
  if (!isFinite(s)) return '–'
  const m = Math.floor(s / 60)
  const r = Math.floor(s % 60)
  return m >= 60 ? `${Math.floor(m / 60)}:${String(m % 60).padStart(2, '0')}:${String(r).padStart(2, '0')}`
    : `${m}:${String(r).padStart(2, '0')}`
}

export function bytes(n: number): string {
  if (n > 1e9) return `${(n / 1e9).toFixed(1)} GB`
  if (n > 1e6) return `${Math.round(n / 1e6)} MB`
  return `${Math.round(n / 1e3)} KB`
}

export function when(iso: string | null): string {
  if (!iso) return ''
  // Apple writes the camera's local time with its offset: keep that
  // wall-clock time. A bare UTC stamp is shown in this machine's zone.
  if (/(Z|\+00:?00)$/.test(iso)) {
    const d = new Date(iso)
    iso = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}T${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  }
  const m = iso.match(/^(\d{4})-(\d\d)-(\d\d)T(\d\d):(\d\d)/)
  if (!m) return ''
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
  const h = Number(m[4])
  return `${months[Number(m[2]) - 1]} ${Number(m[3])}, ${((h + 11) % 12) + 1}:${m[5]} ${h < 12 ? 'AM' : 'PM'}`
}

export const uid = () => Math.random().toString(36).slice(2, 10)

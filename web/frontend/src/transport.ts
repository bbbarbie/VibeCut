// Playback of the edit: one <video>, driven span by span over the sequence.
//
// The playhead position lives in a tiny store, not React state, so moving
// it 60 times a second re-renders only what shows it (timeline, readout)
// instead of the whole app.
import { useSyncExternalStore } from 'react'
import { locate, toSource, type SeqItem } from './sequence'
import type { Target } from './snap'
import { swapSource } from './hold'

export function createStore<T>(initial: T) {
  let v = initial
  const ls = new Set<() => void>()
  return {
    get: () => v,
    set: (nv: T) => { if (nv !== v) { v = nv; ls.forEach((l) => l()) } },
    subscribe: (l: () => void) => { ls.add(l); return () => { ls.delete(l) } },
  }
}
type Store<T> = ReturnType<typeof createStore<T>>
export function useStore<T>(s: Store<T>): T {
  return useSyncExternalStore(s.subscribe, s.get)
}

export const phStore = createStore(0)
export type TransportState = { playing: boolean; rate: number; gap: boolean }
export const transportStore = createStore<TransportState>({ playing: false, rate: 0, gap: false })
// What the playhead last snapped to (or is closing in on) -- shown by name.
export type SnapInfo = { target: Target; snapped: boolean } | null
export const snapStore = createStore<SnapInfo>(null)

const EPS = 0.5 / 30
// Same as the export's (backend audiomix.MUSIC_GAIN): the preview must not
// sound louder than the file. Only used when the mixed track can't play.
export const MUSIC_GAIN = 0.35

export class Transport {
  video: HTMLVideoElement | null = null
  audio: HTMLAudioElement | null = null   // music under the edit, if any (fallback)
  // The edit's whole sound, mixed by the backend exactly as export will write
  // it: joins carried or cut, micro-fades, the music bed. While it plays the
  // picture is muted, so every cut stops cutting the sound.
  mix: HTMLAudioElement | null = null
  mixBroken = false
  items: SeqItem[] = []
  total = 0
  private raf = 0
  private last = 0
  private cur = -1
  private switching = false
  private seekQueued: number | null = null
  private seeking = false
  private lastDrift = 0

  setItems(items: SeqItem[], total: number) {
    const changed = items !== this.items
    const sameLength = Math.abs(total - this.total) < 1e-6
    this.items = items
    this.total = total
    if (changed && transportStore.get().playing) {
      // A cut changes the pieces, not the timing: keep playing through it.
      if (sameLength && transportStore.get().rate > 0) this.cur = locate(items, phStore.get())
      else this.stop()
    }
    if (phStore.get() > total) phStore.set(total)
    if (!transportStore.get().playing) this.showFrame(phStore.get())
  }

  private state(p: Partial<TransportState>) {
    transportStore.set({ ...transportStore.get(), ...p })
  }

  private async ensureClip(clipId: string) {
    const v = this.video
    if (!v) return
    const url = `/api/video/${clipId}`
    if (v.getAttribute('src') === url && v.readyState >= 1) return
    await new Promise<void>((res) => {
      v.addEventListener('loadedmetadata', () => res(), { once: true })
      swapSource(v, url)
    })
  }

  /** Move the playhead. Paused: shows that frame. */
  seek(t: number) {
    t = Math.max(0, Math.min(t, this.total))
    phStore.set(t)
    if (!transportStore.get().playing) this.showFrame(t)
    else if (transportStore.get().rate > 0) this.play(transportStore.get().rate)
  }

  // Coalesce paused seeks: while one is in flight, keep only the latest.
  private showFrame(t: number) {
    this.seekQueued = t
    if (this.seeking) return
    this.seeking = true
    ;(async () => {
      while (this.seekQueued != null) {
        const at = this.seekQueued
        this.seekQueued = null
        const k = locate(this.items, at)
        const it = this.items[k]
        if (!it) break
        if (it.kind === 'gap') { this.state({ gap: true }); continue }
        this.state({ gap: false })
        await this.ensureClip(it.clip_id!)
        if (this.video) this.video.currentTime = Math.min(toSource(it, at), it.src_end - EPS)
      }
      this.seeking = false
    })()
  }

  play(rate = 1) {
    if (!this.items.length || !this.video) return
    cancelAnimationFrame(this.raf)
    this.state({ playing: true, rate })
    if (rate > 0) this.forward(rate)
    else this.reverse(rate)
  }

  stop() {
    cancelAnimationFrame(this.raf)
    this.video?.pause()
    this.audio?.pause()
    this.mix?.pause()
    if (this.video) this.video.muted = false   // shelf previews play their own sound
    this.state({ playing: false, rate: 0 })
  }

  private mixUsable() {
    return !!this.mix && !this.mixBroken && !this.mix.error && !!this.mix.getAttribute('src') && this.mix.readyState >= 2
  }

  /** The bed that follows the playhead: the mix if it plays, else the plain music. */
  private bed(rate: number): HTMLAudioElement | null {
    const useMix = rate === 1 && this.mixUsable()
    if (this.video) this.video.muted = useMix
    if (useMix) { this.audio?.pause(); return this.mix }
    this.mix?.pause()
    if (this.audio) this.audio.volume = MUSIC_GAIN
    return this.audio
  }

  private async enter(k: number, t: number, rate: number) {
    const it = this.items[k]
    const v = this.video!
    if (it.kind === 'gap') { v.pause(); this.state({ gap: true }); return }
    this.state({ gap: false })
    await this.ensureClip(it.clip_id!)
    v.currentTime = toSource(it, t)
    v.playbackRate = rate
    await v.play().catch(() => {})
  }

  private syncMusic(t: number, rate: number, force = false) {
    const a = this.bed(rate)
    if (!a) return
    if (rate !== 1) { a.pause(); return }
    const now = performance.now()
    const drift = a.currentTime - t
    if (a === this.mix) {
      // The mix is the whole sound: a seek is heard as a skip, so small drift
      // (the picture pausing to change file at a cut) is absorbed by playing
      // the sound a touch slower or faster; only a big one is re-seeked.
      if (force || Math.abs(drift) > 0.3) {
        a.currentTime = t
        a.playbackRate = 1
        this.lastDrift = now
      } else {
        a.playbackRate = Math.abs(drift) < 0.02 ? 1 : Math.max(0.94, Math.min(1.06, 1 - drift * 0.6))
      }
    } else if (force || (now - this.lastDrift > 500 && Math.abs(drift) > 0.12)) {
      a.currentTime = t
      this.lastDrift = now
    }
    if (a.paused) a.play().catch(() => { if (a === this.mix) this.mixBroken = true })
  }

  private async forward(rate: number) {
    let t = phStore.get()
    if (t >= this.total - EPS) { t = 0; phStore.set(0) }
    this.cur = locate(this.items, t)
    this.switching = true
    this.bed(rate)   // mute the picture before it starts if the mix will carry the sound
    await this.enter(this.cur, t, rate)
    this.switching = false
    this.syncMusic(t, rate, true)
    this.last = performance.now()
    const tick = (now: number) => {
      if (!transportStore.get().playing) return
      const dt = (now - this.last) / 1000
      this.last = now
      if (!this.switching) {
        const it = this.items[this.cur]
        let pos: number
        let done: boolean
        if (it.kind === 'gap') {
          pos = phStore.get() + dt * rate
          done = pos >= it.seq_end
        } else {
          const ct = this.video!.currentTime
          pos = it.seq_start + (ct - it.src_start)
          done = ct >= it.src_end - EPS || this.video!.ended
        }
        if (done) {
          const next = this.cur + 1
          if (next >= this.items.length) { phStore.set(this.total); this.stop(); return }
          const nx = this.items[next]
          this.cur = next
          phStore.set(nx.seq_start)
          // the other half of a cut, straight after: keep playing, no seek
          const seamless = it.kind === 'shot' && nx.kind === 'shot' && nx.clip_id === it.clip_id
            && Math.abs(nx.src_start - it.src_end) < 0.02
          if (!seamless) {
            this.switching = true
            this.enter(next, nx.seq_start, rate).then(() => { this.switching = false; this.last = performance.now() })
          }
        } else {
          phStore.set(Math.min(pos, it.seq_end))
        }
        this.syncMusic(phStore.get(), rate)
      }
      this.raf = requestAnimationFrame(tick)
    }
    this.raf = requestAnimationFrame(tick)
  }

  // Browsers won't play video backwards; step the playhead and show frames.
  private reverse(rate: number) {
    this.video?.pause()
    this.audio?.pause()
    this.mix?.pause()
    this.last = performance.now()
    let lastShown = 0
    const tick = (now: number) => {
      if (!transportStore.get().playing) return
      const dt = (now - this.last) / 1000
      this.last = now
      const t = Math.max(0, phStore.get() + dt * rate)
      phStore.set(t)
      if (now - lastShown > 70) { this.showFrame(t); lastShown = now }
      if (t <= 0) { this.stop(); return }
      this.raf = requestAnimationFrame(tick)
    }
    this.raf = requestAnimationFrame(tick)
  }
}

export const transport = new Transport()


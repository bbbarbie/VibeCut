// Switching the one <video> to another file blanks it until the new file's
// first frame is decoded -- on 4K HEVC that's a visible black flash at every
// cut, which a fast edit turns into strobing. So before switching, the frame
// on screen is copied to a canvas laid over the video, and the canvas stays
// until the new clip has actually presented a frame at its new position.

type FrameVideo = HTMLVideoElement & { requestVideoFrameCallback?: (cb: () => void) => number }

function holdCanvas(v: HTMLVideoElement): HTMLCanvasElement | null {
  return v.parentElement?.querySelector<HTMLCanvasElement>('canvas[data-hold]') ?? null
}

/** Point `v` at `url`, keeping the current picture up until the new one is ready. */
export function swapSource(v: HTMLVideoElement, url: string): void {
  const c = holdCanvas(v)
  if (c && v.readyState >= 2 && v.videoWidth) {
    const scale = Math.min(1, 960 / Math.max(v.videoWidth, v.videoHeight))
    c.width = Math.round(v.videoWidth * scale)
    c.height = Math.round(v.videoHeight * scale)
    try {
      c.getContext('2d')?.drawImage(v, 0, 0, c.width, c.height)
      c.style.visibility = 'visible'
      const fv = v as FrameVideo
      let done = false
      const hide = () => { if (!done) { done = true; c.style.visibility = 'hidden' } }
      // the seek to the span's start comes after loading; wait for its frame
      v.addEventListener('seeked', () => {
        if (fv.requestVideoFrameCallback) fv.requestVideoFrameCallback(hide)
        else hide()
      }, { once: true })
      setTimeout(hide, 2000)   // never leave a stale frame up
    } catch { c.style.visibility = 'hidden' }
  }
  v.setAttribute('src', url)
  v.load()
}

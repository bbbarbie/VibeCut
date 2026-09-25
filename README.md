# VibeCut

Turn fragmented footage into something worth watching.

This repo starts with the measurement layer. `cutgrammar/` is the first
module; the fixer and the storyline engine are separate modules that will
sit beside it, all reading the same index.

```
VibeCut/
  cutgrammar/    measure how a video is cut          <- this
  web/           first interface: drop a shoot, pick one of three storyboards
  cutfix/        act on those measurements           (later)
  storyline/     propose several edits from one shoot (later)
```

See [`web/README.md`](web/README.md) to run the interface.

---

## cutgrammar — measure the editing grammar of a video

Most of what makes amateur footage read as amateur is craft nobody taught
the person holding the camera — cuts landing on dead frames, sound and
picture changing on the same instant, a rhythm so even it feels like a
slideshow. Whether a vlog is *beautiful* is not computable. Whether it
follows those rules is.

This tool measures them. One codebase, three uses:

- **Grammar check** — run it on a rough cut, get a list of what an editor
  would fix.
- **Style extraction** — run it on a creator's published videos, get the
  numbers that describe how they cut.
- **Reference matching** — run it on a video they admire, get a spec to
  aim at.

Analysis only, for now. Nothing is rendered or modified.

## Install

Needs `ffmpeg` and `ffprobe` on PATH, Python 3.10+, and numpy.

```bash
pip install -r requirements.txt
python analyze.py path/to/vlog.mp4
```

## Use

```bash
python analyze.py vlog.mp4                     # terminal report
python analyze.py vlog.mp4 --json out.json     # machine-readable
python analyze.py refs/*.mp4 --quiet --json refs.json
```

```python
from cutgrammar import media, shots, grammar, report

m = media.load("vlog.mp4")
r = grammar.analyze(m, shots.detect(m))
print(report.to_text(r))
```

## What it measures

| Check | Question | Why it matters |
| --- | --- | --- |
| `rhythm_cv` | Do shot lengths vary? | Uniform pacing reads as mechanical |
| `cut_on_motion` | Do cuts land on moving frames? | Cutting on movement hides the cut |
| `jl_cuts` | Do sound and picture change together? | Offsetting them is the single biggest tell of a professional edit |
| `continuity` | Do exposure and colour jump across cuts? | Reads as a mistake, not a choice |
| `duplicates` | Is the same shot in twice? | Repeated takes left in the timeline |
| `first_cut` / `first_speech` | How long before something happens? | Where most viewers leave |
| `loudness` | Integrated LUFS | Platforms normalise to ≈ −14 |

Thresholds are first guesses. They are meant to be recalibrated against
real reference videos, not treated as received truth.

## Does it actually work?

A metric that only fires on bad footage proves nothing — it has to move
when the edit improves. `tests/test_discriminates.py` builds two files
with **byte-identical picture** and audio that differs only in timing:

```
                 hard-synced   median offset   verdict
hard cut               100%           0.03s       bad
J-cut version            0%          -0.52s        ok
```

The measured −0.52s recovers the 0.5s offset built into the fixture. The
metric is responding to the edit, not to noise.

```bash
python tests/test_discriminates.py
```

## Design

Pixels are touched exactly once. `media.load()` decodes to 48×27 RGB at
native frame rate plus mono 16 kHz audio; every later stage reads those
small arrays. A ten-minute video indexes in seconds and fits in memory,
which is what makes iterating on the rules cheap.

```
media.load()   ffprobe metadata + tiny frames + audio
  └ shots.detect()      histogram distance, adaptive threshold
      └ features.*      motion, spectral-flux novelty, brightness
          └ grammar.*   the rules, each returning a number and a verdict
              └ report  terminal / JSON
```

Shot detection is histogram-based (the PySceneDetect family): it catches
hard cuts, which is what vlogs are made of, with no GPU and no model
download. Dissolves and fades are the known blind spot — TransNetV2 is the
upgrade path when they matter.

Audio novelty is spectral flux plus level change. Level alone misses a
cut from voice to music at the same loudness, which is exactly the kind of
event a J-cut is built around.

## Known limits

- **Motion is frame-differencing**, not optical flow. It cannot tell
  camera pan from subject movement, and it has no direction — so the
  180-degree rule isn't checked yet. Optical flow is the fix.
- **No faces**, so shot size (wide / medium / close) isn't measured and
  the "vary your shot sizes" rule is missing.
- **No beat tracking**, so cut-to-music alignment isn't measured.
- **No text detection**, so nothing is known about subtitles — timing,
  position, or whether they cover a face.
- **Thresholds are guesses.** Until they're calibrated against videos
  known to be well cut, treat verdicts as prompts to look, not as truth.

## Next

1. **Calibrate.** Run it over 20 videos that are well cut and 20 that
   aren't. Every threshold above should come from that distribution
   instead of from judgement.
2. **Optical flow**, which unlocks cut-on-motion properly and the
   180-degree rule.
3. **Faces**, which unlock shot size and subtitle-over-face checks.
4. **The fixer.** Once the measurements are trusted, the same numbers
   drive changes: nudge cuts onto motion, offset audio into J/L cuts,
   normalise loudness, flatten exposure jumps. Analysis first — a fixer
   built on uncalibrated measurements will confidently make things worse.

## Licence

Unlicensed / private.

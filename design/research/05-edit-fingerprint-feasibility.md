# Edit fingerprint: what VibeCut can measure from any finished video

*Research agent output, 2026-09-25 (taste-research workflow). Unedited except for this header. Sources are the agent's; verify before relying on any single claim.*

# Edit fingerprint: what VibeCut can measure from a finished video today

**Bottom line:** most of an edit fingerprint is already built. `cutgrammar/style.learn()` (which `remix.fingerprint()` summarises) covers pace, transition mix, beat, music arc, grade and frame. The prototypes added three things that work: on-screen caption reading (Apple Vision OCR), speech-vs-music detection (Apple SoundAnalysis), and zoom/whip/punch-in transitions. Nothing in the repo was changed; everything is in /tmp/vc_fp.

## 1. What cutgrammar can already produce
- **`grammar.analyze`:** rhythm variation (plus mean, median, p10, p90), longest shot, share of cuts landing on motion, hard-synced cut share and median audio offset, exposure/colour continuity, near-duplicate shots, time to first cut, time to first voice, integrated LUFS.
- **`style.learn`:**
  - Pace: shots, cuts/min, median, p10, p90, rhythm variation, first shot length, 5-bin pace curve, trend.
  - Transitions: counts, shares and lengths of cut / dissolve / dip to black / flash, plus fade in and fade out.
  - Beat: BPM, share of cuts on the beat grid, lift over chance, beats per shot.
  - Music: 32-point energy arc.
  - Look: 19-point tone curve, shadow/mid/high tints, colour cast, saturation, warmth, tint, black and white points, contrast.
  - Frame: aspect ratio, letterbox.

## 2. Analyser output (`python analyze.py <file>`)
Timings are wall-clock for the whole run.

| Export | Length, shots, cuts/min | Rhythm variation | Cuts on motion | Hard-synced | Continuity | Duplicates | First cut | First voice | LUFS | Wall time |
|---|---|---|---|---|---|---|---|---|---|---|
| Sarah remix v3 | 20.5 s, 27, 79.0 | 0.37 ok | 38% BAD | 92% BAD | 15% warn | 1 warn | 1.50 s ok | 0.01 s ok* | −13.8 ok | 8.9 s |
| Viral draft v2 | 46.1 s, 28, 36.5 | 0.57 ok | 52% warn | 64% warn | 19% warn | 1 warn† | 0.48 s ok | 0.01 s ok* | −10.1 BAD | 15.8 s |
| Talking-head cut | 20.5 s, 1, 2.9 | too few shots | – | – | – | – | – | 0.01 s ok | −18.2 BAD | 7.3 s |
| A day out | 11.0 s, 2, 10.9 | too few shots | 100% ok | – | 100% BAD | – | 7.00 s warn | 7.00 s BAD | −21.8 BAD | 2.9 s |

\* These are wrong: the music was read as a voice. This is the level-based `speech_mask` failure CLAUDE.md already lists.
† This one is right: the EDL uses clip 4466 twice.

Ground truth for v2 comes from `/tmp/vcdraft/edl2.txt`: 28 cuts on a 0.48 s (125 BPM) grid. All 28 boundaries were found, and 27 of 28 land within 50 ms of the grid. One cut was mislabelled as a dissolve.

## 3. Fingerprint spec
Speed is on an M-series Mac, after the shared decode, which takes 2.5–6.2 s per export.

| Metric | How | Status | Speed | Reliability |
|---|---|---|---|---|
| Shot median, p10, p90, rhythm variation, pace curve, first shot | `style.pace` | available | <20 ms | v2: 28/28 boundaries found |
| Shot IQR, nPVI (how much each shot differs from the next), cuts in first 3 s, cuts per 10 s | `fp.shot_stats` | prototyped | <1 ms | exact, given the boundaries |
| Edit grid (shots as multiples of one period) | `fp.grid_fit` | prototyped | 1–8 ms | v2: P = 0.47 s (truth 0.48), 93% of shots fit; can latch onto a fraction of the true period |
| BPM and cuts on the beat | `music.estimate_bpm`, `style.beat_sync` | available | 20–100 ms | v2: 125.1 BPM (truth 125), 96% of cuts on the beat vs 25% by chance. Only works when the beat is steady |
| Cuts on the half-beat grid | added to `beat_sync` | prototyped | same | v3 (same cuts, new track): phase came out half a beat off, so 4% on the beat but 100% on the half-beat grid. Needs both grids |
| Cut, dissolve, dip, flash, fades | `style.transitions` | available | 0.14–0.39 s | synthetic: 8/8 of each, 49/49 control cuts. Real: 1 false dissolve in 28 cuts |
| Zoom transition, whip, punch-in | phase correlation plus scale search at 48×27 (`trans.py`) | prototyped | 70 ms per boundary; punch-in scan 9.5 ms per frame | synthetic: 8/8, 7/8, 8/8. Real hard cuts mislabelled: 4 of 53. Punch-in scan: 1 false event (a walking-forward clip), 0 in 1,470 real frames |
| Slow push-in over a shot | whole-shot scale fit | needs work | – | fails: handheld drift reads as ±20–25% where the real push is at most 9% |
| J/L-cut offset, cut on motion | `grammar` | available | – | uncalibrated |
| LUFS, true peak, loudness range, short-term p10/p50/p90 | one `ebur128` pass | integrated LUFS available; the rest prototyped | 0.2–0.7 s | v2: −10.1 LUFS, true peak −0.4, range 4.8, short-term −13.5/−9.8/−8.9. Talking head: range 1.1 |
| Speech vs music timeline | SoundAnalysis `SNClassifySoundRequest` v1, 1 s windows (`snprobe.swift`) | prototyped | 0.3 s per 20 s of audio | talking head: 100% of windows speech. Music edits: 92–100% music, 9–12% speech. Fixes the "first voice 0.01 s" error |
| Grade: tone, tints, saturation, warmth, contrast | `grade.stats` | available | 0.2–1.2 s | grey-world estimate, so scene content leaks in |
| Per-shot grade spread ("one LUT" consistency) | standard deviation of per-shot warmth, saturation, brightness | prototyped | included above | v2 warmth spread 14.5, consistent with its continuity warnings |
| Colour temperature (K) | McCamy formula on the average colour | prototyped | – | 5,350–5,560 K on every export, so it tracks the scenes, not the grade. Low value |
| Motion energy, static-shot share | `features.motion` | prototyped | <50 ms | talking head 0.61 vs b-roll 3.4 |
| On-screen text | Vision `RecognizeTextRequest` at `.accurate`, 4 fps at 540p, plus a fuzzy tracker (`captions.py`) | prototyped | 0.13 s per frame (about 0.5× real time) | see §4 |

## 4. On-screen text (Vision OCR, macOS 26.4)
- **Recall:** every caption line was found.
  - v2: 8 of 8 lines, verbatim ("12:50 pm · lunch" came out with "-" for "·").
  - Remix v3: 10 of 10 lines.
  - Talking-head cut (Chinese): 10 subtitle cues at y = 0.77, 3–11 characters each, all read.
- **Timing:** v2 starts land within 0.13 s of the known section starts (1.92 / 9.6 / 17.28 / 23.04 / 36.48 / 42.24 s against OCR 2.00 / 9.75 / 17.25 / 23.00 / 36.50 / 42.25 s).
- **Position and size in remix v3:** each caption's vertical position is within 0.005 of `_layout()`: title 0.406 (layout 0.40), tag 0.163 (0.16), scene 0.304 (0.30). Measured text heights are in the ratio 3.06 : 1.35 : 1, against font sizes of 3.0 : 1.35 : 1.
- **Telling captions from scene text:** the rule "spans a cut, or at most 4 text boxes in the frame, and height at least 1.5% of the frame" gives 19 correct of 22 tracks. The 3 false positives were a sign, a number and a slide title. Lecture slides, the main source of scene text, were rejected correctly.
- **Misses:** the small tag disappeared for about 1 s over a white projector slide. The animated pop-in makes the first frames misread ("2:50 pm Tunch"), and fuzzy matching absorbs this.
- **Cheaper modes don't work:**
  - `.fast` mode (17 ms per frame) read none of the stylised captions.
  - `DetectTextRectanglesRequest` (7 ms per frame) caught v2's clock-time captions in only 17 of ~40 frames where they were on screen.
  - 540p gives the same results and speed as 1080p, so use 540p.

This measures a caption's position band, size, alignment (v2 left-aligned at x ≈ 0.18, remix centred), characters per line, cue length and cadence, persistent tags, and text patterns such as clock stamps.

## 5. Transitions
- **Cut, dissolve, dip, flash** are already distinguished well.
- **Zoom and whip** currently show up as plain cuts. They separate with two extra signals near the boundary:
  - Consecutive-frame scale fit, for zoom.
  - A large, same-direction phase-correlation shift together with a drop in horizontal-to-vertical gradient ratio (motion blur), for whip.
- **Punch-in** (same shot, cropped tighter) produces no histogram cut, so it needs its own candidate scan. The tell is that the frame after the jump is a rescaled copy of the frame before it.
- **Getting from "prototyped" to trusted** needs:
  - real positives (I have none of zoom or whip);
  - a cheap pre-filter so the punch-in scan doesn't run on every frame;
  - higher-resolution registration for slow push-ins, for example Vision's homographic registration [inferred].

## 6. Measured viral references (already in the cache)
The references cache already holds `style.json` for four "day in my life" Shorts. The view counts come from the yt-dlp `source.info.json` files cached beside them.

- https://www.youtube.com/watch?v=OKpyZArSBuw — Swara Singh, 4.87M views: 0.65 s per shot, first shot 1.4 s, all hard cuts, no steady beat.
- https://www.youtube.com/watch?v=tCWJUFoYDhc — Becca Kim, 2.43M: 0.70 s per shot, first shot 3.7 s, 133 BPM, cuts not on the beat (0.8× chance).
- https://www.youtube.com/watch?v=mZ_WLcJXGNc — galacsea, 1.36M: 0.83 s per shot.
- https://www.youtube.com/watch?v=lIr5Ed2cEuk — YiNi K, 0.36M: 0.83 s per shot, 104 BPM, 1.31× chance (not called on-beat).

All four cut at 61–75 cuts per minute with only hard cuts and are warm-graded; none cuts on the beat grid. That is n = 4 at 360p. OCR at 360p is untested.

## 7. Recommendation
1. **Add the cheap wins to `style.learn`:** IQR, nPVI, cuts in the first 3 s, cuts per 10 s, grid fit, the half-beat grid, and loudness range / true peak / short-term loudness from the `ebur128` pass `check_loudness` already runs. That's under 50 ms extra per video.
2. **Add SoundAnalysis as a Swift helper mode** (alongside vibevision / vibespeech). It gives a speech/music share for the fingerprint and fixes `first_speech` without a model download.
3. **Add caption fingerprinting** as a `--text` mode on `vibevision` (`.accurate`, 2–4 fps, 540p). CLAUDE.md says pixels are touched once, so emit the 540p frames from the same ffmpeg decode as `load()` using a split filter [inferred], rather than decoding a second time.
4. **Ship zoom, whip and punch-in with verdict `pending`** until they are calibrated. `gen.py` fixtures (the same clips joined by each transition kind) are ready to become the discrimination test.
5. **Drop colour temperature**; defer push-in detection.
6. **Calibration is still the gate.** Per-niche "taste" is better modelled as the distribution of these numbers across a niche's top videos than as seven presets. `reference.py` already caches measured references, so collecting about 20 per niche is the next step.

Files are in /tmp/vc_fp:
- fp.py
- captions.py
- ocr_events.py
- ocrprobe.swift
- snprobe.swift
- rectprobe.swift
- gen.py
- trans.py
- fp_real.py
- push.py

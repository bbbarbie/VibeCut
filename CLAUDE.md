# VibeCut — working notes for Claude

Read this before touching anything. It carries the decisions that are
already made, so they don't get relitigated every session.

## What this is

A tool that turns fragmented footage into something worth watching.
Target user: a vlogger who films 100 clips on a trip and cannot face
editing them. Not agencies, not ad teams, not performance marketers.

## The bet

Whether a vlog is *beautiful* is not computable. But most of what makes
amateur footage read as amateur is craft nobody taught the person holding
the camera — and craft is measurable.

Rough split of what drives the impression:

| Share | What | Automatable |
| --- | --- | --- |
| 40% | Hard constraints: exposure jumps, loudness, subtitle over a face | yes |
| 30% | Editing grammar: J/L cuts, cut on motion, 180° rule, shot size | yes |
| 20% | Surface consistency: one LUT, one font, fixed subtitle position | yes |
| 10% | Taste: what to include, where the emotion goes | **no — left to the user** |

The promise to a user is therefore *not* "this will be beautiful." It is
**"this will have no amateur tells."** Don't let the copy drift past that.

## Status

- `cutgrammar/` — measurement. Built, tested, uncalibrated.
- `cutfix/` — acts on the measurements. **Not built. Do not start yet.**
- `storyline/` — proposes several edits from one shoot. Not built as a
  module; v1 axis enumeration (time / place / subject, no LLM) lives in
  `web/backend/storyboard.py`.
- `web/` — first interface (FastAPI + Vite/React). Built at the user's
  explicit request despite the "no web UI" non-goal below; scope is
  deliberately one path: drop → index → three proposals → pick one →
  edit by chat or timeline. Two levels: **Story** (default — parts and
  shots, no timecodes) and **Frames** (the precise timeline). Select, then
  act; no jargon in the UI. See `web/README.md`.
- Chat editing rule: a turn applies operations to the working storyboard
  (`web/backend/board.py`), never regenerates it. The LLM only emits ops;
  the diff is computed, not reported by the model. Keep it that way.

- `cutgrammar/music.py` — energy-shape matching of the user's own tracks to
  the storyboard. Built, synthetic-tested; **not yet judged on a real music
  library** (none on the dev machine). Beat snapping is the next task.

- Timeline precision (`web/backend/timeline.py`, `web/frontend/src/snap.ts`):
  built and tested. Known: scrub-snapping at fit zoom on long edits pulls
  too far (21% of scrubs >1 s); motion targets are ±0.5 s (keyframe index).

- Rough cut (`cutgrammar/reject.py`, `trim.py`, `signals.py`; gate in
  `web/backend/workflow.py`, design adapted from cut-motion — see NOTICE).
  Discrimination-tested on synthetic fixtures; thresholds are guesses and
  every decision passes a human gate. **Known failure on real footage:**
  `speech_mask` is level-based, so music reads as talking and those clips
  are barely trimmed (3 real clips: 7:16 → 7:12). A real VAD is the fix.

- Words on screen + export (`web/backend/overlays.py`, `export.py`,
  `web/frontend/src/overlayDraw.ts`; ideas from Overlay Studio — design
  only, its licence forbids including its code, see NOTICE). Overlays are
  ops in the turn log, anchored to edit / end / part / shot; one style per
  video; suggestions only use words the edit already knows; checks report,
  never change. One Canvas function draws both preview and export frames;
  ffmpeg here has no drawtext, so don't move text rendering server-side.
  Export is the only place pixels are re-encoded. Checks' thresholds
  (reading speed etc.) are guesses, uncalibrated.

- Talking-head mode (`web/backend/talk.py`, `speech.py`, `TalkCut.tsx`):
  rules + optional model review; tested on synthetic transcripts and through
  the real recogniser (`tests/test_talk_speech.py`, macOS TTS). Thresholds
  (MIN_PAUSE 0.45 s, breath 0.27 s, retake similarity 0.6) are guesses. Not
  yet tried on a real creator's talking-head footage or with the live model.

- **Borrow a feeling** (`cutgrammar/style.py`, `grade.py`; `web/backend/
  reference.py`, `restyle.py`; `BorrowStyle.tsx`; idea from Hypit, analysis
  only — see NOTICE). A reference video (file, or link via yt-dlp) is read
  with `load()` and reduced to measurements: pace + arc, transitions, beat
  alignment, look, letterbox, music feel. Applied as one `apply_style` op
  (never from chat): pace/beat retime shots; LUT, transitions and bars are
  rendered only in `export.py` (dissolves use source handles so cuts stay
  on their frame, else fall back to cuts and say so). Tests:
  `tests/test_style.py` (discrimination; optional real footage via
  `VIBECUT_REAL_CLIPS`), `tests/test_restyle.py` (board + full render round
  trip). Dissolve thresholds were set on real handheld footage (a few
  dozen joins); a soft transition only counts as a habit above 15% of joins.
  Beat alignment needs a steady tempo, because hard audio cuts make their own onsets.
  Everything else is a guess. The reference's frames and audio never reach an export.

- **Remix** (`web/backend/remix.py`, `select.py`; `cutgrammar/openverse.py`;
  CLI only so far: `python -m web.backend.remix --ref <link|file>… --footage
  <folder>`). Reference reels + the shoot → one finished short, server-side,
  no browser. The references' styles (Borrow a feeling) are merged into a
  fingerprint (median shot length + arc, hook hold, tempo range, energy arc,
  length); `select.py` picks that many moments — distinctive labels (IDF
  across the shoot), face-in-the-world, subject, steadiness; sqrt-of-footage
  quota per session; look-alikes (cosine ≥ 0.78 in a session) collapse;
  windows cut in just before the busiest second. Music comes from Openverse
  (Jamendo/Freesound, CC0/BY/BY-SA only, credit line written next to the
  export); the drop is found from the waveform and placed at the end of the
  hook; every shot is a whole number of beats. Captions (title, tag, clock +
  a phrase from a label) are drawn by an AppKit helper into export's PNG
  schedule; `export.py` gained `mix` (in-point, gain, original gain, ducks,
  sfx, loudnorm) and a per-item `punch` (zoompan). Tested on synthetic
  fixtures (`tests/test_select.py`, `test_remix.py`, `test_openverse.py`);
  judged on one real shoot (42 clips, 3 references). Every weight is a
  guess; the selector has no model behind it (no key on this Mac).

- From montage-vlog-compiler (MIT; see NOTICE), four pieces:
  - **Evidence levels** (`cutgrammar/evidence.py`): every finding names
    what it rests on — meta / still / motion / audio. A finding whose
    reading the media lacks gets verdict `pending` ("not checked"), value
    kept. `load_index()` carries no motion. Rough-cut "shaky" rejects are
    flagged as guessed from stills.
  - **Inventory** (`cutgrammar/inventory.py`, `inventory.py`): read-only
    sha256 manifest of a shoot folder; verify names missing / changed /
    unexpected files. CLI only, not wired into import.
  - **Preferences** (`web/backend/preferences.py`): each edit turn is a
    candidate; only the creator sorts it. Only "every video" (needs rule +
    when + when-not) and "this video" are ever reused, and only confirmed
    rules reach the model. Undone edits can't be confirmed. Long-term rules
    live in `$VIBECUT_CACHE/preferences.json`.
  - **Voiceover mode** (`web/backend/voiceover.py`): opt-in fourth proposal
    from the creator's SRT or script. See the amended non-goal below.

## The rule that matters most

**Do not build the fixer until the thresholds are calibrated against real
videos.** Every threshold in `grammar.py` is currently a guess. A fixer
driven by guessed thresholds will confidently make footage worse, and it
will be hard to tell that it has.

Calibration means: run the analyser over ~20 videos known to be well cut
and ~20 that aren't, and derive each threshold from that distribution.

## Architecture

Pixels are touched exactly once. `media.load()` decodes to 48×27 RGB at
native frame rate plus mono 16 kHz audio; every later stage reads those
small arrays, never the original file. This is what makes iterating on the
rules cheap, and it is not negotiable — a change that re-decodes video per
rule is a bug even if it passes.

`media.load_index()` is the one other entry point: keyframes only (~1/s on
iPhone), decoded once at 384×216 on the hardware decoder, with the 48×27
grid derived in memory. It exists because full-rate decode of 4K60 HEVC is
~18s per 100s of footage — too slow to index a shoot. Grammar rules still
use `load()`; index mode is for shots, thumbnails (`bestframe.py`) and
storyboards, where ±1s cut accuracy is fine.

```
media.load()   ffprobe metadata + tiny frames + audio
  └ shots.detect()      histogram distance, adaptive threshold
      └ features.*      motion, spectral-flux novelty, brightness
          └ grammar.*   rules, each returning a number and a verdict
              └ report  terminal / JSON
```

## How to validate

**A metric that fires on bad footage proves nothing.** It has to *move*
when the edit improves. `tests/test_discriminates.py` is the pattern:
build two fixtures that differ in exactly one respect, assert the metric
separates them and recovers the magnitude that was built in.

Every new rule ships with a discrimination test or it does not ship.

## Conventions

- Python 3.10+, numpy only. ffmpeg/ffprobe via subprocess.
- New rules go in `grammar.py` as `check_*(media, shots) -> list[Finding]`
  and get registered in `analyze()`.
- Findings carry a raw `value` and a `verdict` (`ok` / `warn` / `bad`, or
  `pending` when the reading can't support a judgement — see
  `evidence.py`). Never a verdict without the number behind it. A new rule
  declares what it needs in `grammar.NEEDS`.
- Comments explain *why a rule exists in editing terms*, not what the
  code does.

## Non-goals

- **No generative video.** The viewer sees only frames the creator
  actually filmed. This is a positioning decision, not a technical limit:
  it is what separates this from every AI video tool, and it keeps
  inference cost sane.
- **No web UI** until the measurements are trusted. An earlier prototype
  (FRAME) burned its effort on a timeline editor before the core worked.
- **No transcript dependency.** ChatCut and Descript own the talking-head
  case because transcript-as-timeline works there. Vlogs have no
  transcript spine; that absence is the whole opening.
  *Amended (user decision):* the default path still needs no transcript.
  A creator who brings their **own** narration (SRT or script) gets one
  extra proposal that follows it — the voice sets time, the words pick
  footage by label, unmatched lines stay as listed gaps. Nothing is
  transcribed, no speech model is added, and no other path depends on it.
  Don't grow it into transcript-as-timeline editing.
  *Amended again (user decision, 2026-09-25):* a **talking-head mode (口播精剪)**
  may transcribe — opt-in, never on the default path. Speech-to-text runs
  on this Mac only (Apple SpeechTranscriber via `web/backend/speech/
  vibespeech.swift`; no Python speech model, audio never leaves). It cuts
  pauses to a breath, earlier takes of repeated sentences, stumbles and
  fillers, shows every cut at a gate, then becomes a normal storyboard with
  subtitle overlays (`web/backend/talk.py`). With a key, only the transcript
  *text* goes to Claude to judge retakes. It still isn't a transcript
  editor: the words are reviewed, not typed into.

## Known limits (upgrade path, in order)

1. Thresholds are guesses — calibrate first.
2. Motion is frame-differencing, not optical flow: no direction, so the
   180° rule can't be checked.
3. No face detection: shot size and subtitle-over-face unmeasured.
4. No beat tracking: cut-to-music alignment unmeasured.
5. Shot detection misses dissolves and fades (TransNetV2 is the fix).

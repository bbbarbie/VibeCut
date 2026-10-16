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
- `web/` — the app (FastAPI + Vite/React). Built at the user's explicit
  request despite the "no web UI" non-goal below; scope is deliberately one
  path: **Projects → Footage → (style questions) → Story → Export**, the rough trim automatic
  (Phase 1 baseline, 2026-09-28; audit, parity matrix against Vyra and the
  plan in `design/specs/phase1-baseline.md`). The stage shown is *derived*
  from project state (`web/frontend/src/stage.ts`), never set by hand.
  Projects persist on disk (`web/backend/projects.py`: clip ids, turn log,
  workflow, cut overrides, brief, exports) and survive restarts; the
  middleware saves after every mutating request. A new video starts from
  its clips on the home page (drop or choose, see the row, remove any,
  Create; `drop.handOff` carries them into the project), and asks for no
  name: it is "New video" until its clips are read, then named from the
  days they were filmed (`projects.auto_name`, "Sep 22" / "Sep 22–24"; sarah:
  just the day for now) until the creator renames it. The Footage page is
  two stacks, Kept / Left out, dealt as clips are read (`Footage.tsx`). Two levels inside Story:
  **Story** (parts and shots, no timecodes) and **Frames** (the precise
  timeline). Select, then act; no jargon in the UI. One design system
  (`web/frontend/src/ui.tsx`); the old Creative-tools page and its four
  "coming soon" cards are gone (see `web/feature-roadmap.md`). What the
  machine can't do (no key, not macOS, no yt-dlp) is stated where the action
  would be, never hidden. Home is as bare as it can be (sarah, 2026-10-06:
  "as simple as possible"): "Good morning / afternoon / evening, <profile first name>!", then
  "Start with your clips", "Drag clips / folder here", Add clips + Add folder (a
  browser picker can't take both; a phone version only needs Add clips).
  Footage has no preview panel: an opened stack is a vertical column on its own side (Kept left, Left out right), the other stack shrinks opposite as the drop target; a clicked clip plays in place with a "Move to …" button (no double-click). See `web/README.md`.
- Chat editing rule: a turn applies operations to the working storyboard
  (`web/backend/board.py`), never regenerates it. The LLM only emits ops;
  the diff is computed, not reported by the model. Keep it that way.
- **Chat on pause** (`web/backend/moment.py`, `/api/moment`, `/api/moment/chat`,
  `PauseChat.tsx`; sarah, 2026-10-05: pausing means something should change).
  While the edit is paused a box under the preview is pinned to that moment
  ("Shot 12 · 0:34 · IMG_4492"): the model gets the shot, its clip time and
  kept range, its neighbours, the words on screen and the paused index frame
  (small JPEG) with the message, through the same `llm.interpret`; its ops
  are only previewed (diff computed on a copy of the log) until Apply sends
  them to `/api/ops` as one undoable turn. `/api/moment` never calls the model
  and returns a per-message cost estimate (Opus 5 list price, output 600–2500
  tokens, priors). No key: the box says so and sends nothing.
  `tests/test_moment.py` (mocked model).

- `cutgrammar/music.py` — energy-shape matching of the user's own tracks to
  the storyboard. Built, synthetic-tested; **not yet judged on a real music
  library** (none on the dev machine). Beat snapping is the next task.

- Timeline precision (`web/backend/timeline.py`, `web/frontend/src/snap.ts`):
  built and tested. Known: scrub-snapping at fit zoom on long edits pulls
  too far (21% of scrubs >1 s); motion targets are ±0.5 s (keyframe index).

- Rough cut (`cutgrammar/reject.py`, `trim.py`, `signals.py`; gate in
  `web/backend/workflow.py`, design adapted from cut-motion — see NOTICE).
  Discrimination-tested on synthetic fixtures; thresholds are guesses. The
  gate's page is gone (sarah, 2026-10-07: "skip it"): once the style questions
  are answered the trim is approved as it stands, and every trim stays
  changeable in Frames by dragging a shot's ends out to the whole shot as
  filmed (`timeline.build` gives `src_min`/`src_max`); left-out clips are
  overruled on Footage's stacks. `speech_mask` is level-based, so
  music read as talking and those clips were barely trimmed (3 real clips:
  7:16 → 7:12). **Voice reading** (`web/backend/sound.py`,
  `sound/vibesound.swift`, `signals.with_voice`): Apple's on-device sound
  classifier (macOS; audio track only, nothing leaves) gives per-second
  voice / music / singing / laughter, cached as `sound.json`; speech counts
  only where a voice is heard (VOICE_LO 0.15 → VOICE_HI 0.45, priors).
  Filled once on project open for older clips. Elsewhere the level mask
  stays. Silero was the brief's default but needs onnxruntime (not numpy-
  only, and pip installs are blocked on her Mac). `tests/test_voice.py`.
  At the gate the kept range can be dragged by its ends (`set` override,
  min 1 s, undone by `auto`; `tests/test_cut_set.py`); hovering the bar shows
  the frame at that moment (index sample first, then the clip seeked).
  **Best moment** (`web/backend/moments.py`, `trim.candidates`): the trim
  offers up to 3 different windows per shot (share ≤ ⅓ of their seconds,
  score within RUNNER_UP 0.1 of the best); with a key, Claude sees 3 index
  frames from each and picks one (frames leave the Mac; nothing else).
  Cached per shot in the clip dir's `moments.json`; no key, an error or a
  bad answer leaves the rules' first pick. `VIBECUT_MOMENTS=0` turns it off.
  `tests/test_moments.py`. Not yet judged against her picks on real footage.

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

- **Two picks up front** (plan of 2026-10-10, step 2; `Setup.tsx`,
  `/api/brief/setup`, `/api/brief/auto {format, look}`, `/api/format`):
  after Footage's "Looks good" one popup asks the **frame** (short ·
  vertical ≤ `SHORT_MAX_S` 90 s / tall · vertical vlog / wide · 16:9;
  default from the upright share of the footage, `brief.suggest_format`)
  and the **look** (the seven of `looks/*.json`, default cozy), then "Make
  my video". They travel as `style.format` / `style.look`: the frame sets
  `export.frame_size(..., want)` for the stage and the export (a chip in
  Frames cycles it; not a board op, so not in the log) and the length
  (`brief.length_for`); the look is the first op when the story is chosen
  (`caption_ops` takes a look id, and dresses the video even with no
  captions). `tests/test_format.py`. `StyleQuestions.tsx` stays only for
  the chat's first message.
- **Style questions** (`web/backend/brief.py`, `StyleQuestions.tsx`,
  `web/frontend/src/brief.ts`): straight after Footage's "Looks good" (no
  "What's this video about?" box since 2026-10-06, sarah; the description is
  guessed from the shoot, `pitch.guess`, never the model). Since 2026-10-07 (sarah: "build") the popup isn't shown on the main path either: `/api/brief/auto` writes the brief itself (suggested length from `length_marks`, captions = describe, no pace question any more) and the stories are built, the one the shoot suggests is taken and the edit opens in Frames (sarah, 2026-10-07: no story choice for now; the others stay under Story). **Tempo** (`web/backend/tempo.py`, `PaceButton.tsx`; sarah: "you should be able to realize what kind of editing tempo we want"): quick / steady / calm read from the shoot (share of moving vs still shots by `activity`, talking and music from sound.json, median clip length), travels as `style.pace`; talking shots keep their whole window at any pace. The story: on camera most of the time → subject, several days over ≥3 places → place, else time. The top bar is Footage · Edit only, there is no Story / Frames switch (Other stories is under More and closes back into Frames), Media in Frames is two piles like Footage's, Kept = in the video / Left out (sarah, 2026-10-13; `Shelf.tsx`, `/api/pile`, `brief.clip_ops`): a clicked clip plays, says why it's out, and "Move to …" puts its rough-cut window in where it was filmed or takes every shot of it out, one undoable turn, the rough cut's call set to match, one Export button (sarah, 2026-10-07). Both shown with their reason under the tempo button in Frames, changeable there (`/api/pace`, one undoable turn). MOVING 30 / STILL 10 were set on her one shoot; the rest are priors. `tests/test_tempo.py`; Length and a Captions on/off switch (`/api/captions`, one undoable turn) sit in Frames. The popup code remains for the chat's first message: a
  popup asks length / pace / opening / focus, one question at a time, before
  the rough cut is shown. Length, pace and opening travel as `style` on the
  direction and reshape each proposal (`brief.shape`); focus and any
  Claude-tailored question (key only) become direction words. Targets (60 s,
  180 s, pace caps 8 / 5 / 2.5 s) are guesses. Tests: `tests/test_brief.py`.
  **Length is a slider** (sarah, 2026-10-06; `brief.length_marks`,
  `LengthSlider.tsx`): 15 s to everything the rough cut kept, Short / Medium
  / Long marks from how much there is and the kind of video the description
  says (day vlog / trip / event / other), one suggested with a reason; its
  end is what the edit can reach (`brief.reachable_s`: look-alikes count once,
  as `length_ops` never puts one back), not every usable second; it
  travels as `style.seconds` (≤ 75 s = one shot per moment, as `short` did).
  The same slider in Frames ("Length · 2:36") is one undoable turn
  (`brief.length_ops`, `/api/length`): weakest shots out first, else good
  shots back in filming order, their rough-cut window only (`add_shot` takes
  start/end), never a look-alike. Kind lengths and the "plenty" rule are
  priors. `tests/test_length.py`.
  **Captions** (none / describe / transcribe) travels as `style.captions`,
  and a follow-up asked only when there are captions (`when` on the
  question), the look (clean / bold = hype / cozy / quiet), as
  `style.caption_look`. When a story is chosen it becomes one undoable turn
  (`brief.caption_ops`: look + captions; no opening title, sarah 2026-10-06 — a cover image is planned instead). **Describe** = per moment
  the day moves on, "7:42 am · coffee run" (`daylog.py`; clock from the
  clip's recording time + shot offset, phrase from Vision labels, a bigger
  table incl. scenery; with a key Claude may phrase labels + time, text
  only) plus, where a new place starts, its name above the line (`sub`):
  GPS rounded to ~100 m → Apple's geocoder on the Mac (`places.py`,
  `place/vibeplace.swift`; coordinates only, free, cached in
  `$VIBECUT_CACHE/places.json`; a place, area or city, never an address).
  The default when the description says day-in-my-life. **Transcribe** =
  subtitles of what's said (`subtitles.py`): only clips where a voice is
  heard, Apple SpeechTranscriber on the Mac (speech.py, cached), lines
  broken at pauses ≥0.6 s / sentence ends / 42 chars (16 CJK), timed to the
  words, anchored to the shot; prefetched in the background when the brief
  is saved. Words never decide the cut. **Ink** (`ink.py`): each overlay's
  colour is checked against the frame behind it (32×18 tone grid per index
  sample, `tones.npy`, written at index time or once from the sample JPEGs
  for older clips); where the look's colour is under WCAG 4.5 it takes a
  tint / shade of the footage's own hue that reads over ≥95% of the band, a
  neutral only if none does; when none does (part light, part dark under
  the words) light words on a tight dark edge + soft shadow, never dark
  words (they vanished into hair and trousers on her footage). Derived per request, never stored in the log. The UI calls
  overlays "Captions". `tests/test_ink.py`. **Dragged by hand**: click a
  caption on the preview to select it, drag to move (snaps to the centre
  lines), drag a corner to size it, double-click for its words; each drop is
  one `edit_overlay` with `place: {x, y, scale}` (block centre, 0–1; null =
  back to its usual spot), drawn by the same `overlayDraw` in export, still
  pulled inside the safe area; checks still only warn. "Same place for all
  captions" is one turn. `test_overlays.py`, `overlayLooks.test.ts`. Older answers (day / simple / bold /
  key) map to describe + a look. `tests/test_captions_answer.py`.
  The description is read from the shoot (`pitch.py`: days,
  morning→night, themes, faces, talking, rough GPS; `guess` = the first
  template line, so `kind_of` sees day / weekend / days away).
  `tests/test_pitch.py`.
- **About the day, not the face** (sarah, 2026-10-14, after comparing
  VibeCut's edit of her school day with her own: half of it was her face,
  one chat with a friend held 14 s, food / stairs / night campus were left
  out). `tests/test_day_picking.py`. **Talk said to the audience vs talk
  overheard** (`trim.addressed`): faces.json rows are now `[presence, edge,
  people, facing]` (`vision.face_track`; the Swift helper adds each face's
  yaw, looking in = |yaw| ≤ 25°; older 2-column caches are re-read once on
  project open, `indexer.refresh_faces`, Mac only). Talking while looking
  into the lens keeps its sentence; talking turned away, or two people with
  no direction read, is chatter: `CHATTER_S` 3 s in the rough cut, cut by the
  pace like any shot, not counted as talking by `tempo.read`. No face at all
  (narration from behind the camera) changes nothing. **Every stop first**
  (`brief.spots`, `weakest`): a new stop when GPS moves > 150 m or 20 min
  pass; shortening (`shape`, `length_ops`) drops from the stop with the most
  shots, lengthening brings back stops not shown yet. **Shorts** hold no
  moment over `SHORT_CAP_S` 3.5 s (`brief.cap_for`, also `/api/pace`). **Lit
  night** shots (after 6 pm, contrast ≥ 0.4) are never left out for quality
  (`storyboard.lit_night`). **Swipe**: cozy and hype join parts with a whip
  (xfade slideleft + sideways smear, `export.swipe_blur`; the player slides
  both pictures, `joinView.swipeAt`); needs a dissolve's handles, else a cut.
  All numbers are priors from one of her edits. Not yet run on her clips.
- **What a moment is worth** (`web/backend/worth.py`; outside evaluation of
  the Oct 16 demo, sarah: "implement"). Every Shot gets `worth` (0..1) and
  `worth_why` in `shots_from_clips`: craft (`score`) plus feeling (laughter
  ≥2 heard seconds, singing, talking to the lens, from sound.json, which
  nothing used for picking before), label rarity across the shoot, the
  first face-free shot at a new stop ("first look at a new place"), minus a
  little for a face with nothing said. `shape` and `length_ops` rank by it
  (hook = the strongest moment, not the best-exposed), and `weakest` drops
  from the stop with the most shots *per its importance* (its best worth),
  so screen time follows what happened at a stop, not how much was filmed;
  a stop's last shot still goes last. Look-alike collapsing stays on craft.
  Weights are priors. `tests/test_worth.py`.
- **Music at social volume**: the bed's `set_music` asks for levelling
  (-14 LUFS, `audiomix.write_wav`), preview and export alike; the Oct 14
  school-day edit was -20 LUFS against her own -15. `tests/test_loudness.py`.
- HDR (HLG/PQ) footage: thumbnails and samples are tone-mapped to SDR in
  `media.to_sdr` so they look like the phone showed them; measurement frames
  are untouched. `tests/test_hdr.py`.

- From montage-vlog-compiler (MIT; see NOTICE), four pieces:
  - **Evidence levels** (`cutgrammar/evidence.py`): every finding names
    what it rests on — meta / still / motion / audio. A finding whose
    reading the media lacks gets verdict `pending` ("not checked"), value
    kept. `load_index()` carries no motion. Rough-cut "shaky" is only a warning
    at the gate, never a rejection: guessed from stills, it threw out 17 of
    42 handheld videos once music stopped counting as talking.
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

- **The bed** (`web/backend/bed.py`, `/api/bed`, the Music switch in
  Frames; plan of 2026-10-10, step 1): choosing a story puts music under
  it and moves the cuts onto its beat, one undoable turn that lands when
  the pick is ready (background job, `session.bed`). Track from the
  creator's folder, else Openverse by moods the pace suggests
  (`PACE_BPM`, `MOODS` — priors); scored by `remix.pick_from` (the Remix
  picker, now source-agnostic); drop at the end of the first shot (`HOOK_S`
  cap 8 s). Beat snap via `apply_style` traits=["beat"] with the grid in
  edit time and `keep` = talking shots (`restyle.retime` gained `keep`);
  `set_music` at `audiomix.MUSIC_GAIN`, original 1.0, ducked to
  `TALK_DUCK` under talking. Not for remix / talk / voiceover boards.
  **Backup songs** (`cutgrammar/songpack.py`; sarah, 2026-10-11: "only
  used if users link fail"): 24 songs VibeCut composes itself (8 per pace,
  CC0, no audio in the repo; rendered once into `$VIBECUT_CACHE/music/
  pack/`, ~20 s each, then measured like any track). Used only when
  Openverse hands back nothing or nothing that fits; never preferred. A
  failed Openverse search is no longer cached as "no songs".
  `tests/test_songpack.py`.
  `timeline.grid_of` now subtracts the music in-point (every Remix grid was
  off before). `VIBECUT_BED=0` keeps tests offline. `tests/test_bed.py`.
  Measured 2026-10-10 on this Mac: a cold online pick took 195 s (36 tracks
  fetched + analysed), so `/api/brief/auto` calls `bed.prefetch(pace)` as
  soon as the pace is read and the chip shows done/total. Openverse's
  commercial slice is thin: one-word moods only (phrases return 0).
  Not yet judged on real footage.
- **Sound as glue** (`web/backend/audiomix.py`; research
  `design/research/08-fluency-and-motion-ux.md`, P0/P1). One numpy mixer builds the
  edit's whole sound; the preview plays it (picture muted, rate-nudged to
  stay in sync) and export muxes the same samples, so they can't disagree.
  Every join is micro-faded (15 ms); joins are per cut on the board
  (`set_join`: cut / carry_out = L / carry_in = J; default carry_out between
  parts, cut inside), carried only where the source has footage past the
  cut, else a clean break reported at the join. Music is board state
  (`set_music`: track, in-point, gains, ducks, sfx, level) — Remix writes it
  (and its grade via `apply_style`), so editing a remix no longer loses its
  mix. Default proposals keep one of each look-alike group filmed within
  15 min (Vision only; cos ≥ 0.78, or ≥ 0.72 from the same spot, GPS ≤150 m).
  An edit that already exists gets the same check (`brief.repeat_ops`, also
  the same stretch of one clip twice, across parts): when a story is chosen,
  and once for stories chosen before it, one undoable turn drops the
  weaker of each (sarah: never identical shots in the edit); later hand
  edits are never second-guessed. Overlay ffconcat gets `option framerate 30` (10 of
  30 frames were wrong). CARRY_S 0.5 s and MICRO_S are priors — calibrate.
  Tests: `tests/test_audiomix.py`, additions in `test_export.py`,
  `test_brief.py`, `test_remix.py`.
- **Extract audio** (`board.SOUND_OPS`: `extract_audio` / `edit_audio` /
  `drop_audio`; `audiomix.strips_of`, `timeline.audio_lane`; sarah,
  2026-10-14: "at least have the basic functions for most video editing
  apps"). The shot bar's Sound › "Take the sound off" puts the shot's sound
  on its own strip in a Sound lane under the picture (`sound.off` +
  `sound.strips` on the board), sounding as the shot did (its speed, volume
  and fades come along): the strip sits at a place in the edit (unlinked,
  like CapCut), drag to move it (sticks to the same targets), click it for
  its own bar (Volume 0–200%, Fade in / out, Mute, Delete this sound).
  Deleting leaves the shot silent; a cut through a silenced shot keeps both
  pieces silent. Preview and export hear it through the same mixer.
  `tests/test_extract_audio.py`.
- **Shot bar** (`ShotBar.tsx`; `board.set_shot`, fields `speed` / `gain` /
  `mute` / `rotate` / `fill` / `mirror` / `fade_in` / `fade_out` on the
  entry, kept through a cut except the fade on the cut side; sarah,
  2026-10-14: the stepped menus were "very not user friendly", one click to
  a tool then a slider). Clicking a shot in Frames opens a bar along the
  bottom, no pop-up menu: Split · Sound (Volume slider 0–200%, Fade in /
  out 0–3 s, Mute, Take the sound off) · Speed (doubling slider ¼×–4×,
  0.5 / 1 / 2 / 4 presets) · Turn & crop (quarter turns, Mirror, Fill the
  frame = cover and crop instead of bars, Show it all) · Swap · Delete.
  A slider is one undoable turn when let go. A shot lasts `bd.seq_dur` =
  source seconds / speed; `timeline.layout`, the board's own arithmetic and
  overlays use it, the player plays the file at rate × speed and dresses
  the picture with the same turn / mirror / fill as `export._shot`. Sound
  at a speed is stretched with atempo (pitch kept, `audiomix.stretched`); a
  sped-up or slowed shot never carries sound or dissolves across its cuts.
  Known: the length slider, the bed's beat snap and restyle still count
  source seconds, so they're approximate on a shot that isn't at 1×.
  `tests/test_shot_fixes.py`.
- **Every cut checked** (`cutgrammar/joins.py`, `web/backend/seams.py`;
  research 08 P2). Report only: per cut, brightness jump, colour change
  (best-frame proxy), same view again, energy step, loudness step, going
  back in time, shot size — each a Finding declared in `grammar.NEEDS`,
  from the index (no pixel decode). Story marks rough cuts (! + numbers on
  hover); each turn gets a second look in chat. The place axis now gives a
  return visit its own chapter in day order. Thresholds are priors.
- **Smoother cuts** (`web/backend/smooth.py`, P3-1/P3-2). Only when asked,
  one undoable turn: beam search over join roughness + filming-order
  penalty inside a part (move_shot), and window nudges ≤2 s onto movement,
  never onto a word (trim). Never runs by default — that would be cutfix.
- **Looks** (`web/backend/looks.py`, `looks/*.json`, P3-3). The spec's 7
  vibes as dated records: type + motion, and since 2026-10-10 (plan step 1)
  the picture too — `grade` (relative to the footage: warmth, black floor /
  ceiling, sat and contrast ratios, split; `grade_target` → `grade.Look` →
  a .cube under `$VIBECUT_CACHE/looks/`, fitted on the story's thumbnails,
  export-only), `joins` (a transition policy, honoured by preview and
  export alike) and, for Hype / Playful, `camera` (Remix's push, export-only).
  `looks.picture(board, px)` is the one place the board's `style` is read
  for rendering (`app._style`): a borrowed reference's own look / joins win,
  the look fills what's empty; with no pixels the grade is `pending` so the
  Export dialog can say it's coming. Texture, sounds and music stay
  `not_yet`. All grade / join / camera numbers are priors; the export round
  trip in `tests/test_bed.py` shows the Cozy file comes out warmer.
  `set_look` (chat too) keeps what was set by hand and
  shows it; the profile's saved style is a default, not a choice.
  `overlayDraw.ts` reads the look's curve, entrance time, stepping, stagger,
  slam/card entrances, case and tracking; beat lock moves words onto a beat
  ≤0.25 s away. `overlayLooks.test.ts` checks every look keeps every word in
  the safe area on every intro frame. Tests: `test_joins.py`,
  `test_axes.py`, `test_smooth.py`, `test_looks.py`.
- **Joins you can see while playing** (P4; `web/frontend/src/joinView.ts`,
  `transport.ts`, `Player.tsx`). The player has two `<video>`s: the next
  shot is loaded and parked on its first frame before the cut, so a cut is
  a swap, not a seek (no black flash; `hold.ts` is only the fallback). A
  dissolve plays both over the export's own overlap window
  (`export.plan_transitions`, sent in `session.mix.transitions`), dips and
  flashes are a colour veil at the same opacity as the export's fade, and
  cinematic bars are drawn. The grade (LUT) still appears only in export.

- **Caption and transition templates** (sarah, 2026-10-15: "build";
  mockups in the project's `templates/` folder). Opt-in: nothing changes
  until picked. Click a caption → the bottom bar's **Style** (8 templates,
  `overlays.TEMPLATES`: outlined = her own hand edit, serif + black edge +
  the time on its own line; bold, label, highlight, handwritten, tape, pop,
  quiet) and **Animation** (6 entrances, `overlays.ENTERS`: fade, pop,
  slide, stamp, type, word). Both are `overlay_style` fields (`template`,
  `enter`; None = the look's own), one per video, kept when the look
  changes, drawn by `overlayDraw.ts` (TEMPLATES, motionFor) for preview and
  export alike; Mac system fonts only. Click the dot between two shots →
  **transitions** (`transitions.py`, `set_transition {shot | all, kind,
  dur}`): cut, fade, dip, flash, zoom through, slide up, blur, light leak;
  board `picture_joins` / `picture_all`, folded into the style's
  transitions policy (`at`) that `export.plan_transitions` reads. The four
  new ones are ffmpeg xfades over footage past the cut (light leak a custom
  expression), else a cut, said at export and in the bar; the player draws
  the same with CSS (`joinView.blendLook`; its blur is a plain blur where
  ffmpeg's hblur smears sideways). Tiles move the way the result will.
  Tests: `test_transitions.py` (each blend really at its cut, centred,
  length kept, all different), `test_caption_templates.py`,
  `overlayTemplates.test.ts` (safe area every intro frame, every template ×
  entrance). Sizes, durations and the glow are priors.
- **polish/** (`polish/`, `web/backend/polish_api.py`, `Polish.tsx`,
  `polishDraw.ts`; page `#polish`). Assisting an edit that is already cut:
  input is one finished video, never raw clips; no auto-editing, no
  storyboard, no selection, no music, no export, no login. One interaction:
  click the picture → anchor `{t on a frame, x, y in the picture, shot}` →
  one sentence → ops on caption/effect layers (turn log, computed diff,
  undo by replay, like `board.py`). Sentences are read by rules first
  (`parse.py`: 写上「…」 / boom / 大一点 小一点 / 删掉 / 改成 / 用我的配方 /
  存成配方); the model is asked only when no rule matches (key only).
  Captions use the creator's **recipe** (`recipe.py`, `$VIBECUT_CACHE/
  polish/recipes.json`): saved *from* a tuned caption, first = default.
  Layout (`layout.py`) is decided once, server-side, and the browser draws
  exactly those lines in that box (shrinking only if its real font is
  wider): off every face over the caption's span (moves above / below /
  top and says so), inside the safe area, no one-character last line.
  Effects snap to a movement onset (±0.4 s, frame-accurate from one
  `media.load()` of the finished video) or a beat (±0.25 s). Face boxes
  come from on-device Vision over the index's samples (macOS only);
  elsewhere the face rule reports `pending`, never "clear". Tests:
  `tests/test_polish.py`, `test_polish_api.py` (face in the lower third vs
  the top, through the API), `polishDraw.test.ts`. Windows and margins are
  priors.
- **Fonts: only what's already on the creator's machine.** A system family,
  or a font file the creator points at (served back only if a saved recipe
  names it). Never bundle or ship a font. **Recognising a font in a
  reference image or video is not a licence to render it** — naming it is
  fine, drawing with it needs the creator's own licensed copy.

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

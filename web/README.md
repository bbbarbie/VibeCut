# web/ — the first VibeCut interface

Drop a folder (or single clips), say in one line what the video is, get
three differently-structured proposals, start from one, then edit it by
talking: "make the opening punchier and cut the market section" changes
exactly those two things. Every turn shows a diff and can be undone.
Footage, thumbnails and the index never leave this machine; with a key set,
the storyboard's *text* goes to Claude to be turned into operations.

```bash
# from the repo root
pip install -r requirements.txt -r web/requirements.txt
(cd web/frontend && npm install && npm run build)
python -m web.backend            # → http://localhost:8765
```

Chat edits need an Anthropic key: put `ANTHROPIC_API_KEY=...` in
`web/.env` (gitignored) or export it. Without one, the first message still
produces proposals (keyword matching), and Apply, timeline edits and undo
all work; only chat *edits* are unavailable.

For UI work, run `npm run dev` in `web/frontend` as well (Vite on :5173,
proxying `/api` to the backend).

Needs macOS for the full experience: the hardware decoder (VideoToolbox)
and the on-device Vision helper. Elsewhere it falls back to software
decode and colour-based subject grouping.

## Creator profile

Open **Creator profile** in the header (or visit `/#profile`). Save your
name, handle, creative goals, platforms, preferred mood and pacing, caption
font/color/placement, things to avoid, and up to 10 reference bookmarks with
notes. The responsive profile page includes a live caption style sample.

Use **Save profile** to persist preferences in this browser's localStorage.
They survive page reloads and editing sessions; they do not sync across
browsers, devices, or different localhost ports. No account is created.
Unsaved changes trigger a warning on leaving through the page's Back button
or reloading. Storage failures are shown without discarding the draft.

This is the profile foundation: preferences are not yet passed to the editing
engine, reference videos are not fetched or analyzed, and the sample is not a
rendered video. Opening the profile keeps the editor mounted and pauses playback.
Tests for persistence, invalid data, and storage failures run with `npm test`.

## Layout: two levels

### Creative tools (feature previews)

Open **Creative tools** from the editor or profile, or visit `/#tools`.
Seven buttons represent the previously reviewed recording workflows:
camera motion, guided edit planning, titles/motion graphics, reference style,
video variants, AI presenters, and supporting B-roll.

Each opens a configuration dialog with direction choices, a written brief,
an optional reference link, and a snapshot of the saved creator profile.
**Save brief** persists one brief per feature in browser localStorage;
**Download brief** exports a JSON plan for handoff. Existing briefs can be
reopened and revised. Draft changes are guarded when closing the dialog.

These are functional planning interfaces, **not connected generators**:
they do not ingest reference videos, call paid providers, modify the timeline,
or render/export video. The panel explains what each integration still needs.
See [feature roadmap](feature-roadmap.md) for the seven source recordings and
implementation boundaries.

**Story** (default, where people live): the edit as parts and shots. Before
a story is chosen, the centre asks what the video is about, then shows the
three options side by side (parts, thumbnails, a one-line explanation, a
Watch button). After choosing: one row per part — drag a row to move it,
click a part's title for Rename / Watch / Move / Remove / "Fine-tune in
Frames", click a shot for Watch / Swap / Remove. No timecodes, no tracks.
The player stays on the right; chat on the left.

**Frames** (drill-down, one click on the switch in the header or from a
part): the shelf, player and the precise timeline with its keyboard.
Clicking a shot or an empty space on the timeline shows what can be done to
it, beside it.

Select, then act: nothing asks you to pick a tool first. Every change shows
an Undo right away. Words say what happens ("Remove — the rest moves up",
"Remove — leave empty space"), not editor terms.

## Pipeline

```
drop ─ locate.py      find the files on disk by name + size + mtime
                      (Spotlight, then folder name under ~/Movies etc.);
                      upload into the cache only what can't be found
     ─ indexer.py     process pool, one clip per worker:
                        media.load_index   keyframes, HW decode, one pass
                        shots.detect       shot boundaries
                        bestframe          best frame → thumbnail, quality
     ─ vision.py      on-device Apple Vision over the thumbnails:
                      labels, faces, aesthetics score, feature-print
     ─ storyboard.py  three axes, no LLM:
                        time     sessions split on 45-min gaps / days
                        place    GPS single-linkage, radius chosen adaptively
                        subject  on-camera shots, then k-means on Vision
                                 feature-prints, named by distinctive labels
```

The direction line is read by keyword matching against Vision labels
("food" → food, dessert, restaurant, …). The reply says which words were
used and which were ignored; there is no language model. Matched shots
are highlighted everywhere and lead the subject storyboard.

Index results are cached per file under `~/.cache/vibecut`
(`VIBECUT_CACHE` to override), so dropping the same folder again is instant.
The shelf itself is in memory only: restart the server and it's empty.

## The rough cut: throwing away, with one human gate

Editing is subtractive: most of every clip is thrown away. After indexing,
two stages run on the whole shoot, then everything stops at one gate.

1. **Reject** (`cutgrammar/reject.py`): whole clips nobody would use — lens
   cap / pocket, murky-dark or blurred end to end, shaking throughout, a
   two-second mis-tap, a second take of the same view (kept: the better one).
   Each has a plain reason ("全片模糊", "和 IMG_4471 几乎一样"). Talking
   clips are never dropped as duplicates — they may say different things —
   only flagged as possible retakes.
2. **Trim** (`cutgrammar/trim.py`): the best window inside each kept shot.
   Per-second scores (quality, steadiness, subject in frame, speech) from
   `cutgrammar/signals.py`; exact max-sum sliding window; windows that start
   mid-pan, mid-word or on a subject leaving frame are penalised, the start
   twice as much as the end. Cut points are moved out of words. Talking clips
   only lose unusable ends: without a transcript nothing can know which
   sentences matter.

**The gate** (`web/backend/workflow.py`, adapted from cut-motion — see
NOTICE): the Story view shows "47 个片段 → 保留 31 → 剪出 3:22（原始 11:24）",
every thrown-away clip with its reason, every trim as a bar over the whole
clip. Use it anyway / Throw away / Shorter / Longer / Keep the whole clip,
each undoable. Nothing (storyboards, chat edits) proceeds until you press
"Looks right — continue". New clips after that reopen the gate. Nothing is
deleted: rejects stay on the shelf with their reason and a "Use it" button;
trims are in/out points and the full source stays reachable.

Signals are per second (the index samples keyframes, ~1 s). Subject presence
is spectral-residual saliency plus on-device Vision faces per second.

## The conversation edits; it never regenerates

`board.py` holds the working storyboard as a pure function of a turn log.
Each turn is a list of operations — `move_beat`, `drop_beat`, `drop_shot`,
`swap_shot`, `add_shot`, `move_shot`, `retitle_beat`, `set_pace`,
`open_with`, `end_with`, `choose_option` — applied by deterministic code.

- `llm.py` gives Claude (`claude-opus-5`, JSON-schema-constrained output) a
  text rendering of the storyboard and shelf, and gets back a reply, at most
  one clarifying question with choices, an optional new direction, and
  operations. It never returns a storyboard.
- Timeline drags, deletes and Apply are the same operations, in the same
  log, with the same undo.
- Undo any turn = replay the log without it. Ops that depended on it are
  skipped and reported, never guessed. Decisions made at apply time (which
  shelf shot a swap picked, what a proposal looked like when chosen) are
  recorded into the op, so replay is exact.
- The diff (removed / added / moved / trimmed / renamed) is computed from
  before/after boards, not from what the model claims it did.
- Setting a new direction rebuilds the three *proposals* only; the working
  storyboard is untouched.

`tests/test_board.py` pins this down without a model: the two ops for the
acceptance request change the opening and remove the market, and every
other beat comes out byte-identical.

## Music that fits the storyboard's shape

Under the working storyboard: the top 5 tracks from the creator's own music
folder (set it in that box; mp3/m4a/wav/flac, walked recursively), each with
a play button and a one-line reason built from the curves — or no reason.

`cutgrammar/music.py` does the work, behind a `TrackSource` seam
(`LocalFolderSource` is the only adapter). Each beat gets an energy value
from its shots' motion and cutting rate; each track an RMS energy curve and,
when the pulse is unmistakable, a tempo. Curves are resampled, z-normalised
and correlated over the part of the track that would play (it's assumed to
start with the edit). Tracks shorter than the edit are left out. Features are
cached in `.vibecut-music.json` inside the music folder.

What `tests/test_music.py` shows, and doesn't: rising vs falling separates
by a wide margin (+0.82 vs −0.95), loudness has no effect, and the score is
far above shapeless tracks. But with a 3-beat storyboard the edit's shape is
only a few numbers, so ~1 in 9 random rising curves out-score a clean ramp:
it can tell a build from a fade, not pick the best of many builds.

## A precise timeline without dragging

The timeline is the storyboard laid out in time (`backend/timeline.py`),
with a sorted list of snap targets: shot boundaries (strongest), silence
edges from `features.speech_mask` (10 ms), motion onsets/offsets (only as
precise as the index's keyframes, ±0.5 s — labelled so), and the beat grid
of a music track put under the edit with "Use". Word boundaries have a seam
and no source until there's a transcript.

`src/snap.ts` looks targets up by binary search. The threshold is 8 px, so
in seconds it scales with zoom; each type pulls with its own weight; Alt
disables it. The snapped (or approaching) target is drawn and named.

Keys follow NLE convention — press `?` in the app for the full list:
Space, J/K/L shuttle, I/O marks, ←/→ frame, ⇧ second, ⌥ next target,
↑/↓ cut points, B or ⌘K cut (during playback it lands on the nearest target,
allowing for reaction time), Q/W ripple-trim to the playhead, `,`/`.` trim
by a frame (⇧ second, ⌘ music beat), Delete removes the In–Out range or the
selection and closes up (⌥ leaves a gap), ⌘Z undo. The timecode box takes
`21.3`, `0:21.3` or `00:00:21:09` and never snaps.

Every one of these is an operation in the same turn log as chat edits:
`split`, `trim`, `drop_range`, `drop_shot` — addressed by entry key and
source time, never by timeline position, so undoing an earlier turn can't
make a later cut land somewhere else.

Tests: `npm test` in `web/frontend` (snap + timecode), `tests/test_timeline.py`
(targets), `tests/test_board.py` (cut / trim / ripple / gap / range / undo).

**Measured on the real clips (5½-min edit, 67 targets):** with keys and typed
times, all five test cuts landed where aimed. Scrubbing with the mouse at the
default fit zoom (1 px ≈ 0.4 s) snaps on 50% of scrubs and pulls 21% of them
more than 1 s from where you pointed — that is snapping fighting you. At 5×
zoom it's 19% and never more than 1 s. Not tuned; see the report.

## Measured

30 real iPhone 4K HEVC clips (1.4 GB, 7 min 18 s of footage), cold cache,
M5 MacBook, Chrome driving the real UI:

| Step | Time |
| --- | --- |
| Folder picked → 30 clips indexed and thumbnailed | 4.9 s |
| → three storyboards on screen | 5.2 s |

When Spotlight and the folder search both miss, the files are copied over
localhost instead; the same 30 clips took 6.9 s that way.

## Out of scope

Captions, music, motion graphics, export, rendering, auth, database,
collaboration, automatic style learning. The timeline plays spans of the original files in
sequence; nothing is re-encoded.

## Known limits

- Cut positions inside a clip are keyframe-accurate (±1 s on iPhone).
- The place axis needs GPS; screen recordings and downloads have none, and
  a shoot filmed in one spot has only one place. The card says so.
- The quality score's weights and the storyboard quality floor are guesses,
  same as every cutgrammar threshold. They only decide ranking and what's
  left off a storyboard — nothing is cut out of a file.

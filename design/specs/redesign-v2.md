# VibeCut redesign v2: final spec

*Lead design, 2026-09-25. Written for the round-2 mockups; nothing in it is built yet.*

*This spec starts from the winning design, creator-first (144). It adds the ideas the judges picked out in taste-first (140) and engine-first (126), and fixes every problem they raised. It builds on CLAUDE.md, `design/research/01`–`07`, the round-1 mockup (`design/mockups/index.html`) and the engine as it reads today. **[prior]** marks a guess that has the same status as a `grammar.py` threshold.*

---

## 0. Principles

1. **The promise is "no amateur tells".** No screen says "viral" or "beautiful", and no screen shows a score. The word "trending" appears only when explaining why trending sounds get added inside TikTok or Instagram.
2. **Three taps and one confirmation.** Drop → Format → **Make my video**.
   - The app guesses what the video *is* (its kind), states the guess together with its evidence, and preselects it on the Vibe screen. The vibe and the music are also preselected.
   - Confirming the kind is required, because kinds flip the editing rules (research 06 §5b). It is a confirmation on an existing screen, not an extra step.
3. **Watch first.** Making ends with the finished, graded video playing with sound. No trims, settings or storyboard come before it.
4. **One log.** Every change is a *turn*: a tap, a drag, a swap, a music or vibe switch, or a typed request.
   - A turn is a set of ops on the working storyboard. `board.py` computes the diff (the model never reports it), and each turn gets its own Undo.
   - Changing the kind, the format or the story order is a **Remake**. A Remake creates a new version and keeps the old one.
5. **Only the creator's frames, words and Mac.**
   - No generated frames and no invented words or numbers.
   - No downloads from links, and no frames or audio from a reference video in any export.
   - There are two opt-in network paths: the Ask bar (sends storyboard text to the model) and free-music search (sends mood words).
6. **Structure caps surface.** The kind decides what may happen and how often. The vibe decides only how it looks and sounds. Motion elements have no styling of their own.
7. **Every choice knows where it came from:** VibeCut's starting rules, a video the creator loves, or the creator. "What I did" says which, in plain words.

**Levels of depth**
- **Level 0, Make:** Clips, Format, Vibe, Making, Watch, Export.
- **Level 1, Change:** the editor.
- **Level 2, Fine-tune:** Fine-tune frames, Change style, More vibes, the music-vs-your-sound slider, film bars, and the trait toggles for a video you love.

**Words the UI uses** (a copy lint for every screen):

| Never in the UI | Say instead |
|---|---|
| kind, sub-style, niche, preset, template | "what it is" ("This looks like a quiet day") |
| look, surface, LUT, grade, filter | vibe, colour |
| transition, dissolve, J cut, L cut | join, soft fade, "the sound carries across the cut" |
| B-roll, cutaway, overlay, lower third, kinetic text | shots, moments, words on screen, name tag |
| BPM, LUFS, render, proxy, keyframe, codec | beat, loudness, making, finishing |
| punch-in | zoom-in |
| viral, beautiful, algorithm | (nothing) |

---

## 1. Shell, flow, deep links

**Canvas.** Design at 1440×900, and make sure it still holds at 1280×800. The chrome uses the round-1 warm editorial system (§3); the colour belongs to the video.

**Top bar (60 px, three columns)**
- **Left:** the logo "Vibe*Cut*" (serif 21, "Cut" in `--accent-deep`), then the project name. The name reads "New video" until Making, then shows the title. Once a second version exists it becomes "A day out with Sarah ▾" and opens the Versions menu.
- **Centre:** the stepper.
- **Right:** "● Footage stays on this Mac" (12 px, faint). From Watch on, an **Export** button also appears here (primary, small).

**Stepper:** **Clips · Format · Vibe · Watch · Edit.**
- Making is a moment between Vibe and Watch, not a step.
- Finished steps show ✓ and can be clicked.
- While clips are still being read, the Clips step shows "18/42".
- From Watch or Edit, clicking Format or Vibe opens a popover: "Changing this makes a new version. This one stays in Versions." with **Make a new version** and **Cancel**.

**Mockup files** (in `design/mockups/v2/`)
- `tokens.css` and `looks.css` are shared, and are written first, together.
- `flow.html` is built by builder A. `studio.html` is built by builder B.
- `index.html` is about 20 lines and forwards `?s=<id>&…` to the right file.
- Reuse `design/mockups/assets/` (t00–t41.jpg, hero.png, hero2.png, hero3.png).

**Deep-link parameters**
- `s`: the screen id (table below).
- `state`: one of the screen's states (table below). The default is the first one listed.
- `fmt`: short, long or youtube. Default short.
- `kind`: fast_day, quiet_day, trip, places_guide, talking or story_day. Default fast_day.
- `look`: clean, cozy, quiet, cinematic, film, playful or hype. The default is the kind's ★ in §4.5.
- `tab`: part, words or music (Edit only).
- `history`: open (Edit only).

| id | Screen | `state=` values | File |
|---|---|---|---|
| `clips` | Clips | empty · reading · done · notices · too-few · returning | flow |
| `format` | Format | default · wide-into-upright · upright-into-wide · short-footage · still-reading | flow |
| `vibe` | Vibe | default · low-confidence · still-reading · more · no-music · kind-changed | flow |
| `making` | Making | running · no-music · short-footage · failed-clips · part-ready | flow |
| `watch` | Watch | default · no-findings · left-out-open · what-i-did · finishing · restyling | flow |
| `export` | Export sheet (over Watch) | default · gate-open · ready · exporting · done · error | flow |
| `love` | "A video I love" sheet (over Vibe) | drop · link-pasted · reading · card · guard · too-short · mismatch | flow |
| `edit` | Editor | default · no-key · thinking · couldnt · undo-dependent · preview-track | studio |
| `frames` | Fine-tune frames | default | studio |
| `gallery` | Motion library (design review) | default | studio |

**Sample data** (use it on every screen)
- **Project:** "A day out with Sarah". 42 clips, 8:06 filmed, one day from 8:35 am to 9:40 pm.
- **Places (5):** Home, Campus, Library, Park, Dinner. She talks in 6 of the clips; 9 clips are left out.
- **Guess:** a day, told fast, with the Clean vibe.
- **Short edit:** 0:38 and 16 shots, in five parts: Morning 0:06, Campus 0:08, Library 0:07, Park 0:10, Dinner 0:07.
- **Other lengths:** Long vertical 2:10; YouTube 6:40.
- **Talking to camera:** the round-1 transcript ("A day in New York", 0:31 → 0:20).
- **Tracks:** see §6.

---

## 2. Screens

### S1 · `clips`: Clips (first launch)
| | |
|---|---|
| Purpose | Get every clip in and start reading at once. |
| Layout | A centred column, max 880 px wide, starting 72 px below the top bar, in this order: eyebrow, H1 (52 serif), lede (16), drop zone (240 px tall, dashed 1.5 px `#463e34`, radius 18), notices (13 px, one line each), "Recent" row. The reading panel replaces the drop zone. The Recent row is for returning users only: up to 5 posters at 72×128, each with title and date. |
| Copy | **Eyebrow:** "New video". **H1:** "Drop everything you *filmed.*" **Lede:** "A whole trip is fine — ten clips or three hundred. I read them on this Mac and never change or upload them." **Drop zone:** "Drop a folder or clips here" / ".mov and .mp4 · screen recordings work too" / **Choose a folder** (primary) · **Choose clips** (quiet). **Reading panel:** "Reading 18 of 42 clips…" / "shots · sound · faces · places" / **Pick a format →** (primary, enabled at once) / "Reading carries on while you choose." (faint). **When done:** "All 42 read in 4.9 s". |
| States | **empty** · **reading** · **done** · **returning**: row titled "Pick up where you left off". **notices**, one line each and never a modal: "6 files aren't videos, so I skipped them." · "12 clips are still in iCloud. Download them in Photos, then drop them again." · "IMG_4412 couldn't be read — it's left out." **too-few:** "Only 2 clips. Add a few more for a story." plus **Add more clips**, and **Pick a format** is disabled. Duplicates are merged without a notice (inventory hash). |
| Fake | Clicking the drop zone starts reading. Thumbnails t00–t41 fade in, 45 ms apart, into a 14-column contact sheet of 9:16 tiles, with a 4 px progress bar. The stepper's Clips step counts up. At 42 the panel shows the done line; 700 ms later the mockup moves to `format`, unless the user has already moved on. |
| Engine | `locate` → `indexer` (`load_index`) → `vision` (labels, face boxes) → the SoundAnalysis speech, music and laughter timeline (P7) → `reject`/`trim` (decisions only; they are gated at Export). |

### S2 · `format`: Format
| | |
|---|---|
| Purpose | One decision that sets the frame, the length band, the text rules and the sound exports. |
| Layout | A centred column, max 1080 px wide. Three cards in a row, each 330×380 with 20 px gaps. Each card holds a silhouette at true proportion filled with one of the creator's stills: 9:16 at 132×235, 16:9 at 290×163. Under the silhouette: title (serif 26), line (muted), estimate (serif 20). The suggested card (from clip orientation) has an outline and a "Suggested" chip. Under the row is one option line. |
| Copy | **Eyebrow:** "Step 2". **H1:** "Where will it *live?*" **Lede:** "You filmed 8 min 06 s. I'll use the best of it." **Cards:** **Short** · "For Reels, TikTok and Shorts" · "about 40 s" / **Long vertical** · "An upright vlog" · "about 2 min" / **YouTube** · "Wide 16:9, with chapters" · "about 7 min". **Option line (checkbox):** "Short videos: make it at least 1 minute (for TikTok creator payouts)". |
| States | **default** · **wide-into-upright:** under the vertical cards, "Most of your clips are wide. I'll frame them around people and what's moving, and leave out any that won't fit upright." · **upright-into-wide:** under YouTube, "Most of your clips are upright. YouTube will crop them to the middle — fine for scenery, tight for faces." · **short-footage:** the YouTube estimate reads "Your good footage makes about 6 min" in `--warn` and stays selectable · **still-reading:** estimates show "…" until a fifth of the clips are read. |
| Fake | Hovering a card lifts its border to `#4a4238`. Clicking a card selects it and goes to `vibe` with `fmt` set. There is no Next button. |
| Engine | The Format record (§4.7) sets the length band, text box, text floors, card density, default words and sound exports. |

### S3 · `vibe`: What it is, and the vibe
| | |
|---|---|
| Purpose | Confirm the kind (required, preselected) and pick the vibe, on one screen. |
| Layout | A centred column, max 1160 px, 40 px below the top bar. **What-it-is block:** the sentence (serif 30), the evidence line (13, muted), then a row of chips (32 px tall; the selected one is raised, with an accent ring and ✓). Then 32 px of space. **Vibe block:** "Pick a vibe." (serif 30) with a subline. **Card row, Short or Long vertical:** 3 cards 240 px wide (preview 200×356, radius 12) plus a dashed tile 200 px wide. **Card row, YouTube:** 3 cards 340 px wide (preview 300×169) plus a dashed tile 240 px wide. Gaps are 20 px. Under each preview: name (serif 22), line (13, muted), music line (12, faint). **More vibes** opens a second row at 80% scale. A sticky bottom bar (72 px) holds the summary on the left and **Make my video** on the right (large button). |
| Copy | **Sentence:** "This looks like **a day, told fast**." **Evidence:** "42 clips · 13 hours · 5 places · you talk in 6 of them". **Chips** (only kinds valid for the chosen format; the guess first with ✓): "A day, told fast" · "A quiet day" · "A trip, place by place" · "A story over your day" · "Something else ▾" (opens the rest: "Places worth saving", "You, talking to camera"). **Heading:** "Pick a vibe." **Subline:** "Everything follows it: colour, words, joins, movement and music." **Cards:** the name and line from §4.3; music line "♪ Slow Sunday · from your music". **Dashed tile:** "Like a video I love…" / "Drop a file — I'll learn its pace and colour". **Link:** "More vibes (2)". Cards in the extra row carry the tag "Toned down for a day, told fast". **Bottom bar:** "Short · about 0:40 · A day, told fast · Clean" with **Make my video**. |
| States | **default** · **low-confidence:** the sentence reads "I can't tell what this is yet. Which is closest?", no chip is selected, the cards show "Pick what it is first" over a blank frame, and **Make my video** is disabled. · **still-reading:** the evidence line reads "Still reading 18 clips — my guess may change", and the button reads "Make my video · starts when reading finishes" (enabled; it queues). · **kind-changed:** after another chip is tapped, the cards cross-fade (250 ms) to that kind's ★ and ● vibes, and the ★ is selected. · **more:** the ○ row is open. · **no-music:** music lines read "♪ Your own sound — add music any time". |
| Preview | Each card loops for 6 s: three stills (the hook shot plus the two best), 2 s each, joined with the vibe's join, with the vibe's hook line or place stamp animating on its motion tokens and its texture on top. In the product the stills are graded on the server (`grade.Look` plus `apply_lut`, as `reference.fit_look` does), so each card shows real colour on the creator's own footage, and the selected card plays 6 s of the top track from its lift. In the mockup, use the CSS filter from `looks.css`. |
| Fake | Tapping a chip re-ranks the cards. Tapping a card selects it. The dashed tile opens `love`. **Make my video** goes to `making`. |
| Engine | `vibes.guess()` (§4.2), the kind records, the look records, `grade.Look`, `overlayDraw` with the look's tokens, and `music.match` over the look's palette. |

### S4 · `making`: Making (the "boom")
| | |
|---|---|
| Purpose | Turn the wait into anticipation, and build trust by showing the video being made from the creator's own moments. |
| Layout | Full stage on `--stage`. A centred group: the output frame (9:16 at 315×560, or 16:9 at 720×405), a 64 px gap, then a checklist column 380 px wide. Under the frame is a 56 px filmstrip where the picked shots arrive. |
| Copy | **Heading:** "Making your video." (serif 34). **Time line:** "About a minute." (Long vertical: "About 2 minutes." YouTube: "Part 1 in about a minute — the rest while you watch."). **Stop** is a ghost button at the top right of the column. **Checklist** (each line is an 18 px circle that turns into an `--accent-deep` ✓; the current line has a spinner): "Read 42 clips, found 412 moments" → "Left out 9 blurry or shaky clips — you'll see them before anything leaves" → "Picked the best 16" → "Put them in order: morning, campus, library, park, dinner" → "Opening on the fountain — your clearest moving moment" → "Found music that builds with your day" → "Timed the cuts" → "Added words: times and places from your clips" → "Colour, joins and finishing touches · 12 of 16 shots" → "Checked for jumps in brightness and loudness". |
| End | The frame fills with the finished first shot, then everything cross-fades (600 ms, `--ease`) into `watch`, which autoplays with sound. |
| States | **running** · **no-music:** line 6 reads "No music on this Mac yet, so I used your own sound. Add music any time." · **short-footage:** a line reads "Your good footage makes 31 s, not 40. I kept it at 31." · **failed-clips:** "3 clips wouldn't open. Made it without them." · **part-ready** (long formats): the last line reads "Part 1 of 5 ready — watch while I finish the rest", with **Watch now** (primary). |
| Fake | The lines tick about 0.9 s apart. Filmstrip thumbnails slide in from 60 px to the right, 120 ms apart. **Stop** returns to `vibe` and saves nothing. |
| Engine | `remix.make()` with a resolved vibe record in `remix.fingerprint()` shape (P1): `select.choose` → `plan_shots` → music pick → `overlays.suggest` → a 720p proxy from `export.py` (P4: shot cache, 3 shots in parallel; long formats render part by part) → `grammar.analyze` + `overlays.check` on the proxy. The `remix.Job` stages drive the checklist, and `Pick.why` supplies the hook line. |

### S5 · `watch`: Watch
| | |
|---|---|
| Purpose | The payoff: watch it the way a viewer would, then decide. |
| Layout | A single stage with no rails. The video is centred: 9:16 at 338×600, or 16:9 at 880×495. Under it are the transport (play button, scrub bar with part blocks, time; the width of the video, at least 520 px), then a block holding the title, a quiet line, the chips and the buttons. A column 200 px wide sits 32 px to the right of the video, vertically centred: "Another vibe", then two graded thumbnails (96×170) with their names, then the link "Like a video I love…". |
| Copy | **Title:** "A day out with Sarah" (serif 30; click to rename in place). **Quiet line** (13, muted): "0:38 · 16 shots · 'Slow Sunday' under your own sound · A day, told fast · Clean". **Chips:** "Left out 9 clips · Check" · "1 thing to check · Show me" · "What I did". **Buttons:** **Export** (primary) · **Change something** (quiet). **After one full play:** the last frame holds with "▶ Watch again". |
| What I did | Opens under the chips, up to 7 lines, measured facts only: "Opened on the fountain — your clearest moment, held 1.4 s" / "Cut on movement at 14 of 15 cuts" / "One colour across 3 cameras" / "Words kept clear of faces and the app's buttons" / "Used 1 of 2 zoom-ins · 0 special joins and 0 sound effects — Clean keeps it plain" / "Not checked: whether voices carry across cuts — music covers them" / "Pace and colour come from VibeCut's starting rules for a fast day — not yet tuned on real videos". |
| Left out | A popover titled "Left out 9 clips", with the subline "Nothing is deleted. Put any back with one tap." It shows a 3×3 grid of 96×170 thumbnails, each with its reason and **Use it**. The reasons are: "Blurry the whole way through" (×3), "Same view as a sharper clip" (×3), "Shaking throughout · judged from a few frames" (×2), "Under a second long" (×1). |
| 1 thing to check | Jumps to 0:01 and draws a dashed box around the words and the face: "The title covers Sarah's face for 1.2 s", with **Move the title** · **Leave it**. |
| States | **default** · **no-findings:** no "1 thing" chip · **left-out-open** · **what-i-did** · **finishing** (long formats): a 36 px banner above the video reads "Still finishing parts 3–5 · about 4 min. What's ready plays now." Parts that aren't ready are hatched on the scrub bar. When playback reaches one, a card appears over the video: "Part 3 is still being made · about 40 s". · **restyling:** a pill at the top left of the video reads "Updating colour and words · about 10 s", with a thin progress bar. The old version keeps playing, then cross-fades to the new one (250 ms). |
| Fake | Tapping an "Another vibe" thumbnail swaps the CSS filter and type classes, runs the **restyling** state for 2 s, and shows the toast "Now Film. Your cuts are kept. · Undo". **Move the title** moves the title to the top band, with the toast "Moved the title above Sarah · Undo". **Export** opens `export`. **Change something** goes to `edit`. |
| Engine | The player plays the proxy. Another vibe is the `apply_surface` op (P3), which keeps the cuts. After P4 moves the colour to the finish pass, only the finish pass re-runs. Findings come from `grammar.analyze` + `overlays.check`, with `evidence.py` supplying the "not checked" items. The spend comes from the Recipe's effect budget. |

### S6 · `edit`: the editor (storyboard)
| | |
|---|---|
| Purpose | Small changes: cuts, words and music. Select something, then act. No editor to learn. |
| Layout | A grid. **Columns:** parts rail 280 px, stage (flexible), panel 360 px. **Rows in the centre column:** stage (flexible) · story strip 88 px · history line 32 px · Ask bar 48 px (8 px bottom margin). **Stage:** the video, 9:16 with height min(stage − 76 px, 600 px), plus the transport. At the top left of the stage is the vibe pill; at the top right is **Fine-tune frames ↗**. **Story strip:** proportional part blocks in `--part-1…6`, a thumbnail film of the shots, word marks (small "Aa" ticks above) and the playhead. **YouTube format:** the rail is hidden, a **Parts** button at the top left of the stage opens it as an overlay, and the video is 16:9 at a width of min(stage − 48 px, 900 px). |
| Parts rail | **Header:** "Parts" (11.5 caps, faint) and the link "Tell it another way ▾". The menu offers "In time order (now)" · "Place by place" · "By what's in it", each with the note "Makes a new version; this one stays in Versions." **Each part row:** name (serif 18), length on the right, six shot thumbnails at 30×53, and a words line (12, `--accent-deep`, e.g. "Aa Clock · Place"). The selected row is raised; a ⋮⋮ drag handle shows on hover. **Foot of the rail:** "+ Add a part from unused clips". |
| Vibe pill | "A day, told fast · Clean ▾". The menu offers: "Another vibe ›" (lists the ★, ● and ○ vibes) · "Change what it is… (makes a new version)" · "Like a video I love…". |
| Panel, Part tab | **Name:** serif 24, edited in place, e.g. "Morning". **Subline:** "3 shots · 0:06 · 8:35–9:01 am". **Shots:** a grid of 4 columns (78×139). Tapping a shot opens a popover with **▶ Watch** · **Swap** · **Remove**. **Swap** lists 6 "Other moments from here", each with **Use this**. **Pace:** a slider from "Let it breathe" to "Punchier" with 5 stops. **Opens on:** a segmented control, "Best moment · As filmed". **Moments** appears only when the kind allows one: a proposal such as "Freeze on Sarah, with her name · **Add**" and a counter "0 of 1 used". **Buttons:** **▶ Watch this part** · **Remove part** (ghost, danger). |
| Panel, Words tab | **Heading:** "Words on screen" with **✦ Suggest words** (primary, small). **Subline:** "Style from your vibe: Clean · *Change style*". Change style is Level 2 and offers the vibe's 2 fonts, its 3 colours, size S/M/L, and "Low / Middle" for position. **Captions:** a dropdown whose options depend on kind and format: None · Clock times · Diary lines · What you said · Subtitle file (YouTube only). **Scope:** a segmented control, "This part · Whole video". **List** (one row per piece of text): glyph (T title, ◷ clock, ⌖ place, § part, ¶ line), the text in bold, and "Clock · 0:02–0:04". A failed check adds a warning line: "▲ Covers a face for 1.2 s" or "▲ Too quick to read — 1.1 s for 9 words". Clicking a row edits it in place and moves the playhead; × appears on hover. A place with no name reads "⌖ Name this place". **Foot:** "+ Add words here". Suggest words only uses dates, clock times, places (GPS looked up offline) and names the creator gave. |
| Panel, Music tab | See §6. |
| History and Ask | See §7. **Ask placeholder:** `Ask for a change: "open on the sunset", "less text", "make it shorter"`. |
| States | **default** · **no-key:** the Ask bar reads "Typing changes needs an AI key · Set up" and is disabled; everything else still works · **thinking:** "Working on it…" with a spinner · **couldnt:** a history entry reads "I couldn't turn that into a change. Nothing changed." with two chips, "Make the opening shorter" and "Remove the words in Park" · **undo-dependent:** the toast "Undone. I also skipped 'end on the sunset shot', which depended on it." · **preview-track:** see §6. |
| Fake | Clicking a part fills the Part tab. Clicking a word mark or on-screen text opens the Words tab with that row selected. Dragging a part swaps it in the list and adds the history entry "You moved Library before Campus" plus a toast with Undo. Pressing Enter in the Ask bar adds a history entry with the diff "Morning: 0:06 → 0:04 · 1 shot trimmed". ⌘Z undoes the latest turn. |
| Engine | `board.py` ops (`move_beat`, `swap_shot`, `drop_shot`, `set_pace`, `open_with`, `retitle_beat`, overlay ops), plus new `add_moment`, `set_music` and `apply_surface` (P3). `llm.py` emits ops only. `storyboard.by_time`, `by_place` and `by_subject` handle "Tell it another way". |

### S7 · `frames`: Fine-tune frames (Level 2)
| | |
|---|---|
| Layout | Same as Edit, except the story strip, history line and Ask bar are replaced by a 240 px timeline. From the top: a 24 px ruler; the **Picture** track (72 px, shot thumbnails and names); the **Words** track (32 px); the **Music** track (48 px, waveform with beat ticks). Between shots, the joins are labelled in plain words ("cut", "soft fade", "leak"). Snap ticks mark cuts, beats and movement. |
| Copy | **Back to story** (quiet) at the top right of the stage. **Panel:** "IMG_4420 · 2.4 s · from 0:12.3 in the clip" / **Split here (S)** · **Trim start to here** · **Trim end to here** · **Remove** / "Join into this shot: Straight cut ▾" (only this vibe's joins) / faint note: "Snaps to cuts, beats and movement · hold ⌥ to move freely". |
| Fake | Clicking a shot selects it. Dragging the playhead snaps to the nearest tick within 8 px. |
| Engine | The `split`, `trim` and `drop_range` ops; `timeline.py`; `snap.ts`. |

### S8 · `export`: Export sheet
| | |
|---|---|
| Layout | A sheet 800×560 over a scrim (`--r-xl`). On the left, a 260 px poster. On the right, the body with 28 px padding: eyebrow, title (serif 34), format line, sections, then the buttons pinned to the bottom. |
| Copy | **Eyebrow:** "Export". **Title:** "A day out with Sarah". **Format line:** "Upright 1080 × 1920 · 0:38 · for TikTok, Reels and Shorts" (YouTube: "Wide 1920 × 1080 · 6:40 · for YouTube"). **Sound:** "With music · Without music — I'll add a sound in the app · Both". The default is Both for Short and With music otherwise. When the no-music file is chosen: "Trending sounds can only be added inside TikTok and Instagram. I'll save the cut times next to the video so you can line one up." **Words (YouTube only):** "On the video · As a subtitle file" (default: subtitle file), plus "Chapters: I'll copy them for your description" (shown when there are at least 3 parts of at least 10 s). **Before you export** (gate): "9 clips were left out and nobody has looked at them yet. **Look**" · "The title covers Sarah's face for 1.2 s · Show me" (doesn't block) · "Some shots show a child in a bedroom or at a pool. Check before posting · Show me" (only when the labels suggest it; doesn't block) · ☐ "This video is paid, gifted or has affiliate links — add a note on screen" · "Place info is removed from the file" (on; toggle "Keep it") · "This track needs a credit. I'll copy it for your caption." **Buttons:** **Not yet** (ghost) · **Export video**, or **Export 2 videos** when Both is chosen. |
| Gate | Expanding **Look** shows the 9 left-out clips (64×114 thumbnails with reasons), each with **Use it** and **Keep out**. Once the list is open, **They're fine left out** answers them all. Every answer gets a ✓. While any left-out clip, cut in what was said, or "judged from a few frames" reject is unanswered, the export button is disabled and the helper line above it reads "Look at the left-out clips first — nothing leaves without a look." |
| States | **default** · **gate-open** · **ready** · **exporting:** progress bar plus "Exporting… about 40 s left · keep this window open — the words are drawn here" · **done:** "Saved to Movies › VibeCut", files listed ("A day out with Sarah.mp4 · A day out with Sarah (no music).mp4 · cut times.txt"), with **Show in Finder** · **Copy music credit** · **Copy chapters** (YouTube). After a no-music export: "In TikTok: tap Add sound, then turn your original sound down to taste." · **error:** "Not enough space on this Mac — needs 1.2 GB." / "Export stopped at 0:21 · Try again" / "One effect failed on shot 7 · Export without it". |
| Fake | Clicking Look expands the list. Answering items enables the export button. Export runs a 3 s progress bar, then shows the done state. |
| Engine | `export.py` gets a music-less variant (own sound at full level, no ducking), writers for SRT, chapters, `cut times.txt` and `credits.txt`, and compliance (P17). Both files come from one render, because the shots are shared. |

### S9 · `love`: "Learn from a video I love" sheet
| | |
|---|---|
| Layout | A sheet 720 px wide, up to 780 px tall, with a scrolling body. Its states replace each other in place. |
| drop | **H2:** "Drop a video you love." **Subline:** "A file on this Mac — one you made, have the rights to, or saved with the app's own save button." A 200 px drop zone. There is no link field. **Required, after the drop:** "Where's it from?" with three chips: "I made it" · "I have the rights" · "Saved for my own reference". **Read it** stays disabled until one is picked. |
| link-pasted | An inline line: "I don't open links. Save the video with the app's own save button, then drop the file here." |
| reading | "Reading its rhythm… only numbers are kept. The file is deleted afterwards." Progress bar. It reads at most the first 10 minutes. |
| card | **Header:** "Closest to **a quiet day** · Cozy". **One row per trait:** toggle, name, value in plain words, and a small visual. The rows are: Pace "Shots about 2.8 s, slowing near the end" · Where cuts land "After movement settles" · Beat "Doesn't cut on the beat" · Joins "Soft fades at 3 of 24 joins" · Colour "Warm, soft blacks", with a before/after on the creator's frame and "Subtle · Full" · Words "Small lowercase lines, low on screen" (position, size and case only; never its words) · Sound ✗ "Its music is never copied. 3 of your tracks feel the same." A trait the file can't support shows in grey as "not checked". **Footer** (faint): "The file is deleted after reading. 41 numbers stay on this Mac." **Buttons:** **Make mine like this** (primary) · **Cancel**. |
| guard | This row appears in `--warn` whenever copying a trait would break a guard: "It flashes on 40% of joins. A quiet day allows none." with **Copy anyway** · **Leave out**. |
| too-short / mismatch | "Too short to learn a rhythm from." · "No cuts to learn pace from — colour and words still work." · "I can't read this file." · "This one is built around talking and your clips aren't. I'll borrow its colour and pace only." |
| After | On Vibe, the result becomes a card titled "Like beach_day.mp4" with a small "learned" tag. The second time it is used, it offers **Save as my style** (a confirmed long-term preference). **Forget it** deletes the numbers. v1 takes one reference per project. |
| Engine | `reference.start` accepts files only (P2). Then `style.learn`, plus SoundAnalysis and caption OCR (P16; the Words row reads "not checked" until P16 lands), `reference.card`, `fit_look`, `make_op` → `restyle.apply`, and `preferences.py`. |

### S10 · Talking to camera (`kind=talking` on S3–S8)
| Screen | What changes |
|---|---|
| vibe | **Sentence:** "This looks like **you, talking to camera**." **Evidence:** "7 clips · 6 min of talking · one place". An inline row under the chips: "Spoken in **English ▾**" (English · Chinese; the UI stays English) · "Have a script? *Add it*" (optional; opens a text box). **Vibes:** Clean ★ (white, mixed case, soft shadow, no box), Quiet ●, Cozy ●, and Playful ○. Hype is never offered for talking. |
| making | Adds "Listening to what you said, on this Mac… 3 of 7 clips" (the first time: "Getting the English speech model — one time") · "Cut 14 pauses, 2 retakes, 3 stumbles" · "Kept your ums where you weren't reading a script". |
| watch | **Quiet line:** "0:31 → 0:20 · 8 pauses shortened · 1 retake · 2 stumbles". **Chip:** "Cuts in what you said · Check", which opens Edit on the Words tab. |
| edit, Words tab | Renamed **What you said**. Transcript paragraphs (serif 20, line-height 1.7) with timestamps. Cut words are struck through and carry a reason tag ("pause 1.8 s → 0.3 s", "said again", "stumble", "filler"); tap one to bring it back. **Chips:** "14 pauses · 2 retakes · 3 stumbles · 4 fillers" (tapping one toggles that whole kind). **Ums and ahs:** "Keep · Cut stumbles only · Cut all"; the default comes from the take type (scripted takes cut all). Hovering a sentence shows "Cover with a shot". **Captions:** "Word groups" (Short), "Sentences" (long formats), "Subtitle file" (YouTube). |
| edit, Part tab | Parts are groups of sentences. "Zoom-ins: 3 (up to 4 a minute)". The opening greeting is proposed as a cut: "Starts with 'Hi everyone' · Cut it". |
| export | The gate adds "2 cuts in what you said haven't been checked · **Look**". |
| rules | Never speed up speech. Never shorten a pause that is followed by laughter. Captions sit at chest height (the caption's centre at 0.55–0.66 of the frame height). The video ends on the payoff, with no follow or subscribe outro. Music is off by default; choosing "Under your voice" ducks it 18–25 dB. Zoom-ins are anchored on the face box and alternate 100% and 110% at idea changes. |
| states | "On this Mac I can't read speech yet (it needs macOS 26), so I'll keep your talking whole and only cut between clips." · "I couldn't hear talking in these clips. Try 'A day, told fast' or 'A quiet day'?" · "3 lines from your script weren't said · Show". |
| Engine | `speech.py` (en-US, zh-CN), `talk.build`, `talk.toggle`, `talk.caption_overlays`, `voiceover.py` (script), and `export._duck_expr`. |

### S11 · `gallery`: the motion library (design review only; not in the product)
| | |
|---|---|
| Layout | The top bar reads "Motion library v1 · design review" (serif 21), followed by controls: chips for the 7 vibes · a "9:16 · 16:9" segmented control · a **Beat** toggle · **Play all**. Below is a grid of 20 tiles in 4 columns: each tile is a frame (216×384, or 384×216 for 16:9), then the name (serif 16), the family (11 px caps, faint), a status chip (exists / extend / new / engine work), and a 2-line "used when" (12 px, muted). |
| Behaviour | Each tile loops every 4 s (Cozy's leak drift loops every 13 s). Switching the vibe restyles every tile using §4.4 and §5c. **Beat on** means 100 BPM (a beat every 600 ms): a dot pulses on each beat, and hit frames snap to beats following the §5 rule. Clicking a tile enlarges it to 560 px tall, with a keyframe ruler underneath (ticks from 0 to 4000 ms, each keyframe labelled). |

---

## 3. Design tokens

**Reuse unchanged from `design/mockups/index.html`:**
- Colours: `--bg #13110e`, `--surface #1a1714`, `--raised #221e1a`, `--hover #2a251f`, `--line #322c25`, `--line-soft #28231e`, `--text #efe8dd`, `--muted #a59b8d`, `--faint #72695d`, `--accent #c9dcc1`, `--accent-ink #18221a`, `--accent-deep #93b088`, `--accent-glow #c9dcc11f`, `--warn #e9c78f`, `--danger #e59c8f`.
- Type and radius: `--serif` EB Garamond, `--sans` SF / Inter, `--r 12px`, `--r-lg 18px`.
- Components: the button family (primary / quiet / ghost, sizes 36 and 28), `.chip`, the stepper styles, the tabs, the segmented control, the slider, the toast.

**Additions:**

| Token | Value | Use |
|---|---|---|
| `--stage` | `#0c0b09` | behind the video on Making and Watch |
| `--r-xl` | 22px | sheets |
| `--shadow-video` / `--shadow-sheet` | `0 30px 80px #0008` / `0 40px 120px #000a` | video frame / sheets |
| `--scrim` | `#0009` + `backdrop-filter: blur(6px)` | behind sheets |
| `--ease` | `cubic-bezier(0.16,1,0.3,1)` | all chrome motion (the expo-out curve measured in research 07) |
| `--dur-1` / `--dur-2` / `--dur-3` | 150 / 250 / 600 ms | hover / panels, drawer, cross-fades / the Making → Watch cross-fade |
| `.btn-lg` | height 44, padding 0 22, font 15 | Make my video, Export video |
| Type scale | serif 52 / 34 / 30 / 26 / 22 / 18; sans 16 / 14 / 12.5 / 11.5 (eyebrow in caps, +.16em) | display / sheet titles / sentences / cards / panels / rows |
| `--part-1…6` | `#c9dcc1 #e8c39e #a7c4a0 #d9b8c4 #b9c7d9 #e0d3a8`, text `--accent-ink` | part blocks in the strip, scrub bar and music waveform |
| `--ok` | `var(--accent-deep)` | ticks, answered gate items |
| `--focus` | `0 0 0 3px var(--accent-glow)` + 1px `--accent-deep` | keyboard focus |
| Layout | `--top 60` · `--rail 280` · `--panel 360` · `--strip 88` · `--hist 32` · `--ask 48` | editor grid |
| Hatched | `repeating-linear-gradient(45deg,#1f1b17 0 5px,#2a251f 5px 10px)` | parts not ready yet |

**Vibe fonts** (OFL, bundled in the product). In mockups, load them from `@fontsource` if installed, otherwise fall back:
- Inter → -apple-system
- Caveat → "Bradley Hand", "Marker Felt", cursive
- Courier Prime → "Courier New", monospace
- Poppins → "Avenir Next Rounded", "Arial Rounded MT Bold", sans-serif
- Anton → Impact, "Arial Narrow", sans-serif
- DSEG7 Classic → Menlo, with amber colour
- EB Garamond is already loaded.

`looks.css` defines one class per vibe (`.look-clean` and so on). Each class sets:
- `--look-filter` (the stills' stand-in for the colour);
- `--m-curve`, `--m-dur`, `--m-steps`, `--m-stagger`, `--m-hold` (§4.4);
- `--w-1`, `--w-2`, `--w-3` (the words palette);
- `--f-display` and `--f-text`.

---

## 4. The vibe system

A video comes from **kind (structure) × look (the "vibe" in the UI) × format**. Structure lasts and surface dates (research 06 §4), so each is its own dated record:

```
Kind      id, chip, sentence, guess, spine, hook, cut_point, sound, beat,
          pace {median_s, p10, p90, curve[5], hook_s}         # remix.fingerprint() shape
          formats {short|long|youtube: {length[lo,hi], words}}, budget, guards,
          looks {default, cards[], more[]}, status prior|calibrated(n, date), first_seen, review_by
Look      id, name, line, grade {target: grade.stats, strength_max}, type {display, text, case, backing, palette[3]},
          motion {curve, dur_ms, step_fps, overshoot, stagger_ms, min_hold_s, max_on_screen},
          joins {family[], fallback}, camera, texture {v, h}, sfx[], music {words, tempo[lo,hi], arc},
          appetite {stylised_per_30s, zoom, sfx}, review_by
Format    id, size, length, text_box, rail_notch, text_min_px, cards_per_min, chapter_device,
          words_default, sound_exports, end_rule, allow {grain, bars}
Reference fingerprint (style.learn), nearest_kind, nearest_look, traits {on|off|not_checked},
          provenance made|rights|reference, created
Recipe  = resolve(kind, look, format, reference?, turns)     # every field carries its source: prior | learned:<file> | you
```

**Resolution order**
1. The kind's prior.
2. The look fills in the surface fields.
3. Any reference traits the creator left ticked replace their fields.
4. **Budget:** each effect is capped at min(the kind's budget, the look's appetite).
5. **Guards clamp the result.** A guard that clamps something says so in "What I did":
   - no hue shift on skin, food, foliage or sea;
   - slow motion only from sources of 60 fps or more, and at 0.5× or faster;
   - Film's flash only on real flash or night clips;
   - never bars on 9:16.
6. **Format clamps it again:** text box, text floors, length band, card density, and grain on 16:9 only.
7. The creator's turns replay last and win over steps 1–6.
8. **Compliance wins over everything, and no one can override it:**
   - at most 3 flashes a second;
   - no generated frames;
   - words only from metadata or from the creator;
   - credits are written;
   - a disclosure note when the video is marked paid, gifted or affiliate;
   - a child-privacy warning;
   - location stripped by default.

### 4.1 v1 kinds (structure)
| id | Chip / sentence | Spine | Hook | Cut point | Sound lead | Music beat | Pace [prior] | Status |
|---|---|---|---|---|---|---|---|---|
| `fast_day` | "A day, told fast" / "a day, told fast" | time (capture time, time-zone corrected) | the payoff shot, 1.0–1.5 s, plus a clock kicker | on the action | music; own sound at 12% | **free**: cuts follow the picture (the 4 measured DIML references don't cut on the grid) | 0.7 s (0.4–1.4); the references run 0.65–0.83 | calibrate first |
| `quiet_day` | "A quiet day" / "a quiet day, no talking" | time or process | none, or clock time | 0.5 s after the movement settles | own sound; music at −18 dB or off; everyday sounds never ducked | free | 2.5 s (1.5–4.5) | calibrate first |
| `trip` | "A trip, place by place" / "a trip, place by place" | place (GPS clusters), in time order within each place | the most distinctive *moving* shot, **never a slow establishing wide**; still wides move to shots 2–4, under the place stamp | on the action, matched on brightness and colour | music; the place's own sound breaks through 1–2 times a minute | parts change on the bar; cuts land on beats only inside the drop (≤ 8 bars) | 1.2 s (0.5–2.5), quickening to a peak at 70–80% | prior |
| `places_guide` | "Places worth saving" / "places worth saving" | numbered places (3–7 clusters) | a premise line built from metadata, "5 places in Lisbon" (editable) | on the action | music | parts on the bar | 1.0 s (0.6–2.0) | prior |
| `talking` | "You, talking to camera" / same | speech | the first real sentence by 2.5 s; a greeting is proposed as a cut | at a pause, keeping a breath | dry voice; no music by default | free | per sentence | calibrate first |
| `story_day` | "A story over your day" / "a story told over your day" | the voice plus shots over it; parts by time | the best moment within 5–12 s, then the first line | at a pause; shots over the voice every 2–5 s | voice; music ducked 18–25 dB | parts on the bar | 3 s while talking, 1.5 s in montage | prior |

**Formats, lengths and default words for each kind.** ★ marks the natural format; – means the kind isn't offered in that format.

| Kind | Short | Long vertical | YouTube |
|---|---|---|---|
| fast_day | ★ 25–45 s · clock stamps + hook line | ● 1–2 min · clock stamps | – |
| quiet_day | ● 30–60 s · diary lines | ★ 1–3 min · diary lines | ● 8–15 min · part titles + subtitle file |
| trip | ★ 30–60 s · place stamps | ● 1–3 min · place stamps + part titles | ● 8–15 min · place stamps + chapters |
| places_guide | ★ 20–45 s · numbered places + recap | ● 1–2 min · same | ○ 8–12 min · same + chapters |
| talking | ★ 30–60 s · word groups | ● 1–3 min · sentences | ● as long as it's said · subtitle file |
| story_day | ○ 45–90 s · sentences | ★ 1–5 min · sentences | ★ 8–15 min · subtitle file + chapters |

### 4.2 The guess (rules, not a model; thresholds [prior])
| Order | Signals | First guess, second guess |
|---|---|---|
| 1 | speech ≥ 50% of the runtime (SoundAnalysis, P7) **and** a face in ≥ 50% of shots | talking, then story_day |
| 2 | speech 15–50% **and** ≥ 10 clips with no talking | story_day, then talking |
| 3 | 3–7 GPS clusters within one city, ≥ 2 clips each, mostly café, food or shop labels | places_guide, then trip |
| 4 | span ≥ 2 days, **or** ≥ 3 GPS clusters ≥ 1 km apart | trip, then places_guide |
| 5 | one day, low motion, ≥ 30% hands, food or household labels | quiet_day, then fast_day |
| 6 | one day, anything else | fast_day, then quiet_day |

- **Confidence is low** when the top two scores are within 15% of each other, or fewer than half the clips have been read. Then no chip is preselected (`low-confidence`).
- **Evidence template:** "{n} clips · {h} hours · {p} places · you talk in {k} of them".
- **Only kinds valid for the chosen format** are offered.

### 4.3 v1 looks (the vibes): type and colour
| Vibe | Card line (UI) | Fonts (display / text) | Words style | Colour | Mockup stand-in (`--look-filter`) | Words palette |
|---|---|---|---|---|---|---|
| **Clean** | "Crisp and simple, nothing extra." | Inter 600 / Inter 500 | sentence case, white, soft shadow; a 60% black box only when the background is bright | as filmed, with white balance evened across cameras | `none` | `#FFFFFF #F2C14E #B9D9EB` |
| **Cozy** | "Warm and soft, your own sounds up front." | Caveat 600 / EB Garamond italic | lowercase, cream, no box | warm, lifted blacks, a little less colour | `sepia(.14) saturate(.9) contrast(.9) brightness(1.04)` | `#F6EBD9 #F3C9A5 #C9DCC1` |
| **Quiet** | "Still and spare, lots of air." | EB Garamond italic / Inter 300 caps (+.2em) | small, one line, lots of space | muted cream and taupe, low contrast | `saturate(.72) contrast(.86) brightness(1.05) sepia(.08)` | `#EFE8DD #D8CBB6 #FFFFFF` |
| **Cinematic** | "Slow and wide, like a film." | Inter 300 caps (+.3em) / EB Garamond | small, sentence case, lower third | soft contrast, gentle warm highlights; never shifts skin, food, foliage or sea | `contrast(.94) saturate(.9) brightness(.97)` | `#FFFFFF #E9D8B8 #BFD0DA` |
| **Film** | "An old camera: light leaks and real dates." | Courier Prime / DSEG7 (the date only) | typewriter lowercase; amber date | faded blacks, warm reds, soft glow | `contrast(.88) saturate(.85) sepia(.22) brightness(1.03)` | `#F5EEDC #FF9A3C #E8D5A8` |
| **Playful** | "Bright and bouncy, a little silly." | Poppins 700 / Poppins 600 | rounded, coloured boxes, sticker tags | bright and saturated; skin kept natural | `saturate(1.3) brightness(1.05) contrast(1.02)` | `#FFD84D #FF6FA8 #7BD3F7` |
| **Hype** | "Fast and loud, hits on the drop." | Anton / Inter 700 | condensed caps, white, **one** emphasis (the current word lifts); no stroke, no yellow keyword, no emoji | high contrast, deep blacks; skin kept natural | `contrast(1.18) saturate(1.12) brightness(.96)` | `#FFFFFF #FF6A3D #E8FF5A` |

- **Product colour:** each look is one LUT from `grade.Look`, applied after HLG → SDR conversion and bounded by `MAX_SHIFT` and `SAT_RANGE`.
- **Review date:** every look has `review_by: 2027-03-31`; every kind has `review_by: 2027-09-30`.

### 4.4 Looks: motion, joins, sound, music
| Vibe | Entrance | Stagger | Overshoot | Min hold · max on screen | Joins (with spare footage → without) | Camera | Texture 9:16 / 16:9 | Sounds (CC0, 18 dB under voice) | Music (UI words · internal tempo) | Appetite: special joins / zoom-ins / sounds |
|---|---|---|---|---|---|---|---|---|---|---|
| Clean | quint-out `cubic-bezier(0.22,1,0.36,1)`, 800 ms [prior] | 160 ms | 0 | 2.0 s · 1 | cuts; dip to black at day changes (long formats) | slow push to 1.04 on held shots | none / none | none | "calm piano and soft electronic" · 90–110 | 0 / low / 0 |
| Cozy | the measured paper-card path: expo-out `(0.16,1,0.3,1)`, 1150 ms, **stepped at 12 fps** (`steps(14)`); rise 26 px, rotate +5°→−2°, scale .88→1 | 150 ms | **0** (measured) | 2.0 s · 2 | soft fade 8 f at part changes → warm leak; cream dip at day changes | slow push to 1.05, 4–5 s | vignette + warm leak / same (no grain) | paper rustle, pencil, wood knock (≤ 3) | "lo-fi and acoustic, warm and even" · 70–90 | leak ≤ 1 per 30 s / 0 / 3 |
| Quiet | in-out `(0.45,0,0.55,1)`, 1200 ms [prior] | 240 ms | 0 | 3.0 s · 1 | cuts; long soft fade 36 f only between matching compositions → dip to black | none | faint vignette / same | none | "ambient, neo-classical, soft jazz" · 60–90 | 0 / 0 / 0 |
| Cinematic | in-out `(0.45,0,0.55,1)`, 1000 ms [prior] | 240 ms | 0 | 2.5 s · 1 | cuts; dip to black between parts; silent whip 10 f at place changes → dip | slow push to 1.06, 5–7 s, one direction | vignette / vignette + grain on twos; 2.39 bars only when turned on (Level 2, "Film bars", off by default) | low riser, sub hit (≤ 2, at peaks) | "ambient and orchestral, builds to a late peak" · 70–100 | ≤ 1 per 30 s / 0 / 2 |
| Film | stepped linear at 8 fps (375 ms in 3 steps); the date switches on hard | 40 ms per character (typing) | 0 | 2.0 s · 2 | light leak over the cut (no spare footage needed); warm flash only on real flash or night clips; grey fade at day changes → leak | none (handheld stays) | leak + vignette / + grain on twos | shutter, tape click (≤ 4) | "indie and lo-fi hip-hop" · 80–100 | ≤ 1 per 30 s / 0 / 4 |
| Playful | back-out `(0.34,1.56,0.64,1)`, 500 ms [prior] | 70 ms | ~10% | 1.0 s · 2 | pastel flash on a downbeat at part changes | zoom-in to 110%, ≤ 1 per 8 shots | highlight glow / same | bubble pop, boing, ding (≤ 5) | "bouncy dance-pop" · 120–150 | ≤ 2 per 30 s / low / 5 |
| Hype | slam: scale 1.5→1.0, expo-out 150 ms (t90 ≈ 120 ms, measured) | 70 ms | 0 | 1.0 s · 2 | whip 8 f + whoosh → white flash 3 f; flash on drops | zoom-in to 115–125% on drop beats, face-anchored; decaying shake **on drop hits only** | none / none | whoosh, impact, on drops only (≤ 5) | "phonk, trap, EDM — builds then drops" · 130–160 | ≤ 3 per 30 s / high / 5 |

- **Exits** mirror the entrance at 0.6× its duration. Film switches off hard. Hype fades out over 150 ms.
- **What was measured** (research 07): Cozy's path, Hype's slam t90, and the 110–130 ms cluster of staggers. Every other value above is a prior.

### 4.5 Which vibes go with which kind
★ = default · ● = shown as a card · ○ = under "More vibes", with its budget capped · – = never offered

| Kind | Clean | Cozy | Quiet | Cinematic | Film | Playful | Hype |
|---|---|---|---|---|---|---|---|
| fast_day | ★ | ○ | – | – | ● | ● | ○ |
| quiet_day | ○ | ★ | ● | ○ | ● | – | – |
| trip | ○ | ○ | ○ | ★ | ● | ○ | ● |
| places_guide | ★ | ● | – | ○ | ○ | ● | – |
| talking | ★ | ● | ● | – | – | ○ | – |
| story_day | ● | ★ | ○ | ○ | ● | ○ | – |

### 4.6 Effect budget per kind ([prior]; the look spends within it)
| Kind | Special joins (flash, leak, whip, freeze) | Soft fades | Zoom-ins | Slow push | Moments (freeze + label, proposed only) | Words per min (Short · long) | Sounds |
|---|---|---|---|---|---|---|---|
| fast_day | ≤ 1 per 30 s, at part changes | 0 | ≤ 1 per 8 shots | ≤ 20% of shots | ≤ 1 | 4–6 · 2–3 | ≤ 3 |
| quiet_day | 0 | at part changes | 0 | ≤ 30% of held shots | 0 | 2–3 · 1–2 | 0 |
| trip | ≤ 10% of joins, only at a change of place or day, ≤ 1 per 30 s | at chapters | ≤ 2 | ≤ 25%; ≤ 2 aerials in a row, ~15% of runtime | ≤ 1 | 3–4 · 2 | ≤ 4 |
| places_guide | 1 per change of place | 0 | 0 | ≤ 20% | 0 | 1 per place + recap | ≤ 1 per place |
| talking | 0 | 0 | at idea changes, ≤ 4 per min | 0 | 0 | ≤ 10 (big word ≤ 1 per 30 s) | ≤ 3 |
| story_day | ≤ 1 per 60–90 s | at chapters | ≤ 2 per min, while talking | ≤ 20% | ≤ 2 | 2–4 | ≤ 1 per min |

- **Long formats** allow at most 1 special join per 60–90 s.
- **The effective budget** is min(kind, look appetite). For example, Hype on a trip keeps Hype's type and colour, but only 10% of its joins can be special.
- **When a join has no spare footage,** it falls back to a join of the same vibe that needs none (dip, flash or leak), never silently to a plain cut. Each export reports how many joins fell back. Research 07 measured spare footage on both sides at only 1 of 16 part boundaries.

### 4.7 Format records
| Format | Frame | Text box | Min text | Words density | Chapter device | Words default | Sound files | Ending |
|---|---|---|---|---|---|---|---|---|
| Short | 1080×1920 | x 120–888, y 288–1248; nothing at x > 780 below y 840 (button rail) | 40 px (24 px bold at the very least) | 4–6 cards per min, 1 on screen at a time, ≥ 3 s apart | 1 s corner kicker | on the video | Both | ends on the payoff; no end card |
| Long vertical | 1080×1920 | same | 40 px | 2–4 per min | "01 / 04" counter tile | on the video | With music | 2 s closing title (the video's title); never "follow" or "subscribe" |
| YouTube | 1920×1080 | x 5–95%, y 5–75% (YouTube's own subtitles use 75–85%) | 44 px | 2–4 per min | part titles, plus a chapters list when there are ≥ 3 parts of ≥ 10 s | subtitle file | With music | nothing over the last 20 s (the end-screen zone) |

**Always:**
- Grain only on 16:9. No bars on 9:16.
- **Wide clips in an upright format are cropped, not padded.** The crop centres on the face box, otherwise on the salient subject, otherwise on the frame's centre (P9).
- A clip that can't be cropped without cutting through a face is left out, and listed with **Use it**.

### 4.8 How "a video I love" plugs in
- **Reading the file.** `style.learn` reads the file into the Kind shape (pace, cut point, beat, joins, first-shot hold) and the Look shape (colour stats, join mix, caption band once P16 lands).
- **Nearest kind.** Chosen by median shot length, pace trend, speech share and join mix. That kind supplies the guards and every field the file couldn't measure.
- **Nearest look.** Chosen by colour, join mix and caption case/position. That look supplies the fonts and motion, which a file never provides, so the whole video still matches one vibe.
- **Colour.** The reference's colour becomes `fit_look` on the creator's own shots, inside the guards.
- **Ticked traits override their fields.** A trait over budget is asked about, never copied silently.

---

## 5. Motion library v1 (20 elements)

**Our own library, in the spirit of Overlay Studio.** It copies behaviour only, never Overlay Studio's code, assets, colours or copy (see NOTICE). Every element takes its timing, type, colour and sound from the active vibe (§4.3–4.4) and its permission from the kind's budget (§4.6).

**Render split**
- **ffmpeg:** anything that moves or recolours footage. Shot stage: camera moves (one `perspective` primitive). Join/finish pass: joins, leak, glow and the LUT (in RGB).
- **Canvas (`overlayDraw.ts`):** anything drawn on top. It is identical in preview and export.

**Rules**
- **Beat lock.**
  - A card's *hit frame* is onset + t50 (onset + t90 for slams). It snaps to the nearest beat only if that moves it 3 frames or fewer.
  - The picture may land up to 2 frames before the beat or 1 frame after it.
  - Stagger = beat ÷ n, choosing the n closest to the vibe's own stagger.
  - Holds end on a beat and last at least max(min hold, 2 beats).
  - A sound effect's attack lands on the beat.
- **Holds stay pixel-still,** so a held card is one PNG. Motion lives only in entrances and exits (≤ 0.6 s). Anything that keeps moving loops every 2 s or less, so long videos never reach the 20,000-frame cap.
- **Density.**
  - Never two cards of the same kind in a row.
  - The cards of one part leave together.
  - List items that have been covered dim to 45% instead of leaving.
  - Nothing goes over a face box.

### 5a. What each element is and when it's used
| # | Element | Family | Used when (within the budget) | Words from | Render | Status |
|---|---|---|---|---|---|---|
| 1 | Hook line | text | Short only, 0–2.5 s, kinds with a clock or premise hook; ≤ 7 words | the creator, or clock and place from metadata | Canvas | extend `title` |
| 2 | Clock / date stamp | text | time spine: at each new session, ≤ 1 per 8 s. Film: a camera-back date on every shot | `capture_time` (time-zone corrected) | Canvas | extend `date` |
| 3 | Place stamp | location | once per place, after the hook | GPS → offline GeoNames (credited), editable | Canvas | new kind `place` |
| 4 | Part title | chapter | each part on long formats; a 1 s corner kicker on Short | part names (editable) | Canvas | restyle `part` |
| 5 | Diary line | caption | quiet_day, story_day; ≤ 8 words, ≤ 1 per 10–15 s | the creator, or metadata | Canvas | `caption` |
| 6 | Word-group captions | caption | talking: 1–4 words on Short, sentences on long formats, in one fixed band | the transcript | Canvas | extend `talk.caption_overlays` |
| 7 | Big word | emphasis | talking: one key word per idea, ≤ 1 per 30 s | the transcript | Canvas | new kind `word` |
| 8 | Name tag | lower third | 0.5 s after a person first speaks or appears | the profile, or typed | Canvas | `name` |
| 9 | Numbered place + recap | list | places_guide: one card per place; a 1.5–2.5 s recap at the end, in pages of 3 on 9:16 | place names | Canvas | new kind `list` |
| 10 | Closing title | close | Long vertical: the last 2 s. Never on Short (end on the payoff) or in YouTube's last 20 s | the title | Canvas | restyle `end` |
| 11 | Slow push | camera | held shots ≥ 2.5 s; one direction for the whole video | — | ffmpeg `perspective` from the 4K source (cubic) | replaces remix `PUNCH` and zoompan |
| 12 | Zoom-in | camera | talking at idea changes; Hype and Playful on beats | — | ffmpeg crop from the 4K source (free), face-anchored (P9) | reimplement `punch` |
| 13 | Freeze + label | peak | **only as a proposal the creator adds** (Part tab, "Moments") | typed name or place | ffmpeg `loop` (the source span shortens by the held frames, so the frame count is unchanged) + Canvas label | new |
| 14 | Soft fade | join | part changes (Cozy); long fade only between matching compositions (Quiet, Cinematic) | — | ffmpeg `xfade=fade`; needs spare footage, otherwise the look's fallback | exists (dissolve) + fallback |
| 15 | Dip | join | day or chapter changes; the fallback when there's no spare footage | — | ffmpeg `fade color=` | exists (`dip_black`) + colours |
| 16 | Flash | join / peak | Playful and Hype on downbeats; Film only on real flash or night clips; ≤ 3 per s | — | Canvas alpha-white frames | exists |
| 17 | Light leak | join / texture | Film and Cozy over a cut at part changes; needs no spare footage | — | ffmpeg procedural `gradients`, screen blend **in RGB**, finish pass | new (tune the colour) |
| 18 | Whip | join | trip (Hype, Cinematic) at a change of place, when both shots move the same way | — | ffmpeg `hstack` + eased crop + `avgblur` via `sendcmd`; needs 0.3 s of spare footage, otherwise a flash | new |
| 19 | The sound carries across the cut | join (sound) | where speech or place sound continues across a cut (possible at 53% of cuts as a J cut and 40–44% as an L cut, after trims) | — | ffmpeg audio from source handles; the picture is unchanged | new (P10) |
| 20 | Atmosphere | texture | the whole video, per vibe and format | — | vignette = one Canvas PNG; leak and glow in the finish pass after the LUT; grain on twos only on 16:9 | new |

### 5b. Gallery fake (keyframes; ms from the start of the 4 s tile; In and Out use §4.4)
| # | Keyframes |
|---|---|
| 1 | Still t03. At 0: text 0→1 opacity over 120 ms (Clean: box scale .96→1 at the same time); no slow entrance. Hold to 2500, then opacity →0 over 150 ms. Centred, y 520–700 of 1920, up to 3 lines: "8:35 am · first day of term". Hype: each word slams 1.5→1 over 150 ms, 70 ms apart. |
| 2 | Clock: at 400, "8:35 am" In (rise 12 px + fade) at x 120, y 300. Hold 2000, then Out. Film date: at 0, "9 25 '26" switches on hard at the bottom right (x 780–888, y 1180–1240), with a 2 px amber glow and opacity flickering between .97 and 1.0 at 12 fps. It switches off hard at 3600. |
| 3 | 400: the pin drops 40 px→0 (In). 550: the name wipes left to right (`clip-path: inset(0 100% 0 0)`→`inset(0)`, 400 ms, In curve). 630: the second line, "Lisbon, Portugal", fades in over 250 ms. Hold to 3200, then opacity →0 over 300 ms. Box x 120–600, y 288–400. |
| 4 | 400–800: a black dim overlay 0→30%. 400: the kicker "PART 2" fades in over 250 ms. 550: the title "Campus" rises 16 px and fades in, letter-spacing .08em→0 (In). 700–1200: a hairline grows from the centre, 0→120 px. Hold to 3000, then everything fades and the dim returns to 0 over 400 ms. The Short toggle shows a 1 s top-left kicker instead (fade 200 ms in and out). |
| 5 | 400: "slow start. coffee first." In (Film: typed at 40 ms per character). Hold for max(min hold, words/3 + 1 s), then fade out over 300 ms. Bottom band, y 1080–1248. |
| 6 | The groups "we finally" / "made it" / "to the" / "top" swap instantly at 400 / 1300 / 2200 / 3100, centred at y = 0.60 H. The current word takes the vibe's single emphasis (5c). |
| 7 | 800: "NEVER" In (Hype: 1.5→1 in 150 ms; the others per 5c). Hold 800 ms, then scale 1→1.05 and fade over 150 ms. Placed in x 120–780, y 520–1000, never over the face box. |
| 8 | 900: the name slides 24 px in from the left, revealed by a clip wipe (In). The role line follows 100 ms later. Hold 3000, then a mirrored Out. "Sarah" / "@sarahvlogs", box x 120–780, y 1080–1248; name 48 px, role 32 px. |
| 9 | 400: "1 · Café Lina" In. Then the recap builds: items 1–3 arrive 600 ms apart, and each earlier item dims to 45% when the next arrives. At 3400 everything leaves together. |
| 10 | 2000: a dim overlay 0→20% over 400 ms, and the title comes In. It holds, and the tile fades to black from 3600 to 4000. |
| 11 | The still scales 1.00→1.06 over 4000 ms with `cubic-bezier(0.45,0,0.55,1)`, `transform-origin` on the subject (50% 40%). Always a push in. |
| 12 | The still sits at 1.00 until 1200. At 1200 (a beat) it jumps instantly to the vibe's zoom (5c; 1.10 for Clean), with no transition. At 3200 it cuts to still B at 1.00. Hype adds a shake from 1200 to 1467: `translateX(4·e^(−t/80ms)·sin(2π·11·t)) px`. |
| 13 | From 0 to 1000 a slow push stands in for motion. At 1000 the frame freezes: over 200 ms, saturate 1→.3 and brightness 1→.7, while the scale keeps easing 1.00→1.04 until 2600. At 1150 the name label comes In in Name-tag style; Cozy and Playful also draw a doodle arrow over 300 ms. At 2600 the filters snap back and it cuts to B. |
| 14 | Still A until 2000. B's opacity goes 0→1 linearly from 1867 to 2133 (8 f). Long variant: 1400–2600 (36 f). Under the tile: "Needs 8 frames of spare footage each side — otherwise: warm light leak". |
| 15 | From 1800 to 2000, A fades to the dip colour (6 f). The colour holds for 67 ms (2 f). B fades up over 200 ms. The Quiet variant is 18 f in total. |
| 16 | At 2000, a white layer 0→1 in 33 ms (1 f), then 1→0 over 100 ms (3 f), with B underneath. |
| 17 | At 1700 a radial gradient (`#FF7A1A`→transparent, `mix-blend-mode: screen`) enters from the top edge (9:16) or the left edge (16:9). Its opacity rises 0→.8 over 250 ms while it drifts 30% of the frame over 600 ms. It peaks at 2000, the cut to B, and fades out from 2000 to 2350. |
| 18 | From 1867 to 2133, a strip holding A and B side by side moves `translateX` 0→−100% with a smoothstep curve (u²(3−2u)). Its `filter: blur` goes 0→12→0 px, peaking at 2000. A whoosh marker shows at 2000. On 9:16, when the shot tilts, it moves `translateY` instead. |
| 19 | Two lanes under the frame, *Picture* and *Sound*. The picture cuts at 2000. B's waveform starts at 1667 under A, labelled "Sound leads by 0.33 s". Toggling L instead carries A's waveform on to 2500. |
| 20 | Vignette: `radial-gradient(ellipse at center, transparent 55%, rgba(0,0,0,.35))`, static. Cozy leak: an orange blob drifting on a 13 s loop, its opacity moving between .15 and .3 every 4.7 s. Playful glow: a duplicate still with `blur(8px) brightness(1.4)`, `mix-blend-mode: screen` at .4 opacity. Grain (16:9 only, Cinematic and Film): an SVG `feTurbulence` layer at 8% opacity, re-seeded every 83 ms. |

### 5c. How each element restyles per vibe (timing from §4.4; – = not used in this vibe)
| # | Clean | Cozy | Quiet | Cinematic | Film | Playful | Hype |
|---|---|---|---|---|---|---|---|
| 1 Hook | white Inter 600 on a black rounded box (r 12, padding 16×24) | lowercase Caveat, cream, no box | small EB Garamond italic | small EB Garamond, on at once | Courier Prime, on hard, no box | Poppins 700, black on a `#FFD84D` box, −2° | Anton caps, white, per-word slam |
| 2 Clock / date | clock: Inter 500 at 60% white | clock: Caveat lowercase, cream, fading up; **never boxed, no typing sounds** | Inter 300 caps, +.2em | Inter 300 caps, +.3em, plus a hairline | **date**: DSEG7 amber camera-back stamp, no animation | Poppins on a highlighter swipe (width 0→100%, 300 ms) | – |
| 3 Place | pin glyph + Inter 600, shadow | round pin, cream pill `#F3E6CF`, Caveat, text `#3A2E22` | no pin; Inter 300 caps; fade only | no pin; tracked caps + hairline + lat/long in small mono; 800 ms fade | ink stamp in Courier Prime amber; 3-step scale 1.15→1; 1 px jitter | bouncing red pin, sticker pill at −4° | Anton caps slam 1.5→1 + 4 px shake decaying over 200 ms |
| 4 Part title | Inter 600, numeral in the accent colour, no dim | Caveat "Day 2" with a drawn underline (stroke 400 ms), 20% dim | EB Garamond italic, 20% dim | tracked caps, 40% dim | intertitle: a black card, Courier Prime centred, 1.5 s | letters bounce in, 40 ms apart | slam + a 3 f white flash |
| 5 Diary | Inter 500, small | EB Garamond italic, lowercase, cream | EB Garamond italic, small, at 90% | Inter 300, sentence case, small | Courier Prime typed at 40 ms per character, silent | Poppins 600 on a soft pill | – |
| 6 Word groups | Inter 600 white; current word 100%, the others 70%; shadow, no box | static lowercase lines in EB Garamond | static italic sentence | – | – | current word pops 1→1.12→1 on a coloured pill | Anton caps; current word at 110%; no stroke, yellow or emoji |
| 7 Big word | Inter 800, scale 1.1→1 over 200 ms, no shake | Caveat, fade, no slam | – | thin tracked caps, 600 ms fade | Courier Prime, stamped with jitter | Poppins 800 with a colour pop, overshoot | Anton slam 1.5→1 |
| 8 Name tag | Inter 700 name + 500 role, scale 95→100% | Caveat with a doodled underline | Inter 300 caps, tracked | tracked caps, no box | typed on paper tape (a `#EDE3CC` strip at −1°) | die-cut sticker tag at −3° | a coloured slab slides in + 3 f flash |
| 9 Numbered | white notes card, tabular numerals, round ticks | notebook scrap `#F3E6CF` at −2°, hand-drawn tick | – | numbered serif, no card | index card, red-pen tick | coloured number circles, bouncing ticks | – |
| 10 Closing | Inter 600 | Caveat | EB Garamond italic | EB Garamond, slow fade | Courier Prime, fading out like a projector run-out | Poppins 700 | Anton |
| 11 Slow push | 1.04 over 4 s | 1.05 over 4–5 s | – | 1.06 over 5–7 s | – (handheld stays) | 1.06 over 2.5 s | 1.06 over 2 s |
| 12 Zoom-in | 110%, alternating with 100% | – | – | – | – | 110% | 115–125%, with a shake on drops |
| 13 Freeze | dim + a small Inter label | sepia + Caveat name + doodle arrow | – | slow desaturate + serif name, silent | black and white + typed name | record-scratch sound + sticker tag + doodle arrow | slam name + 2 f flash |
| 14 Soft fade | – | 8 f | 36 f, matching compositions only | 36 f, matching compositions only | grey fade, 12 f | – | – |
| 15 Dip | black, 14 f (long formats) | cream `#F3E6CF`, 14 f | black, 18 f | black, 18 f | grey, 14 f | – | – |
| 16 Flash | – | – | – | – | warm white `#FFF1DC`, 4 f (real flash or night clips only) | pastel `#FFF4D6`, 4 f | white, 3 f |
| 17 Leak | – | peach `#FFB38A` at .5 | – | amber at .35, rare | orange-red `#FF7A1A` at .8 | – | – |
| 18 Whip | – | – | – | 10 f, silent | – | – | 8 f + whoosh |
| 19 Sound across the cut | same in every vibe | same | same | same | same | same | same |
| 20 Atmosphere | none | vignette + warm leak drift | faint vignette (.2) | vignette; grain on twos on 16:9 | leak + vignette; grain on twos on 16:9 | highlight glow | none |

---

## 6. Music

| Source | In v1 | Badge (UI) | Licence handling |
|---|---|---|---|
| My music folder | yes, ranked first once it's set | "Yours" | the creator holds the licence; each track is analysed once and cached (`music.py`) |
| Starter pack | yes: ~35 tracks (5 per vibe), bundled, offline | "Comes with VibeCut" | **CC0 / CC BY only**, with credit lines written in advance |
| Free music (Openverse: Jamendo, ccMixter) | opt-in, needs the internet; sends mood words only | "Free · needs a credit" | CC0 / CC BY only. **BY-SA, NC and ND are dropped**: music synced into a video can pull the whole video under BY-SA |
| Licensed catalogue (Epidemic Partner API) | evaluate only | — | sublicensed through the partner |
| Trending or commercial songs | **never** | — | the no-music version instead |

**How recommendations work** (no model involved):
1. **Gate by the vibe.** The track's tempo must sit inside the vibe's band; half time and double time count. It must be at least as long as the edit, or loopable at a section boundary. It must have no singing when a voice or the creator's own sound leads.
2. **Rank** by how well the track's energy shape follows the video (`music.match`). For music-led kinds, then rank by *drop fit*: can the track's biggest lift land where the hook ends (`find_drop`)?
3. **Spread:** never the same artist twice in the top five.
4. **Explain** each pick in plain words (`music.explain`), or say nothing.

**Music tab** (Edit panel, 360 px):
- **Header:** "Music" (serif 24). **Subline:** "Ranked by how each track's energy follows your video."
- **Now playing card** (raised, radius 12, padding 14):
  - a 48×48 cover, "Slow Sunday" (600 weight), and "Mira Vale · Yours";
  - a reason: "Builds as your day gets busy and eases off at dinner. Its lift lands on the fountain.";
  - a 40 px waveform with the video's parts as coloured blocks underneath, and the playing window highlighted;
  - the line "Starts 0:12 into the song".
  - **More** (Level 2) reveals the slider "Music ↔ your sound".
- **Also fits** (5 rows, each 64 px): ▶ (a 28 px circle) · title and artist · source badge · one reason line · a 56×20 curve (the track's energy in sage, the video's busyness as a cream dashed line) · **Use**. The rows:

| Title · artist | Badge | Reason |
|---|---|---|
| Paper Boats · Juniper Hall | Comes with VibeCut | "Gentle start, lifts right as you reach the park" |
| Harbour Lights · Ode Tanaka | Free · needs a credit | "Steady and warm; its peak falls on dinner" |
| City Walk · The Linen Room | Yours | "Even all the way — good if you want it calm" |
| Early Tram · Sol & Ash | Comes with VibeCut | "Quick start that matches your busy morning" |
| Window Seat · Petra Lune | Yours | "Builds late, peaks on your last shot" |

- **After the list:** a row "No music — just your own sound" with **Use**.
- **Footer:** "Choose my music folder" · "Find free music (online)". Once a folder is set: "From ~/Music/Vlog · 212 tracks".
- **Toggle:** "Show all my music". Tracks outside the vibe say why in plain words: "Quicker than Cozy usually goes" · "Has singing — may fight your voice".
- **Faint note at the bottom:** "Want a trending sound? Those can only be added inside TikTok or Instagram. Export without music and add it there."

**▶ Preview** (`state=preview-track`)
- The main player plays *the creator's video* with this track for 15 s around its peak.
- The row shows a progress ring.
- Under the video: "Previewing Paper Boats · 15 s" with **Use it** · **Stop**.

**Switching is one turn:** `set_music(track, in_point)`.
1. The track is placed so its lift meets the edit's peak (music-led kinds) or so it starts at a calm point (others).
2. **Beat policy:**
   - *free* moves no cuts;
   - *parts* moves part changes onto the nearest bar line;
   - *drops* also moves cuts inside the drop onto beats.
   Each move is ≤ 0.35 s (`restyle.MAX_SNAP_S`), and a shot is never held longer than it was filmed.
3. It ends on the track's own ending if that falls within 2 s; otherwise it fades over the last 2 s, ending on a bar.
4. Card hits re-snap (≤ 3 frames), and ducking is redone.
5. It writes a history line, for example "Music: Slow Sunday → Paper Boats · 4 part changes moved onto its bars, all under 0.3 s" (parts policy) or "Music: Slow Sunday → Paper Boats · its lift lands on the fountain · ends on its own ending" (free). **Undo** restores the track and the cuts together.

The first time a track outside the vibe is chosen, an inline prompt asks: "This one is quicker than Cozy usually goes. Use it anyway?" with **Use it** · **Cancel**.

**States**
- **No folder and offline:** only the starter pack, with **Choose my music folder** prominent.
- **Reading a folder:** "Reading your music… 40 of 212 — suggestions from what's ready".
- **Track missing:** "Can't find Slow Sunday. It may have moved." with **Locate** · **Pick another**.
- **Nothing fits** (shape below `MIN_SHAPE_R`): "None of these follow your video closely. Here's the nearest."
- **Search offline:** "Free music search needs the internet. Your music and the starter tracks still work."

**Mix:**
- Loudness −14 LUFS.
- Voice-led kinds duck the music 18–25 dB within 300 ms, with a slow release, driven by the SoundAnalysis speech timeline (the level-based mask hears music as talking).
- quiet_day never ducks everyday sounds.
- Trips let the place's own sound through 1–2 times a minute.

**No-music version**
- Same picture, words and cuts. The creator's own sound returns to its natural level with no ducking.
- It writes `<title> — cut times.txt`:
  ```
  A day out with Sarah — cut times
  The hook ends at 1.4 s.
  Your cuts don't follow a fixed beat, so any sound that fits the mood works.
  0:00.00  open · 0:01.40  cut · 0:02.73  cut · …
  ```
- When cuts do sit on a grid (the *parts* and *drops* policies), the second line reads "Pick a sound around 92 beats a minute." instead.

---

## 7. Conversation history (the Ask bar's past turns)

**What goes in:** every change, whether typed or tapped, including moves, swaps, trims, words, music and vibe switches. Each entry is one turn. Its diff is computed by `board.diff` / `describe` and never written by the model; the model only emits ops.

**Collapsed** (a 32 px line directly above the Ask bar):
- On the left, the last change and **Undo**: "Opened on the sunset · Undo".
- On the right, "All changes (6) ▴".

**Expanded**
- The drawer slides up (250 ms, `--ease`) over the story strip and the bottom of the stage. It spans the centre column, up to 55% of the stage height, and scrolls.
- **Newest is at the bottom, next to the Ask bar,** as in a chat, and it auto-scrolls to the newest.
- **Esc** or ▾ closes it.

**Anatomy of an entry**
- **Icon:** ✦ for a typed request, ● for a tap.
- **Line 1:** "You asked: 'open on the sunset'" or "You moved Library before Campus".
- **Next lines:** the computed diff (muted, up to 3 lines, then "+2 more").
- **On the right:** **Undo**. After undoing, the entry is faint and struck through, and the button reads **Redo**.
- **Remember…** (typed edits only) offers "Just this video" · "Every video". "Every video" asks for *When* and *Not when* before it can be saved.
  - Only confirmed rules ever reach the model.
  - An undone edit can't be remembered.

**Sample entries** (oldest first):
1. "VibeCut made this video — a day, told fast · Clean" (no Undo)
2. "You asked: 'open on the sunset'" → "Opens on: fountain at dusk (was: the tram) · 1 shot moved"
3. "You added a shot to Park" → "Park: 3 → 4 shots · 0:08 → 0:10"
4. "You asked: 'end on the sunset shot'" → "Ends on: the sunset in Park"
5. "Music: Slow Sunday → Paper Boats" → "Its lift lands on the fountain · ends on its own ending"
6. "You asked: 'less text'" → "Removed 2 of 7 words on screen: 'campus', 'library'"

**Dependent undo.** Undoing entry 3 also skips entry 4, which then shows a "Skipped — it depended on an undone change" tag. The toast reads "Undone. I also skipped 'end on the sunset shot', which depended on it." (`board.Session.replay` already records what it skipped.)

**Remakes.** A new kind, format or story order appears as a divider entry, "New version: told place by place", with **Back to version 1**. The Versions menu appears in the project name only once a second version exists.

**Failures.**
- A request that can't be done: "I couldn't turn that into a change. Nothing changed." plus 2 suggestion chips.
- A refused op states its reason: "Couldn't: Library has only 2 shots."

**Keys:** ⌘Z undoes the latest active turn; ⇧⌘Z redoes.

---

## 8. What must be built for this to be honest, and in what order

| # | Change | Where | Why |
|---|---|---|---|
| P1 | Kind, look and format records as dated JSON. Move the `remix.py` constants (`MOODS`, `PUNCH`, `ORIGINAL_GAIN`, `TAG_TEXT`, `DEFAULT_LEN`, `BPM_DEFAULT`) into `fast_day`. Add `make(vibe, clips, format)`. `pick_music` reads any `TrackSource` (folder, then starter pack, then Openverse) | `remix.py` → `vibes/*.json` | Today there is no boom without references, and remix is one hard-coded kind |
| P2 | File drop only: remove `_fetch`, `ytdlp`, `is_url` and the link fields in `MatchStyle.tsx`, `Remix.tsx` and `BorrowStyle.tsx`. Add the "Where's it from?" mark. Delete the source after learning. Purge the cached `source.mp4` files | `reference.py` + 3 components | User decision; research 06 §1 and §5(d) |
| P3 | New ops `set_music`, `apply_surface` and `add_moment`. A Remake uses the `choose_option` snapshot pattern | `board.py`, `musiclib.use` | A music or vibe switch must be a turn with Undo |
| P4 | HLG → SDR (`scale_vt … bt709`) before any colour. `perspective` replaces zoompan. Zoom-ins are cropped from 4K. The LUT, leak and glow move to the finish pass. Render 3 shots in parallel. Add a shot cache keyed by (clip, span, move, fades), a 720p proxy mode, and per-part proxy files for long formats | `export.py` | Graded Watch in about a minute; every colour is applied to HLG today |
| P5 | `safe()` → top .15, bottom .35, left .111, right .178, plus the rail notch. Text floors of 40 and 44 px. `option framerate 30` in the ffconcat (**600 of 1800** overlay frames are wrong today). Per-look motion tokens replace the single cubic ease | `overlayDraw.ts`, `export._overlay_input` | Words sit under the platforms' buttons; animation judders |
| P6 | One text renderer: retire remix's AppKit caption helper (`SWIFT`, `text_tool`, `render_captions`) | `remix.py` | Preview must equal export |
| P7 | SoundAnalysis helper mode: a speech, music and laughter timeline per clip at index time | Swift helper, `indexer` | The guess, ducking, J/L cuts and the quiet day all need it |
| P8 | Read the beat by vector strength; choose the tempo octave inside the look's band | `music.py`, `style.py` | Beat readings are wrong today |
| P9 | Store face and salient-subject box centres per keyframe (today: presence and edge per second). `_fit` crops instead of padding when a wide clip goes upright | `vision.py`, `export._fit` | Zoom-in anchor; no bars on a Reel |
| P10 | Audio handles in export, for sound carried across cuts (the picture frame count doesn't change) | `export.py` | Editing grammar (CLAUDE.md's 30%) |
| P11 | openverse: drop `category`; don't cache failed searches; CC0 and CC BY only | `openverse.py` | `sfx()` can never return a sound; licence risk |
| P12 | English for every user-facing string, including the reason strings in `reject.py` and `talk.py` | backend + frontend | UI is English only |
| P13 | Remove the "Camera motion" and "My on-screen character" cards | `CreativeTools.tsx` | Generative video is a non-goal |
| P14 | Bundled assets: the starter music, ~30 CC0 sounds, 6 OFL fonts, and GeoNames cities for offline place names (CC BY, credited). Correct time zones on capture times | assets, `media.py` | Offline boom; true clock stamps |
| P15 | `vibes.guess()`; an after-the-action cut window; a `cut_mid_action` finding with a discrimination test | `select.py`, `grammar.py` | quiet_day (research 06 Increment 2) |
| P16 | Caption OCR (Vision `.accurate`, 2–4 fps, 540p, from the same decode). May slip to v1.1; the Words trait then reads "not checked" | `vibevision --text` | Learning word position and size |
| P17 | Compliance: the flash cap in the plan; child-privacy warnings from labels; strip the location atom; the disclosure note | `export.py`, `overlays.py` | Research 06 §4 compliance layer |

**Build order**
1. **Round-2 mockups from this spec**: `tokens.css` and `looks.css` first, then builders A and B in parallel. The user reviews the mockups before anything else.
2. **Honesty and rendering:** P2, P4, P5, P6, P7, P8, P11, P12, P13.
3. **The core path:** P1, P3, P14, P15, plus `fast_day` and `quiet_day` with Clean, Cozy and Film, and `talking` with Clean.
4. **Calibration pilot** on `fast_day` (research 06 Increment 3).
5. **The rest:** the remaining kinds and vibes (labelled as priors internally), P9, P10, P16, P17.

---

## 9. Deliberately left out, sign-offs, risks

**Left out of v1**
- Link import, yt-dlp, "import from TikTok".
- Trending or commercial songs; generated music.
- Any generated frame:
  - interpolated slow motion (research 07's option A: slow motion only from ≥ 60 fps footage, at ≥ 0.5×);
  - AI camera moves;
  - avatars.
- Virality scores and any "viral" copy.
- The retention loop that needs a platform login (v2).
- Speed ramps. They read as dated when overdone, and the timeline must own output durations first.
- Kinds not in v1: photo dump, family & pets, comedy/skit, outfit transitions, food review, raw log.
- Data cards (rings, bars, counters, prices, receipts), route maps, weather badges and countdowns: all of them need the creator's numbers, which means more questions.
- Overlay Studio's talking-head cards (pin board, versus card, 3D terminal, energy meter, burst halo) and a HUD look.
- Visual effects we can't do well:
  - blur-in text (Safari exports it sharp);
  - text behind the subject (needs a matte);
  - perspective cards;
  - xfade zoomin;
  - hard, iris and clock wipes;
  - zoompan.
- Textures and bars: grain on 9:16, dust, gate weave, and bars by default.
- Chapter progress bars, follow and subscribe nudges, and "see you next time" end cards.
- Pooling several references; a shared style library; font upload; templates.
- `cutfix`: findings are reported, and nothing fixes itself.
- WebGL previews; mobile.

**Needs the user's sign-off**
1. **The rough-cut gate moves** from before the story to Export. There it becomes one-tap answers that block the export.
2. **Wide clips in an upright format are cropped** around faces and subjects. A clip that can't be cropped is left out and listed.
3. **v1 stays numpy-only.** librosa (which adds scipy) and beat_this (PyTorch, run as a subprocess) are proposed, not assumed, because CLAUDE.md says numpy only.
4. **App size:** about 140 MB of starter music, plus sounds, fonts and the GeoNames city list.
5. **No interpolated slow motion.** 30 fps clips get a freeze or a zoom-in instead.

**Riskiest assumptions**

| Assumption | How we'll know | If it's wrong |
|---|---|---|
| The kind guess is usually right | share of projects that change the preselected chip (aim < 30% [prior]) | ask with nothing preselected |
| The priors leave no amateur tells | blind pairwise tests by 3 editors on 5 creators' own footage | calibrate the 3 core kinds first; keep the rest internal |
| The vibes look clearly different | 3 people match tiles to vibe names on one shoot | ship only Clean, Cozy and Film in v1 |
| Special joins actually happen | the fallback share reported on each export | trim so part changes keep spare footage |
| Going without trending music is acceptable | no-music export share vs "Use" rate | Both files by default (already the case) |
| Long formats are fast enough | time to first playback per format on the 42-clip shoot | per-part proxies, 3 shots in parallel |

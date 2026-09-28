# Phase 1 — one coherent baseline

*Founding product engineering, 2026-09-28. Audit of what exists, what the
competitor demonstrably offers, and the consolidation that follows. Written
before the code changed; the "after" state is recorded in `web/README.md`.*

Competitor: **Vyra** (YC F26, usevyra.com — "autonomous video editing for
non-editors"). The brief's reference URLs were left blank, so the study
below rests on public web material only (site, docs, YC page, landing-site
repo). Direct fetches of the product were blocked from this machine; every
claim is marked **verified** (seen in fetched text or a search-engine copy of
that exact page) or **inferred**.

---

## 1. Audit of VibeCut as found

### 1.1 Routes and major components

Hash routes, no router. One FastAPI process, one in-memory project.

| Route | Component | What it is |
| --- | --- | --- |
| `/` | `App.tsx` (928 lines) | The editor. Header: Story/Frames toggle, *Creative tools*, *Style reference*, *Talking to camera*, profile avatar, *Export*. Story level = Chat · main · aside (player, words on screen, music). Frames level = Chat · shelf/words tabs + player · timeline. |
| `#profile` | `CreatorProfile.tsx` + own CSS | Full-page form (name, handle, vibes, pace, font, colour, references as bookmarks). Saved to `localStorage`. Different palette (green tint), different top bar, different buttons. |
| `#tools` | `CreativeTools.tsx` + own CSS | Seven feature cards. Three "live" (Plan my edit = a chat message; Titles & motion = the overlay suggester; Borrow a feeling = the reference dialog). Four disabled "coming soon" (camera motion, variants, avatar, B-roll). |
| `#polish` | `Polish.tsx` | A separate tool for a *finished* video (point at a moment, say what to put there). Shares nothing with the editor but the server. |
| modals | `StyleQuestions`, `CutReview` (in main), `TalkCut` (in main), `Export`, `Remix`, `BorrowStyle`, `Keys`, `Menu`, `SwapPicker` | |
| inline | `MatchStyle` ("Make it feel like" paste-a-link bar above the story), `Voiceover`, `Music`, `Overlays` | |

Backend routes (57) fall into: import/index, session/chat/ops/undo, rough-cut
gate, talking-head, overlays, export, music, remix, references, polish, media.

### 1.2 What actually works (verified by running it on Linux with a synthetic 8-clip shoot)

- Import → index (shots, thumbnails, per-second signals, capture time) — 2.6 s for 8 clips; colour fallback when the macOS Vision helper is absent.
- Rough cut (reject + trim) and its human gate; overrides; approve.
- Style questions → three proposals (time / place / subject) by keyword matching, no key needed.
- Choose a proposal → working storyboard; every direct edit is an operation in a turn log with a computed diff; undo/redo of any turn.
- Timeline (Frames): cut / trim / delete / reorder / drag from shelf, snapping, keyboard.
- Words on screen: suggest, add, edit, style, looks; findings (report only).
- Sound: one mixed track for preview and export; joins; music from the creator's own folder.
- Every cut checked (seams); smoother cuts on request.
- Export: 49 s edit rendered in 10.6 s to a real MP4.
- Borrow a feeling from a **file** (links need yt-dlp); Remix (CLI-tested; UI needs links/yt-dlp and Openverse network).
- Preferences (what edits teach) and voiceover proposal.

### 1.3 Mocked, disconnected, or platform-gated

| Feature | State |
| --- | --- |
| Chat *edits* | Need `ANTHROPIC_API_KEY`; without it the server returns a clear 409. Provider boundary already exists (`llm.py`). Not mocked. |
| Talking to camera (transcribe) | macOS 26 + Xcode tools only (`vibespeech.swift`). Elsewhere the job errors immediately with the reason. The header button is shown regardless. |
| Vision labels / faces | macOS only; colour fallback elsewhere. Reported in `project.vision`. |
| Reference by link | Needs yt-dlp; reported in `references.links`. |
| Four "coming soon" tool cards | Disabled buttons on a full page. Their briefs are saved to localStorage and go nowhere. |
| "Plan my edit" card | A second front door to `/api/chat` with the profile pasted into the message. |
| Profile → editing | Profile is only read when suggesting overlays (font, colour, name). Its "pace"/"vibes" are never used. Its reference bookmarks are not analysed (the page says so). |
| Project persistence | **None.** The turn log, workflow state, cut overrides and brief live in process memory (brief in `sessionStorage`). Restart = everything gone except the per-file index cache. One project only. |

### 1.4 Duplicated screens and entries

- Three ways into "make it like a reference": `MatchStyle` bar (inline), `BorrowStyle` (inside the tools page), `Remix` (header "Style reference"). Two different vocabularies for one idea.
- Two "talking to camera" entries (header button and a dashed button in the Story empty state).
- Two "what's this video" prompts (chat placeholder and the Ask screen) that do the same thing.
- Import from four places (window drop, Story empty state, Shelf header, chat instruction) with progress reported only as chat messages.
- Two profile entries (avatar in the editor, link on the tools page) and cross links between the two full pages.

### 1.5 Features without a clear place in the workflow

Creative tools page (a menu of ideas, not a step), Remix (a whole parallel pipeline that ends by replacing the story), Polish (a different input: one finished file), Voiceover (a dashed button next to the description box), Preferences "Remember…" (a small link under each turn).

### 1.6 Data model and backend capabilities

- **Clip index** (`indexer.py`): per file, cached on disk under `$VIBECUT_CACHE/clips/<id>/` (index.json, vision.json, faces.json, thumbnails, samples). Id = sha1(path, size, mtime, version). Immutable; the original file is only read.
- **Cut plan** (`cut.py`): decisions + overrides + targets, recomputed from the index.
- **Storyboard** (`board.py`): pure function of the turn log. Ops are typed (`OPS`), replayed, diffed. Overlays, music, joins, style and look live on the board as ops.
- **Workflow** (`workflow.py`): `intake → indexing → rough-cut → cut-review (gate) → story → styling`.
- **Session** = turns + board + proposals. Not serialised anywhere.
- **Provider boundary** (`llm.py`): Anthropic only, key from env or `web/.env`; offline interpreter for the first message.

### 1.7 Visual and interaction inconsistencies

- Three visual systems: editor (zinc, Columbia-blue accent, Garamond for prose), profile/tools pages (green-tinted palette, 64 px top bar, pill badges, `!important` buttons), polish (its own header).
- Buttons: at least five different button styles across `Act`, `Btn`, `creator-primary`, header pills, timeline chips.
- Dialogs: `<dialog>` with CSS classes (tools) vs fixed overlays with Tailwind (export, remix, keys).
- The story header wraps the structure note into a 120 px column beside the action buttons.
- The header shows tool buttons that do nothing useful yet (Talking to camera on Linux, Style reference before a story exists).
- No stage indicator: a first-time user cannot tell what comes next.
- Nothing is responsive below ~1200 px (three fixed columns).

### 1.8 Working behaviour that must be preserved

The engine: `media.load()` touches pixels once; ops-only editing with computed diffs and replay undo; the rough-cut gate; preview == export (one Canvas draws both; one mixer feeds both); everything stays on the machine; no generated frames; findings carry numbers and evidence levels.

---

## 2. What Vyra demonstrably offers

| # | Item | Evidence |
| --- | --- | --- |
| Primary user | Non-editors with real footage who don't want to learn a timeline; vlog / silent vlog / talking head / commentary formats | YC page; `/formats/*` — **verified** |
| Central promise | "Upload your footage, say what you want in plain words, and it makes the cut. Nothing is generated." | usevyra.com — **verified** |
| Workflow | Sign up → home upload area (video/images/audio) with per-file progress → editor opens → left "Vyra AI" chat: brief it (length, platform, keep/cut, captions, music, reference) → edit appears on the timeline live → iterate by chat or by hand → export in the browser → Exports section | docs/first-project, docs/guide — **verified** |
| Indexing | Word-level transcript, scene detection with written descriptions, subject tags, embeddings for semantic search | /ai-video-editor — **verified** (uses OpenAI + Anthropic: privacy page) |
| IA | Home/upload → editor; Assets page (with Exports); navbar with cloud backup and "Connect MCP". Editor: left tabs (AI chat · Footage (searchable) · References), preview, tool/properties panels, multitrack timeline below | docs — **verified**. No projects dashboard, transcript panel, versions or collaboration seen — **inferred absent** |
| Editing | Chat/agent first (50+ tools, also via MCP); manual multitrack timeline (trim, split, rearrange, keyframes, masks); word-timed styled captions incl. karaoke; agent-built titles/lower-thirds/transitions; user-uploaded music with beat-aligned cuts; one reference video per project for pacing/transitions/fonts/feel; semantic footage search; agent can capture a frame and read the timeline back | marketing + docs — **verified** as claims, not exercised |
| Inputs | Own clips, images, audio; long files; reference video upload. No link import seen | **verified** / **inferred absent** |
| Outputs | MP4 up to 1440p/4K, 9:16 and 16:9, browser render, download + Exports list; cloud or local asset storage | **verified** |
| Pricing | Free tier; $24–$129/mo credit tiers; figures unstable across sources | **verified**, inconsistent |
| Not verifiable | Product screenshots, actual panel names, undo/history, error states, quality | — |

---

## 3. Parity matrix

| Vyra capability | Evidence | VibeCut equivalent (before) | Gap | Decision | P1 |
| --- | --- | --- | --- | --- | --- |
| Projects saved and reopened | docs (cloud/local modes) | none; one in-memory project | whole | **Build**: project store on disk, dashboard, open/rename/delete | must |
| Upload area with per-file progress | docs/first-project | window drop + chat progress lines | status only in chat; errors not retryable | **Build**: Footage stage with per-file status, errors, retry | must |
| Footage indexed (scenes, descriptions, tags) | site | shots, thumbnails, labels (macOS), signals | no transcript, no text descriptions | keep; state capability | — |
| Semantic footage search | site | none | whole | defer (needs embeddings + model) | later |
| Chat brief → first cut on the timeline | docs | description + style questions → rough-cut gate → 3 proposals | ours adds a gate and a choice of structure | keep (a strength), make the sequence visible | must |
| Chat edits | docs | ops-only chat edits (key needed) | none when key set | keep; surface key state honestly | must |
| Manual timeline | site | Story + Frames | parity for cut/trim/reorder; no keyframes/masks | keep | — |
| Word-timed captions | site | talk mode subtitles (macOS); overlay captions typed by hand | no cross-platform speech-to-text | keep gate; **expose blocker** in UI | must |
| Titles / lower thirds / end card | site | words on screen (7 kinds, looks, findings) | parity+ | keep; one entry (Words panel) | — |
| Music with beat-aligned cuts | site | own folder → suggestions, beat grid, joins, mix | parity | keep | — |
| Reference video (one per project) | site | Borrow a feeling (file / yt-dlp link), Remix | three entries | **Consolidate** to one *Reference* entry | must |
| Preview == export | docs | already true by construction | none | keep | — |
| Export MP4, 9:16/16:9 | site | export follows footage shape; MP4 | no explicit format choice | keep; record exports on the project | should |
| Exports list | docs | none | list | **Build**: per-project export history | should |
| Assets page | docs | shelf | fine | fold into Footage stage | — |
| MCP / external agents | docs | none | whole | defer | later |

---

## 4. The unified VibeCut workflow

```
Projects ──▶ Footage ──▶ Brief ──▶ Rough cut ──▶ Story ⇄ Frames ──▶ Export
 (home)      drop clips   one line    the gate     edit by chat,       one file,
             + status     + 4 picks   (approve)    direct controls     history
```

1. **Projects** — a dashboard of projects (cover, name, clips, length, stage, last edited). New project. Secondary entries: *Polish a finished video*, *Your profile*.
2. **Footage** — drop clips or a folder; per-file indexing status; errors with *Retry*; the clip grid with shots; capability line (on-device labels available or not). Primary action: *Tell me what this video is →*.
3. **Brief** — one line; then the style questions (length, pace, opening, focus). Optional: *Follow my voiceover*, *This is me talking to camera* (macOS).
4. **Rough cut** — what would be thrown away and trimmed, with reasons and evidence; override; *Looks right — continue*.
5. **Story** — three proposals; pick one; parts and shots; chat (ops only); words on screen; music; joins; smoother cuts. *Reference* (borrow a feeling / remix) lives here as an action on the project.
6. **Frames** — the same edit, frame-accurate (a view of the Story stage, not a separate step).
7. **Export** — one file; recorded on the project; download / reveal.

Context is preserved across stages because everything is one project on the server: the stage is derived from project state and the stepper lets the creator go back to Footage or the Rough cut without losing the story (new clips reopen the gate, as before).

### Target screen structure

- `#/` Projects
- `#/p/<id>` Workspace (stage derived; stepper: Footage · Brief · Rough cut · Story · Export)
- `#/p/<id>/frames` Frames view of the same workspace
- `#/profile` Your profile (same design system, a settings page, reachable from the dashboard and the avatar)
- `#/polish` Polish (its own tool; header aligned with the app)

Removed: `#tools` (Creative tools). Its live functions already exist in the workspace (chat, Words on screen → *Fill in the rest*, Reference). Its four "coming soon" cards move to `web/feature-roadmap.md`.

---

## 5. File-level plan

Backend
- `web/backend/projects.py` — new. `Project` record (id, name, created, updated, clip ids + paths, turns, workflow, plan overrides/targets, brief, exports, import errors). `list / create / open / save / delete`. JSON under `$VIBECUT_CACHE/projects/<id>.json`.
- `web/backend/indexer.py` — `load_indexed(cid)` to reload a clip from its cache; `attach_vision` refactor.
- `web/backend/app.py` — project routes; the open project's state loaded on start and saved after every mutation (middleware + job callbacks); import job that doesn't advance on zero clips; brief and exports on the session; `capabilities` on the session (speech, vision, links, llm).
- `tests/test_projects.py` — create → import → approve → proposals → choose → edit → undo → save → reload → same board; list/rename/delete; capability report.

Frontend
- `src/router.ts` (+ test) — hash routes.
- `src/main.tsx` — route → Projects | Workspace | Profile | Polish.
- `src/components/Projects.tsx` — dashboard.
- `src/components/Footage.tsx` — the footage stage (drop, status, errors, retry, grid).
- `src/components/Stepper.tsx`, `src/ui.tsx` — one header, one set of buttons/fields/dialog/notice/progress.
- `src/App.tsx` — becomes the workspace: stage derivation, header, chat only from Story on, capability-aware actions, responsive grid.
- `src/components/CreatorProfile.tsx` — rewritten on the app's tokens; CSS files deleted.
- `src/components/BorrowStyle.tsx` — restyled on the app's tokens; gains the Remix entry.
- Deleted: `CreativeTools.tsx/.css`, `CreatorProfile.css`, `MatchStyle.tsx`, `creativeTools.ts` + test.
- `src/types.ts`, `src/api.ts` — project, brief, export record, capabilities.

Docs: `web/README.md`, `web/feature-roadmap.md`, `CLAUDE.md` status.

---

## 6. Outcome (same day)

Built and verified on Linux with a synthetic 8-clip shoot, through the UI
with Playwright and through the API (`tests/test_projects.py`):

- **Projects**: dashboard, create / rename / delete, stage per project,
  export count and cover; a project reopened after the server forgets
  everything has the identical board, timeline, log, brief and gate.
- **Workspace**: one header with the stepper; stage derived from state;
  Footage (per-file progress, unreadable files with *Try again*, clip
  grid), Brief (one line + style questions, voiceover and talking-to-camera
  side doors gated by capability), Rough cut (unchanged gate), Story /
  Frames (unchanged engine), Export (history on the project).
- **Removed**: the Creative tools page, its CSS, the four "coming soon"
  cards, the inline *Make it feel like* bar, the duplicate talking-to-camera
  entry. Profile and reference dialogs rebuilt on the app's tokens.
- **Honesty**: the home screen lists what this machine can do (key, macOS,
  yt-dlp); disabled actions say why.
- **Bug found on the way**: the index pool forked from a threaded server
  and a worker could deadlock, leaving an import at "7 of 8" forever on
  Linux. The pool now uses a spawn context.

Still true after Phase 1: every threshold is a guess; chat edits need a
key; transcripts and on-device labels need macOS; nothing is generated.

# Eval, launch plan and weekly update · 2026-10-11

## 1. Eval: 20 real cases

**System tested:** VibeCut, branch `claude/finish-the-video` at commit `eff6c5b` (main `86fd934` + 10 commits from 2026-10-10/11: music by default, beat cuts, graded looks, the two-pick setup, the calibration harness and first record). Python 3.14 venv on the creator's M5 MacBook, macOS 26. No API key configured, so every path ran on rules alone; nothing a model does was exercised.

**Pass rate: 20 / 20** (plus one reserve case, also passing). Script: `design/eval/eval_2026_10_11.py`; raw results: `design/eval/2026-10-11-eval.json`. Each case names its criterion before its result. One measurement bug in the eval itself was found and fixed (case 10's clock check mis-parsed single-digit hours, so the first run read it as FAIL; the criterion did not change, and the raw captions are listed below).

**Inputs are real, the run is partial.** The index cache holds the creator's Sep 22 shoot (42 iPhone 4K clips, 8.1 min, with on-device Vision labels, embeddings, faces, GPS and capture times), her four reference reels, 14 vlogs fetched for calibration and 19 free tracks. The original clip files sit in a folder this session cannot read, so every case ran from the index onward: **not run here** were export (pixels), the audio mix the preview plays, the on-device voice reading, transcription, the import itself and the web UI. Those are covered by the synthetic-fixture tests (`tests/`, 43 files green) and by the creator's own use, not by this eval.

**Human assistance:** none during the run. The inputs came from the creator's earlier sessions (her shoot, indexed on Sep 25; her four references). Labels in the calibration set ("well cut" = popular on YouTube) are a proxy she has not confirmed.

| # | case | input / context | pass criterion | observed | result |
| --- | --- | --- | --- | --- | --- |
| 1 | The shoot reloads from the index | 42 clips of the Sep 22 shoot, index cache only | ≥40 clips load, every one with shots, a Vision embedding and a capture time | 42 clips reloaded, 42 with shots + Vision embedding + capture time, 8.1 min | PASS |
| 2 | Rough cut | those clips | 50–100% kept; a shake reading only warns, never rejects | 42 of 42 kept, 0 thrown out (), shaky rejections 0; 42 clips · 6:51 (from 8:06) | PASS |
| 3 | Tempo read from the footage | those clips | one of quick/steady/calm with a reason that names the clips | fast — Quick cuts: your clips have lots of movement and short clips. | PASS |
| 4 | Frame suggested | the usable shots | all upright → a vertical frame, short or tall by how much there is | upright share 1.00 of 405 s usable → tall | PASS |
| 5 | What the video is, from the clips | those clips | a description, no model | “A day in my life, morning to night, with friends” | PASS |
| 6 | Length marks | usable seconds + the description | marks in order; the Short format ≤ 90 s; a reason | marks [60, 180, 405], suggested short (60 s); short format → 60 s | PASS |
| 7 | Three stories | clips + style (tall, cozy, read pace) | ≥2 stories, each with parts | 3 stories: As it happened (6 parts); Place by place (11 parts); Subject by subject (5 parts); suggested time | PASS |
| 8 | Choose the suggested story | the stories | a board whose shots all resolve, within 30% of the asked length | “As it happened”: 6 parts, 24 shots, 59 s (asked 60 s) | PASS |
| 9 | No shot repeats another | the board | after one pass, a second pass finds nothing | 0 look-alike shots taken out (); second pass finds 0 | PASS |
| 10 | Describe captions | the board + capture times + labels | ≥3 captions, every one starting with the clock | 16 captions, 16 start with the clock, 9 also say what's happening — e.g. 8:35 am; 10:03 am; 10:04 am · getting ready | PASS |
| 11 | Every cut checked | the board's cuts | ≥5 cuts, each with at least one numeric finding | 23 cuts checked, 23 with numbers, 7 rough | PASS |
| 12 | Smoother cuts | the board | rough cuts do not increase | 0 ops; rough cuts 7 → 7; “Nothing to smooth: no reorder or nudge made the cuts clearly smoother.” | PASS |
| 13 | Length slider to 60 s | the board | lands within 20% of 60 s | 0 ops → 59 s for a 60 s target; “It's already about 59 seconds.” | PASS |
| 14 | Pace: fast | the board | no non-talking shot longer than the fast cap | 0 ops; longest non-talking shot 2.50 s (cap 2.5 s); 0 talking shots kept | PASS |
| 15 | The bed: a track picked | the board + 19 free tracks on disk | a track with in-point ≥ 0 that covers the edit | 19 tracks → “Blik — Pop, Soda Pop!” 130 BPM, in 4.5 s, drop 7.0 s | PASS |
| 16 | The bed: cuts on the beat | the board + the track | ≥50% of cuts land on a beat; one undo restores everything | 23 of 24 cuts onto the beat (96%); undo restores: True | PASS |
| 17 | Cozy grades the shoot | the board's thumbnails | warmer by ≥3, blacks lifted to the floor, a .cube written | 24 thumbnails; warmth 19.5 → 27.5, black 16.9 → 30.2, sat 0.095 → 0.114; cozy-9df1ed7829.cube | PASS |
| 18 | A reference reel learnt | the creator's 50 s reference reel | median shot < 2 s; transition shares sum to 1 | “A Day in My Life *No talking #minivlog #”: 0.65 s a shot, cuts 100%, hard cuts only | PASS |
| 19 | Four reels → one fingerprint | the 4 references' style records | 15–90 s, median shot < 2 s, a tempo range | 4 refs → 18 s, about 0.77 s a shot, first shot held 1.4 s, music 96–144 BPM that builds; from 4 reference(s) | PASS |
| 20 | Remix picks the moments | the shoot + the fingerprint | ≥8 moments inside their shots, a hook, spread over clips | 23 moments from 21 clips, 20.5 s, hook 1 shot(s) | PASS |
| 21 | A downloaded vlog measured | one of the 14 fetched vlogs | ≥6 findings with numbers (reserve case) | A Letter To Myself / Cinematic Travel Fi: 53 shots, 8 findings (continuity, cut_on_motion, duplicates, first_cut, first_spee) | PASS |

Observations worth more than the pass marks:

- **Case 10 — captions.** All 16 captions carry the clock, but 7 are time-only ("nothing in the picture said clearly what was happening") and "getting ready" appears 5 times. The label-to-phrase table is small. Passes the criterion; a viewer would notice.
- **Case 17 — Cozy.** Warmer and lifted as asked, but saturation went *up* (0.095 → 0.114) where the look asks for 0.9×. The tone lift raises measured saturation and the fit doesn't compensate. Logged; not a pass/fail criterion here.
- **Case 2 — rough cut.** Nothing thrown out of 42 clips. Since shake became a warning (2026-10-04) the reject rules fire only on lens-cap, blur, mis-taps and duplicates; on this shoot none applied. That may be right; it has not been judged by the creator against her own picks.
- **Cases 12–14** passed by doing nothing (the story was already at 59 s, already at fast pace, nothing to smooth). They prove the guards, not the operations; the operations are exercised in `tests/test_smooth.py`, `test_length.py`, `test_tempo.py` on fixtures.

## 2. Launch plan, by the checklist

The checklist (course, Launch readiness, 2026-10-11) has five items. Each is answered with what exists in the build, what is planned, and how it is checked.

### 2.1 One workflow, one observable outcome

**The workflow:** drop a day's clips → pick the frame and the look → watch → export. No chat, no timeline, no questions beyond the two picks.

**Completion** (observable, logged automatically): an MP4 is written from that path — the export record carries `default_path: true`, meaning no typed chat edit was involved. **Success**: after the export the dialog asks *Would you post this?*; a *yes* is a success. Both are read from the project records by `python -m web.backend.launchlog`. Secondary signals already on the record: turns undone (a step the user rejected), time from clips to export, render seconds.

### 2.2 The eval set on the launch version

Section 1 above: 20 real cases at commit `eff6c5b`, 20 pass, no human assistance during the run, one eval-side measurement bug found and disclosed. Review of what the passes do and don't cover is in the observations under the table: export, preview sound, voice reading and the UI were not exercised here because the originals are unreadable from this session; three cases passed by correctly doing nothing. The launch version is this branch plus the launch-log commit; the eval script is rerun before the branch is merged.

### 2.3 A small group who have the problem, invited directly, watched

1. **The creator first (this week).** She restarts her server on this branch and runs her Sep 22 shoot through the workflow. Someone watches the whole session: where she hesitates, what she undoes, what she says at the export. Her undo log is read with her afterwards.
2. **Three to five vloggers she knows (next two weeks),** each invited personally, each on their own Mac, each bringing one day of their own clips and one reel they wish they'd made. A 30-minute sitting, watched, not demonstrated: they drop, pick, watch, export, and answer the one question. No editing vocabulary is expected; the app uses none. Their exports and their rejected drafts go into the calibration sets with permission.
3. **Why this group:** they film 40–100 phone clips a day and don't edit — the problem as stated in CLAUDE.md — and they are reachable for a second session.

### 2.4 Limits stated, permissions minimal, recovery possible

- **Limits, in the product:** the home screen lists what this machine can do (on-device labels and faces, speech, places: macOS; links: yt-dlp; typed edits: a key). A disabled action says why. Every finding carries its number and what it rests on, or says *not checked*. The export dialog says what will be rendered that the preview didn't show (the grade, the push). The music chip says when nothing was found and why.
- **Limits, to the user up front:** the promise is *no amateur tells*, not *beautiful*; thresholds are first guesses with one calibration record behind three of them; the music is a first pick from a free catalogue; captions name the time and, when the picture says it plainly, what's happening — on the creator's shoot 7 of 16 could only say the time.
- **Permissions and data:** the app reads the clips folder and writes to the cache and the exports folder; nothing else is touched (originals are never written; projects are JSON on disk). Network: a reference link goes to yt-dlp, a mood word to Openverse; with a key, storyboard *text* only, and index frames only when the creator uses chat-on-pause or best-moment, which say so. No account, no telemetry; the launch log is a local file.
- **Recovery:** every change is one undoable turn with a computed diff; a project reopens exactly as left after a crash or restart; a failed music pick, link fetch or transcription leaves the edit standing and says why; the previous build on `main` runs on the same cache and records. A stuck render has a Cancel button.

### 2.5 Tracking, and deciding what's next

`python -m web.backend.launchlog` prints, from the records: projects, completions, successes, exports judged not postable with the user's words, unreadable files, music hunts that found nothing or failed, model calls, render seconds, music-hunt seconds, and turns undone. Run after every session with a user; the numbers go into the weekly update.

**Decision rule.** Each failure is one of four kinds and gets one response: (1) *judgement* — the cut is legal but they wouldn't post it: their export joins the calibration bad set and their reference the good set; no threshold moves until the next record says which; (2) *honesty* — the app claimed what it didn't measure: fixed before anything else; (3) *crash or stall* — reproduced as a fixture in `tests/` before the fix; (4) *platform* — a dependency the UI didn't state: the capability line is extended. **What to test next** is whichever of these is most frequent in the log; today, with one user, the open question is (1) on the bed and the looks, which is why the creator's own session comes before anyone else's.

**Go / no-go for a wider group:** three of five would post one export unedited, and the calibration record holds at least eight rejected edits from shoots other than the creator's.

## 3. Weekly update · week ending 2026-10-11

**Shipped (branch `claude/finish-the-video`, 10 commits, not yet pushed).**
- The default path finishes the video: after Footage, two picks (frame and look), then music by default, cuts on the beat, a look that grades the picture and sets the join family. All as undoable turns; the Music chip and a format chip in Frames.
- A calibration harness and the first record: 18 well-cut vs 18 VibeCut exports; rhythm variation, cut-on-motion and hard-sync thresholds moved on it, the rest left with reasons.
- Three stale tests brought back; the timeline's beat grid fixed (it ignored the music in-point, so every Remix's snap targets were off).

**Measured.** Eval above: 20/20 real cases from the index. Cold online music pick: 195 s for 36 tracks → prefetched from the moment the brief is read. Cozy export round trip: +7.6 warmth in the file.

**Risks and open questions.**
- None of this week's work has been judged by the creator on her real footage; the eval could not decode her originals.
- The bad side of the calibration set is one shoot (11 remix iterations): the moved thresholds are better than guesses, not calibrated.
- Cozy's saturation goes the wrong way under the tone lift (eval case 17).
- No API key on the dev machine: chat edits, best-moment picking, pause chat and retake judgement remain untested against the live model.
- Six stray test exports from the first run sit in `~/Movies/VibeCut` ("As it happened 2026-10-10 22.4x"); the tool was not allowed to delete them.

**Next week.** The creator's verdict on this build; fix what she rejects; then Step 4 (Remix as a home-page front door, the model behind its shot picker when a key exists) and a second calibration record with rejected edits from other shoots.

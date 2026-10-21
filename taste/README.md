# taste/ — what a good vlog looks like, measured

VibeCut cuts every video to a house style. This folder is where that style
comes from: a set of real vlogs, each marked good or ordinary, reduced to
numbers, and the per-group fingerprint derived from them.

## Two groups

- **long** — YouTube vlogs, roughly 5–30 min (`data/long-youtube.csv`)
- **short** — TikTok / Instagram Reels / Shorts vlogs, under 3 min (`data/short-reels.csv`)

A video gets in two ways: sarah sends it (her verdict counts as *good*), or a
web search finds a young day-in-my-life creator and their videos are ranked
by likes per view against the creator's own typical video, so a big channel
doesn't win for being big. Each creator gives one good and one ordinary
example. `data/candidate-creators.csv` is that list before she strikes any.

## Filling it in one run (on sarah's Mac)

    cd ~/Desktop/VibeCut/repo && git fetch -q origin claude/vlog-taste-model-i4z3mi && git checkout origin/claude/vlog-taste-model-i4z3mi -- taste/__init__.py taste/collect.py taste/measure.py && .venv/bin/python -m taste.collect

`taste/collect.py` finds each candidate creator's recent videos, reads views
and likes, adds their best (most likes per view among their better-watched)
and an ordinary one, then downloads, measures and deletes every listed row
that has a verdict. Only vlogs count: titles that say vlog, day in my life, a week in… and not GRWM, haul, Q&A, podcast. New links from the thread come in from the branch without losing what the Mac already measured. Resumable: a row's `status` says how far it got. The
Mac's safety check only lets a command typed by her download videos, which
is why this is one line she pastes rather than something Claude runs.

## How a video is measured

`python -m taste.measure <file> --id S001` → `measurements/S001.json`:
the traits "Cut it like" already learns (`cutgrammar/style.learn`: pace and
shot lengths, transitions, beat alignment, music feel, look, frame, opening,
ending, words on screen where the Mac can read them) plus integrated
loudness. No AI calls. Links are downloaded on sarah's Mac (yt-dlp), measured
and deleted; this repo keeps numbers only — never a video, a recording or a
still of someone else's work.

Known: a screen recording carries the app's buttons over the picture, and
shot detection under that chrome under-counts cuts (her Oct 17 reference
read as 4 shots in 55 s). Recordings need the chrome cropped before they
count.

## How the fingerprint is used

`fingerprints/<group>.json` (once measured): the good side's ranges per
trait and how they differ from the ordinary side. It becomes the default
recipe every video is cut to (`remix.fingerprint` / vibes) and the standard
the AI self-check judges against. Uploads land in the project's shared
folder `taste/`; the CSVs here are synced from there.

## First house style (2026-10-21)

`python -m taste.fingerprint` → `fingerprints/long.json` (18 vlogs) and
`fingerprints/short.json` (7, thin). Videos whose typical shot is held over
6 s (someone sitting and talking) are listed as `held_out`, not averaged in.
`python -m taste.scorecard measurements/V001.json --group short` scores one of
VibeCut's own exports (V001 = "Your video 2026-10-19", V002 = "As it happened
2026-10-14 18.54", both on sarah's Mac): 4 and 6 of 17 traits inside.

## Shot by shot, for the taste model (2026-10-21)

The measurements above are one number per trait. The taste model
(`taste/model.py`) learns from how an edit unfolds, so every measured
video is also written down shot by shot (`taste/describe.py`): each
shot's length and how it joins the next (cut, jump cut, dissolve, dip,
flash), how much moves, whether a face looks into the lens, whether
someone talks or laughs or music plays, Vision's top three labels, and
where words sit on screen, how big and for how long. One file per video,
`descriptions/<id>.json`.

On sarah's Mac, from the repo root, on a try-out branch that has this
branch merged in (one line):

    cd ~/Desktop/VibeCut/repo && caffeinate -i .venv/bin/python -m taste.collect --only measure --describe --ai --cap 2.50 --train

- `--describe` downloads each measured video once more at 480p (the
  first five minutes of a long one), describes it and deletes it. Rows
  measured in the same run are described from that one download. S007
  was measured with the old decoder's timing (a variable-frame-rate
  file); its description is read with the fixed one.
- `--ai --cap 2.50` asks the AI editor (`taste/editor.py`, the course's
  OpenAI key in `web/.env`) to name each shot's job (hook, setup, step,
  payoff, talk…) and the chapters, from numbered contact sheets of one
  still per shot, while the frames still exist. Its estimate is printed
  before every call and the running total after; it stops before the call
  that would pass the cap. About 3¢ a short, 3–10¢ a long vlog, so the 33
  videos measured now come to about $2 [priors; the real cost is read from
  each reply]. Leave `--ai` off and nothing paid is called.
- `--train` retrains the model at the end (`python -m taste.model train`).
- How long: words are read with Vision's accurate recogniser (it reads
  Korean, Japanese and Chinese captions, which the fast one used for the
  measurements can't), several times slower: roughly a minute or two a
  short and several minutes a long vlog, so a few hours for the whole set
  [a guess, not yet timed; the first run took about 5 minutes a long
  vlog]. `caffeinate -i` keeps the Mac awake, but not with the lid shut;
  everything is resumable (a described video is never fetched or paid for
  again), one bad link is skipped, not fatal, and a download that fails is
  tried once more at the end of the run. A download given up on is stopped
  with everything it started (yt-dlp's own helpers and ffmpeg).
- `--cap` is for the whole set, not one run: every paid call is written
  to `descriptions/spend.jsonl` before it is sent (at the most it could
  cost) and again once its real cost is known, and a new run counts that
  first. A call is only made if its most still fits, and a video is asked
  at most once a run, so after a stop the same line can be run again and
  the total still stays under the cap.

What is kept: numbers and labels only. The words on screen are counted,
placed and dropped; what's said (English videos only, read by the Mac's
own recogniser) goes into the one AI call and is never written. The
editor's own short notes are kept, scrubbed of anything quoted. Video,
frames and sound are deleted after each video.

The descriptions and the trained model are JSON the repo keeps
(`.gitignore` lets `taste/*/*.json` through). The model file,
`taste/model/<group>.json`, is what turns the taste pick on in Make.

The first run on the Mac rebuilds the Vision helper (its source gained the
accurate `--text2` reader). If it doesn't build, the app falls back to
colours, and the collector writes no descriptions rather than ones with no
faces, labels or words — the log says so.

## How the model is built and used

- **What it learns from.** A trigram grammar over shot tokens (kind,
  length, join) and a logistic scorer trained on each real edit against
  copies the computer damaged one way (shuffled, evened rhythm, flashes,
  words on top…). Where a creator really has the habit (say, flashes), the
  damage is mirrored so the data, not the breaker, sets the weight's sign.
  The report (`model/<group>-report.md`) gives accuracy with a whole
  creator left out and with a whole kind of damage left out.
- **Roles.** The AI editor's shot jobs are distilled into a small role
  model, used only when it has at least 3 creators and beats the majority
  guess on an unseen creator by 0.1; otherwise roles stay unread.
- **Her own layer.** What she exports vs what Make made, her picks and her
  "would you post this?" answers move a small offset held near zero
  (`$VIBECUT_CACHE/taste/personal.json`, stamped to the model it was
  learnt against).
- **In Make** (`web/backend/tastepick.py`, rules path only, not the AI
  story editor's chapters): today's edit and up to 8 one-change versions
  (held opening, runner-up hook, rhythm by role, ending held 1 or 3 beats,
  strongest last, wide first, filming order) are described with
  `describe.from_board` (no rendering) and scored; another version wins
  only if it beats today's by `MIN_GAIN`. The choice is in
  `job.result["taste_pick"]` and one sentence of the reply. Off until
  `model/<group>.json` exists; `VIBECUT_TASTE=0` turns it off.
- **Fixed on the way.** `media.load` decodes on the nominal frame-rate grid
  (variable-frame-rate files were stretched about 2×, S007);
  `shots.jump_cuts` finds jump cuts inside a "shot"; Vision `--text2` reads
  captions accurately, CJK included.
- Every token threshold and every L2 strength is a prior. Tests:
  `test_taste_describe`, `test_taste_model`, `test_taste_editor`,
  `test_tastepick`, `test_media_vfr`, `test_jump_cuts`, `test_taste_collect`.

## First training (2026-10-21, on sarah's Mac)

31 videos described (23 long by 8 creators, 8 shorts by 4); the AI editor
read all 31 for $1.39 of the course key. L005 and L009 didn't download and
wait for the next run. Reports: `model/long-report.md`, `model/short-report.md`.

- **Long vlogs**: on a creator it never saw, it tells the real edit from a
  damaged copy 91% of the time. On a kind of damage it was never shown,
  only 29%: it knows the mistakes it was taught, not editing in general.
  Every change Make tries is one of those taught mistakes undone (rhythm,
  opening, ending, order), so the 91% is the number that matters there.
  The story-job model names a new creator's shots right 52% of the time,
  against 29% for always guessing the commonest job.
- **Shorts**: 66% on an unseen creator, from 4 creators, and no story-job
  model. Below `tastepick.MIN_LOCO` (75%), so Make doesn't let it choose:
  shorts stay as the rules cut them until more shorts are learnt.
- Strongest signals (long): music under as much of it as the good edits,
  words rarely at the top, neighbouring shots' lengths changing gradually,
  a varied rhythm, talk broken up by cutaways, few capitals, no repeats.

## Second training (2026-10-21, more shorts)

sarah: "lets train a few more short vlogs?". 13 more short-vlog creators
were listed (`data/candidate-creators.csv`); the run on her Mac found vlogs
for 9 of them (4 had none among their recent videos), read 26 shorts plus
the two long vlogs left over, and spent $0.89 (the set's total is $2.28 of
the $2.50 cap). Looking at what was read, 7 weren't vlogs (a sports
highlight, interviews, a skit, two one-shot clips, a sit-down Q&A): marked
`not a vlog` and left out, and Katie Feeney dropped as a creator. Retrained
without them (training here reproduces the Mac's to 1e-8):

- **Shorts**: 85% on an unseen creator, from 28 shorts by 12 creators (was
  66% from 8 by 4). Past `MIN_LOCO`, so Make now lets it choose for shorts
  too. Still no story-job model for shorts (55% against 50% guessing).
- **Long vlogs**: 90% on an unseen creator (24 by 8).


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

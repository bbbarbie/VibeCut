# Existing code for suggesting music (non-AI welcome) — research, 2026-09-25

Question from the product owner: is there an existing codebase that suggests
what music can go where? Licences and dates checked 2026-09-25 via GitHub/PyPI
and vendor pages. **(inference)** = researcher's judgement.

**Short answer:** several projects help, none replaces VibeCut's own
energy-shape matcher (`cutgrammar/music.py`). The useful ones are
MIT/ISC libraries that give real beats, downbeats and song sections to cut
to, plus Freesound for transition SFX. Every AI "pick music for this video"
system found is research-only or a closed cloud API.

## 1. Music analysis libraries (local, rule-based)

| Project | Licence | Maintenance | Gives | Fit |
|---|---|---|---|---|
| librosa | ISC | 1.0.0 (2026-08-11), active | tempo, beats, onsets, chroma, RMS, novelty for segmentation; no downbeats/labels | Drop into `music.py`: `onset_strength` + `beat_track` replace the hand-rolled tempo; beat grid for snapping. Offline |
| beat_this (CPJKU) | MIT (code + weights); some training data copyrighted | v1.1.0 (2026-04-14) | beats **and downbeats**, SOTA (ISMIR 2024), CPU, 78 MB / 8 MB small | Best upgrade for cutting on the downbeat; needs PyTorch → optional subprocess, cached per track (inference) |
| All-In-One / allin1 | MIT | upstream stale (2024-05); MIT Apple-Silicon port `ssmall256/all-in-one-mlx` pushed 2026-09-23 | tempo, beats, downbeats, **labelled sections** (intro/verse/chorus/bridge/outro) | Only source of "chorus starts here". Heavy (torch, NATTEN, Demucs); trained on pop — unproven on ambient vlog music (inference) |
| madmom | code BSD, **models CC BY-NC-SA 4.0** | last release 2018 | beat/downbeat/tempo | Avoid bundled models commercially |
| BeatNet | CC BY 4.0 | 2023 | beat/downbeat/meter | Superseded by beat_this (inference) |
| aubio | **GPL-3.0** | 2019 | onsets, tempo | Only as a separate process; redundant |
| Essentia + MTG models | **AGPL-3.0** + models **CC BY-NC-SA 4.0** | very active | best free mood tagging, danceability, arousal/valence, genres | Hardest legally; isolated opt-in subprocess or buy MTG licence; osx-arm64 import bug #1486 |
| basic-pitch | Apache-2.0 | 2025 | audio→MIDI | Not relevant |

## 2. Catalogs/APIs with metadata

- **Jamendo API** — free for non-commercial only; commercial needs a quote + per-track paid licence. Best free metadata (vocal/instrumental, speed, acoustic/electric, mood, genre, licence filters). Cloud; fits as an opt-in `TrackSource`.
- **Free Music Archive / FMA dataset** — code MIT, metadata CC BY 4.0, audio per-artist CC; no maintained API. Good for calibrating the matcher, not a catalogue.
- **ccMixter** — free query API; CC BY or BY-NC (filter NC out); small.
- **Pixabay Music** — no music API found; licence forbids standalone redistribution. Not integrable.
- **YouTube Audio Library** — no API; YouTube-focused licence. Not integrable.
- **Epidemic Sound Partner API** — proprietary; free prototyping tier, production by agreement; "video prompts" (music matched to a video's pace/vibe), length adaptation, similar-track search, 250k+ SFX, sublicensing. The only turnkey "suggest music for this video". Cloud.
- **Artlist Enterprise API**, **Soundstripe API** — proprietary B2B. **Uppbeat** — no public API.
- **Freesound API** (SFX) — API commercial use negotiated case by case; per-sound licence; CC0 filterable.

## 3. Spotify and replacements

Spotify removed Audio Features/Analysis/Recommendations for new apps on 2024-11-27 (403s); no official replacement. ReccoBeats (free, terms unclear, uploads break local stance), GetSongBPM (free with mandatory backlink), AcousticBrainz CC0 dump (shut down 2022; only for commercial songs with MusicBrainz IDs). None needed — VibeCut analyses the file itself.

## 4. "Match music to video" / "edit to the beat" projects

- **auto-editor** — public domain, active, now Nim; cuts silence/motion; no music features.
- **mugen** — MIT, 2023; librosa beats + MoviePy, cuts clips to beats; worth reading its event model, not adopting.
- Hobby librosa+MoviePy beat-sync repos — examples only.
- **Video2Music** (MIT) — *generates* music (off-positioning). **Diff-BGM** — no licence. **MuVi, MVPt/MuseChat, VM-NET/CBVMR** — research only.
- No maintained rule-based mood→music mapper exists; VibeCut should own a table (inference).
- **Remotion** — company licence above small teams; JS stack; not a fit (inference, not re-checked).

## 5. Transitions/SFX to beats

No dedicated library. Pattern: downbeats (beat_this/allin1) → snap cuts within a tolerance → riser ending on a section boundary / whoosh centred on the cut, from a small bundled CC0 set.

## Ranked recommendation

1. **librosa (ISC) in `cutgrammar/music.py`** — real beat grid for snapping (the next CLAUDE.md task). Adds scipy.
2. **beat_this (MIT) as an optional downbeat pass**, subprocess, cached — cutting on downbeats is the audible difference.
3. **allin1 via the MIT MLX port, opt-in**, for intro/chorus/outro boundaries (align the edit's peak to the chorus; riser before a drop). Judge labels on real libraries first.
4. **Bundled pack of ~20 CC0 transition sounds** hand-picked from Freesound — offline, no credit, no API negotiation.
5. **Jamendo as an opt-in cloud `TrackSource`** only with a commercial agreement; Epidemic Partner API as the paid alternative.

**Avoid:** Essentia (AGPL + NC models) unless licensed; madmom models; aubio; Spotify's removed endpoints; video-to-music generators.

## Sources
- https://github.com/librosa/librosa
- https://github.com/CPJKU/beat_this, https://pypi.org/project/beat-this/
- https://github.com/mir-aidj/all-in-one, https://github.com/ssmall256/all-in-one-mlx
- https://github.com/CPJKU/madmom
- https://github.com/mjhydri/BeatNet
- https://github.com/aubio/aubio
- https://github.com/MTG/essentia, https://essentia.upf.edu/models.html, https://github.com/MTG/essentia/issues/1486
- https://github.com/spotify/basic-pitch
- https://developer.jamendo.com/v3.0/tracks, https://devportal.jamendo.com/api_terms_of_use
- https://github.com/mdeff/fma
- https://ccmixter.org/query-api
- https://pixabay.com/api/docs/, https://pixabay.com/service/license-summary/
- https://support.google.com/youtube/answer/3376882?hl=en
- https://www.epidemicsound.com/business/developers/, https://developers.epidemicsound.com/
- https://developer.artlist.io/welcome, https://www.soundstripe.com/api
- https://freesound.org/help/tos_api/
- https://techcrunch.com/2024/11/27/spotify-cuts-developer-access-to-several-of-its-recommendation-features/
- https://reccobeats.com/docs/documentation/introduction, https://getsongbpm.com/api
- https://acousticbrainz.org/download
- https://github.com/WyattBlue/auto-editor, https://github.com/scherroman/mugen
- https://github.com/AMAAI-Lab/Video2Music, https://github.com/sizhelee/Diff-BGM

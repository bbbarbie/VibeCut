# What VibeCut learns from viral videos

*Lead product design, 2026-09-25. This builds on `design/research/01`–`05` and on four reports from this round: the niche taste library, evidence round 2, legal sources, and fingerprint feasibility. The taste library is appended after this document without edits. "§ Travel", "§ Food" and so on refer to its sections. External claims carry a URL, code claims name the file, and **[inferred]** marks my own judgement.*

---

## 1. The short answer

"Learn from all the viral videos online" can't mean what it sounds like, for two separate reasons.

**Legally, there is no bulk route to the videos.**
- TikTok's US terms ban any attempt to "scrape, crawl, export or otherwise extract any data or content… for any purpose" by automated means unless TikTok approves it in writing (https://www.tiktok.com/legal/page/us/terms-of-service/en).
- YouTube allows viewing "for your personal, non-commercial use", and downloading only where YouTube itself offers it (https://www.youtube.com/static?template=terms). Its developer policies ban downloading, scraping, and creating "derived data or metrics" (https://developers.google.com/youtube/terms/developer-policies).
- Douyin grants a personal, non-commercial licence and bans "爬虫抓取、模拟下载" (crawling, simulated downloads) (https://www.douyin.com/agreements/?id=6773906068725565448).
- TikTok's Research API answers "No" to commercial users (https://developers.tiktok.com/doc/research-api-faq).
- Every official API returns only metadata, or analytics about the account owner's own videos.

**Statistically, "viral" mostly measures who posted.**
- Adding video, audio and text features on top of creator and metadata features raises TikTok tier classification by about 0.4–3 F1 points (https://doi.org/10.1609/icwsm.v18i1.31405).
- Context, topic and channel alone explain R² = 0.77 of YouTube engagement (https://arxiv.org/abs/1709.02541).
- Technical quality correlates with engagement at only r = 0.07–0.31 (https://arxiv.org/abs/2410.00289).
- On Kuaishou, the top 0.1% of videos take 58.8% of views (https://arxiv.org/abs/2410.16058).
- YouTube now counts a view as soon as playback starts (https://support.google.com/youtube/answer/2991785).

A model trained on "viral vs. not" would therefore learn creators and topics, not craft [inferred].

**What "learning from viral videos" can honestly mean.** There are four things, all legal and all modest:
1. **A dated taste library**, written by people from public breakdowns, trend pages and studies. That is the 10 niches appended below. Captions reached "40+ AI Edit styles" the same way: each one hand-designed and named (https://captions.ai/styles).
2. **Learning from a video the creator loves**, using a file they already have, analysed on the Mac and reduced to numbers.
3. **The creator's own retention data**, through a platform login they approve (OAuth):
   - YouTube's `relativeRetentionPerformance` and `audienceWatchRatio` (https://developers.google.com/youtube/analytics/metrics);
   - Instagram's `reels_skip_rate` (https://developers.facebook.com/docs/instagram-platform/reference/instagram-media/insights).
4. **A licensed calibration corpus** that also does CLAUDE.md's threshold calibration (§5c).

The promise stays CLAUDE.md's "no amateur tells", extended to "and it reads like your niche". It never becomes "this will go viral."

**The repo contradicts this today.**
- `web/backend/reference.py` fetches pasted links with yt-dlp and keeps `source.mp4` "so a style can be re-learnt".
- `MatchStyle.tsx` ("paste a link to a video you love") and `Remix.tsx` ("TikTok, Reels, Shorts") invite links.
- `~/.cache/vibecut/references/` currently holds four YouTube Shorts downloaded this way.

yt-dlp belongs to the youtube-dl family that the RIAA targeted under DMCA §1201 (https://en.wikipedia.org/wiki/Youtube-dl). China's Anti-Unfair Competition Law, Art. 13, bans obtaining another business's data by getting around technical measures (https://zh.wikisource.org/wiki/中华人民共和国反不正当竞争法_(2025年)). Increment 1 removes the link path.

---

## 2. Cross-niche principles

A principle is kept only if it appears in at least 7 of the 10 niche sections, or rests on the robust evidence in §3.

| # | Principle | Niches | Evidence | Strength | What it changes in the engine |
|---|---|---|---|---|---|
| 1 | **The sub-style sets the editing rules; the niche alone doesn't.** | All 10 list sub-styles whose rules conflict: silent vs. chaotic DIML, raw log vs. velocity edit, podcast clip vs. Hormozi | https://filmora.wondershare.com/youtube-video-tips/lifestyle-video.html ; https://skinnedcartree.com/what-are-silent-vlogs.html ; https://www.writepanda.ai/blog/how-diary-of-a-ceo-edits-podcast-clips/ | Practitioners agree; no effect size | Sub-style becomes a required input (§4). `check_cut_on_motion` and `first_speech` depend on it (§ Day in my life #2) |
| 2 | **Moderate beats maximal.** Pace, sensation and effects each have a band | Travel (effects ≤ ~10% of joins), Fitness (≤ 3 effect types), Talking-head ("one engine"), Comedy (one punch-in), Chinese (剪映 kit), Aesthetic (flash cap), GRWM (hand wipe about once), Food (punch zooms dated), Family (one swell) | Inverted U for sensation (https://arxiv.org/abs/2604.19995), pacing (https://doi.org/10.1007/s10660-026-10193-6) and visual variation (https://doi.org/10.1177/00472875231219634). Exception: Douyin found no downturn in its range (https://doi.org/10.3390/jtaer20020069) | Robust for sensation; where pace peaks is unresolved | An effect budget per sub-style, reported as a number. `remix.py` pushes in on every shot (`PUNCH`), which breaks this in at least 5 niches |
| 3 | **The subject's own sound stays audible.** | Travel, Food, Fitness, Family, Comedy, Aesthetic, DIML, GRWM, Talking-head (dry audio) | Picture–sound energy match β = 0.22 (https://doi.org/10.3390/jtaer20020069). Spontaneous laughter makes jokes funnier (https://doi.org/10.1016/j.cub.2019.05.073). In travel, face plus voice together lift engagement (https://doi.org/10.1177/00472875251415384) | Moderate | Needs speech, music and event labels. SoundAnalysis runs on-device (https://developer.apple.com/documentation/soundanalysis/snclassifysoundrequest). `remix.ORIGINAL_GAIN = 0.12` suits a fast reel but is wrong for quiet niches |
| 4 | **Correct each clip first, then apply one bounded look. Never shift food, skin or landscape hue.** | Travel, Food, GRWM, Aesthetic, Family, DIML, Chinese, Comedy (no look at all) | Photo filters that raise warmth, exposure and contrast: +21% views (https://ojs.aaai.org/index.php/ICWSM/article/view/14622). Warm light makes food more appealing (https://ora.ox.ac.uk/objects/uuid:dba2e23a-1abd-432e-8c3a-1e8b0bfa0f1e/files/r8w32r625v). Teal-orange on landscapes reads as low effort (https://pixflow.net/blog/teal-and-orange-color-grading/) | Moderate; the evidence is mostly photos | `grade.Look` already clips shifts (`MAX_SHIFT`, `SAT_RANGE`) and uses one LUT per edit. Add per-sub-style guards, plus HLG tone-mapping before any look (`media.py` never reads `color_transfer`) |
| 5 | **The first seconds carry the most weight, but what goes there depends on the sub-style.** | Travel, Fitness, Comedy, GRWM, Talking-head, DIML, Food, Chinese. Exception: slow-living and process videos | Share still watching at 5 s tracks watch % at r = 0.926 (https://arxiv.org/abs/2410.00289). On-screen text in 67% of viral vs. 30% of non-viral videos, n = 400 (https://arxiv.org/abs/2111.02452). TikTok's "first 3 s" guidance cites no data (https://ads.tiktok.com/help/article/creative-best-practices?lang=en) | Robust that the opening matters; weak on what to put there | `select.choose()` already picks a hook. The kind of opener becomes a sub-style field: payoff, premise card, clock time, occasion card, or none |
| 6 | **Faces help, with conditions.** | Talking-head, GRWM, DIML, Comedy; Travel (only with the person's voice); Family (privacy reverses it) | Photos with faces: +38% likes (https://doi.org/10.1145/2556288.2557403). Larger faces help in brand video (https://doi.org/10.1108/jcm-01-2024-6526). Travel exception (https://doi.org/10.1177/00472875251415384) | Robust | `select.camera()` already rewards a face in `FACE_ON_CAMERA`. Add a face-plus-voice pairing for travel and a share-safe mode for children (§ Family #2) |
| 7 | **Real beats fabricated.** Text, dates, stats and slow motion come from the footage or the creator | Every niche except Talking-head | China's AI labelling measures (https://www.cac.gov.cn/2025-03/14/c_1743654684782215.htm). YouTube's inauthentic-content rule (https://support.google.com/youtube/answer/1311392?hl=en). Backlash to AI slop (https://www.kapwing.com/resources/the-tiktok-ai-slop-report/) | Strong as policy; effect on engagement unmeasured | Already the rule in `remix.captions()`. Extend it: `synthetic_frames` = 0, slow motion only from high-frame-rate source, date stamps only from metadata |
| 8 | **Trends expire; craft doesn't.** | DIML, GRWM, Aesthetic, Comedy, Fitness, Family, Chinese | "Quiet luxury" was considered outdated by Jan 2024 (https://en.wikipedia.org/wiki/Quiet_luxury). Great Meme Reset, Jan 2026 (https://en.wikipedia.org/wiki/Great_Meme_Reset) | Strong (observed) | Every label carries `first_seen`, `peak` and `review_by`. Rename "Quiet luxury" to "Quiet" |
| 9 | **The format decides captions, not fashion.** | Talking-head, Chinese, Comedy, Food (Korean subtitles), DIML, GRWM, Aesthetic | Captions aid comprehension in >100 studies (https://pmc.ncbi.nlm.nih.gov/articles/PMC5214590/). Burned-in captions: 0 of 502 long-form frames, but all 13 Shorts sampled (https://www.writepanda.ai/blog/youtube-videos-dont-burn-captions-study) | Robust for comprehension; weak for reach | Caption policy set by sub-style × format. Long YouTube exports get an SRT file instead of burned-in text |

**Not promoted:**
- **Beat-grid cutting as a default.** The four cached DIML references cut 61–75 times a minute, all hard cuts, and none of them on the beat grid (`design/research/05` §6). Yet `remix.quantise()` forces every cut onto the grid. That could be a real mismatch, or it could be the beat-phase bug (§5). We can't tell until Increment 1.
- **Loop seams** (no evidence; `03` §C).
- **Trending sounds** (only platform statements).

---

## 3. Robust vs. weak quantitative evidence

| Tier | Finding | Numbers | What VibeCut does with it |
|---|---|---|---|
| **Robust** | Editing adds only a little on top of creator and metadata | F1 +2.95 / 1.6 / −0.1 / 0.4 (https://doi.org/10.1609/icwsm.v18i1.31405); SRCC 0.660 → 0.710 (https://arxiv.org/abs/2509.02969) | No virality score. The promise is hygiene |
| Robust | Holding viewers through the first 5 s ≈ engagement | r = 0.926, 90k videos (https://arxiv.org/abs/2410.00289) | Put the most ranking effort into the opening shot. Use the 5 s hold as a calibration label |
| Robust | More cuts help, up to a moderate point | Douyin β = +0.27, squared term not significant (https://doi.org/10.3390/jtaer20020069). Inverted U on Kickstarter and in tourism videos. Eye tracking favours "short simple scenes" (https://doi.org/10.1007/s11747-025-01137-x) | Pace is a band per sub-style; Hype gets a cap |
| Robust | Moderate sensation beats maximal | Peaks at ≈ 3.2–3.4 on the study's scale (https://arxiv.org/abs/2604.19995). Vocal arousal β = 0.24, β² = −0.12 (https://doi.org/10.3390/jtaer20020069) | Effect budget; match music energy to picture energy |
| Robust | Faces help (travel is the exception) | See §2 row 6 | Face share and size become measurements |
| Robust | Engagement per view falls with length | Kuaishou like rate 9.3% at 10 s → 3.3% at ~1000 s (https://arxiv.org/abs/2410.16058). Duration best predicts watching to the end (https://doi.org/10.1145/3795513.3810457) | Length bands per format. Calibration labels must be normalised for duration |
| Robust | Captions help comprehension; text barely predicts engagement | Text features add < 1 F1 point. Overlay-heavy posts do worse unless the text is informative and fits the image (https://doi.org/10.1177/00222437251373042) | Captions exist to be understood, not to go viral |
| **Moderate** | Speeding up speech lowers satisfaction | Rated lower at 1.25× and 1.5× (https://pmc.ncbi.nlm.nih.gov/articles/PMC12675162/) | Never speed up talking. Food: speed up only silent filler |
| Moderate | Long-form shape | Emotion changing direction more often → more engagement (https://doi.org/10.1007/s11747-026-01147-3). Chapter progress bars make viewers more impatient (https://doi.org/10.1287/serv.2024.0172). A larger sponsored segment lowers engagement (https://doi.org/10.1080/10864415.2025.2515725) | Keep intros short; make chapter markers opt-in |
| Moderate | Travel snapshot | n = 20: saves outnumber comments 40 to 1; 60% of videos ≤ 15 s (https://orange142.com/blog/15-seconds-half-a-million-views-what-tiktoks-top-travel-content-actually-looks-like) | A "guide" proposal built to be saved |
| **Weak / none** | Loops, whether trending sounds cause reach, eye contact, effect size of the first 1–3 s | No usable study | Measure nothing and claim nothing |
| Usage, not performance | OpusClip, 13.5M clips: captions 80.2%, transitions 2.4% | https://www.opus.pro/research/video-editing-guide-short-form | Shows what people use, not what works |
| Discard | "Captions lift retention 25–40%", "80% fail by 3 s" | Unsourced | Don't cite them |

**What this means for the taste library.** None of its numbers has an effect size behind it. They are priors with the same status as the thresholds in `grammar.py`. The Douyin study's follower statistics don't add up (SD 9.4k over a range of 11k–1.38M), so treat its β values with care.

---

## 4. Structure vs. surface

A vibe has two layers:
- **Structure**, set by the niche sub-style: what is in the video, in what order, for how long, where the cuts land, what you hear, and what the text says.
- **Surface**, set by the preset: how all of that looks and sounds on top.

The library's "premium vs. cheap" lists are mostly about structure (timing, sound, restraint). Its "dated" lists are mostly about surface (fonts, filters, named aesthetics) [inferred]. Structure lasts; surface dates.

| Field | Set by | Example values | Code that already holds it |
|---|---|---|---|
| Spine | Sub-style | time, place, subject (built); process, guide list, then/now, highlight order (new) | `storyboard.py` axes |
| Length band | Sub-style × format | DIML short 15–60 s; podcast clip 60–140 s | `remix.DEFAULT_LEN` |
| Pace band and arc | Sub-style | median, p10/p90, 5-bin curve | `style.pace`, `remix.fingerprint`, `restyle.targets` |
| Cut point | Sub-style | on the action · after the action · at a speech pause · on a performed transition · on the downbeat | `select.window` (on the action only) |
| Hook | Sub-style | payoff, premise card, clock time, occasion card, none | `select.choose`, `check_opening` |
| Sound lead | Sub-style | music / voice / the scene's own sound / dry voice | `remix.ORIGINAL_GAIN`, `MUSIC_GAIN` |
| Caption policy | Sub-style × format | none, diary, 1–4-word groups, premise card, SRT only | `remix.captions`, `talk.py` |
| Effect budget | Sub-style | share of soft joins, number of punch-ins, SFX per 30 s | `restyle.transition_policy` (`HABIT_SHARE`) |
| Look | Surface, within sub-style guards | a `grade.stats` target | `grade.Look`, `reference.fit_look` |
| Transition flavour | Surface, only where the structure allows a soft join | dissolve / dip to black / flash | `restyle.transition_policy`, `export.py` |
| Type | Surface | font family, case, weight, position band | `remix._layout`, `overlays.py` |
| Music palette | Surface | tags, BPM range, energy arc | `remix.MOODS`, `openverse.py`, `music.py` |
| Texture and frame | Surface | grain, letterbox (horizontal video only) | the letterbox check in `reference.card` |

**How the layers combine**
1. **Structure caps surface.** A surface can only spend the effect budget its structure grants. Y2K on a silent-vlog structure gets Y2K's type and palette, not its zoom punches.
2. **Sub-style guards can veto part of a surface.** Cinematic's teal shadow split is set to 0 on food (§ Food #3) and landscapes (§ Travel #1). Bars never go on 9:16 video; `reference.card` already enforces this.
3. **Compliance belongs to neither layer**, and no preset can switch it off:
   - disclosure cards (§ GRWM #6);
   - child privacy (§ Family #1–2);
   - AI labels (§ Chinese #4).
4. **The creator can override structure and surface**, but not compliance.

**The seven presets from research 01, as surfaces:**

| Surface | Typical sub-styles | Guards |
|---|---|---|
| Cinematic | Travel cinematic montage, slow travel; Aesthetic film; Fitness hybrid series | No teal-orange on food, foliage, sea or skin; bars only on horizontal video; export at the source frame rate for 24p (§ Aesthetic #6) |
| Cozy | Silent DIML; Food silent kitchen; Family slow-home; Chinese 田园 | The scene's own sound leads; no punch-ins |
| Clean | Talking-head minimal and edu; GRWM editorial; DIML minimal; Travel guide | One emphasis mechanism per video |
| Film/VHS | Aesthetic digicam and 2016 revival; Chinese CCD风 | Flash look only on real flash or night clips; date only from metadata; ≤ 3 flashes/s (https://www.w3.org/WAI/WCAG21/Understanding/three-flashes-or-below-threshold.html) |
| Y2K / Playful | Comedy (opt-in); DIML and GRWM chaotic; photo dump | Not in tribute mode; meme SFX only when the irony is the point |
| Quiet luxury → rename **Quiet** | GRWM editorial and CBK; Aesthetic CBK; DIML reflective | Name gets a `review_by` date |
| Hype | Fitness phonk, velocity and highlights; Travel run-and-gun | Cap the cut rate; slow motion only from high-frame-rate source |

Ten niches × 3–13 sub-styles × 7 surfaces makes several hundred combinations, and most of them are invalid. So the product asks for the sub-style first, then offers 2–3 compatible surfaces [inferred].

**One data shape for everything.** A sub-style is stored in the same shape `remix.fingerprint()` returns (`median_s`, `curve`, `spread`, `hook_s`, `bpm`, `arc`, `duration`), plus the new structure fields. A library prior, a single learned reference, and several pooled references then all run through the same `restyle.apply` and `remix.plan_shots` path.

Today, `remix.py` is one hard-coded sub-style, the fast DIML reel:
- `TAG_TEXT` = "a day in my life";
- upbeat-pop `MOODS`;
- tempo 100–130 BPM;
- a push-in on every shot;
- the phone's own sound at 12%.

Moving those constants into a sub-style record is the first refactor.

---

## 5. How VibeCut keeps learning

**What already exists** (read from the repo, 2026-09-25):

| Piece | What it does today | What it's reused for |
|---|---|---|
| `cutgrammar/style.py` `learn()` | Reads pace, transitions (cut, dissolve, dip, flash, fades), beat, music arc, look and frame. Each trait names its evidence and reads `pending` when the media lacks it | Reference fingerprints; corpus measurement |
| `cutgrammar/grade.py` | `stats()` measures a look. `Look` fits a bounded tone curve, cast, split tone and saturation. Writes one `.cube` LUT | Surface looks; hue guards |
| `web/backend/reference.py` | Takes a file or a yt-dlp link. `card()` says what can be borrowed and why not; also `music_matches()`, `fit_look()`, `make_op()` | Steps 1–5 below, with the link path removed |
| `web/backend/restyle.py` | The `apply_style` op: retimes pace along the reference's arc, snaps to the beat, applies the transition policy, LUT and bars. Undoable and replays exactly | Applies both learned styles and library styles |
| `web/backend/select.py` | Hero score from craft, label rarity, face, subject and motion. Spreads picks over sessions, removes near-repeats, picks the hook, and sets a window that cuts on the action | Niche-aware selection; cut-point policy |
| `web/backend/remix.py` | Pools several references by median, picks Openverse music and finds its drop, quantises to the beat, writes captions from metadata, renders | The multi-reference pipeline and the sub-style pipeline |
| `web/backend/preferences.py` | An edit becomes a candidate rule; only the creator confirms it | "Save as my style" |
| Tests | `test_style`: fixtures that differ in exactly one respect. `test_restyle`: apply → render → re-learn must read back. `test_select`: each weight moves the choice. `test_remix`: pooling isn't stretched by one outlier | The verification pattern for each increment |

**Readings that are wrong today** (fingerprint report; `design/research/05`):
- **Beat:** remix v8 was cut exactly to 0.46 s beats but reads 0% on the grid. The estimated beat phase is 0.385 s against 0.028 s in the cuts.
- **J/L cuts:** the same picture edit reads 4%, 35% or 70% hard-synced depending on the track under it.
- **First voice:** it comes from the level-based `speech_mask`, which hears music as talking.
- **Whips:** they fall below the `shots.detect` floor of 0.28.

No reference can be trusted until the first three are fixed.

### (a) "Learn from a video I love"

1. **Drop a file.** A pasted link opens in the browser with the hint "save it with the app's own button, then drop the file here". The creator marks where it came from: *mine*, *licensed*, or *saved for personal reference*. The last matches the "personal, non-commercial" wording in the YouTube and Douyin terms (URLs in §1). This reuses `reference.start` without `_fetch`.
2. **Read it once.** `media.load(limit_s=600)` → `style.learn()`, plus three new readings:
   - a SoundAnalysis timeline of speech, music and laughter;
   - on-screen captions via Vision OCR (https://developer.apple.com/documentation/vision/vnrecognizetextrequest) at `.accurate`, 2–4 fps and 540p, taken from the same decode (9 of 9 captions found, 0 false positives);
   - IQR, nPVI and the number of cuts in the first 3 s.
3. **Keep the numbers, delete the file.** Write `style.json`, then remove the source. The cost: when `style.VERSION` changes, the creator has to drop the file again [inferred: acceptable].
4. **Show the card with the niche.** `reference.card()` already lists each trait, how it would be applied, and why it can't be. Add two things:
   - the nearest library sub-style ("closest to: silent / slow-living DIML");
   - a warning wherever copying would break a guard, e.g. "flashes on 40% of joins, copy that?" (§ Travel #3), or "this grade is cooler than your food shots allow" (§ Food #3).
5. **Apply as one undoable turn.** `make_op` → `restyle.apply`; `restyle.describe` writes the diff lines. All of this exists.
6. **Several references become one style.** `remix.fingerprint()` already takes medians. When the references disagree widely (median shot length differing by more than 3× across them [inferred]), say so and ask which to follow.
7. **Keep it only if asked.** When the creator reuses a learned style on a second video, offer "save as my style". This is a `long_term` candidate in `preferences.py`, which needs the rule plus when it applies and when it doesn't.
8. **Close the loop (opt-in).** After posting, show the creator's `relativeRetentionPerformance` or skip rate next to the edit's fingerprint. Compare only within their own videos.

### (b) Niche-aware auto-edit

1. **Guess the niche from signals the index already has.** These are simple rules, not a trained model [inferred]:
   - Vision labels (1,303 classes: https://developer.apple.com/documentation/vision/classifyimagerequest);
   - face share;
   - speech coverage (`vibespeech`, and SoundAnalysis after Increment 1);
   - the motion distribution;
   - the time span and GPS spread of the shoot;
   - source frame rate.
2. **Ask one question, with the guess preselected.** For example: "Looks like a day-in-my-life without talking. Closest: silent · chatty · chaotic · minimal?" The question is required, for two reasons:
   - the sub-styles flip rules (§ DIML #1);
   - labels can't separate beauty steps: Vision's only beauty label is `cosmetic_tool` (§ GRWM, measurable #7).
3. **The sub-style record sets everything downstream:**
   - the storyboard axis;
   - `select.py` settings (cut point, weights `W`, kind of hook);
   - the constants `remix.py` currently hard-codes;
   - which grammar checks run, which are inverted, and which read `pending`.
4. **Offer 2–3 compatible surfaces.**
5. **Report against the sub-style's band, not a universal one.** For example: "median shot 0.7 s, inside the fast-DIML band (a prior, not yet calibrated)".

### (c) A calibration corpus that is also CLAUDE.md's calibration

| Tier | Source | Licence and handling | What it's for |
|---|---|---|---|
| Gold | 20–40 paid creators: raw clips + finished edit + retention export | Written licence covering derived measurements and commercial use | Raw→edit pairs show what editors choose (this calibrates `select.py`). Comparing within one creator removes the creator effect |
| Silver | FineVideo's vlog, travel and lifestyle videos (https://huggingface.co/datasets/HuggingFaceFV/finevideo) | Per-video CC-BY with an attribution log; honour removal requests. Ignore its LLM-written editing notes (https://huggingface.co/blog/fine-video) | Distributions per sub-style; views are only a weak label |
| Research checks only | SnapUGC, Shot2Story, KoNViD-1k, VADB, SoccerNet | Non-commercial, unstated or under NDA | Check that a measurement separates good from bad. Never ship numbers from these |
| Human trend log | TikTok Creative Center Top Ads (https://ads.tiktok.com/business/creativecenter/inspiration/topads/pc/en); YouTube `mostPopular` metadata kept ≤ 30 days; Instagram Edits Inspiration | Read by people, never collected by software | New dated entries in the taste library |

**Protocol.** This is CLAUDE.md's 20 good / 20 bad, run per sub-style:
1. **Start with three sub-styles:** fast DIML reel, silent/slow, talking-head short. They cover the most niches and have the most code already [inferred]. That means about 120 edits from about 30 creators.
2. **Label "well cut" without using views.** Use two labels:
   - within each creator, the top vs. bottom third by duration-normalised retention;
   - a blind pairwise judgement by 3 editors of "which one has amateur tells" [inferred].
3. **Measure.** Run `analyze` and `style.learn` over every edit. For each metric, the well-cut p50 becomes the prior, and p10–p90 becomes the warn band.
4. **Ship a threshold only if it passes both tests:**
   - it separates well-cut from not on creators held out from fitting (report the AUC);
   - its discrimination fixture passes.
5. **Record where each constant came from**, next to it in code.

### (d) What never to do

- **Never download from a link.** No yt-dlp, no scraper, no "import from TikTok" button (§1 sources).
- **Never pool fingerprints of other people's videos** into a shared library or onto a server. That is the step closest to *Thomson Reuters v. Ross* (https://www.ded.uscourts.gov/sites/ded/files/opinions/20-613_5.pdf) and to YouTube's ban on derived metrics. Library priors are written by people.
- **Never let a reference's frames or audio reach an export.** This is already the rule.
- **Never show a virality score.** OpusClip doesn't disclose what its score is based on (https://help.opus.pro/docs/article/virality-score).
- **Never ship thresholds taken from non-commercial datasets or LLM-written labels.**
- **Never generate frames:**
  - no interpolated slow motion on children or animals (§ Family #6);
  - no fake flash, date stamp or film roughness (§ Chinese #10).
- **Never write claims for the creator.** Calories, weight lost, stats and occasions come from them (§ Food #2, § Fitness #6 and #10).
- **Never use data from the TikTok Research or Commercial Content APIs**, and never use scraped TikTok datasets from Hugging Face.
- **Never let a fixer act on library priors that haven't been calibrated** (CLAUDE.md).

---

## 6. Build plan: the first three increments

**Increment 1: honest references.**
- **Scope:**
  - Remove the link path from `reference.py`, `MatchStyle.tsx` and `Remix.tsx`. Add file drop and the provenance mark. Delete the source file after learning, and purge the cached `source.mp4` files.
  - Fix the three wrong readings:
    - beat alignment from the vector strength of cut times against the beat period, with no audio phase needed;
    - J/L verdict `pending` when SoundAnalysis says music dominates;
    - first voice from SoundAnalysis.
  - Add IQR, nPVI, cuts in the first 3 s, cuts per 10 s, edit grid, loudness range and true peak to `style.learn`, and bump `VERSION`.
- **Reuses:** `style.learn`, `evidence`/`grammar.NEEDS`, `reference.card`, `restyle.apply`.
- **How we verify it:**
  - One picture edit under three tracks must give the same J/L reading. Today it gives 4%, 35% and 70%.
  - A beat-cut fixture whose track phase is offset 0.4 s must still read as on the beat. Vector strength was about 0.7 against about 0.19 by chance in the report.
  - On a music-only fixture, no speech is found.
  - A URL is rejected, and no media file remains after learning.
  - **The metric must move when the edit improves:** quantising a jittered edit onto the grid must raise the beat reading, and the J/L reading may change only when the audio offset changes.

**Increment 2: sub-style as data, starting with the quiet/fast split.**
- **Scope:**
  - Dated sub-style records in the fingerprint shape plus the structure fields.
  - The `remix.py` constants move into a "fast DIML reel" record.
  - Add a "quiet" record covering silent vlog, slow living, silent kitchen and process. Its rules:
    - cut after the action, as a new `select.window` policy;
    - no punch-ins;
    - the scene's own sound leads;
    - soft joins only between parts;
    - diary captions built from metadata.
  - New finding `cut_mid_action` (needs motion; reads `pending` under `load_index`).
  - The one-question niche prompt.
  - Rename "Quiet luxury" to "Quiet".
- **How we verify it:**
  - A fixture cut mid-action vs. 0.5 s after the motion settles: `cut_mid_action` must separate the two and recover the offset.
  - A round trip in the style of `test_restyle`: apply quiet → render → re-learn. It must read back with longer shots, no flashes or punch-ins, and native sound leading.
  - On the same shoot, the quiet edit's `cut_mid_action` share must be below the fast edit's.
  - Five creators compare quiet vs. the current remix blind, on their own footage. Report the raw counts.

**Increment 3: calibration pilot on the fast DIML reel.**
- **Scope:**
  - The first ~10 gold creators, plus FineVideo's vlog subset.
  - A `calibrate.py` script that writes a p10/p50/p90 distribution for each metric.
  - The fast-DIML priors are replaced with these numbers, with where they came from recorded in code.
  - YouTube Analytics OAuth for gold creators only.
- **How we verify it:**
  - Each threshold separates well-cut from not on held-out creators. Drop any metric with an AUC near 0.5.
  - Test one hypothesis, written down in advance: within each creator, edits closer to the band retain better. If they don't, keep the band as a *description of the style*, not a quality gate.
  - Every existing discrimination test still passes.

**Deferred:**
- the other six surfaces as a `Preset` object;
- zoom, whip and punch-in detection, which stays `pending` until real positive examples exist;
- the other eight niches' records, shipped labelled "uncalibrated prior".

---

# Appendix: taste library (10 niches)

*One section per niche, each written from that niche's skeptic-reviewed takeaways (222 kept, 13 dropped). 'Weaken' verdicts appear in their corrected, weaker form.*

### Travel

**Sub-styles creators recognise**
- **Cinematic transition montage ("Kolder-style"):** drone shots, speed ramps and seamless whip transitions. Reads as 2016–2019 when overdone. https://fstoppers.com/vfx/art-creating-captivating-travel-films-210692
- **Run-and-gun fast cut (Brandon Li school):** cuts matched on shape, colour or luma, punch-ins, and "mini films within a big film". https://alphauniverse.com/stories/pro-tips-for-epic-travel-films/
- **Human-story documentary:** built around one person rather than one place. Drew Binsky says his "sleepless man" video has ~100M views (his own claim). https://www.kajabi.com/blog/drew-binsky
- **Street-food vlog:** food-led, authenticity over polish, contrast framing (Mark Wiens, Best Ever Food Review Show). https://air.io/en/creators-spotlight/21-most-popular-youtube-travel-vlogs
- **City guide / micro-itinerary:** "48 hours in X", numbered places. Made to be saved. https://wandervlogs.com/blog/top-travel-trends-from-youtube-creators-in-2025
- **Budget / versus reels:** "$50 a day in Bali vs Albania", real prices on screen. https://viryze.com/blog/tiktok-travel-trends-2026
- **Hotel room tour / review:** a whole sub-niche (Walk With M Tim, ~997K average views). https://creatordb.app/blog/top-travel-influencers/
- **Faceless reel:** scenery with place names, coordinates, route maps and running counters. https://flowshorts.app/faceless-reels/travel
- **Constraint series:** a visible counter drives the story (Ryan Trahan's "50 States in 50 Days"). https://en.wikipedia.org/wiki/Ryan_Trahan
- **Slow travel / slow TV:** long takes with natural sound; window-seat train rides and walking tours. https://en.wikipedia.org/wiki/Slow_television

**What to apply** (strongest first)
1. **Grade so the place still looks like itself.** No teal-orange on foliage, sea or sky; it is still fine for city night. Correct each shot's white balance and exposure to its chapter before any look goes on. Travel bands: hue shift ≤ 5–8° and saturation ×0.9–1.2 on landscape shots [inferred]. https://pixflow.net/blog/teal-and-orange-color-grading/ ; https://www.hasanabdulla.co.uk/2026/06/18/what-makes-a-video-look-cinematic/
2. **"Guide" proposal built for saves.** 3–7 numbered places (one `by_place` cluster each, 2–4 shots per place), ending on a 1.5–2.5 s recap card [inferred durations]. In the top 20 travel TikToks, saves outnumbered comments more than 40 to 1 (n=20). https://orange142.com/blog/15-seconds-half-a-million-views-what-tiktoks-top-travel-content-actually-looks-like
3. **One signature transition, at a real boundary.** Effect transitions on ≤ ~10% of joins [inferred], and only at a place, day or indoor↔outdoor change. When `style.learn()` finds a reference above `HABIT_SHARE`, report it as "transition-heavy" and ask the creator before copying the habit. https://x.com/samkolder/status/1100823677652946946
4. **Cut on matched luma, hue and position.** Use luma-centroid, dominant-hue and mean-luma distance between the end of shot A and the start of shot B to pick cut points and break ties. Never reorder a chapter against chronology. https://www.iso1200.com/2017/02/5-fast-tips-for-fast-cut-editing-brandon-li.html
5. **Normalise drone log and HLG footage before any look.** Drones like the DJI Mini 4 Pro record HLG / D-Log M. A flat clip next to a phone clip is exactly the consistency tell VibeCut promises to remove. DJI's 100/200 fps files also play back as slow motion, so an ffprobe fps check alone misclassifies them for speed ramps. https://www.dji.com/mini-4-pro/specs
6. **Reconcile clock time zones before building any time axis.** Many cameras store local time instead of UTC, and `parse_when` currently shifts bare stamps into the Mac's own zone. Estimate a per-device offset from iPhone clips or GPS; mark clips that can't be resolved `pending`. Offer an "N hours in {place}" title only when the corrected span supports it. https://exiftool.org/TagNames/QuickTime.html
7. **Don't open a short on a slow establishing wide.** Keep a low-motion landscape or aerial clip out of shot 0 (below the shoot's 25th percentile of motion [inferred]) and move it to shots 2–4, under the place title. https://viryze.com/blog/tiktok-travel-trends-2026
8. **Ration aerials.** An aerial must show what the ground can't: ≤ 2 in a row, ~15% of runtime [inferred]. Offer letterbox only on footage framed for it. https://www.hasanabdulla.co.uk/2026/06/18/what-makes-a-video-look-cinematic/
9. **Keep the place's own sound under the music.** 1–2 times a minute, duck the music for 1.5–4 s under a non-speech place sound (bells, waves, vendors) [inferred]. https://realitybox.in/the-role-of-sound-design-in-travel-films-why-immersive-audio-matters-a-practical-workflow/
10. **Show "{PLACE}, {COUNTRY}" once per place cluster, after the hook.** Fill it offline from GPS using GeoNames (CC BY 4.0, credit required), editable by the creator. https://flowshorts.app/faceless-reels/travel ; https://www.geonames.org/about.html

**Premium vs cheap**
- Premium: transitions mark only a change of location, time or mood (https://spliceapp.com/blog/common-travel-day-vlog-editing-mistakes-to-avoid/). Joins follow a dominant shape, colour or luma (https://www.iso1200.com/2017/02/5-fast-tips-for-fast-cut-editing-brandon-li.html). "Color carries geography" (https://www.lafilm.edu/blog/everything-is-beige-now-flattening-contemporary-color/). Ambience is kept because some of it can't be recreated with foley (https://alphauniverse.com/stories/pro-tips-for-epic-travel-films/).
- Cheap: an effect on every cut. Li: "the worst ones use trendy filmmaking techniques to resuscitate dull footage." http://thetravelvideoawards.com/spotlight_article/brandon-li-a-new-kind-of-film-school/
- Cheap: a LUT on uncorrected footage, fake letterbox bars (https://www.hasanabdulla.co.uk/2026/06/18/what-makes-a-video-look-cinematic/), heavy filters and over-polished editing (https://matadornetwork.com/read/how-to-create-compelling-travel-tiktok-video/).

**Dated / overused in 2026**
- Slow cinematic establishing openers; "15 countries in 30 days" speed tourism. https://viryze.com/blog/tiktok-travel-trends-2026
- Teal-orange on landscapes, which audiences now link with low effort. https://pixflow.net/blog/teal-and-orange-color-grading/
- Excess transitions and effects. https://www.opus.pro/blog/short-form-video-trends-reshaping-creator-marketing-2026
- Drone for the sake of drone. https://www.hasanabdulla.co.uk/2026/06/18/what-makes-a-video-look-cinematic/

**Measurable by VibeCut?**
1. Grade: **yes**. Per-shot hue, saturation and exposure spread on the 48×27 grid.
2. Guide: **no**. It is a structure; whether it works shows up in saves, not in the media.
3. Transition share: **yes**. `style.learn()` already counts it.
4. Luma/hue match: **yes**. Screen direction: **later** (needs optical flow).
5. Log/HLG: **yes** for HLG (ffprobe `color_transfer`); **later** for log, since low contrast and saturation is only a heuristic [inferred].
6. Time zones: **yes**, at meta evidence level.
7. Opening: **yes**, with motion from `load()`. Under `load_index()` the finding is `pending`.
8. Aerials: **yes**. Metadata or labels plus runtime share.
9. Place sound: **later**. The level-based `speech_mask` reads music as speech; needs a real VAD.
10. Place title: **no**. It is generated, not measured.

### Day in my life (DIML)

**Sub-styles creators recognise**
- **Silent / slow-living** (Her 86m2, about 2.28M subscribers; Haegreendal): no talking, natural light, muted colour, and household sound carries the mood. https://skinnedcartree.com/what-are-silent-vlogs.html
- **ASMR routine** (Emily Mariko, 12.4M TikTok followers): wordless cooking and cleaning, hands and process, "soothingly organized". https://en.wikipedia.org/wiki/Emily_Mariko
- **5-to-9**: the hours after work, "Emily Mariko-esque, almost ASMR-style". #5to9 has 13M+ views. https://www.bustle.com/life/what-is-the-tiktok-5-to-9-routine
- **Whispered voiceover, cooking from scratch** (Nara Smith): a soft voiceover recorded at night after the shoot (https://singjupost.com/transcript-of-nara-smith-interview-call-her-daddy-podcast/), an ambient or jazz music bed, and a recurring sonic jingle. https://chosenvesselstudio.substack.com/p/nara-smith-the-sonic-branding-maestro
- **Poetic voiceover** (BestDressed): cross-dissolves and a warm grade. **Reflective** (Lavendaire): soft grade and slow motion. **Minimal** (Catherine Manning): clean cuts plus time-lapses. https://filmora.wondershare.com/youtube-video-tips/lifestyle-video.html
- **Chaotic-comedic** (Emma Chamberlain, 12M subscribers): jump cuts, sudden zooms, on-screen commentary. https://en.wikipedia.org/wiki/Emma_Chamberlain
- **GRWM** (Alix Earle, 8.5M TikTok followers): tells the story of her day to camera while doing her makeup. https://en.wikipedia.org/wiki/Alix_Earle
- **Great Lock-In**: habit-list overlays, 6am starts, check-offs. https://www.bustle.com/wellness/what-is-the-great-lock-in-2025-meaning-ideas-tiktok
- **Reali-TEA / real day**: keeps the low moments, as culture "shifts away from polished fantasy". https://newsroom.tiktok.com/introducing-tiktok-next-2026-our-trend-forecast-for-marketers-for-the-year-ahead?lang=en
- **Study-with-me**: a centred Pomodoro timer (https://gridfiti.com/aesthetic-study-timers/) over rain, café or keyboard ambience. https://www.flexclip.com/learn/study-with-me-video.html
- **Digicam**: the Kodak Charmera look, 1440×1080 at 30 fps. https://en.wikipedia.org/wiki/Kodak_Charmera

**What to apply** (strongest first)
1. **The creator's sub-style must be a required input, because the grammar rules change with it.** "Lifestyle" covers at least four editing styles with opposite rules:
   - chaotic: quick cuts, speed changes, stickers
   - poetic voiceover: dissolves, warm grade
   - reflective: slow motion
   - minimal: hard cuts, time-lapses

   Per-style numbers stay [inferred] until `style.learn()` has run on references the creator supplies. https://filmora.wondershare.com/youtube-video-tips/lifestyle-video.html
2. **In slow mode, cut after the action finishes.** Silent vlogs "let moments breathe" and are wordless by design. `check_cut_on_motion` would mark their cuts BAD, and `first_speech` should return `pending` instead of a verdict. Target: at least 60% of cuts land within 0.5 s after motion drops below 30% of the shot's peak [inferred]. https://skinnedcartree.com/what-are-silent-vlogs.html
3. **Store trends as dated data, never inside presets.**
   - Fields: `first_seen`, `expires` (60–90 days [inferred]), `sound_bound`, a text template.
   - Add a recurring `season`. The Lock-In ran 1 Sep–31 Dec 2025 (https://www.bustle.com/wellness/what-is-the-great-lock-in-2025-meaning-ideas-tiktok).
   - Hide expired entries rather than delete them.

   https://www.ramd.am/blog/trends-tiktok
4. **Name presets by feel, not by trend.** "Quiet luxury" was already considered outdated by January 2024. Keep its parameters, rename it ("Quiet"), and add `trend_peak` and `status` fields to preset metadata. https://en.wikipedia.org/wiki/Quiet_luxury
5. **In silent mode, native audio leads.**
   - Music is absent or low, and foley is never ducked.
   - Trims never clip a sound event. The onset comes at least 0.2 s after the in-point and the decay ends before the out-point [inferred].
   - This is blocked on a real VAD, because the level-based `speech_mask` reads foley as voice.

   https://skinnedcartree.com/what-are-silent-vlogs.html
6. **No digital silence inside the mix.** Flag any gap over 250 ms below −60 dBFS [inferred]. Fill it with a crossfaded loop of the quietest non-silent 2 s from the same clip. Recording room tone per location is standard practice. https://vloggingpro.com/vlogging-tips/
7. **Optional clock-time opener.**
   - Format: "{h:mm am} · {premise}", at most 7 words, on screen 0–2.5 s.
   - The time comes from `media.capture_time` (zone-aware). If a clip has no timestamp, drop the time.
   - That a clock time works better than other hooks is [inferred].

   https://www.bustle.com/life/what-is-the-tiktok-5-to-9-routine
8. **A short DIML runs morning to night by capture time, 15–60 s.** Report `loop_seam_distance` (last shot against first) without a verdict until it is calibrated. https://www.latestly.com/india/information/a-day-in-my-life-viral-trend-what-it-is-and-why-its-growing-7607971.html
9. **"Real day" is opt-in.** The creator tags the low moments (a mess, a failed attempt) at the human gate. Pick them by content, never by a low bestframe score. It stays opt-in because mainstream DIML is still "carefully edited highlight reels" (same LatestLY link). https://newsroom.tiktok.com/introducing-tiktok-next-2026-our-trend-forecast-for-marketers-for-the-year-ahead?lang=en
10. **A long YouTube DIML exports its time-of-day parts as chapters.** YouTube requires the first chapter at 00:00, at least 3 in ascending order, and each at least 10 s long. https://support.google.com/youtube/answer/9884579?hl=en

**Premium vs cheap**
- **Grade.** Premium edits use one grade on every clip (https://vloggingpro.com/vlogging-tips/). Cheap edits let each clip keep its own camera look [inferred].
- **Timing and sound.** Premium edits let actions finish before the cut, and you can hear the pours and page turns. Cheap edits cut mid-gesture and leave dead silence between clips [inferred]. https://skinnedcartree.com/what-are-silent-vlogs.html
- **Voice and effects.** Premium edits have a soft voice or none, over ambient or jazz (https://chosenvesselstudio.substack.com/p/nara-smith-the-sonic-branding-maestro). Cheap edits paste stickers, zoom punches and speed ramps onto slow-living footage; those belong to the chaotic sub-style. https://filmora.wondershare.com/youtube-video-tips/lifestyle-video.html
- **Polish.** Premium edits keep some reality visible. Cheap edits have an over-smoothed, over-saturated "AI polish". https://www.euronews.com/culture/2025/12/17/ai-slop-clean-girl-aesthetic-and-clutter-2025s-biggest-cultural-trends

**Dated / overused in 2026**
- The bright-white, desaturated clean-girl look ("a moving Pinterest board"), now called "joyless". https://shopping.yahoo.com/beauty/makeup/articles/2025-killed-clean-girl-194432306.html
- The CapCut intro: typewriter title, typing sound effect and boxed timestamp. The two DIML templates have 256.7K and 141.7K uses, so it should never be our default intro. https://www.capcut.com/explore/Day-in-my-life-video-template
- "Romanticize your life", now giving way to #TheGreatLockIn and Reali-TEA. https://newsroom.tiktok.com/introducing-tiktok-next-2026-our-trend-forecast-for-marketers-for-the-year-ahead?lang=en
- Text lines tied to one month, such as "how life feels when…" (April 2026). Treat these as data that expires. https://clipchamp.com/en/blog/tiktok-trends-challenges/

**Measurable by VibeCut?**
| # | Check | How |
| --- | --- | --- |
| 1 | later | `style.pace` and `transition_style` exist; each sub-style needs its own reference set to get a median and IQR |
| 2 | yes | `features.motion` exists; invert the rule, add a discrimination test, calibrate on about 20 silent vlogs |
| 3 | no | data, not a measurement |
| 4 | no | naming |
| 5 | later | needs a real VAD |
| 6 | yes | RMS on the 16 kHz mono track; discrimination test with a gap fixture against a room-tone fixture |
| 7 | yes | `capture_time` plus a word count |
| 8 | yes | order by capture time; the seam is the `shots.detect` histogram distance |
| 9 | no | taste, which is the creator's 10% |
| 10 | yes | a fixed rule checked at export |

Gaps: I could not find sources for Korean and Japanese subtitle conventions, or for named 2025–26 DIML videos with view counts.

### Food

**Sub-styles**
- **Silent kitchen** (Emily Mariko): no talking or music, only kitchen sound. Her first silent video got 4.6M views. https://openlab.macaulay.cuny.edu/messenger/2021/11/04/has-emily-mariko-found-the-recipe-for-success/
- **Korean/Japanese silent vlog** (Haegreendal, 2.11M subscribers): subtitles carry the recipe, with sizzle under light piano. https://www.amraandelma.com/influencers-who-make-vlogs-with-no-talking/
- **Whisper-voiceover from scratch** (Nara Smith): shot on a tripod, voiceover recorded afterwards, about 1.5 min. https://singjupost.com/transcript-of-nara-smith-interview-call-her-daddy-podcast/
- **Hands-and-pans overhead** (Tasty): top-down, big white captions, opens and closes on the dish. https://www.pickuptable4.com/chefs/tasty/
- **Scored review** (Keith Lee, 1–10 per item). https://en.wikipedia.org/wiki/Keith_Lee_(food_critic)
- **Series ritual**: the same opener every time ("Let's make some lunch for my kids!"). https://en.wikipedia.org/wiki/Sulhee_Jessica_Woo
- **Meme-edit comedy** (Cooking with Lynja). https://en.wikipedia.org/wiki/Cooking_with_Lynja
- **What I eat in a day**: "Breakfast. Cut. Coffee. Cut." https://www.griproom.com/fun/why-tiktoks-what-i-eat-in-a-day-videos-are-so-addictive
- **Girl dinner**: a deliberately unstyled snack plate. https://en.wikipedia.org/wiki/Girl_dinner

**What to apply** (strongest first; every number is a guess until calibrated)
1. **Speed up only silent, repetitive filler**: 2–8×, at most 3 s of output per ramp, room tone replacing the audio, never pitch-shifted. Cutting and plating stay at 1.0×. In the ASMR preset, so does any shot with a food sound, because crisp sounds and slow movements are common ASMR triggers (https://pmc.ncbi.nlm.nih.gov/articles/PMC4380153/). Whole cooking videos at 1.25× and 1.5× scored lower on satisfaction (3.82 and 3.90, against 4.17 at 1×). https://pmc.ncbi.nlm.nih.gov/articles/PMC12675162/
2. **What I eat in a day: no automatic calorie overlays, and no body or mirror shots without a food label.** The creator may add them, and the review flags them. Body cues raise viewers' body dissatisfaction. https://www.frontiersin.org/journals/human-dynamics/articles/10.3389/fhumd.2025.1694787/full
3. **Never grade a food shot cooler than its source**: the `grade.stats` warmth change must be 0 or more, and Cinematic's teal shadow split is 0 on food shots. Food under about 3000K light was rated more appealing than under 5600K, and both beat 9500K. https://ora.ox.ac.uk/objects/uuid:dba2e23a-1abd-432e-8c3a-1e8b0bfa0f1e/files/r8w32r625v
4. **Protect gloss and plate whites**: at most 1% of pixels at luma 250 or above (on the index frames), black point at least 6, no added sharpening, and saturation no higher than the source inside face boxes. https://filmora.wondershare.com/video-creative-tips/capcut-food-video-luts-vibrant.html
5. **Slow presets: never cut mid-action** ("don't cut mid-pour"). Cut after motion stays below 40% of the shot's peak for 3 frames, or on a chop onset. https://filmora.wondershare.com/vlog-tips/make-asmr-cooking-video.html
6. **Opt-in "Kitchen sounds" preset**: no music, and the original audio is the soundtrack. Mariko's talking videos sit at the low end of her views (2021, anecdotal). https://openlab.macaulay.cuny.edu/messenger/2021/11/04/has-emily-mariko-found-the-recipe-for-success/ Pro ASMR audio is sweetened, with the original at 30–40% under close-mic effects. https://filmora.wondershare.com/vlog-tips/make-asmr-cooking-video.html [inferred] Allow an added effect only within about 80 ms of a visible motion onset. Comfort with food sounds tracked visual engagement. https://pmc.ncbi.nlm.nih.gov/articles/PMC12609435/
7. **Cap mouth sounds outside ASMR and mukbang**: [inferred] at most 1.5 s each and 2 per minute. Sizzles and chops aren't capped. Eating sounds are the most commonly reported misophonia trigger. https://en.wikipedia.org/wiki/Misophonia
8. **Open on indulgent motion** (a pour, ooze or cut-open) if it clears an absolute motion floor; otherwise open on the plated hero. The evidence is mixed: a 626-person replication found no effect from implied motion. https://ora.ox.ac.uk/objects/uuid:dba2e23a-1abd-432e-8c3a-1e8b0bfa0f1e/files/r8w32r625v
9. **Instrumental beds only under food sound** (light piano, soft ambient). [inferred] Dip the music about 6 dB for 0.3–0.8 s on each sizzle. https://thesmartlocal.kr/aesthetic-korean-vloggers/
10. **Review template**: arrival, then order, then the first bite held through the spoken reaction (never cut mid-sentence), then a spoken score per item. https://en.wikipedia.org/wiki/Keith_Lee_(food_critic)

**Premium vs cheap**
- Every sound has a visible source, not library foley over nothing. https://pmc.ncbi.nlm.nih.gov/articles/PMC12609435/
- The action finishes before the cut; no cutting mid-pour. https://filmora.wondershare.com/vlog-tips/make-asmr-cooking-video.html
- Warm-to-neutral light and a clear background, not a cool cast and clutter behind the plate. https://ora.ox.ac.uk/objects/uuid:dba2e23a-1abd-432e-8c3a-1e8b0bfa0f1e/files/r8w32r625v
- Gloss kept and blacks slightly lifted, not blown plates, "crunchy" blacks, harsh crumbs or orange skin. https://filmora.wondershare.com/video-creative-tips/capcut-food-video-luts-vibrant.html
- Much of what reads as premium is production value: Nara Smith can spend 7 hours on one sandwich video. https://blavity.com/nara-smith-viral-tiktok-how-much-time-to-film-videos [inferred] VibeCut should avoid undercutting that: no speed-up and an intact voiceover.

**Dated / overused in 2026**
- The all-overhead Tasty template as the whole video; it lost dominance in 2022–24. https://www.pickuptable4.com/chefs/tasty/
- Punch zooms and meme stings outside comedy; Wikipedia frames the style as 2020–24. https://en.wikipedia.org/wiki/Cooking_with_Lynja
- Calorie-count what-I-eat-in-a-day videos. https://www.frontiersin.org/journals/human-dynamics/articles/10.3389/fhumd.2025.1694787/full
- Mukbang excess: China's 2021 law bans overeating streams. https://en.wikipedia.org/wiki/Mukbang
- The couture from-scratch kitchen, now read through "tradwife" criticism. https://en.wikipedia.org/wiki/Tradwife

**Measurable by VibeCut?**
1 yes: speed per shot comes from VibeCut's own edit list; `features.motion` shows repetitive motion. · 2 later: needs OCR for overlays; Vision labels already exist. · 3 yes: `grade.stats` before and after the look. · 4 yes for the whole frame, later for the food region only. · 5 yes: `features.motion` plus `style.onsets`, next to `check_cut_on_motion`. · 6 yes: `check_loudness` plus the offset from each effect to its motion onset. · 7 later: no mouth-sound detector yet. · 8 later: needs a calibrated motion floor. · 9 yes for dip depth, later for vocals. · 10 later: speech ends come from the speech helper; spoken scores can't be read.

### GRWM & fashion (get-ready-with-me, fit checks, outfit transitions)

**Sub-styles**
- **Storytime GRWM:** the routine is B-roll behind a story that refers back to the last video and teases the next (Alix Earle). https://www.saramccord.com/blog/alix-earle
- **Chaotic / voice-note GRWM:** an unpolished, best-friend tone (Alexa Losey: storytime 1.8M views, update 4.6M). https://corq.studio/insights/chaotic-creators-chatty-grwm-videos-and-unfiltered-storytime-posts-are-a-goldmine-for-brands/
- **Event GRWM:** names the occasion up front (first date, wedding). https://iqfluence.io/public/blog/grwm-meaning
- **Silent / ASMR GRWM:** no voice; taps, crinkles and brushing carry it. https://en.wikipedia.org/wiki/Autonomous_sensory_meridian_response
- **Soft glam:** peach, cream, soft gold, dewy skin. https://captions.ai/styles/bloom
- **Outfit-transition shorts:** the change hides inside a spin, stomp, shoe toss or leg swipe. https://later.com/blog/instagram-reels-trends/
- **Concept ladder:** one idea at several price levels, all in the same framing (Wisdom Kaye). https://goatagency.com/blog/fashion-creator-wisdom-kaye/
- **Editorial / lookbook:** a few slow shots, texture close-ups, clean cuts. https://fluxnote.io/guides/create-fashion-reels-with-ai
- **Digicam / direct flash:** harsh flash, grain, blur. https://www.refinery29.com/en-us/digital-camera-trend-fashion-style
- **0.5x ultra-wide:** low-angle and distorted, so it looks unposed. https://www.newsweek.com/05-selfie-trend-depicts-youngsters-distorted-bodies-1728874
- **CBK (90s minimalism, Mar 2026) and whimsymaxxing (bedazzled maximalism):** each label arrives with its own sound. CBK is roughly quiet luxury under a new name [inferred]. https://later.com/blog/tiktok-trends/

**What to apply** (strongest first)
1. **Voice-led mode.** When speech covers at least 50% of the runtime, the audio stays continuous. The picture cuts only at pauses of 150 ms or more, and the routine angles swap every 2–5 s. https://corq.studio/insights/chaotic-creators-chatty-grwm-videos-and-unfiltered-storytime-posts-are-a-goldmine-for-brands/
2. **Only performed transitions.** Look for occlusion frames: 60% or more of the 48×27 cells change by more than 25 luma levels within 2 frames, or luma drops below DARK. Prefer these as cut points. If there is no performed move, hard-cut on the downbeat; never add a synthetic wipe. https://later.com/blog/instagram-reels-trends/
3. **Hold the plain "before" until the drop.** The first outfit switch lands within ±1 frame of the largest novelty rise after at least 2 bars. After that, switch every bar (energetic) or every 2 bars (calm). https://later.com/blog/tiktok-trends/
4. **A same-room swap is a match cut at the peak of the move.** Pair clips where the border ring matches and the centre changes. Cut A at its last motion peak and B at its first. If luma or R/B differs across the pair, warn but don't reject (limits [inferred]). Skip glow-ups, which change the light on purpose. https://www.flexclip.com/learn/dress-change-video.html
5. **No face retouching in claims content.** Use one global look. In tutorials and reviews, warn when a before/after pair differs in light: "this may read as lighting, not makeup" (thresholds [inferred]). https://en.wikipedia.org/wiki/Mikayla_Nogueira
6. **A disclosure card when the creator marks a video paid, gifted or affiliate.** It goes in the video, over the picture, and stays up long enough to read. It overrides the minimal-text presets. https://www.ftc.gov/business-guidance/resources/disclosures-101-social-media-influencers
7. **GRWM spine:** hook → routine in capture-time order → reveal (full body, longest hold, late in the video) → optional tease of the next video, 2 s or less. Check the reveal's position only in silent or routine-led GRWMs [inferred]. https://www.saramccord.com/blog/alix-earle
8. **Occasion-card hook:** "grwm for {occasion}", 6 words or fewer, on screen from frame 0 to at least 1.5 s. The occasion comes from the creator or a Vision scene label and is never generated. Frame 0 needs a person, not necessarily a face [inferred]. https://iqfluence.io/public/blog/grwm-meaning
9. **Every fit check gets a head-to-shoes shot.** Leave ultra-wide distortion alone. https://www.flexclip.com/learn/dress-change-video.html ; https://www.newsweek.com/05-selfie-trend-depicts-youngsters-distorted-bodies-1728874
10. **Presets are parameter bundles with dated aliases.** A label with no fresh references in 12 months shows as "classic". Rename "Quiet luxury" to something descriptive. https://en.wikipedia.org/wiki/Quiet_luxury

**Premium vs cheap**
- **Colour.** Premium: white balance first, a slight shadow lift, clothes that "pop without looking artificial". Cheap: a grade that shifts garment or skin hue. https://galibfashionedits.wordpress.com/2026/06/17/how-to-edit-cinematic-fashion-reels-clothing-brands/
- **The switch.** Premium: both looks filmed from the same spot in the same light. Cheap: a brightness or white-balance jump that reads as a jump cut. https://www.flexclip.com/learn/dress-change-video.html
- **Sound.** Premium: a fabric swish or camera click under the key moments. Cheap: stock whooshes everywhere [inferred]. https://galibfashionedits.wordpress.com/2026/06/17/how-to-edit-cinematic-fashion-reels-clothing-brands/
- **Type.** Premium: light, spaced type where the "text never competes with the speaker". Cheap: karaoke captions on a quiet beauty video [inferred]. https://captions.ai/styles/bloom
- **Both extremes read as ads:** the polished commercial, and "flat, unedited, continuous footage". https://iqfluence.io/public/blog/grwm-meaning

**Dated / overused in 2026**
- "Quiet luxury" as a label: "considered outdated" by Jan 2024. https://en.wikipedia.org/wiki/Quiet_luxury
- "Clean girl" as a name: mocked by "very demure" (34M views, Aug 2024). https://en.wikipedia.org/wiki/Jools_Lebron
- The plain routine GRWM: engagement down 19% and views down 17% year on year (Traackr). https://iqfluence.io/public/blog/grwm-meaning
- Long GRWMs without a story: TIME says Earle's Netflix series "drags". https://time.com/article/2026/08/28/earle-meets-world-review/
- A hand-over-lens wipe on every outfit. It is still current, but doing it every time is the tell, so cap it at about one per video [inferred]. https://www.tiktok.com/discover/hand-covering-camera-transition
- Beauty filters on product claims. https://en.wikipedia.org/wiki/Mikayla_Nogueira

**Measurable by VibeCut?**
1. Voice-led: **yes** (talk.py speech coverage; cuts that land inside words).
2. Performed transitions: **yes** (occlusion frames on the 48×27 grid).
3. Drop sync: **later**. The novelty envelope exists; the share of switches on downbeats needs beat tracking (known limit 4).
4. Same-room swap: **yes** (border vs centre histograms; luma and R/B across the cut, like the exposure-jump check).
5. Before/after light: **yes**, once the creator marks the pair. Detecting retouching: **no**.
6. Disclosure: **yes** for whether our card is present and how long it holds. Whether a video is paid: **no** (the creator marks it).
7. Spine: **yes** for the reveal's hold and position. **No** for step order: the only beauty label among Vision's 1,303 is `cosmetic_tool`. https://developer.apple.com/documentation/vision/classifyimagerequest
8. Occasion card: **yes** for timing. Person in frame 0: **later**.
9. Head-to-shoes: **later**. vibevision.swift doesn't call DetectHumanRectanglesRequest yet. https://developer.apple.com/documentation/vision/detecthumanrectanglesrequest
10. Aliases: **no** (catalogue metadata, not a measurement).

Every number here is a starting guess until it is refit with style.learn() on about 20 reference videos the creator supplies: the medians become the preset, and p10/p90 become the thresholds. https://later.com/blog/tiktok-trends/

### Fitness & sports

**Sub-styles**
- **Gym phonk edit**: drift phonk or funk automotivo, grunge visuals, text calling out reps and weights. https://www.pippit.ai/templates/phonk-gym-edit
- **Velocity edit**: speed ramps locked to the beat, plus shake, flash and motion blur. https://thealightmotions.com/velocity-edits-tutorial/
- **Aura edit**: one calm subject held against frantic action (Kelce's 2025 remake: 14M+ views). https://en.wikipedia.org/wiki/Aura_farming
- **Raw log (Sulek-style)**: car talk → full sets → car talk, no music, no grade, 30–40 min daily (4.49M subscribers). https://en.wikipedia.org/wiki/Sam_Sulek
- **Hybrid-athlete series**: numbered episodes, drone, an arc across a training block (Nick Bare, 1.46M subscribers); **Hyrox splits breakdown**: station chapters and split times (Jake Dearden). https://www.tatlerasia.com/lifestyle/sports/hyrox-youtube-channels
- **Hybrid day-in-the-life**: clock-time blocks, each with one measured stat (Luke Hopkins, 1M+ views). https://athelogroup.com/blog/incoming-social-media-trend-hybrid-athlete/
- **Highlight package**: payoff first; long-form versions keep a running stat tally (NBA Fantastic Finishes, Player Duels). https://www.hashtagsports.com/awards/shortlist-2024/nba-tiktok
- **Mic'd up**: the athlete's audio carries it. https://gis.sport/news/nba-fan-engagement-strategy-2025-digital-innovation-all-star-weekend-and-constant-coverage/
- **Progress montage**: struggle → mastery, music, quick cuts, little dialogue. https://www.studiobinder.com/blog/what-is-a-montage-definition/

**What to apply** (strongest first)
1. **Real speed first; slow only on the replay, only when it clarifies technique.** One replay per moment. Slowest clean factor = output_fps / source_fps; below ~50 fps source, hold a 0.4–0.8 s freeze instead [inferred]. https://www.capcut.com/create/sports-highlight-editing-that-gets-shared
2. **Highlight order: hook → context → setup → action → clarification → reaction.** Six optional slots; one context card at most (≤6 words, creator's facts only). https://www.capcut.com/create/sports-highlight-editing-that-gets-shared
3. **Raw-log preset as a first-class mode** (proven 2023–24; 2026 dominance not shown). Car/gym chapters in capture order; no music, transitions or grade; trim dead time between sets, never inside a set; title '{Series} – Day {N} – {target}', text-free thumbnail. https://www.tastyedits.com/sam-sulek-bodybuilding-youtuber-strategy/ Gym speaker music can draw Content ID claims; offer an export that drops it during sets [inferred]. https://support.google.com/youtube/answer/6013276?hl=en
4. **Keep the sport's own sound**: dip music for whistles, impacts and commentary (extends research 01's speech ducking). Starting values to calibrate: transients above the shot's 99th-percentile spectral flux, 6–9 dB for 250–400 ms, ≤1 per bar [inferred]. https://www.capcut.com/create/sports-highlight-editing-that-gets-shared
5. **Sports: open on the payoff (≤1.5 s), then cut back to the play's start.** OpusClip's 61% shock-hook share counts frequency, not performance, so it sets no threshold; talking fitness clips most often open on a problem/solution hook (39%). https://www.capcut.com/create/sports-highlight-editing-that-gets-shared ; https://www.opus.pro/research/best-video-hooks-sports ; https://www.opus.pro/research/best-video-hooks-health-and-fitness
6. **On-screen numbers are real, in one fixed corner and font.** Stats stamps come from the creator's Strava PNG or a locally parsed GPX/FIT file, never guessed (the "Strava jump" trend is unverified). https://www.tiktok.com/discover/how-to-overlay-strava-stats Edits over 60 s of repeated events may tick a counter ('SET 3/5', 'KM 7'), an NBA format; fit for gym/run is [inferred]. https://www.hashtagsports.com/awards/shortlist-2024/nba-tiktok Day-in-the-life: '{h:mm AM} – {activity} · {metric}', metric empty until supplied. https://athelogroup.com/blog/incoming-social-media-trend-hybrid-athlete/
7. **Cap distinct effect types at 3 and report the count.** "Too many effects" is the named beginner mistake, yet a ramp alone "isn't enough". https://thealightmotions.com/velocity-edits-tutorial/ ; https://www.videoproc.com/video-editor/how-to-make-a-velocity-edit.htm
8. **Land the peak on the drop** (tutorial recipe, not measured on viral videos): ~2x in, peak-motion frame on the drop onset, 0.2–0.3x for 1–2 beats, ease back; clean only from high-fps source. https://aejuice.com/blog/how-to-do-velocity-edits-in-after-effects/
9. **Hyrox race-day template**: 8 × 1 km runs, each followed by a fixed station, so 16 chapters in known order; splits only from creator input. That good Hyrox edits follow it is [inferred]. https://en.wikipedia.org/wiki/Hyrox
10. **Progress edits framed as performance** (a PR, a time), ending on the payoff held ≥2 s at 1x [inferred]. Never auto-write '30 days' or 'lost X kg': TikTok bars body-comparison trends and makes "fast or dramatic results" claims For You–ineligible. https://www.tiktok.com/community-guidelines/en/mental-behavioral-health

**Premium vs cheap**
- Peak exactly on the hit vs effects sprayed across the beat grid. https://aejuice.com/blog/how-to-do-velocity-edits-in-after-effects/
- Slow-mo shot at 60+ fps vs interpolated 30 fps, where crossing limbs warp [inferred]. https://thealightmotions.com/velocity-edits-tutorial/
- Bar clank, breath, whistle audible vs a wall of music. https://www.capcut.com/create/sports-highlight-editing-that-gets-shared
- Text kept off faces, the ball and the direction of play vs captions over the action. https://www.capcut.com/create/sports-highlight-editing-that-gets-shared
- Real stats vs motivational quote cards with nothing behind them [inferred].
- Holding a still, controlled moment vs cutting every beat. https://en.wikipedia.org/wiki/Aura_farming
- Raw can beat glossy: locker-room and fan content "tend[s] to out-viral" brand content. https://theshortmedia.com/the-future-of-us-sports-marketing-on-tiktok/

**Dated / overused in 2026**
- Phonk on everything ("the most lucrative yet lifeless genre of the 2020s", Pitchfork): suggest it only in hype, never block. https://en.wikipedia.org/wiki/Phonk
- Sincere sigma/Patrick Bateman edits, now satire [inferred].
- Shake and flash on every cut. https://thealightmotions.com/velocity-edits-tutorial/
- "Aura" as a label: already "aura battles" in 2026, so the word dates before the held-still technique [partly inferred]. https://en.wikipedia.org/wiki/Aura_farming

**Measurable by VibeCut?**
1. Real speed first: **yes** (source-fps limit); **later** (spotting slow replays).
2. Highlight order: **later** (faces + crowd level per slot); card count **yes**.
3. Raw log: **yes** (no cut inside a high-motion run); **later** for music under speech, since `speech_mask` reads music as talking.
4. Sport sound: **yes**, `spectral_flux` transients vs music level, with a discrimination test.
5. Payoff first: **yes**, rank of the opener's motion × `audio_novelty` peak, extending `check_opening`.
6. Real numbers: **no** for truth; **yes** for one-corner/one-font consistency.
7. Effect cap: **yes** for flashes (`style.py`); **later** for shake and ramps.
8. Peak on drop: **yes** (argmax motion vs `beat_grid`), but `BEAT_TOL_S` = 0.06 s is looser than ±1 frame.
9. Hyrox chapters: **later** (ClassifyImage labels).
10. Progress: **yes** (`style.py` quickening); **no** for copy, which is never generated.

Calibrate 1, 2 and 5 on SoccerNet-v2 (~300k annotations, 500 games, shot boundaries, replay grounding; videos under NDA). https://arxiv.org/abs/2011.13367 ; https://www.soccer-net.org/data

### Family & pets

**Sub-styles**
- **Serial character**: one named pet or child with running storylines (Tucker Budzyn, 27M followers). https://en.wikipedia.org/wiki/Tucker_Budzyn
- **Then / now** ("How it started / How it's going"): far-apart moments, one hard cut (Punch edit, 3.2M views). https://knowyourmeme.com/memes/punch-the-monkey
- **1 Second Everyday**: one second per day in date order ("baby's first year"). https://en.wikipedia.org/wiki/1_Second_Everyday
- **Pet POV / personality skit**: the pet narrates or its quirks carry a skit (Life with Klee Kai, 5.6M followers). https://impact.com/influencer/how-to-become-a-pet-influencer/
- **Mock-epic**: solemn pipe organ over a tiny animal ("nihilist penguin", Jan 2026). https://www.aprasi.com/blogs/trending-topics/punch-monkey-lonely-penguin-why-they-broke-the-internet
- **-core calm animals**: Ottercore was October 2025's #2 most-liked TikTok (13.6M likes). https://socialbook.io/blog/top-20-most-liked-tiktok-videos-october-2025/
- **Couple costume reveal**: seasonal chemistry pieces (Abbie Herbert's Farquaad/Fiona, 6.0M likes). https://socialbook.io/blog/top-20-most-liked-tiktok-videos-october-2025/
- **Found camera footage**: doorbell and pet-cam clips left raw. https://en.wikipedia.org/wiki/Ring_Nation
- **Faceless family**: backs, hands, silhouettes instead of emoji faces. https://www.betches.com/article/lifestyle/stop-covering-your-babys-face-on-social-media-do-this-instead-252831-20240802
- **Slow-home ASMR**: quiet voiceover, raised foley (Nara Smith; labelled "tradwife"). https://en.wikipedia.org/wiki/Nara_Smith

**What to apply** (strongest first; engine rules translate the cited evidence, and [inferred] numbers are uncalibrated guesses)
1. **Privacy warnings (keep).** Warn, not block, on child/baby + {bathroom, bedroom, crib, swimsuit, pool} labels. Strip the location atom on export by default. No ASMR sound emphasis on child shots. YouTube restricts videos of minors and names bedrooms, bathrooms and ASMR. https://support.google.com/youtube/answer/2801999?hl=en
2. **Share-safe mode.** Prefer child shots with no visible face (detected face under 0.3% of frame [inferred]), then use tracked blur as the fallback. Never stickers; report remaining child-face frames. Experts say covering faces only partly protects a child. https://www.abc.net.au/news/2024-09-01/does-hiding-childrens-faces-online-social-media-protect-them/104241988
3. **Then/now proposal (keep).** From one identity cluster, pair clips from the earliest and latest 20% by creation_time at 1.5–2.5 s each. Hard-cut on a downbeat at 40–50% of runtime, with two lowercase labels and no other captions [inferred]. https://knowyourmeme.com/memes/punch-the-monkey
4. **Protect the subject's own sound.** On pre-mix source audio, a sharp onset (laugh, bark, button word) is protected: the music dips from −0.3 s to +1.0 s around it, and no cut lands within 0.5 s after it [inferred]. Bunny the sheepadoodle's recorded button words were the whole content (8M followers, 210M likes, 2022). https://en.wikipedia.org/wiki/Bunny_(dog)
5. **Cast memory and tribute mode.** Save named identity clusters per project, and offer "Part N" when clips with new capture dates arrive. A pet marked passed gets a chronological tribute: no comedy SFX, trending audio or "Part N" [inferred]. Tucker Budzyn died September 2026. https://en.wikipedia.org/wiki/Tucker_Budzyn
6. **Native slow motion only.** Slow motion only when source fps is at least 2× timeline fps, and never frame interpolation on animal or child shots. Keep one unbroken take of 4 s or more with sync sound [inferred]. The 2025 AI-bunny fake was exposed by morphing bodies. https://www.today.com/news/bunnies-jumping-trampoline-viral-video-ai-concern-rcna223637
7. **Hold the reaction.** After an ask or reveal, don't cut until at least 1.5 s after the voice or laugh onset and until level returns within 6 dB of pre-event. No zoom, shake or SFX during the reaction [inferred]. https://www.studiobinder.com/blog/what-is-a-reaction-shot-definition/
8. **One swell on togetherness.** Put the hug, reunion or two-faces shot within ±0.25 s of the track's largest section change [inferred]. One swell per short, two at most per long video. Kama muta (being moved) follows sudden closeness. https://en.wikipedia.org/wiki/Kama_muta
9. **Down-rank quirky stock music.** For family, pet and couple vibes, penalise pizzicato, whistle and ukulele tags unless the user picks comedy, and allow at most one meme SFX [inferred]. "Monkeys Spinning Monkeys" plus "Electrodoodle" reached 151.8B TikTok plays. https://en.wikipedia.org/wiki/Kevin_MacLeod
10. **Minor-share meter.** On export, show monetising creators the share of runtime with a child label. Minnesota bars under-14s from content creation once they appear in at least 30% of compensated videos in 30 days. https://www.revisor.mn.gov/statutes/cite/181A.13

**Premium vs cheap**
- Premium keeps the kid's shout or the dog's sigh above the music and holds on the reaction [inferred]. Cheap zoom-punches the baby and syncs an "Oh no!" SFX to every expression, which pet guides still advise [inferred that it now reads cheap]. https://www.miracamp.com/learn/content-creation/how-to-create-viral-pet-content-on-tiktok-instagram
- Premium films at eye level in natural light. Cheap films looking down from adult height [inferred] or grades skin orange with teal-orange [inferred]. https://www.miracamp.com/learn/content-creation/how-to-create-viral-pet-content-on-tiktok-instagram
- Premium frames faces out: backs, hands, a ponytail in the wind ("artsy"). Cheap puts emoji over children ("lazy, creepy"). https://www.betches.com/article/lifestyle/stop-covering-your-babys-face-on-social-media-do-this-instead-252831-20240802
- Premium uses small lowercase text that clears before the payoff; cheap uses robotic TTS narration [inferred].
- Premium titles name a specific moment. Cheap titles read "Family Vlog #32". https://packapop.com/blogs/youtube-success-blog/family-youtube-video-ideas

**Dated / overused in 2026**
- Couple tests (orange peel peaked Nov 2023–Jan 2024) [inferred]. https://knowyourmeme.com/memes/orange-peel-theory
- Emoji faces over kids. https://www.betches.com/article/lifestyle/stop-covering-your-babys-face-on-social-media-do-this-instead-252831-20240802
- Quirky ukulele and pizzicato stock music. https://en.wikipedia.org/wiki/Kevin_MacLeod
- The tradwife persona. Borrow its sound design, not the persona. https://en.wikipedia.org/wiki/Ballerina_Farm
- Reposted "wholesome compilations", which YouTube demonetises as reused content. https://support.google.com/youtube/answer/1311392?hl=en
- Crying-child hooks and thumbnails, amid the 2025–26 family-vlog backlash. https://influencity.com/blog/en/family-influencers-to-parenting-educators
- AI "glow-up" pet transformations are trending but off-positioning (no generated frames). https://tailframe.com/faq/tiktok-pet-video-ideas

**Measurable by VibeCut?**
| # | Verdict | Why |
|---|---|---|
| 1 | yes | ffprobe reads location; room/child labels from existing ClassifyImage; OCR later |
| 2 | yes | vibevision already runs DetectFaceRectangles |
| 3 | later | needs identity clustering (feature prints exist) plus beat snapping (not built) |
| 4 | later | RMS onsets yes; `speech_mask` is level-based; laugh-vs-bark no |
| 5 | later | feature prints exist, cast storage doesn't; no animal detector yet |
| 6 | yes | fps from ffprobe; take length from `shots.detect` |
| 7 | later | onsets yes; window uncalibrated |
| 8 | later | `music.py` novelty + face count ≥ 2 yes; "hug" no |
| 9 | later | needs track tags or fingerprints; no music library on the dev machine |
| 10 | yes | label share of runtime; label accuracy uncalibrated |

### Talking-head (口播 / talking to camera)

**Sub-styles**
- **Dynamic minimalism ("Hormozi 2.0")**: white mixed-case captions with a drop shadow, no box or emoji, ~1.5x crop toggles on idea boundaries, no B-roll. https://www.writepanda.ai/blog/hormozi-style-shorts-editing
- **Podcast clip (DOAC)**: dry audio, the speaker full frame, 1–1.5 s reaction cutaways, 1–3 word captions coloured by speaker. https://www.writepanda.ai/blog/how-diary-of-a-ceo-edits-podcast-clips/
- **Edu Short (Ali Abdaal)**: face on screen ~95% of runtime, a top-band graphic every 3–8 s, at most one punch-in. https://www.writepanda.ai/blog/how-to-edit-shorts-like-ali-abdaal/
- **Clean review (MKBHD)**: 48% face, 43% B-roll, no burned captions, one spec card, a late uncut verdict. https://www.writepanda.ai/blog/mkbhd-editing-style-measured/
- **Faceless meme-explainer (Fireship)**: no face, 13.3 cuts a minute, tilted keyword stickers, meme inserts. https://www.writepanda.ai/blog/fireship-editing-style-measured
- **Vox essay / greenscreen explain**: a chart every 8–10 s, or the presenter on one third with visuals swapped every 4–6 s (opinion). https://www.opus.pro/blog/editing-aesthetics-dominating-short-form-2026
- **Deadpan static (penguinz0)**: the personality carries the video. https://en.wikipedia.org/wiki/Penguinz0
- **Roast/response (Drew Afualo)**: replies to commenters, laugh left in. https://en.wikipedia.org/wiki/Drew_Afualo
- **Multi-part storytime (Reesa Teesa)**: unstaged ~10-min parts linked by cliffhangers. https://en.wikipedia.org/wiki/Who_TF_Did_I_Marry%3F
- **一口气了解 data-card (小Lin说)**: animated data cards and question titles. https://index.datastory.com.cn/article/121
- **表情包流 (半佛仙人)**: an article performed as joke voiceover over memes and BGM. https://www.niaogebiji.com/article-72337-1.html
- **信息设计 (回形针PaperClip)**: no presenter, dense motion graphics. https://zh.wikipedia.org/wiki/回形针PaperClip
- **高级感口播 (Douyin)**: one background colour, readable type, highlighted keywords. https://finance.sina.com.cn/tech/roll/2025-05-15/doc-inewruvz5306799.shtml

**What to apply** (the numbers are priors from 3–4 videos per creator)
1. **Keep the speaker's register.** Unscripted takes keep "um", stammers and laughter; DOAC keeps pauses on serious clips ("the pauses are the content"). Remove fillers fully only in scripted takes. `filler_policy` = keep / stumbles_only / remove, chosen by take type. https://www.writepanda.ai/blog/how-diary-of-a-ceo-edits-podcast-clips/ ; https://www.writepanda.ai/blog/retention-editing-7-laws
2. **Captions sit at chest height.** Caption centre at 0.55–0.66 of frame height (measured range 0.48–0.70), below the chin; graphics use y < 0.40H. https://www.writepanda.ai/blog/retention-editing-7-laws
3. **Captions are 1–4 words, swapped as a group** (every ~0.8–1.0 s for Hormozi). Use one emphasis mechanism per video (colour, weight or box). A "faster" setting shortens caption groups before it adds cuts. https://www.writepanda.ai/blog/hormozi-style-shorts-editing
4. **Format decides the text.** YouTube long-form burns no speech captions (0 of 502 frames across 9 videos). Export an SRT and use keyword pops plus 2–4 quote cards instead. Vertical exports keep captions on. https://www.writepanda.ai/blog/youtube-videos-dont-burn-captions-study
5. **Every punch-in marks something.** `punch_mode` = toggle 1.0/1.5 on idea-boundary cuts (Hormozi) or single 1.5x at ~0.75T (Ali). Only punch in if the face box stays inside the crop [inferred]. https://www.writepanda.ai/blog/hormozi-style-shorts-editing ; https://www.writepanda.ai/blog/how-to-edit-shorts-like-ali-abdaal/
6. **Podcast-clip grammar.** Keep the active speaker full frame, with the listener only in ≤1.5 s J-cut reactions. Change crop every 5–6 s in monologues, colour captions by speaker, and run 60–140 s. Serious clips get small lowercase captions and no end card. https://www.writepanda.ai/blog/how-diary-of-a-ceo-edits-podcast-clips/
7. **Hook.** Shorts start speech by 2.5 s. Long-form states the thesis within 10 s, with intro ≤ 6% of runtime. Report `first_speech_t` and `intro_share`. Set-up openers become removal proposals. https://www.writepanda.ai/blog/retention-editing-7-laws ; https://www.opus.pro/blog/tiktok-hooks-that-go-viral-2026
8. **Payoff and ending.** Trim Shorts so the answer lands at ~0.55–0.80T, and cut after the last payoff word. Long-form allows one late uncut verdict (MKBHD: 32–55 s at 72–92%) and ends ≤ 6 s after the last speech, or reserves 5–20 s for end screens. https://www.writepanda.ai/blog/how-diary-of-a-ceo-edits-podcast-clips/ ; https://www.writepanda.ai/blog/mkbhd-editing-style-measured/ ; https://support.google.com/youtube/answer/6388789?hl=en
9. **Pacing is a clock and a curve.** In Shorts something visible changes every 3–8 s. Cuts tighten before the payoff (DOAC down to 2.5–3 s) and thin out at the close (MKBHD: 10–14 cuts in the first 30 s, 2–5 in the last). https://www.writepanda.ai/blog/how-diary-of-a-ceo-edits-podcast-clips/ ; https://www.writepanda.ai/blog/mkbhd-editing-style-measured/
10. **The sub-genre sets music and B-roll.** Podcast clips run dry. B-roll is 0% for Hormozi, 0–6.5% for DOAC and 43% for MKBHD (pages above). In one OpusClip test, 40% beat 0% and 70%, and CTAs did better on face. Use only the creator's own clips. https://www.writepanda.ai/blog/how-diary-of-a-ceo-edits-podcast-clips/ ; https://www.opus.pro/blog/does-b-roll-increase-watch-time

**Premium vs cheap**
- Premium picks one engine and keeps the rest still (Ali: one punch-in; DOAC: speaker switches; MKBHD: B-roll) [inferred synthesis]. Cheap stacks yellow caps, emoji, a whoosh per cut and a zoom per sentence. https://www.writepanda.ai/blog/retention-editing-7-laws
- A split screen held for 45 s is "exhausting"; cut to the speaker full frame instead. https://www.writepanda.ai/blog/how-diary-of-a-ceo-edits-podcast-clips/
- In zh 高级感, the premium look is one background colour, a readable font pairing and one highlight. https://finance.sina.com.cn/tech/roll/2025-05-15/doc-inewruvz5306799.shtml
- Polish alone reads hollow: 何同学 draws "形式大于内容" criticism. https://zh.wikipedia.org/wiki/何同学

**Dated / overused in 2026**
- Hormozi 1.0 (yellow/green caps with a stroke, emoji, whoosh) now reads as hustle-guru content. https://joyspace.ai/hormozi-editing-style-2026-analysis
- Set-up openers such as "Let me tell you about the time…" and "Have you ever wondered…". https://www.opus.pro/blog/tiktok-hooks-that-go-viral-2026
- Subscribe outros; Ali ends on the payoff. https://www.writepanda.ai/blog/how-to-edit-shorts-like-ali-abdaal/
- Templated, mass-produced output: YouTube's "inauthentic content" rule (Jul 2025). https://support.google.com/youtube/answer/1311392?hl=en

**Measurable by VibeCut?**
1 yes (vibespeech timings: fillers a minute, pause lengths) · 2 yes on our output against vibevision face boxes, later on references (needs text detection) · 3 yes on our output, later on references · 4 yes (export setting) · 5 yes on our output, later on references (48×27 can't tell a punch-in from a cut [inferred]) · 6 later (needs diarisation and face tracks) · 7 yes for `first_speech_t`, later for the thesis · 8 yes for the ending tail, later for payoff position · 9 yes (`style.pace` boundaries, cuts per runtime decile) · 10 yes for music on or off (`music_feel`), later for B-roll share (proxy: face-absent index frames).

Calibrate every number with an extended `style.learn()` over ~20 viral and ~20 non-viral videos per sub-style.

### Aesthetic & film (slow living, silent vlog, "-core" looks, film emulation)

**Sub-styles**
- **Silent vlog / gamsung:** faceless, hands-on routines, ambient sound, and captions in place of speech. https://i-d.co/article/anonymous-korean-vloggers-meditative-content-youtube/
- **Slow-living craft (Li Ziqi, 32.7M subs):** she rarely speaks, the sound is real foley, and each 5–20 min film follows one seasonal process. https://en.wikipedia.org/wiki/Li_Ziqi_(vlogger)
- **From-scratch ASMR (Nara Smith):** hushed voiceover over a jazz bed, with a recurring jingle as a sonic logo. https://chosenvesselstudio.substack.com/p/nara-smith-the-sonic-branding-maestro
- **Cottagecore / pastoral:** florals, prairie dresses, bread baking, indie folk. https://en.wikipedia.org/wiki/Cottagecore
- **Dark academia → Poetcore (+175%), plus Vamp Romantic (+180%) and Cool Blue (+150%):** Pinterest's 2026 split into micro-aesthetics. https://newsroom.pinterest.com/news/pinterest-predicts-nonconformity-self-preservation-and-escapism-drive-21-trends-for-2026/
- **CBK / 90s minimalism:** beige, black, slip dresses, restraint (213.1K posts, Mar 2026). https://later.com/blog/tiktok-trends/
- **Regencycore:** everyday clips set to string or cello covers of pop songs (700K posts). https://later.com/blog/instagram-reels-trends/
- **Digicam / indie sleaze:** direct flash, blown highlights, an orange date stamp. https://www.whatcameragear.com/2026/02/the-y2k-aesthetic-5-forgotten-digicams.html
- **2016 revival:** warm, saturated Clarendon/Valencia filters and lowercase captions. https://www.truefuturemedia.com/articles/what-is-the-2016-trend-2026-is-the-new-2016-instagram
- **Film / Super 8:** CineStill's red halation around night lights, and 4:3 home-movie framing. https://en.wikipedia.org/wiki/CineStill, https://en.wikipedia.org/wiki/Super_8_film
- **Photo dump / blink-and-miss-it:** many very short shots of favourite things. https://later.com/blog/instagram-reels-trends/

**What to apply**
1. **Choose the shots first; the grade only nudges.** A pack is 4–6 Lab palette centroids plus lists of Vision labels to allow or reject (dark academia allows candle, book, wood). Rank shots by ΔE from their 48×27 k-means colours to the nearest centroid, and aim for ≥70% of runtime within ΔE 15 [inferred]. The grade stays within `grade.MAX_SHIFT`. https://en.wikipedia.org/wiki/Dark_academia
2. **Learn each pack from ≥20 references.** A trait is the p10/p50/p90 of a `style.learn()` value. It only counts if its spread across the pack's references is narrower than across all references. Test: the pack's references and 20 generic vlogs must separate on ≥3 traits. Creators supply the references; nothing is bulk-scraped [inferred]. https://later.com/blog/instagram-reels-trends/
3. **Photo-dump mode with a variety rule.** Use 12–30 items at 0.2–0.6 s each on the beat, and hold the last one 1.5–2.5 s [inferred]. Adjacent items need a histogram distance above 1.5× the `shots.detect` threshold and a different top Vision label. 20–35% of items should be candid or flash-blown frames that still fit the palette, never two in a row [inferred]. Pick them by palette, not by `overallScore`, which probably ranks them low [inferred]. https://martubegift.com/blogs/news/why-ccd-cameras-are-trending-again-in-2026, https://developer.apple.com/documentation/vision/imageaestheticsscoresobservation/overallscore
4. **Quiet packs: the clip's own foley is the soundtrack.** Music is optional, instrumental only, and sits well under the foley (the level is [inferred] and needs calibrating). Rank shots by sound onsets where the real speech detector in `web/backend/speech` finds no speech, not the level-based `speech_mask`. Never cut while a sound is still decaying [inferred]. https://skinnedcartree.com/what-are-silent-vlogs.html
5. **Quiet packs: the action sets the out-point** ("show the whole pour"). Cut once motion has stayed below 0.2× the shot's peak for ≥0.5 s. Minimum shot is 3 s and beat snapping is off [inferred]. This applies to quiet packs only, because it reverses the cut-on-motion rule. https://skinnedcartree.com/what-are-silent-vlogs.html
6. **Fix the pipeline before any look.** HLG footage that isn't tone-mapped shows desaturated, hue-shifted colour. `media.py` and `export.py` never read `color_transfer`, so looks are fitted to washed-out pixels. Tone-map to Rec.709 once, at decode and at export [inferred]. https://en.wikipedia.org/wiki/Hybrid_log%E2%80%93gamma. Also, `timeline.FPS = 30` adds 24→30 judder to 24p footage [inferred], so film packs should export at the source frame rate. https://en.wikipedia.org/wiki/24p
7. **Build texture from the image.** Grain strength varies with brightness band. Halation appears only where a bright source meets a dark surround, in red→orange, mostly in night or tungsten shots (thresholds [inferred]). https://www.dehancer.com/learn/learn_articles/how-does-film-grain-work-in-dehancer-ofx-plugin, https://www.dehancer.com/learn/learn_articles/halation-in-dehancer
8. **A white flash is a pack trait with a hard cap.** It belongs to digicam, indie sleaze and photo dumps, and is off-vibe in quiet or dark-academia packs [inferred]. Allow it only when `pack.transition_mix.flash > 0`. Never more than 3 flashes per second; the cap also covers the "Flicker" effect. https://en.wikipedia.org/wiki/Indie_sleaze, https://www.w3.org/WAI/WCAG21/Understanding/three-flashes-or-below-threshold.html
9. **Write diary captions from metadata.** The time comes from `creation_time` and the place from offline-geocoded GPS ("7:42 am · jeju, day 3"). Captions are lowercase, ≤8 words and static, at most one every 10–15 s [inferred], and never over a Vision face rectangle. https://skinnedcartree.com/what-are-silent-vlogs.html
10. **Packs are dated data.** Each pack's label records `first_seen`, `peak` and `review_by`; the craft underneath isn't dated. After `review_by` (default peak + 12 months [inferred]) the app shows "may read dated". https://en.wikipedia.org/wiki/Quiet_luxury

**Premium vs cheap**
- Grain built from the image vs one scanned grain plate over every shot. https://www.dehancer.com/learn/learn_articles/how-does-film-grain-work-in-dehancer-ofx-plugin
- The whole pour held with its own sound vs a pour cut to the beat with lyrics on top. https://skinnedcartree.com/what-are-silent-vlogs.html
- A tone-mapped 2016 look vs an old VSCO filter slapped on HDR iPhone files, which comes out "muddy". https://justcitrusit.com/blog/what-is-the-2026-is-the-new-2016-photo-trend-how-to-make-your-pictures-look-like-old-instagram-again
- The digicam look on real flash or night clips vs a fake flash on sunny exteriors [inferred].
- A dump with some candid, blurred frames vs only perfect frames, which reads as an ad [inferred]. https://martubegift.com/blogs/news/why-ccd-cameras-are-trending-again-in-2026

**Dated / overused in 2026**
- A Ken Burns zoom on every still, the slideshow default. https://en.wikipedia.org/wiki/Ken_Burns_effect
- Brat lime lowercase Arial (declared over Sep 2024). https://en.wikipedia.org/wiki/Brat_summer
- "Quiet luxury" as a label (outdated by Jan 2024); the look lives on as CBK. https://en.wikipedia.org/wiki/Quiet_luxury
- Clean girl (saturated and criticised). https://en.wikipedia.org/wiki/Clean_girl_aesthetic
- Corecore (peaked 2023). https://en.wikipedia.org/wiki/Corecore
- Slowed + reverb (no evidence it is current in 2026). https://en.wikipedia.org/wiki/Slowed_and_reverb

**Measurable by VibeCut?**
1. Yes: k-means colours on the 48×27 frames.
2. Yes: `style.learn()` already exists.
3. Yes: pace, beat grid, and histogram distance between adjacent shots.
4. Later: needs the real speech detector.
5. Yes: a `cut_mid_action` check from `features.motion`, though small actions like steam may not register at 48×27.
6. Yes: ffprobe `color_transfer` and `r_frame_rate`.
7. No: grain is invisible at 48×27, so check the rendered export instead.
8. Yes: `style._dips` already finds flashes; count them per second.
9. Later: needs the caption track and face rectangles.
10. No: this is data, not a measurement.

### Comedy / POV skits

This belongs in an opt-in "Skit / POV / Reaction" mode, not in the vlog defaults. In this niche what reads as premium is timing and restraint, not production value. The premise, script and performance stay with the creator, which is CLAUDE.md's 10% taste share.

**Sub-styles**
- **POV skit:** the camera is the viewer, and a "POV: …" premise is on screen from frame 0. Example: "POV: I fell, but I saved my…", about 40K posts. https://later.com/blog/instagram-reels-trends/
- **Multi-character skit:** one performer plays several recurring characters, told apart by costume and position in frame (KallMeKris, 50.3M followers). https://en.wikipedia.org/wiki/Kallmekris
- **Silent reaction:** a wordless duet or stitch, answered with a gesture (Khaby Lame, 160.3M followers). https://en.wikipedia.org/wiki/Khaby_Lame
- **Digital sleight of hand:** the cut is hidden inside motion (Zach King, 2.2B views on one video). https://en.wikipedia.org/wiki/Zach_King
- **Gilligan / smash-cut bit:** someone makes a confident declaration, then a hard cut shows them doing the opposite. https://en.wikipedia.org/wiki/Smash_cut
- **Ironic-audio fail:** cheerful audio over a disaster (the Jet2 meme, 124K+ TikToks). https://knowyourmeme.com/memes/nothing-beats-a-jet2-holiday
- **Genre parody and layouts:** "Reality TV editing", where the polish is the joke. Also iPhone-transition reveals, the "Me and my POV" split screen and "3 clips". https://later.com/blog/tiktok-trends/
- **Labelled-group and chat-bubble skits:** "How your trio works" (about 90K posts) and the fake-iMessage "Where are you?". https://later.com/blog/instagram-reels-trends/
- **Episodic "Part N":** vertical episodes that end on a cliffhanger (*Beauty and the Beat*, 200M+ views). https://en.wikipedia.org/wiki/Alan_Chikin_Chow
- **Out of scope:** Italian brainrot, because it is AI-generated. https://en.wikipedia.org/wiki/Italian_brainrot

**What to apply** (strongest first)
1. **Gilligan cuts stay hard.** Trigger: the transcript line before a cut is a negation or prediction ("never", "no way", "不可能"), and the next clip is a new scene. Then audio and picture change within 1 frame, with no SFX and no transition, and the cut is tagged `exempt_from=['jl_cuts']`. https://en.wikipedia.org/wiki/Smash_cut
2. **Keep the creator's timing.** In skit mode, `talk.py` must not shorten a gap that is followed within about 1 s by laughter, a gasp or a jump in face-box area. It must also leave the reaction after a bit's last line alone. Today it cuts every pause over 0.45 s down to 0.27 s [inferred from code]. It shouldn't insert beats either: a study of 20 joke performances found no evidence that punchlines are preceded by pauses. https://doi.org/10.1515/humr.2011.015
3. **Detect the payoff by sound type, not loudness.** Apple's built-in on-device sound classifier labels laughter, chuckle, gasp, screaming and applause. Feed those labels to the payoff, timing-protection and punch-in rules. https://developer.apple.com/documentation/soundanalysis/snclassifysoundrequest
4. **Captions never give away the punchline.** Break the caption before a bit's last clause, show that clause only when it is spoken, and clear captions over a reaction shot with no speech. https://www.bbc.co.uk/accessibility/forproducts/guides/subtitles/
5. **Show the POV premise text from frame 0.** Keep it on screen until at least 2.5 s or the first cut. Put it in the top third inside the safe zone, never over a face, at most 10 words [inferred]. In a 2021 sample of 400 TikToks, 67% of viral videos had on-screen text, against 30% of non-viral ones. https://arxiv.org/abs/2111.02452
6. **Meme fonts:** use Arial, Montserrat or TikTok Sans. Impact reads as a "2006 image macro" and Comic Sans as "Boomer"; use them only in an explicit retro-irony style. https://www.kapwing.com/resources/meme-fonts-which-ones-to-use-and-how-to-use-them/
7. **No look by default.** Apply continuity fixes only: no LUT, letterbox, grain or speed ramps. TikTok's own guidance asks for a "DIY or not overly polished" style. Documentary and reality-TV looks come only as opt-in parody packs. https://ads.tiktok.com/help/article/creative-best-practices
8. **Meme sound effects are `irony_only`.** Their cap is 0 in default packs. An opt-in shitpost pack allows at most 2 per 30 s, never on consecutive cuts [inferred]. https://knowyourmeme.com/memes/vine-boom-sound-effect
9. **Keep real laughter audible.** Spontaneous laughter makes jokes funnier. Don't denoise or trim the camera operator's laugh, and add no canned laughter [inferred]. https://doi.org/10.1016/j.cub.2019.05.073
10. **No promise without a payoff.** Use "wait for it" text or a 0.3 s tease of the aftermath only when a payoff candidate scores above the clip's 90th percentile of event scores. Flag a dead middle, a stretch with no cut, new text or strong sound (warn above 3 s, bad above 5 s [inferred]), and fix it by trimming the setup. https://www.opus.pro/blog/youtube-shorts-hook-formulas

**Premium vs cheap**
- Premium holds the reaction long enough to read; cheap cuts every silence down to a breath [inferred]. https://en.wikipedia.org/wiki/Comic_timing
- Premium uses one punch-in on the punchline; cheap puts a zoom every ~2 s on a fixed grid [inferred]. `remix.py` currently pushes in on every shot. https://www.submagic.co/blog/how-to-make-a-viral-video
- Premium lets the music choice carry the irony; cheap puts a meme sound effect on every line. https://knowyourmeme.com/memes/nothing-beats-a-jet2-holiday
- Premium has clean dry audio, steady framing and a consistent character look; cheap has room echo. https://www.kapwing.com/resources/how-to-create-a-high-quality-micro-drama/
- Premium loops the last frame into the first, with no end card. This rests on a vendor blog only. https://aibrify.com/blog/youtube-shorts-retention-curve-playbook
- Cheap: other apps' watermarks (https://buffer.com/resources/instagram-algorithms/), and TTS voices or AI-generated inserts. Backlash comments got more likes than the AI-slop posts themselves. https://www.kapwing.com/resources/the-tiktok-ai-slop-report/

**Dated / overused in 2026**
- 6-7, after the January 2026 Great Meme Reset. https://en.wikipedia.org/wiki/Great_Meme_Reset
- A record-scratch freeze frame used sincerely, now listed as a "Cliché" (https://knowyourmeme.com/memes/record-scratch-freeze-frame), and "To Be Continued", which peaked in 2016–19. https://knowyourmeme.com/memes/to-be-continued
- A "wait for it" whose build-up is empty. https://knowyourmeme.com/memes/wait-for-it
- The same template stamped identically across videos, which YouTube now treats as inauthentic content. https://support.google.com/youtube/answer/1311392?hl=en
- Rule for the engine: memes and sounds store `{first_seen, peak}` and drop out of auto-suggest 90 days after their peak [inferred]. Formats such as POV and before/after never expire. https://blog.hootsuite.com/tiktok-trends/

**Measurable by VibeCut?**
- **1, yes:** the audio/picture offset at the cut (`check_jl_cuts`), plus the speech helper's transcript.
- **2, later:** needs #3 first, then pause lengths measured on about 20 well-cut skits.
- **3, later:** needs a new SoundAnalysis Swift helper.
- **4, later:** needs a way to find where each bit ends. After that, the check is that a punchline caption never appears before the words are spoken.
- **5, yes:** text timing and safe box, checked against vibevision's face boxes.
- **6, yes:** from style metadata.
- **7, yes:** `check_continuity` covers the fixes; whether a LUT is applied is an export setting.
- **8, yes:** count sound effects per time window.
- **9, later:** needs #3.
- **10, later:** the loudness × motion stand-in already runs on `load()`; trust it only after #3 and calibration.

### Chinese platforms (Douyin, Xiaohongshu/RED, Bilibili)

Most craft claims rest on one secondary blog (woshipm). Every number is a `grammar.py`-style guess until calibrated.

**Sub-styles creators recognise**
- **活人感** ("feels like a real person"): imperfections kept, everyday speech, moments nobody staged. https://www.woshipm.com/share/6382040.html
- **生活碎片** (fragments of life): unpolished compilations that displaced 精致vlog. https://www.woshipm.com/share/5988031.html
- **第一视角**: first-person day-in-the-life, often a numbered series. https://www.bilibili.com/video/BV1qQZaY6E2T
- **文案型旅行vlog**: about 1 minute of scenery under sparse, emotional copy the creator wrote. https://www.woshipm.com/it/6079171.html
- **田园 / 李子柒式**: a craft process with no speech, shot from a fixed camera. https://www.woshipm.com/it/6144474.html
- **口播知识**: 17–51 min talking-head explainer. https://www.bilibili.com/video/BV1Pho9YrEre
- **草台班子微综艺**: scrappy self-made variety show built on real reactions. https://www.woshipm.com/share/6295515.html
- **松弛感**: relaxed; real photos with hand-drawn outline stickers. https://www.uisdc.com/group/632039.html
- **日系奶油 / 古早韩系 / 港风 / 美拉德 / 多巴胺 / 清冷国风**: creamy Japanese, retro Korean, Hong Kong film, Maillard browns, dopamine brights, cool guofeng (all 剪映 filter names). https://github.com/GuanYixuan/pyJianYingDraft/blob/main/pyJianYingDraft/metadata/filter_meta.py
- **CCD风**: digicam flash, grain, blur. https://www.woshipm.com/it/6386702.html
- **新中式**: calligraphy, silk, cloud motifs, restrained styling. https://www.woshipm.com/marketing/6033907.html
- **金碟豹 / KTV复古**: 90s karaoke-disc music-video look, "borrowed nostalgia". https://www.woshipm.com/ai/6431334.html

**What to apply**
1. **Subtraction for process edits.** Li Ziqi's comeback (120M plays in 5 h) used fixed frames, no narration, craft sound plus calm music, and small text at the frame edge, following one craft from start to finish. Engine: add a "Process" storyline axis (one subject, capture order, a clear start and end state). The Pastoral preset drops speech, keeps ambience continuous, holds a median shot of ≥ 4 s and keeps motion ≤ the edit's 40th percentile [inferred numbers]. https://www.woshipm.com/it/6144474.html
2. **On RED a still decides the click.** RED shows a two-column grid with about 4 notes per screen and 20-character titles; its auto big-text cover reads as cheap over time. Engine: the RED export always ships a cover (top bestframe, favouring food/landscape/face labels) and a hard-validated title of ≤ 20 characters. https://www.woshipm.com/share/6413054.html
3. **Chinese caption grammar.** ≤ 16 characters per line, ≤ 2 lines, ≤ 9 characters/s, no commas or full stops (a space instead), a single ？ or ！. Engine: keep talk.py's 14-character lines and swap internal ，、 for a space. Default to sentence mode; per-character highlight only in Hype. New finding `caption_punct_count`, target 0. https://partnerhelp.netflixstudios.com/hc/en-us/articles/215986007-Simplified-Chinese-Timed-Text-Style-Guide
4. **Real camera footage is a legal asset.** China's labelling measures (in force from 1 Sep 2025) require a visible label at the start plus metadata on synthesised video. Art. 10 forbids tools that strip labels. Engine: add a manifest field `synthetic_frames` (default 0; slow motion only from native high-fps footage). Label at t = 0 when it is above 0, and carry imported clips' AI-content labels through export [inferred implementation]. https://www.cac.gov.cn/2025-03/14/c_1743654684782215.htm
5. **Dead stretches, not a 3-second rule.** An unofficial September 2026 summary says Douyin now weighs the average share of the video watched, with drop-offs near 20 s and past 1 min. Engine: a report-only `dead_stretch` finding (≥ 8 s with no cut, no speech and below-median motion). Don't encode the article's weights or re-hook times. https://www.woshipm.com/share/6461663.html
6. **Protect 活人感.** RED operators call it essential: unpolished, not templated, spoken. Engine: the rough-cut gate never auto-rejects 1–3 candid "human moments" (laughter, speech with a face on screen) without the creator's say. Never fake roughness with filters [inferred]. https://www.woshipm.com/share/6382040.html
7. **Stay out of the 剪映 stock kit.** It ships 453 transitions (3D, cube, heart, page-turn, white flash) plus one-tap letterbox, DV and CCD effects; that these read as "template" is [inferred]. Engine: allow only cut, dissolve, dip, whip and match cut. No letterbox on 9:16, white flashes only on music drops, and a `flash_per_min` finding that warns above 2. https://github.com/GuanYixuan/pyJianYingDraft/blob/main/pyJianYingDraft/metadata/transition_meta.py
8. **Borrow 剪映's look vocabulary, not its numbers.** Its 1,052 filter names are the words creators ask for. Engine: use them as labels on reference edits the creator supplies, measured with `style.look`. Ship preset numbers only after calibration. https://github.com/GuanYixuan/pyJianYingDraft/blob/main/pyJianYingDraft/metadata/filter_meta.py
9. **Bilibili rewards length.** A 21:23 travel episode drew 19.9M views in 2025. Engine: the Bilibili export keeps long pacing and writes "MM:SS 标题" chapters from storyboard parts (≥ 3, each ≥ 60 s). It flags `parts_per_10min` below 4 [inferred]. https://www.bilibili.com/video/BV1V1ZcY5ESQ
10. **Real CCD, not a CCD filter.** #今天玩CCD了吗# has 970M+ reads. Engine: take the date stamp only from real capture metadata. Detect genuine old-camera sources (ffprobe make/model, width ≤ 1280) and exempt their noise from rough-cut rejects [inferred]. https://www.woshipm.com/it/6386702.html

**Premium vs cheap**
- Premium: one look throughout; real dates, real pasted comments and the creator's own 文案; restraint. https://www.woshipm.com/it/6144474.html
- Premium: an open CJK font per vibe (LXGW WenKai: OFL licence, can be embedded), never fonts licensed only inside 剪映. https://github.com/lxgw/LxgwWenKai
- Cheap: 3D, heart or page-turn transitions; a flash and shake on every beat; letterbox on vertical footage; DV/CCD frames as decoration; 综艺花字 (variety-show text) outside comedy [inferred].
- Cheap: anything that looks AI-made. https://www.woshipm.com/share/6461663.html
- Paradox: relaxedness is itself performed ("松弛感也能卷"). Protect candid moments; don't simulate them. https://www.woshipm.com/it/5630437.html

**Dated / overused in 2026**
- The 精致vlog wake-up opener (curtains, stretch, wash) and its props (aroma diffuser, flowers, coffee), now called "太假了" (too fake). Engine: a report-only `routine_opener` check on the first 10 s [inferred]. https://www.woshipm.com/share/5988031.html
- Douyin 神曲 (viral hit songs) as the default soundtrack, while 国风 and healing music rise (2023 evidence). https://www.woshipm.com/it/5960174.html
- Generic 鸡汤 (platitude) copy [inferred].

**Measurable by VibeCut?**
| # | Check | Verdict |
| --- | --- | --- |
| 1 | shot length, motion | yes; "no speech" later (`speech_mask` is level-based) |
| 2 | title length, cover pick | yes |
| 3 | punctuation, characters/line, characters/s | yes |
| 4 | `synthetic_frames` | yes; incoming labels later (export.py has no metadata passthrough) |
| 5 | dead stretches | yes (cuts, motion); speech later |
| 6 | human moments | later (needs VAD, faces) |
| 7 | flashes, letterbox | yes (`style.transitions`, `style.letterbox`); 3D/page-turn no |
| 8 | look labels | yes (`style.look`) |
| 9 | chapters | yes |
| 10 | old-camera source | yes (ffprobe); CCD grade later |

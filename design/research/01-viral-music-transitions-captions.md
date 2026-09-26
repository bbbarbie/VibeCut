# How viral vertical and vlog edits are made (research, 2026-09-25)

Web research for the auto-edit presets. `[n]` = source number at the bottom.
**[inferred]** = the researcher's synthesis, not stated by a source. Almost
all sources are secondary vendor blogs; only [2], [19], [20] are
platform-official. Treat every number here like a `grammar.py` threshold:
a guess until calibrated.

## 0. Rules that apply to all three formats

- **Loudness:** mix the voice to about −14 LUFS. YouTube turns louder audio down to −14 and leaves quieter audio alone [8][9].
- **Ducking:** under speech, music sits 18–25 dB below the voice. Duck in under 300 ms, release slowly, let the music swell back in gaps [8].
- **Beat cutting:** cut every bar (4 beats ≈ 2 s at 120 BPM) for a calm pace, every beat or two only for intensity; every-beat cutting is exhausting beyond ~8 bars. The downbeat is the most reliable cut point; change scenes every 4–8 bars with the song's sections [12].
- **Transitions:** clean cuts are the default; a transition on every clip is the classic beginner mistake [14]. Star and linear wipes read dated [15]. Short dissolves are fine; long ones only in slow, reflective stretches [15].
- **Whip pans** only look polished when exposure matches on both sides [16] — fits our exposure-jump check [inferred].
- **Transition SFX:** at most 3–5 per short video; a sound on every cut is chaotic [13]. Quick cut/swipe → short whoosh; fade → swell or nothing [13].

## 1. Short vertical (Reels / TikTok / Shorts, 9:16, 7–90 s)

- **Length:** in an OpusClip sample of 1,449 TikToks the most viral 10% had a median of 41 s [10]. Shorts now run to 3 min [20]. TikTok Creator Rewards need ≥ 1 min [19]. [inferred] Default 25–45 s; offer 60–75 s for monetising creators.
- **Hook:** keep ≥ 70% past second 3; the typical failure is a 30–50% drop between seconds 1 and 3. Open with a pattern break (framing, motion, contradiction) plus 3–6 words of on-screen text, never a greeting [11]. [inferred] Put the best-scoring shot first.
- **Pacing:** [inferred] cut on beats/bars; at 100–130 BPM that's ~1–2 s shots, longer holds on payoff shots. Pattern interrupts fix mid-video drops [11][18].
- **Music:** trending sounds matter for reach on TikTok/IG [32]; IG also favours original audio [32]. We can't place trending songs (§5).
- **Captions:** dominant talking style = word-by-word karaoke, ALL CAPS, heavy sans (Montserrat Black, Anton, Bebas Neue, "The Bold Font"), thick black stroke, yellow keyword highlight [27]. TikTok's open-source UI font: TikTok Sans (2025) [29].
- **Safe zones (1080×1920):** TikTok top 108–130, bottom 250–320, left 60, right 120 [5][6]. Reels: text ≥ 250 from top and ≥ 420 from bottom (Meta), others say 14%/35%/6% [7]. Shorts: avoid the bottom 10–15% [6]. Reels grid crop: key visuals inside the central 4:5 (1080×1350) [7]. [inferred] Universal text box: x 60–960, y 250–1500.

## 2. Long vertical vlog (9:16, 2–10 min, "day in my life")

- TikTok reportedly pushes 1–3 min videos in 2026; ≥ 1 min earns Creator Rewards [19].
- Music: soft lo-fi instrumental under slow mornings, coffee, routines [30].
- Captions: small timestamps, lowercase diary text [30][28]; lowercase serif = poetic/soft, Typewriter = minimal, Inter = clean; static captions suit aesthetic content better than karaoke [28].
- [inferred] Structure: 3 s hook, chapters by time of day, one track per chapter with an L-cut on ambient sound between chapters, ~2–4 s shots. Fits our time/place/subject axes.
- When the creator talks: word-level captions, music ducked per §0 [8].

## 3. YouTube long vlog (16:9, 8–25 min)

- Hook: the first 30 s shape retention most [18]; vlog intro 5–12 s — best moment first, then the goal [18]; branded intro ≤ 3–5 s [18].
- Grammar: J/L-cuts [17]; B-roll every ~10–20 s in talking stretches [17]; fast cuts for action, slow for reflection [17]; montage bursts of 1–3 s clips on the beat [17].
- [inferred] Music: change track per section/location; ducked 18–25 dB under speech; montages music-forward.
- Content ID: registered "royalty-free" music can still be claimed; libraries whitelist channels [34].

## 4. Aesthetic presets

- **Cinematic:** 2.39:1 letterbox, teal-orange grade, 24 fps cadence, slow motion from 60/120 fps, ambient score [26]. [inferred] Hard/match/J-cuts; rare low risers/sub hits; small, widely spaced lower-third sans.
- **Cozy / soft:** lo-fi, soft visuals [30]; lowercase serif or handwritten static captions [28]. [inferred] Warm lifted-shadow grade, 6–10 frame dissolves, soft pops/page-turns.
- **Clean minimal:** Inter or TikTok Sans, static text [28][29]. [inferred] Neutral grade, hard cuts, no SFX.
- **Film / analog / VHS:** grain, muted colour with blooming reds, tracking lines; a Gen Z reaction to over-polish [24]. [inferred] Film burns, light leaks, flash frames; shutter/tape-click SFX; Typewriter [28].
- **Y2K / playful:** chrome and bubble type, glitch, scan lines, star/butterfly stickers, pastel-to-neon, hyperpop [25]. [inferred] Zoom punch-ins, swipes, pop SFX.
- **Quiet luxury:** restraint, slow pacing, deliberate transitions, script or elegant sans, optional B&W B-roll, cream/taupe palette, ambient music [23].
- **Energetic hype:** phonk, speed ramps, velocity edits, shakes and flashes synced to SFX [31]. [inferred] Beat-cut only in drops; cap SFX per [13].

## 5. Licensing

| Source | Can VibeCut bundle or auto-place it? |
|---|---|
| TikTok Commercial Music Library | **No** — in-TikTok only, no separate distribution [2]; commercial accounts must use it or hold a licence since 25 Jul 2025 [1] |
| Instagram library | **No** — in-app only; business accounts get only the ~14k-track Meta Sound Collection [33] |
| YouTube Audio Library | **No** — standard licence is YouTube-only; only CC-BY tracks usable elsewhere, with attribution [4] |
| Shorts audio library | In-app only, ≤ 90 s per Short [20]; from 24 Sep 2026, 1–3 min Shorts with a Content ID claim aren't auto-blocked [20] |
| CapCut | Personal/non-commercial in-app library; "commercial sounds" work on few platforms [3]. [inferred] ByteDance-internal deals we can't copy |
| Epidemic Sound Partner API | **Yes** — 55k+ tracks, 250k+ SFX, cleared globally, sublicensing, length adaptation and music-to-video matching; free prototyping tier, production via sales [21] |
| Artlist | Standard licence can't be sublicensed; Enterprise API by agreement [22] |
| User's own tracks | Already supported (`cutgrammar/music.py`); the user carries the licence |

[inferred] For trending sounds: export a full mix **and** a no-music version (original audio + captions), and let the creator attach the trending sound in TikTok/Instagram, with a sidecar listing the cut points.

## Preset parameter table ([inferred]; BPM ranges are judgement)

| Preset | Music genre / BPM / energy curve | Transitions + SFX | Shot length | Captions | Fonts | Grade |
|---|---|---|---|---|---|---|
| Cinematic | Ambient/orchestral, 70–100, slow build to a peak at 70–80% then resolve | Hard, match, J/L-cut; low riser at 1–2 peaks | 2.5–5 s, every bar or two | Lower third, small, sentence case, fade in | Inter Light, Montserrat Light | Teal-orange, 2.39 letterbox, soft contrast |
| Cozy / soft | Lo-fi, acoustic, bedroom pop, 70–90, flat and warm | Cut + 6–10 frame dissolve; soft pop/page turn ≤ 3 | 2–4 s | Static, lowercase, timestamps | Lowercase serif, handwritten | Warm, lifted blacks, low saturation |
| Clean minimal | Minimal electronic/piano, 90–110, steady | Hard cuts only; no SFX | 1.5–3 s on the bar | Static, small, centred low | Inter, TikTok Sans | Neutral, accurate WB |
| Film / VHS | Indie, 90s-sampled, lo-fi hip-hop, 80–100 | Film burn, light leak, flash; shutter/tape click ≤ 4 | 1.5–3 s | Typewriter + date stamp | Typewriter, VCR mono | Grain, halation, faded blacks, warm reds |
| Y2K / playful | Hyperpop, dance-pop, 120–150, bouncy | Zoom punch, swipe, glitch; pop/ding ≤ 5 | 0.8–1.5 s on the beat | Bubble/chrome, emoji, stickers | Bubble display, Poppins Bold | Saturated pastel-neon, bloom |
| Quiet luxury | Ambient, neo-classical, soft jazz, 60–90, flat | Slow cut, long dissolve, optional B&W B-roll; no SFX | 3–6 s | Sparse, wide tracking | Script + light sans | Muted cream/taupe, low contrast |
| Energetic hype | Phonk, trap, EDM, 130–160, build → drop | Speed ramp, whip, flash, shake; whoosh/impact on drops only ≤ 5 | 0.4–1 s in drops, 1.5 s in builds | Word-by-word caps, stroke, yellow keyword | Montserrat Black, The Bold Font, Anton | High contrast, crushed blacks |
| Talking (any format) | Instrumental, ducked 18–25 dB | Jump cuts, punch-ins; none | Per sentence | Karaoke word highlight | Montserrat Black, TikTok Sans | Natural skin |

## Recommended first builds

1. Beat snapping on the bar (beat-level only in drops) — measurable: cuts per bar, share on a downbeat [12].
2. Ducking + −14 LUFS target, measured [8][9].
3. Caption safe-zone check + two caption styles (karaoke-bold, static-lowercase).
4. A `Preset` object with this table's parameters; start with Cozy, Cinematic, Clean (no new visual effects needed).
5. Music: user's own tracks + no-music export for trending sounds now; evaluate Epidemic's Partner API (free prototyping tier).

## Sources
1. https://www.soundstripe.com/blogs/tiktok-music-licensing-rules
2. https://www.tiktok.com/legal/page/global/commercial-music-library-user-terms/en
3. https://www.foximusic.com/royalty-free-music-licensing-for-capcut-videos/ ; https://blazemedia.co.uk/2025/06/26/capcut-2025-copyright-changes
4. https://lickd.co/youtube-audio-library/ ; https://www.licenseorg.com/guide/music-audio/youtube-audio-library
5. https://zeely.ai/blog/tiktok-safe-zones/
6. https://kreatli.com/guides/safe-zone-guide
7. https://billo.app/blog/meta-ads-safe-zones/ ; https://zeely.ai/blog/master-instagram-safe-zones/
8. https://zellahq.com/blog/music-ducking-explained/
9. https://www.criticallisteninglab.com/en/learn/loudness/youtube
10. https://www.opus.pro/blog/how-long-should-a-tiktok-be-2026
11. https://www.opus.pro/blog/youtube-shorts-hook-formulas ; https://www.shortimize.com/blog/youtube-shorts-retention-rate ; https://aibrify.com/blog/youtube-shorts-retention-curve-playbook
12. https://clipmusic.ai/blog/bpm-video-editing-guide
13. https://esecut.com/blog/sound-effects-that-boost-engagement ; https://sonilo.com/blog/guides/transition-effect-sound-video-edits
14. https://www.descript.com/blog/article/video-transitions
15. https://insideeditors.com/video-editing-transitions/
16. https://www.adobe.com/creativecloud/video/discover/whip-pan.html
17. https://www.obsbot.com/blog/vlog/editing-a-vlog
18. https://socialrails.com/blog/youtube-audience-retention-complete-guide ; https://www.renderforest.com/blog/how-long-should-youtube-intro-be
19. https://www.tiktok.com/creator-academy/article/creator-rewards-program ; https://benly.ai/learn/tiktok-ads/creator-rewards-program-2026
20. https://support.google.com/youtube/answer/15424877?hl=en
21. https://www.epidemicsound.com/business/developers/ ; https://www.netinfluencer.com/epidemic-sound-launches-api-to-embed-ai-powered-music-licensing-into-third-party-platforms/
22. https://artlist.io/help-center/privacy-terms/artlist-license/ ; https://developer.artlist.io/use-cases
23. https://captions.ai/styles/byline
24. https://www.canonoutsideofauto.ca/2025/09/13/why-vintage-camcorder-footage-is-making-a-major-comeback-in-modern-photography/ ; https://www.storyblocks.com/resources/blog/retro-video-aesthetics
25. https://studio2am.co/blogs/news/the-rise-of-y2k-aesthetic-in-graphic-design ; https://fontvibe.ai/styles/y2k
26. https://www.hasanabdulla.co.uk/2026/06/18/what-makes-a-video-look-cinematic/
27. https://ascynd.io/en/blog/hormozi-captions ; https://sendshort.ai/guides/hormozi-captions/
28. https://blitzcutai.com/blog/best-caption-fonts-tiktok ; https://memefont.org/blog/best-viral-text-fonts-tiktok-instagram-reels-2026
29. https://www.kapwing.com/resources/what-fonts-does-tiktok-use-and-how-to-get-them/
30. https://www.tiktok.com/discover/lofi-vlog-music ; https://www.tiktok.com/discover/day-in-my-life-edit-tutorial
31. https://www.tiktok.com/discover/phonk-speed-ramp ; https://www.tiktok.com/discover/fast-paced-phonk-music-for-edits
32. https://buffer.com/resources/trending-audio-instagram/ ; https://creatorflow.so/blog/instagram-algorithm-2026/ ; https://www.serotonin.co.uk/news/how-instagrams-reels-ranking-works-in-2025-what-creators-need-to-know
33. https://www.foximusic.com/blog/instagram-reels-music-copyright-legal-guide/ ; https://www.trymaas.com/blog/instagram-business-account-trending-music-risks/
34. https://www.foximusic.com/blog/need-background-music-that-wont-trigger-content-id/ ; https://www.epidemicsound.com/how-it-works/license-music-legally/

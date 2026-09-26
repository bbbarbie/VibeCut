# What the data says predicts virality and retention

*Research agent output, 2026-09-25 (taste-research workflow). Unedited except for this header. Sources are the agent's; verify before relying on any single claim.*

# What predicts virality, retention and engagement in short-form and vlog video: the quantitative evidence (research, 2026-09-25)

`[n]` = source number. **[inferred]** = my synthesis, not something a source states. This report does not repeat 01/02; where it touches their topics (length, hooks), it only adds detail they lack.

**Coverage limit:** the session's web-search budget was already spent when this task started. Every source below was fetched directly from a URL I already knew, or looked up by its DOI. So some likely sources were not retrieved: TikTok Marketing Science reports (their pages are JavaScript-only), 2024–26 marketing-journal papers on TikTok ads, and Dash Hudson, Tubular and Later studies. Treat this as a floor, not a survey.

## Headline [inferred]

Who posts, and what the video is about, explain most of the variance in reach. Editing features explain a small but real remainder. The strongest editing-related signal is **whether the first ~5 s holds the viewer**. So VibeCut should measure and promise *retention hygiene*, not virality. That fits CLAUDE.md's "no amateur tells".

## A. Robust findings (large sample and/or peer-reviewed, direction consistent across sources)

| # | Claim | Numbers | Sample | Caveats |
|---|---|---|---|---|
| A1 | **The first 5 s almost is the engagement.** The share of viewers who watch past 5 s tracks duration-normalised watch % closely. | r = **0.926**; the distribution is bimodal (people skip fast or stay) [1] | 90k Snapchat Spotlight videos, 10–60 s, ≥2k views; ECCV 2024 [1] | Correlational; one platform |
| A2 | **Watch % falls as duration rises; raw watch time favours long videos.** | Top-3% videos: average watch time = 0.556·d + 5.64 s [1]. That is ≈74% watched at 30 s and ≈65% at 60 s **[inferred arithmetic]**. Watch % depends on duration across 5.3M YouTube videos [2]. Kuaishou's recommender was biased toward long videos by duration alone [3] | [1][2][3] | Any calibration label has to be duration-normalised |
| A3 | **Technical quality barely predicts engagement.** | Video-quality scores vs engagement: r = 0.07–0.31. Adding aesthetic features: +0.007 SRCC. Background-sound class: +0.011. Semantic captions of the content: +0.038 (final SRCC 0.696) [1] | Same as [1] | Ablation on one model |
| A4 | **Creator and context dominate.** | Creator has ≥10k followers: 90% of viral vs 24% of non-viral [4]. Context, topic and channel alone explain **R² = 0.77** of engagement [2]. In a sock-puppet audit, "follow" had the strongest effect, then likes, then view rate [5]. Attention stays ~45% over a user's lifetime; users engage more with creators they follow [6] | 400 hand-coded TikToks [4]; 5.3M YouTube videos (2016 data, ICWSM 2018) [2]; WWW'22 [5]; 347 users / 9.2M recommendations, CHI'24 [6] | TikTok says follower count is not a *direct* ranking factor [7]. [2] is from 2018 |
| A5 | **Emotion beats information, and moderate length is shared most.** | Amusement, excitement, inspiration, warmth and surprise raise sharing. Information-focused content lowers it. Sharing peaks at **1.2–1.7 min**. Early or persistent brand placement hurts sharing [11] | Two field studies plus a holdout, 60+ ad features; *J. Marketing* 2019 [11] | Ads, not vlogs. **[inferred]** analogue: don't front-load intros or logos |
| A6 | **Platforms optimise for watch-through.** | TikTok: finishing a longer video is a "strong indicator" [7]. Instagram predicts reshares, watching all the way through, likes, and audio-page visits [8]. YouTube's "Intro" metric is the % still watching at 30 s [9] | Platform statements | No effect sizes given |

## B. Moderate or suggestive (small sample, vendor data, older, or another domain)

- **Shot scale:** among viral TikToks, 64% used close-ups vs 54% of non-viral, and 35% used medium shots vs 29%. **Wide/long shots: 1% of viral vs 17% of non-viral.** Hand-coded, kappa 0.89, n = 400 [4]. Small sample.
- **On-screen text:** present in 67% of viral vs 30% of non-viral TikToks [4]. Facebook (c. 2016): captioned ads got **+12%** view time [15]. TikTok's 2025 ad guidance says "5–10 words per second" of text [14]. That is faster than comfortable reading, so treat it as unreliable **[inferred]**.
- **Direct address (talking to the viewer, second-person point of view):** 70% of viral vs 60% of non-viral [4].
- **Speech rate:** across 6.9M edX viewing sessions, engagement rose up to **2×** with faster speakers (range 48–254 wpm, mean 156). There was a dip at 145–165 wpm for 6–12 min videos. Median engagement time was ≤6 min whatever the video length [16]. This is education data from 2014; applying it to vlog voiceover is **[inferred]**.
- **Length by niche:** OpusClip studied 1,449 TikToks, with "viral" = top 10% (≥5.1M views). **Lifestyle & Aesthetic averaged 39.5 s** vs 60.8 s for Narrative/Documentary. Viral videos over-index at 15–30 s (24.3% vs 17.3% overall) and under-index at 60–90 s (13.9% vs 18.5%) [17]. Vendor data; niches are defined by the vendor.
- **Front-loaded value:** Facebook/Nielsen (c. 2016): up to **47%** of campaign value came in the first 3 s and 74% by 10 s. 65% of people who watched 3 s reached 10 s [15]. Old, and about ads.
- **The ABCD bundle:** ads that follow all of Google's ABCD guidelines got **+30%** short-term sales likelihood and +17% brand contribution (Google/Kantar, 2021) [12]. This is for the bundle, not any single feature.
- **Pace follows story acts (films):** in the setup, shots get longer and motion drops. Into the climax, shots shorten and motion rises; at the end, shots lengthen again. Images darken through the middle acts and brighten at the climax [18]. Evidence is from Hollywood films; transfer to vlogs is **[inferred]**.
- **Long YouTube baseline:** among channels with ≥250k subscribers, median video length was ~12 min, and 10% of videos took 79% of views (243k videos, 2019) [20]. Shorts get more views and likes per view than regular videos, but fewer comments per view (16.8M videos, WebSci'24) [22].

## C. Weak, or no usable evidence found

- **Cut rate in short-form:** I found no peer-reviewed effect size. Google's open-source ABCD detector encodes *heuristics*, not validated thresholds [13]:
  - quick pacing = ≥5 shots within a 5 s window;
  - overall average shot ≤2 s;
  - "dynamic start" = first shot shorter than 3 s;
  - close-up face = face box ≥15% of the frame;
  - "early" = first 5 s;
  - Shorts tight framing = subject ≥60% of the frame, with close-up share ideally 30–60%.
- **Trending sound and music tempo:** nothing quantitative. The only data point is that background-sound class adds +0.011 SRCC [1]. Instagram does use audio-page visits as a ranking target [8].
- **Loops and rewatch:** no study found. YouTube now counts a view when a video starts to play, in all formats (from 24 Aug 2026) [10]. **[inferred]** Public view counts are therefore a poor label for calibration.
- **Colour and brightness:** only image evidence. Professional, high-quality photos raise engagement; the effect of colourfulness varies by category; faces help on Twitter but not on Instagram [19]. No short-form video result.
- **Faces in the first seconds:** "visible face in first 5 s" is an ABCD check [13], but no per-feature result is published.
- **Discard:** unsourced vendor claims such as "60% of viewing is sound-off" and "viewers decide in under 2 s" [23]. Also discard Wistia's "52% engagement for videos under 1 min" [21]: it is hosted B2B video, not feeds.

## D. What VibeCut can take from this [inferred]

1. **Calibration label:** use watch % normalised by duration, or the share still watching at 5 s. Do not use views. Compare **within one creator** (their hits vs their flops) to remove the creator effect from A4. The creator's own retention exports from YouTube Studio or TikTok analytics are the best data we can get.
2. **New `grammar.py` measurements, each with a discrimination test:**
   - first-shot duration and shots in the first 5 s;
   - share of wide shots and close-up share, from the Apple Vision helper's face/subject boxes;
   - text on screen in the first 3 s;
   - speech rate in wpm, from the speech helper;
   - pace arc per part: shot length, motion and brightness;
   - length vs a per-niche target (e.g. ~40 s for aesthetic/lifestyle).
3. **Where to spend effort:** because the 5 s hold predicts the rest (A1), put the most ranking work into choosing the opening shot and its first cut.
4. **Positioning:** A3 means a clean edit won't create reach by itself. It removes reasons to swipe away. Keep the copy there.

## Sources

1. https://arxiv.org/abs/2410.00289 (Li et al., ECCV 2024; details from https://arxiv.org/html/2410.00289)
2. https://arxiv.org/abs/1709.02541 (Wu, Rizoiu & Xie, ICWSM 2018)
3. https://arxiv.org/abs/2206.06003 (Zhan et al., Kuaishou, 2022)
4. https://arxiv.org/abs/2111.02452 (Ling et al.)
5. https://arxiv.org/abs/2201.12271 (Boeker & Urman, WWW 2022)
6. https://arxiv.org/abs/2301.04945 (Zannettou et al., CHI 2024)
7. https://newsroom.tiktok.com/en-us/how-tiktok-recommends-videos-for-you
8. https://about.instagram.com/blog/announcements/instagram-ranking-explained
9. https://support.google.com/youtube/answer/9314415
10. https://support.google.com/youtube/answer/2991785
11. https://doi.org/10.1177/0022242919841034 (Tellis et al., J. Marketing 2019)
12. https://business.google.com/us/think/future-of-marketing/youtube-video-ad-creative/
13. https://github.com/google-marketing-solutions/abcds-detector (`configuration.py`, `features_repository/shorts_features.py`)
14. https://ads.tiktok.com/help/article/creative-best-practices?lang=en
15. https://www.facebook.com/business/news/updated-features-for-video-ads
16. https://doi.org/10.1145/2556325.2566239 (Guo, Kim & Rubin; PDF: https://pg.ucsd.edu/publications/edX-MOOC-video-production-and-engagement_LAS-2014.pdf)
17. https://www.opus.pro/blog/how-long-should-a-tiktok-be-2026
18. https://doi.org/10.1186/s41235-016-0029-0 (Cutting 2016; PMC5256470)
19. https://doi.org/10.1177/0022243719881113 (Li & Xie, JMR 2020)
20. https://www.pewresearch.org/internet/2019/07/25/a-week-in-the-life-of-popular-youtube-channels/
21. https://wistia.com/learn/marketing/optimal-video-length
22. https://arxiv.org/abs/2403.00454 (Violot et al., WebSci 2024)
23. https://www.opus.pro/blog/youtube-shorts-hook-formulas

# Learning from viral videos legally: data access, datasets, ToS, how other tools learn taste

*Research agent output, 2026-09-25 (taste-research workflow). Unedited except for this header. Sources are the agent's; verify before relying on any single claim.*

# Learning from viral videos, legally (research, 2026-09-25)

`[n]` = source; **[inferred]** = my own synthesis, not a source's claim. This reports what sources say; it is not legal advice. The web search budget ran out at the start, so everything below comes from fetching known URLs directly.

**Short answer:** no official channel gives a commercial app viral *video files* in bulk. The legal routes are:
- files the user already has, analysed on the Mac into numbers only;
- the creator's own analytics, with their permission (OAuth);
- CC-BY or commissioned corpora for calibration;
- people on the team watching trend pages and writing down what they see.

## 1. Official data access

| Channel | Who can use it | What it returns | Fit for VibeCut |
|---|---|---|---|
| TikTok Research API | Academics and EU non-profits "independent of commercial interests" [1]. FAQ: "creator, advertiser, or commercial user… eligible? No." [2] | Public metadata. No "commercial or unauthorized purpose"; data must be refreshed every 30 days [3] | **Closed** to us |
| TikTok Commercial Content API | "The public and researchers"; **EU ads only** [4] | Ad metadata plus `videos[].url` [5] | Ads only; its terms were not checked |
| TikTok Creative Center | Login required [7] | Top Ads (filter by region, objective, format, likes; sort by reach or CTR) and Trends. The only API on offer is Symphony, which generates ads [6][7] | Reading by people only |
| TikTok Display API | The authorised user | Their **own** public videos: views, likes, shares, duration [8] | Per creator |
| YouTube Data API | Any developer | `chart=mostPopular` by region and category; **metadata only** [10] | Trend metadata |
| YouTube Analytics API | Channel owner [inferred] | `audienceWatchRatio`, and `relativeRetentionPerformance` against "videos of similar length" [14] | **The best legal "what works" signal** |
| Instagram Graph API | Pro accounts | Hashtags: "30 unique hashtags within a 7 day period" [15]. Business Discovery shows other accounts' counts, but "GET on any returned IG Media will fail" [16]. Own Reels: `reels_skip_rate` (first 3 s), average watch time, saves, shares [17] | Own insights only |
| Douyin / Xiaohongshu | — | **Not verified**: the portals only render with JavaScript | — |

YouTube's developer policy [11] forbids you to:
- "download, import, backup, cache, or store copies of YouTube audiovisual content" (III.E.1.a);
- "scrape" (III.E.6);
- "create new or derived data or metrics" from API Data (III.E.4.h).

Stored data may be kept for 30 days at most (III.E.4.c). YouTube also publishes Trending Charts [13].

## 2. Datasets for calibration

| Dataset | Contents and labels | Licence |
|---|---|---|
| **FineVideo** | 43,751 CC YouTube videos, 3,425 h, 122 categories. Views and likes; scenes, mood, "editing details (transitions, effects)" | Per video, "including attribution"; access is gated [20]. CC-BY allows commercial use [inferred] |
| SnapUGC | 90k Snapchat shorts with watch-based engagement labels. The authors say quality scores (MOS) "do not strongly correlate" with engagement | **None stated** [21] |
| SMP-Video | 6k TikTok videos; popularity | "All rights reserved" [22] |
| MicroLens | 1M micro-videos including raw video; 1B interactions | No licence; "secondary downloads" not allowed [23] |
| VADB | 7,881 videos (the paper says 10,490); 37 professionals score composition, shot size, lighting, colour | **CC BY-NC 4.0** [25] |
| MovieCuts | 173,967 clips; 10 cut types (J/L cut, cutting on action, match cut) | Code MIT; film clips on request [27] |
| AVE | Movie scenes; shot size, angle, motion | You download the clips yourself with yt-dlp; "We do not own the movie clips" [28] |
| KVQ, DOVER/DIVIDE-3k, Shot2Story | Quality and aesthetic scores; shot captions | Unclear / S-Lab "non-commercial" / CC BY-NC-SA [24][26][29] |
| Edit3K | 3,094 editing components, 618,800 rendered videos | Repo MIT; dataset licence not shown [30] |
| YouTube-8M | Pre-computed features only | CC BY 4.0 [31]. No pixels, so no use for measuring craft [inferred] |
| Hugging Face "TikTok-10M" and similar | 6.65M rows of play and share counts | "other" [32]. Probably scraped; avoid [inferred] |

I found no dataset of professional vs. amateur vlogs [33].

## 3. Legal and ToS status (as reported)

- **Platform terms:**
  - TikTok bans any attempt to "scrape, crawl, export or otherwise extract any data or content in any form, for any purpose… except as approved in writing" [9].
  - YouTube bans "automated means (such as robots, botnets or scrapers)" and any download it hasn't authorised [12].
  - Instagram bars collecting "in an automated way without our express permission" [18].
  - Douyin §5.3(4) bans "爬虫抓取、模拟下载" (crawling and simulated downloads), and §5.3(7) bans commercial use [19].
- **US scraping cases:** Meta v. Bright Data (2024) found that scraping public data while logged out did not breach Meta's terms. X v. Bright Data was dismissed [34]. hiQ v. LinkedIn held that scraping public data does not violate the CFAA [35]. [inferred] Those rulings covered logged-out scraping. VibeCut's users are logged-in account holders, so the terms bind them.
- **Stream ripping:** in 2020 the RIAA used DMCA §1201 to take down youtube-dl, treating YouTube's "rolling cipher" as a copy-protection measure. GitHub reinstated the project, and in 2023 the Hamburg Regional Court ruled against a host of it [36].
- **Analysis vs. redistribution:**
  - The US Copyright Office (2025) calls training "most transformative when… research, or in a closed system that constrains it to a non-substitutive task" (p.45).
  - The same report says "knowing use of… pirated or illegally accessed works should weigh against fair use" (p.51) [37].
  - In Thomson Reuters v. Ross (2025), fair use was **rejected** for a *non-generative* AI built "to compete with Westlaw". One factor still went Ross's way because it "did not make West headnotes available to the public" [38].
  - In Bartz v. Anthropic (2025), training on purchased books was fair use; training on pirated copies was not [39].
- **China:**
  - Copyright Law Art. 24(1) allows use "为个人学习、研究或者欣赏" (for personal study, research or appreciation) [40].
  - The Anti-Unfair Competition Law, Art. 13, in force from 15 Oct 2025, bans obtaining another business's data "以欺诈、胁迫、避开或者破坏技术管理措施等不正当方式" (through fraud, coercion, circumventing technical measures or other improper means) [41].
  - The Generative AI Interim Measures, Art. 7, require "具有合法来源的数据" (data from lawful sources) [42].

## 4. How products learn "taste"

- **CapCut:** templates show usage counts ("484.6K · 00:13"), plus "Trending Templates" and "Editor's Pick" [43]. The signal is how often people reuse a template's timing and fill it with their own clips [inferred].
- **Instagram:** "Use template" keeps "the original clip timing and structure while you substitute your own media" [44]. The Edits app adds an Inspiration tab ("only… trending videos", with "Use audio"), skip rate and a retention graph [45].
- **OpusClip:** its Virality Score (0–99) rates Hook, Flow, Value and Trend, based on "big data… latest social and marketing trends" [46]. Its own length study says: "We scraped 1,449 public TikToks" [47].
- **Captions:** "40+ AI Edit styles", named by aesthetic ("Bloom: A soft, dewy aesthetic") [48].
- **Submagic:** "viral caption styles"; it doesn't say how they were chosen [49].
- **VEED:** templates to "scale what works" [50].

[inferred] None of these tools has published a model trained on scraped viral video. What they have built up instead:
- counts of how often templates are reused;
- creators' own retention data;
- many small, named **style recipes**.

That last one is the way to go past the 7 presets.

## 5. Recommended pipelines [inferred]

**(a) "Videos I love" reference feature**
1. Accept only files the user drops in:
   - their own exports;
   - videos saved with a platform's own download button;
   - files a creator sent them.

   A pasted URL opens in the browser and is never fetched. No yt-dlp.
2. Decode once with `media.load()` and keep only a **style fingerprint**:
   - shot-length distribution;
   - cut offsets against the beat;
   - motion and brightness curves;
   - caption box position and size;
   - loudness.

   Throw away the frames and upload nothing. This matches the "closed, non-substitutive" pattern where nothing is made public [37][38].
3. Apply the fingerprint to the user's own clips, the way "Use template" does [44]. Never reuse the reference video's audio or frames.
4. The user confirms they have the right to use the file, and fingerprints stay on the Mac.
5. Offer an opt-in OAuth link to the user's own retention, skip-rate and view data [8][14][17].

**(b) Calibration corpus**
1. **Clean base:** the vlog, travel and lifestyle categories of FineVideo. Check each video's licence, keep the attribution, and treat view counts as a weak label [20].
2. **Gold set:** pay 20–40 creators to license their raw clips *plus* their finished edits. This fits the calibration plan in CLAUDE.md.
3. **Research-only check:** SnapUGC, VADB, MovieCuts and AVE, once each licence is confirmed. Use them only to check that metrics separate good from bad; never ship thresholds derived from non-commercial data.
4. **Human trend log:** team members go through Creative Center, YouTube Charts and Edits Inspiration and note timings and styles by hand.

**Avoid:** scrapers, the Hugging Face TikTok dumps, the Research API (we aren't eligible), and the Commercial Content API's video URLs until its terms have been reviewed.

## Sources
1. https://developers.tiktok.com/products/research-api/
2. https://developers.tiktok.com/doc/research-api-faq
3. https://www.tiktok.com/legal/page/global/terms-of-service-research-api/en
4. https://developers.tiktok.com/products/commercial-content-api
5. https://developers.tiktok.com/doc/commercial-content-api-query-ads
6. https://ads.tiktok.com/business/creativecenter/pc/en
7. https://ads.tiktok.com/business/creativecenter/inspiration/topads/pc/en
8. https://developers.tiktok.com/doc/tiktok-api-v2-video-list ; https://developers.tiktok.com/doc/tiktok-api-v2-video-object
9. https://www.tiktok.com/legal/page/us/terms-of-service/en
10. https://developers.google.com/youtube/v3/docs/videos/list
11. https://developers.google.com/youtube/terms/developer-policies
12. https://www.youtube.com/static?template=terms
13. https://support.google.com/youtube/answer/7239739
14. https://developers.google.com/youtube/analytics/metrics
15. https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-hashtag-search ; https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-hashtag/top-media
16. https://developers.facebook.com/docs/instagram-platform/instagram-api-with-facebook-login/business-discovery
17. https://developers.facebook.com/docs/instagram-platform/reference/instagram-media/insights
18. https://www.facebook.com/help/instagram/581066165581870
19. https://www.douyin.com/agreements/?id=6773906068725565448
20. https://huggingface.co/datasets/HuggingFaceFV/finevideo
21. https://github.com/dasongli1/SnapUGC_Engagement ; https://arxiv.org/abs/2509.02969
22. https://smp-challenge.com/dataset.html
23. https://github.com/westlake-repl/MicroLens ; https://arxiv.org/abs/2309.15379
24. https://lixinustc.github.io/projects/KVQ/
25. https://github.com/BestiVictory/VADB ; https://arxiv.org/abs/2510.25238
26. https://github.com/VQAssessment/DOVER (S-Lab-LICENSE)
27. https://github.com/PardoAlejo/MovieCuts ; https://arxiv.org/abs/2109.05569
28. https://github.com/dawitmureja/AVE
29. https://github.com/bytedance/Shot2Story
30. https://arxiv.org/abs/2403.16048 ; https://github.com/GX77/Edit3K ; https://huggingface.co/datasets/Gstar666/Edit3K
31. https://research.google.com/youtube8m/download.html
32. https://huggingface.co/datasets/The-data-company/TikTok-10M
33. http://export.arxiv.org/api/query?search_query=abs:professional+AND+abs:amateur+AND+abs:video+AND+abs:dataset ; https://arxiv.org/abs/2011.02356
34. https://techcrunch.com/2024/01/24/court-rules-in-favor-of-a-web-scraper-bright-data-which-meta-had-used-and-then-sued/ ; https://www.reuters.com/legal/musks-x-corp-loses-lawsuit-against-israeli-data-scraping-company-2024-05-10/
35. https://en.wikipedia.org/wiki/Web_scraping
36. https://en.wikipedia.org/wiki/Youtube-dl
37. https://www.copyright.gov/ai/Copyright-and-Artificial-Intelligence-Part-3-Generative-AI-Training-Report-Pre-Publication-Version.pdf
38. https://www.ded.uscourts.gov/sites/ded/files/opinions/20-613_5.pdf
39. https://en.wikipedia.org/wiki/Bartz_v._Anthropic
40. https://zh.wikisource.org/wiki/中华人民共和国著作权法_(2020年)
41. https://zh.wikisource.org/wiki/中华人民共和国反不正当竞争法_(2025年)
42. https://www.cac.gov.cn/2023-07/13/c_1690898327029107.htm
43. https://www.capcut.com/templates
44. https://later.com/blog/instagram-reels-templates/
45. https://buffer.com/resources/how-to-use-instagram-edits/ ; https://creators.instagram.com/edits
46. https://help.opus.pro/docs/article/virality-score ; https://www.opus.pro/
47. https://www.opus.pro/blog/how-long-should-a-tiktok-be-2026
48. https://captions.ai/styles
49. https://www.submagic.co/
50. https://www.veed.io/templates

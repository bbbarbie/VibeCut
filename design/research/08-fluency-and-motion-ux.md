# 先缝接缝，再加动效：VibeCut 流畅化路线

**结论先行：** VibeCut 的成片"东一个西一个"，主因不在动效太少。它的默认路径只做了**分组**，没有做**剪接**。三个提案把每一个可用镜头都按时间、地点或主体装进最多 6 个桶，桶内按拍摄顺序播放。每个镜头的 2–5 s 窗口是在单个 clip 内孤立选出来的，而且画面和声音在每个接口都是硬切。整条流水线里没有任何一步去看**相邻的两个镜头**（[storyboard.py:145-182](web/backend/storyboard.py)；[trim.py:117-144](cutgrammar/trim.py)；[export.py:335-351](web/backend/export.py)）。

同类产品让成片显得流畅，靠的是三层"胶水"。第一层是一条贯穿全片的声床，外加一个原声与音乐的比例。第二层是对齐节拍的切点。第三层是整片统一的风格包。这三层都不生成像素（[Google blog](https://blog.google/products-and-platforms/products/photos/new-video-editor-templates-custom-text/)；[GoPro](https://gopro.com/en/us/news/quik-moments-updates-and-gpmf)；[Apple Support](https://support.apple.com/guide/iphone/personalize-your-memory-movies-iph1a5832438/ios)）。2022–2026 年的研究再往前走了一步，给**相邻镜头对**打分，看是否在动作上切、是否匹配、景别怎么递进（[FilmGPT](https://arxiv.org/abs/2607.14645)；[Netflix match cut](https://arxiv.org/abs/2210.05766)）。redesign-v2.md 和 07 号动效研究已经定好了渲染层怎么做：vibe token、接口库、fallback、J/L 和 `set_music`。它们缺的是一个**接口（join）模型**：一个衡量相邻镜头之间代价的函数，外加让它可见、可操作的 op。

因此建议的顺序是：先修**声音连续性**和预览与导出一致（最便宜、收益最大）；再建只报告、不修改的 `cutgrammar/joins.py`；然后把"顺滑顺序"作为一个需要创作者确认的提案；最后才把已有的动效库以"整片 look + 可见的接口"的形式接进 UI。每一步都满足 ops 而非重生成、不生成画面、像素只解码一次，并且附带判别测试。

> 代码引用以审计时的 `main`（HEAD `18c99c6`）为准。当前工作目录 `/home/user/VibeCut` 停在更早的 `8d637f9`，其中没有 Remix、Borrow a feeling 等模块。

## 碎片感有六个来源，只有一个和动效有关

审计按影响从大到小列出了六个原因。

**第一，保留的镜头太多。** 默认长度下，`usable()` 只剔除截图和 quality < 0.25 的镜头，其余全部上板（[storyboard.py:185-196](web/backend/storyboard.py)）。结果是几十个 2–5 s 窗口，而且没有谁判断过它们在故事里担任什么角色。

**第二，窗口是逐 clip 选的，精度 1 s，看不到邻居。** trim 的打分公式是 `0.35*quality + 0.25*(1-shake) + 0.25*subject + ...`，只和片段自身有关（[trim.py:72-81](cutgrammar/trim.py)）。所以切点落在哪个动作上，基本是随机的。

**第三，两条非时间轴故意打乱时间顺序。** 地点轴里"a return visit joins its first chapter"，同一章节内部时间会来回跳。主体轴则明确"ignoring when and where it was filmed"（[storyboard.py:381-431, 477-523](web/backend/storyboard.py)）。

**第四，接口处没有任何连续性判断。** 颜色和曝光是否匹配、主体是否延续、景别是否递进，都没有检查。`check_continuity`、`check_jl_cuts`、`check_cut_on_motion` 这几条规则确实存在，但只在 CLI 的 `analyze.py` 里跑，`web/backend` 一次也没有 import（[grammar.py:99-250](cutgrammar/grammar.py)）。

**第五，每个接口的声音也是硬切。** 每段只用手机自带的原声，没有声床。预览里音乐音量根本没设置，默认 1.0；导出时是 0.35，从音轨的 t=0 开始播，也没有 ducking（[transport.ts:131-141](web/frontend/src/transport.ts)；[app.py:664-674](web/backend/app.py)）。

**第六，hook 把最好的镜头从原来的位置拿走，之后没有回收。**

动效"没被用上"，是结构性的问题，不是因为漏接了某个开关。动效库目前主要停在设计阶段：`motion.html` 列了 20 个元素，redesign-v2 的 P1–P17 写明"nothing in it is built yet"（[redesign-v2.md:3](design/specs/redesign-v2.md)）。app 里真正在跑的只有三类东西：

- 文字：4 种入场动画、一条 cubic 缓动，预览和导出一致（[overlayDraw.ts:172-200](web/frontend/src/overlayDraw.ts)）。
- 转场：dissolve、dip 和 flash，只在导出时出现，而且只能通过 Borrow a feeling 触发（[export.py:271-313](web/backend/export.py)）。
- Remix 专属：punch、ducking 和 riser。可一旦结果落到 board 上，这些全部丢失，再从编辑器导出就是另一部片子（[remix.py:663-675](web/backend/remix.py)）。

另外有两个限制让转场在实际素材上很难成立：

- **素材余量（handles）不足。** 在 42 个真实 clip 上，只有 **0.8%** 的整镜头切点两侧各有 6 帧余量；做完粗剪后是 **24.6%**；在部分边界上是 16 个里有 1 个。所以 dissolve 大多数时候会退回硬切（[07-motion-library-study.md:338-350](design/research/07-motion-library-study.md)）。
- **预览放不出过渡。** 预览用单个 `<video>` 一段段 seek，本来就不可能播出交叉过渡（[transport.ts:168-180](web/frontend/src/transport.ts)）。

**这组数据还说明了另一件事：J 切在 53% 的切点上可行，L 切在 40–44% 的切点上可行。** "声音跨过切点"是 VibeCut 素材上**最容易成立的平滑手段**，比任何画面转场都容易。

## 同行的流畅感来自声床、节拍和统一风格，研究界又加了一层"接口打分"

消费级产品的做法高度一致，都分两步。先把范围收窄到一个事件或主题（一次旅行、一个人、一个地点），再在范围内挑精彩片段。GoPro Quik 读取 GPMF 里的 GPS、速度和 g-force 来选片，并"beat-syncs them"（[GoPro](https://gopro.com/en/us/news/quik-moments-updates-and-gpmf)）。Apple 的 Memory Movie"crafts a storyline with unique chapters and a narrative arc"（[iDownloadBlog](https://www.idownloadblog.com/2024/09/25/how-to-create-photo-memory-using-apple-intelligence/)），换一首歌就会"re-edit a movie to match the music's pace and tone"（[AppleInsider](https://appleinsider.com/articles/16/06/16/inside-ios-10-photos-memories-will-generate-slideshow-movies-automatically)）。Google Photos 模板的切点"match the beat of included music"，并且让用户调节原声和音乐的相对音量（[TechCrunch](https://techcrunch.com/2025/12/09/google-photos-launches-new-video-editing-tools)；[Thurrott](https://www.thurrott.com/music-videos/google-photos/330568/google-photos-gets-redesigned-video-editor-on-mobile)）。CapCut Beat Sync 会"trim and arrange your clips so each cut lands on a beat marker"（[CapCut Help](https://www.capcut.com/help/auto-cut-in-capcut)）。

GoPro 有一项专利走得更远：它按脉冲强度给音乐事件分类，再把不同类别映射到不同效果，包括变速（[US10679670B2](https://patents.google.com/patent/US10679670B2/en)）。

**没有任何消费级产品公开过排序规则，也没有公开过是否避免在动作中间切。** 这类产品暴露出来的失败主要在**选片**上（"weird video clip"、"hit-or-miss"），以及长片里的**重复感**：CapCut AutoCut 用在长 vlog 上"results may feel repetitive"（[Filmora review](https://filmora.wondershare.com/video-editor-review/how-to-use-capcut-autocut.html)；[Google Photos community](https://support.google.com/photos/thread/421153436/weird-video-clip-displayed-in-memories?hl=en)）。用户也会抱怨自动加的音乐，希望能关掉（[thread](https://support.google.com/photos/thread/255289219/please-turn-off-the-memories-music?hl=en)）。

专业工具几乎不按电影语法给 B-roll 排序。它们的做法是：

- 按转写或波形切对话（Eddie、Descript、TimeBolt）。
- 按谁在说话切机位（Resolve SmartSwitch）。
- 提供节拍标记，让切点吸附到最近的帧（Resolve 20 AI Detect Music Beats）。
- 用 Audio Assistant 把对白、音乐和音效调到一致（[Mixonline](https://www.mixonline.com/technology/news-products/blackmagic-davinci-resolve-20-adds-ai-audio-features)）。

Premiere 的 Remix 比较每一拍和其他所有拍的相似度，把用户自己的歌重新剪到目标长度，全程不生成音频（[Adobe HelpX](https://helpx.adobe.com/premiere/desktop/add-audio-effects/apply-audio-effects/remix-in-premiere.html)）。这对 VibeCut 的"用你自己的音乐库"很有参考价值。Premiere 的 Generative Extend 会生成新画面，属于 VibeCut 明确排除的方向（[Adobe HelpX](https://helpx.adobe.com/premiere/desktop/edit-projects/edit-with-generative-ai/generative-extend-overview.html)）。

研究界填的正是排序这个空白：

- **MovieCuts**（ECCV'22）把切点分成 10 种专业类型（cut on action、match cut、J/L 等）。最好的模型也只有 **47.7% mAP**，作者称这是"open research problem"（[arXiv 2109.05569](https://arxiv.org/abs/2109.05569)）。
- **Netflix 的 match cut** 系统在上千万镜头对里检索候选：用人物 mask 的 IoU 找画面匹配，用光流找运镜匹配（[arXiv 2210.05766](https://arxiv.org/abs/2210.05766)；[Netflix/matchcut](https://github.com/Netflix/matchcut)）。
- **AVE** 和 2025 年的 SSO 基准把镜头排序做成了 Kendall tau 任务。加入景别先验后，在电影和 UGC 上都有稳定提升（[arXiv 2503.17975](https://arxiv.org/abs/2503.17975)）。
- **FilmGPT**（SIGGRAPH 2026）最接近 VibeCut 的形态。它是自回归模型，**不生成画面**，用 footage-constrained decoding 从用户素材里挑下一个镜头，establishing、cut on action 和 POV 这些习惯会自己学出来（[arXiv 2607.14645](https://arxiv.org/abs/2607.14645)）。
- **AutoTransition**（ECCV'22）给每一对相邻镜头推荐转场（[ECVA](https://www.ecva.net/papers/eccv_2022/papers_ECCV/html/7634_ECCV_2022_paper.php)）。
- Davis & Agrawala 的 **visual beats** 把运动突变对齐到音乐节拍（[visbeat](https://abedavis.com/visualbeat/)）。

学术界的准确率普遍不高，这对 VibeCut 是个信号：以它的规模，**可解释的手工接口代价函数比黑盒模型更合适**，也更容易纳入 CLAUDE.md 要求的判别测试和校准流程。下表列出可用的线索、用 VibeCut 已有数据怎么近似，以及现在能否计算。

| 接口线索 | 研究或产品依据 | VibeCut 已有数据（不重新解码） | 现在可算？ |
|---|---|---|---|
| 曝光/颜色跳变 | CLAUDE.md 40% 硬约束；`check_continuity` | 16-bin `hist`、每秒 luma | 可以 |
| 内容延续 vs 跳切 | Netflix embedding 相似度 | Vision `embedding` 余弦 | 可以（需要 Vision） |
| 在动作上切 | MovieCuts、FilmGPT | 每秒 motion、`marks()` 里的 motion_on/off | 可以，但只有 ±0.5 s 精度，没有方向 |
| 声音连续 / J·L | MovieCuts J/L 类型；handle 统计 | RMS、speech mask、源素材 handles | 可以（speech mask 需要换成 VAD） |
| 景别递进 | AVE、SSO 景别先验 | `face_area` | 只在有人脸时可算，否则 `pending` |
| 时间跳跃 | Apple 章节 | capture time | 可以 |
| 运动方向 / 180° | Netflix 光流 | 无 | 不可以（已知限制 2） |

## 动效 UX：整片一个 look，接口是可见对象，建议挂在具体位置上

UX 这边，业界的主流心智模型已经很清楚：**风格是一包 token，作用于整片，在用户自己的素材上边播边换。** 下面几个产品都是这个模式：

- iMovie Magic Movie 的 Style 打包了转场、音乐、标题字体和颜色，点一下预览，点 Done 应用到整片（[Apple Support](https://support.apple.com/guide/imovie-iphone/change-style-a-magic-movie-storyboard-project-knad9ba15999/ios)）。
- Photos 的 Memory Mix 在影片继续播放的同时左滑切换，Look 和 Music 可以分开改（[Apple Support](https://support.apple.com/guide/iphone/personalize-your-memory-movies-iph1a5832438/ios)）。
- Captions 的 AI Edit 让用户在"your own footage"上预览每一种风格（[Captions Help](https://captions.ai/help/llms.txt)）。

VibeCut 的 vibe 就是这个对象。redesign-v2 已经规定了它的解析顺序：kind 先验 → look → 参考特征 → 预算 → 各种保护 → 格式限制 → 创作者的 turn 优先（[redesign-v2.md:267-304](design/specs/redesign-v2.md)）。本报告不再重复这部分，只补上三处 spec 没写的交互语义。

**第一处：覆盖（override）的方向和它在换风格后是否保留。** Descript 的"Apply to all scenes"把局部设置推到全局，但明确说图层叠放顺序不会被复制（[Descript Help](https://help.descript.com/visuals/scenes-layers)）。Edits 的 Apply All 覆盖滤镜、效果、转场和调色（[Inrō](https://www.inro.social/blog/edits-new-meta-app)）。Clipchamp 的 brand kit 只是"选的时候排在最前"，不会自动改掉已有元素（[Microsoft Support](https://support.microsoft.com/en-us/clipchamp/how-to-use-the-brand-kit-tool-in-clipchamp)）。

**没有哪个产品公开说明换风格之后局部覆盖还在不在，这里要主动做决定。** 建议的做法：`set_look` op 不碰带显式覆盖的镜头，Story 层显示一个"3 个镜头和整体 look 不同"的徽标，点开可以一键并回。这样全局和局部的关系都落在 op 日志里，diff 仍然是算出来的。"每个视频都这样"的偏好，走 `preferences.py` 现有的"候选 → 确认"流程，不另起一套模板系统。

**第二处：接口本身要成为可选中的对象，默认是硬切，"应用到全部"要收紧。** 通行的做法是点两个 clip 之间的接缝，打开转场库，再勾"Apply to all"（[TourBox](https://www.tourboxtech.com/en/news/capcut-transitions.html)）。这恰好是业余感的主要来源："98% of your transitions should be cuts"（[Storyblocks](https://www.storyblocks.com/resources/blog/editing-mistakes-beginners-make-with-video)）。连教程作者自己都提醒，全片用同一种转场会显得重复（[capcutguide](https://capcutguide.com/capcut-transitions/)）。

VibeCut 的 Story 层应该在镜头之间画出接缝点。点一个接缝只给三个白话选项，沿用 spec 里的 copy lint：**"直接切 / 柔和淡入淡出 / 声音带过去"**。批量操作只提供"所有段落交界处"，不提供"所有接缝"，因为段落交界才是"一种 vibe 一个转场家族、只放在 part 边界"这条规则的落点（[07:307-336](design/research/07-motion-library-study.md)）。

余量不够时，按 spec 退回"同 vibe、不需要余量的接口"（[redesign-v2.md:393](design/specs/redesign-v2.md)），并在接缝点上直接标出"这里只能直接切 / 已改为暗场"，不要只在导出日志里悄悄说一句。度量也可以当护栏用：显示"40 个接缝里有 12 个用了转场"这类**只报数、不拦截**的计数。目前没有竞品这样做（未经验证的差异点）。

**第三处：AI 建议挂在具体位置上，逐个或一次全部接受。** Descript Underlord 的做法和 VibeCut 的"只发 op、diff 由系统计算"几乎一样：每次改动前留 checkpoint，每个回合都能 Revert，改完后还有一轮自动 diff 审查，检查误删、改过头和越界操作（[Descript Help](https://help.descript.com/hc/en-us/articles/36958274409357-Revert-or-rollback-changes-made-by-Underlord-beta)；[Descript changelog](https://descript.canny.io/changelog)）。相反，一次性"AI 高光剪辑"的典型抱怨是撤不回（[Descript users](https://www.facebook.com/groups/descriptusers/posts/783710183914921/)）。

VibeCut 应该把动效建议做成挂在 part 边界、带地点标签的镜头、音乐 drop 上的"待确认小标签"。每接受一个就是一个 turn。每个 turn 结束后跑一遍 `cutgrammar` 审查，比如新标题是否压住人脸（没有人脸数据时报 `pending`）、转场密度是否超出预算。结果以"值 + 结论"的形式挂在这个 turn 上。

对话里描述动效的词汇可以借 Adobe Express 的 **In / Loop / Out × Intensity / Speed / Direction**（[Adobe HelpX](https://helpx.adobe.com/express/web/audio-and-animation/animation.html)）。这组参数不需要术语，LLM 可以直接输出，UI 上也能做成三个滑杆，并映射到 vibe token。

预览要和导出一致，这是动效能不能"被看见"的前提。Remotion 让同一份 React composition 同时驱动 Player 和渲染器，这是"一套代码两处用"的样板（[Remotion Player](https://www.remotion.dev/docs/player/player)）。Lottie 的 expressions 在渲染时不确定，会闪烁，帧率不一致还会导致速度错误（[@remotion/lottie](https://www.remotion.dev/docs/lottie/)）。VibeCut 在文字上已经做对了：`overlayDraw.ts` 一个函数同时画预览和导出。应该把这个原则推广到声音和接缝上，下文清单里的 P0/P1 就是这么做的。

## 优先实施清单：先修声音，再建接口模型，最后接上动效

下表按"对碎片感的改善 ÷ 成本 × 规则风险"排序。凡是 redesign-v2 已经编号的项，只写 VibeCut 在它之上要补的部分。

| 优先级 | 做什么 | 文件 | 约束与验证 |
|---|---|---|---|
| **P0-1** | 预览音乐音量设成导出的 `MUSIC_GAIN=0.35`，让预览听到的就是导出的声音 | `web/frontend/src/transport.ts`、`App.tsx` | 纯一致性修复。加一个测试断言两边增益相同 |
| **P0-2** | 每个 PCM 拼接点加 10–20 ms 的 `afade` 微淡变，消除爆音（目前没测过） | `web/backend/export.py`（逐段渲染处） | 不产生新画面。判别测试：人为构造一个有台阶的拼接点，断言峰值瞬态下降 |
| **P0-3** | ffconcat 加 `option framerate 30`（spec P5），修掉 1800 帧里错的 600 帧 | `export.py` | 已由 spec 决定，这里只提高优先级：不修它，任何动效都会抖 |
| **P0-4** | Remix 落到 board 时把 `mix`（in-point、增益、duck）一并带上，落地方式就是 spec 的 `set_music(track, in_point)` op | `remix.py:663-675`、`board.py`、`app.py:664-674` | 仍然是 op，重导出要和 Remix 文件一致。回归测试：board 导出和 remix 导出的音频包络一致 |
| **P1-1** | **声音预览代理**：后端只渲染整条混音 WAV（原声、音乐、以后加上 J/L 和微淡变），预览时视频静音，播这条混音 | 新增 `web/backend/audiomix.py`；`transport.ts` | 只处理音频，不碰像素，成本低。同时解决"预览听不到平滑效果"的问题 |
| **P1-2** | **段落交界默认用 L 切带环境声**（research 01 的规则），用 spec P10 的音频余量实现；新增 `set_join(at, kind, sound)` op，`sound ∈ {cut, carry_in, carry_out}` | `board.py`（加入 `OPS`、`LLM_OPS`）、`export.py` | 不生成画面。余量不够就退回直接切，并在接缝点标出来。偏移量（0.3–1.0 s）是先验，要写进校准表 |
| **P1-3** | 默认长度也按"长得像的聚在一起、每类留一个"去重（`brief.py` 里已有 cosine ≥ 0.78 的逻辑） | `web/backend/brief.py`、`storyboard.py` | 选片是同类产品失败最多的地方。判别测试：插入 5 个近似重复镜头，断言最多留下 1 个 |
| **P2-1** | **`cutgrammar/joins.py`：只报告的接口代价**。每个相邻对算出曝光/颜色、embedding、tail/head 运动、RMS 台阶、时间跳跃、景别（有 `face_area` 才算）几项分量，都以 `Finding(value, verdict)` 输出，并在 `grammar.NEEDS` 里声明依赖 | 新文件；输入是 indexer 已存的 `hist`、`signals`、`embedding`、`faces` | 只读索引数组，**零解码**。每个分量一个判别测试，两个 fixture 只差这一项。先在 42 个真实 clip 的默认提案上跑一遍，把"多少接缝是跳变"这个缺失的数字补上 |
| **P2-2** | 把 `joins.py` 的结果接到 Story 层的接缝点上（颜色 = 结论，悬停显示数值）；每个 turn 结束后做一次审查 | `workflow.py` / `app.py`；前端 Story 组件 | 只报告、不修改，不算 `cutfix` |
| **P2-3** | 地点轴里"回访"拆成按时间排列的子段，不再并回第一次到访的章节；主体轴的聚类按第一次出现的时间排序 | `storyboard.py:381-431, 477-523` | 直接去掉故意制造的时间跳跃。用 `same_order_as_time` 前后对比来验证 |
| **P3-1** | **窗口感知邻居**：在 `best_window` 已选窗口的 ±1–2 s 内，按 tail/head 运动的乘积往"动作上切"挪（Remix `select.py` 的"busiest second"思路推广到默认路径）。产出**第四个提案或一个"让接缝更顺"的 turn**，不改默认 | `cutgrammar/trim.py`、`web/backend/cut.py` | 这是改动，受校准规则约束：阈值标成先验，必须经过人工确认，默认关闭，校准后再议 |
| **P3-2** | **顺滑顺序提案**：在 part 内用小 beam search，对象是 `Σ join_cost + λ·Kendall(时间序)`，输出 `move_shot` op 序列（diff 由系统计算） | 新增 `web/backend/sequence.py`；`board.py` | FilmGPT 的"约束解码"思路，用手工分数代替模型。λ 设大，保住时间主线。只作为提案 |
| **P3-3** | 按 spec P1/P3 落地 vibe record，加上 `set_look` 的覆盖语义（保留覆盖并显示徽标）；`overlayDraw.ts` 接入 vibe token 和 beat lock（spec gap 1/2） | `overlays.py`、`overlayDraw.ts`、`board.py` | 只用 Canvas，一个函数画两处。判别测试：每一帧的标题包围盒都在安全区内 |
| **P4** | 接缝画面预览：dip/flash 用 Canvas alpha 近似；dissolve 用预加载的第二个 `<video>`（A/B，顺便替代 `hold.ts` 的补丁）；或者 Watch 页播 spec P4 的 720p 代理 | `transport.ts`、`hold.ts`、`Player.tsx` | 属于架构改动，放在最后。画面处理在浏览器里做，不影响"像素只解码一次"的分析规则 |

**明确不做：** 不做 Generative Extend 式补帧，不做 minterpolate 慢动作（spec 已选"不插帧"），不给每个镜头都加 punch（research 06 的"适度胜过极致"），不提供"所有接缝都加转场"的一键操作。人脸居中的变焦和景别递进要等 P9 人脸框做完；运动方向匹配和 180° 规则要等光流，这些都排在已知限制 2、3 之后。

## 值得试、但先当实验的四个新方向

**方向一：强拍分级。** 借 GoPro 按强度给音乐事件分类的思路，用 `music.beat_grid` 的能量把拍子分成强、弱两级：part 交界落在强拍或小节线上，part 内的切点只吸附到弱拍，而且移动不超过 0.35 s（spec 定的值）（[US10679670B2](https://patents.google.com/patent/US10679670B2/en)）。这比"每一刀都对拍"更不容易产生 Remix 被批评的机械感。research 06 看过的 4 个参考视频全部是硬切，而且都不在网格上（[06:57,64-66](design/research/06-what-vibecut-learns-from-viral-videos.md)）。

**方向二：visual beats 的廉价版。** 用每秒 motion 的峰值当作"视觉拍"，窗口选择时让视觉拍和音乐拍对齐（[Davis & Agrawala](https://abedavis.com/visualbeat/)）。由于 index 分辨率只有约 1 s，这里只能做粗对齐。要做到更细，需要在已选窗口上跑一次 `media.load()`。这仍然满足"一次解码"，因为它针对的是另一个输入（窗口）的第一次解码，不属于逐规则重复解码。但要先测成本。

**方向三：Premiere Remix 式的音乐重剪。** 用 numpy 计算节拍间的自相似矩阵，把创作者自己的歌剪到成片长度，避免"音乐从 t=0 开始、最后 2 s 淡出"这种一听就是业余的结尾（[Adobe HelpX](https://helpx.adobe.com/premiere/desktop/add-audio-effects/apply-audio-effects/remix-in-premiere.html)）。可以和 `cutgrammar/music.py` 的能量形状匹配合并。

**方向四：每片 1–2 个 match cut 候选。** 在 embedding 余弦和颜色直方图上做 Netflix 式的候选对检索，只在 part 交界处作为"一个时刻"推荐给创作者，由创作者接受（[Netflix TechBlog](https://netflixtechblog.com/match-cutting-at-netflix-finding-cuts-with-smooth-visual-transitions-31c3fc14ae59)）。

这四个方向都只读现有数组、只产出 op，所有权重都写进校准清单。

**校准本身也可以借力 UI。** CLAUDE.md 的规则要求先用约 20 个剪得好的视频和约 20 个剪得差的视频定阈值。在那之前，可以在 app 里放一个"两种顺序你更喜欢哪个"的 A/B 选择，结果按 `preferences.py` 的逻辑只由创作者本人归类。这些选择**不能代替**这 40 个视频的校准，只能提供额外的偏好信号。

## 结论

这次研究最主要的发现是：**VibeCut 缺的是接缝，不是动效。** 竞品花大力气包装的转场和模板，本质是用整片统一去掩盖接缝处的断裂。VibeCut 的优势恰恰在于它能**测量**接缝：`check_continuity` 等规则、per-second 信号和 embedding 都已经有了，只是没有接进 web 路径。先把声音接顺，也就是 J/L 切、微淡变、声床和预览一致，再把接缝代价变成看得见的数字，碎片感会比加任何特效下降得都快，而且这样做完全符合"无业余痕迹"的承诺。

还有一点值得注意：研究界最好的切点分类模型只有 47.7% mAP，而消费级产品根本没有公开排序规则。**"按电影语法自动排序"在整个行业都还没有解决。** 所以 VibeCut 更实际的做法是把接缝代价做成可解释、可校准、由人来确认的提案。等 40 个视频的校准完成，P3 的顺滑顺序和动作切点再从提案升级为默认；在那之前，P2 是 P3 的前置，不能跳过。

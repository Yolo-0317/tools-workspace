# 影视稿模板 tv_review_v2（定稿：《铁拳教育》）

> **优先于**《亢奋》旧样例。换片只换 topic、评分、剧照与分集内容，**不重发明结构**。

## 真源（Agent 先读）

| 文件 | 用途 |
|------|------|
| [`stock-ai/data/wechat_mp_tv_review_template.json`](../../../stock-ai/data/wechat_mp_tv_review_template.json) | 机器可读：5 节、10 图、`after_anchor` 锚点 |
| [`stock-ai/data/wechat_mp_tv_review_golden/teach_you_a_lesson.body_core.md`](../../../stock-ai/data/wechat_mp_tv_review_golden/teach_you_a_lesson.body_core.md) | **正文金样**（无评分、无 `[[fig:]]`） |
| [`stock-ai/docs/WECHAT_MP_TV_REVIEW.md`](../../../stock-ai/docs/WECHAT_MP_TV_REVIEW.md) | 人类可读 SOP |
| [`wechat-mp-writing/anti-ai-voice.md`](../wechat-mp-writing/anti-ai-voice.md) | 去 AI 味 |

## 五节结构（口语小标题）

| # | role | 写什么 | 小标题怎么起 |
|---|------|--------|--------------|
| 1 | conclusion | 上映/意象/主题钩子；**评分插在第一节第一段正文之后** | 首段不写豆瓣/烂番茄具体分；第二段再接口碑与观感 |
| 2 | about | 平台/阵容/背景；点立意 | 贴合本片一句判断；**勿**每篇都「看着像 X，其实是在 Y」 |
| 3 | episode_guide | **按集 bullet**（`· 第N集（副标题）：`），每集 2–4 句 + 具体桥段 | 小标题自拟（如「三集各有场面」「按集记几笔」）；**勿**固定「分集速写：」 |
| 4 | audience | 谁会追 / 谁该跳过 | 直接说劝退或入坑理由；**勿**「爱 X 会追，Y 会更烦」对称句 |
| 5 | try_it | 试看哪几集、哪场戏定去留 + 互动问句 | 写具体集数/场次；**勿**照搬「拿不准就开前两集」 |

金样《铁拳教育》的小标题是早期定稿，**新片只学五节意思，禁止连抄五句句式**。

## 院线单片剧评（纯段落）— 固化规则

> 蜘蛛侠《崭新之日》试跑沉淀；**换片照此执行**，勿重发明。

### 开头排序（硬）

1. **首段**：上映日 + 具体意象/场面 + 主题钩子（可写票房，**不写**豆瓣/烂番茄具体分）
2. **脚本注入**：竖排评分 bullet（全文**唯一**列分处）
3. **第二段起**：口碑/观感判断，进入剧评正文

### 段落（硬）

- 每段 **2～4 句**连成一块；**禁止一句一段**（`finalize_tv_review_body` 合并碎段；`finalize_public_body_text` 对 tv_review **不再**按 120 字拆句）
- 单段上限约 **220 字**；用分号、破折号把相关句织在一起，而不是每句换行

### 口吻（硬）

- **禁止第一人称**（「我看的晚场」「我倒是想起」）
- **大白话**：禁「戏眼」「意象」「正向反馈」「遮羞布」「场面堆叠」等影评腔；见 [anti-ai-voice.md](../wechat-mp-writing/anti-ai-voice.md) 影视表
- **感情挂在戏上**：冷清、发紧、闷——写在表演、镜头；**禁止**读者自传式假共情（加班、没人回消息等）
- **去 AI 味禁句**：剧情承接、梗概也熟、把设定当主线/开场工具、这是客观缺点、几场戏值得单独说、综上所述

### 评分与数字

- 竖排块用阿拉伯数字（7.8、90%）；首段正文不重复念分
- 标题可带豆瓣分（脚本 `build_tv_review_title`）

### 配图锚点

- 首图勿插在评分块前；锚点用**完整短语**（如「战衣补丁」），避免「战衣」误匹配「缝战衣」

## 仿写必读

- **[tv-review-voice.md](../wechat-mp-writing/tv-review-voice.md)** — IGN 中国等真人剧评节奏、开篇/中段/结尾 checklist

### 口吻（硬约束）

- **排版**：与热点深评一致——**纯段落**，无 `> ` / `#` 小标题；每段 2～4 句，禁止单句成段
- **参考写法**：IGN 中国剧评、文娱号长评（事实+数字开篇，场面写进叙述，不用节标签）
- **禁止第一人称**：不用「我看的」「我倒是想起」；客观剧评口吻
- **感情色彩**：对剧情、镜头、表演下判断时带温度（冷清、发紧、压人），**不要**把作者私生活套进角色（假共情）
- 小标题：`> 一句完整口语`；禁「先说结论」「它是什么」、禁「简单交代：」「分集速写：」
- 第三节用 **分集 bullet**，不是《亢奋》式「人物/节奏/镜头」三条（单元剧/纪录片适用）
- 单季 ≤6 集：分集写全；≥8 集：重点写 4–6 集 +「第X—Y集」汇总

### 配图（脚本 `after_anchor`）

- 最多 **10 张**；`scene=` 桥段 + `cap=` 图源
- **TMDB 有分集剧照**（如《铁拳教育》）：人工选 `backdrops` 路径写入 `CURATED_TV_STILLS[slug].files`
- **纪录片 / 新片只有海报**：TMDB 常只有横版 key art + 竖版海报（看起来像封面）；改从 **预告片抽帧** 落盘 `inline-tv/{slug}/still-*.jpg`，`source: local`
- 锚点写在 `slots` 的 `after_anchor`；正文 bullet 须含可匹配文案
- 封面：`cover.jpg`（勿与正文重复同一张 hero 海报）

### 缓存（勿互相覆盖）

- 定稿正文：`data/wechat_mp_tv_body_cache/{topic_slug}.json`
- 金样备份：`data/wechat_mp_tv_review_golden/{slug}.body_core.md`
- **改定稿** → 改 cache/golden → `repush`；**新片首日** → 按本模板手写/生成 → `save` → `repush`
- `build_tv_review_article` 仅当 **该 topic 已有 cache** 时复用定稿；无 cache 才调 DeepSeek

## 命令

```bash
cd stock-ai

# 预览当日影视热搜选题（微博+百度）
uv run python -m scripts.tools.wechat_mp_tv_refresh_topics --trends

# 指定热搜片名推稿（mixed=热搜优先+curated 兜底，默认）
WECHAT_MP_TV_TOPIC=凤囚凰 uv run python -m scripts.tools.wechat_mp_draft --kind tv_review

# 只从热搜选题（不限美剧）
WECHAT_MP_TV_SOURCE=trends uv run python -m scripts.tools.wechat_mp_draft --kind tv_review

# 刷新队列（热搜 + curated + 可选 TMDB）
uv run python -m scripts.tools.wechat_mp_tv_refresh_topics

# 只改字/图/评分（推荐）
uv run python -m scripts.tools.wechat_mp_repush_tv_review_draft --title-en "<English Title>"

# 试跑批次（18:20 替代 evening）
uv run python -m scripts.tools.wechat_mp_draft_batch --batch tv_trial
```

## 新片上线清单

1. `wechat_mp_tv_topics.py` · `CURATED_HOT` + `trial.json` 队列（`pick_on` / `cover_slug` / `ratings`）
2. TMDB `tmdb_id` → `inline-tv/{slug}/still-*.jpg` + `cover.jpg`
3. `wechat_mp_tv_figures.py` · `CURATED_TV_STILLS` 锚点表
4. 按金样写 `body_core` → `save_tv_body_cache` → `repush`
5. mp 后台原创选 **生活 / 娱乐**

## 交叉引用

- 深度/立意：[depth-and-opinion.md](../wechat-mp-writing/depth-and-opinion.md)
- 改稿门禁：[wechat-mp-writing/SKILL.md](../wechat-mp-writing/SKILL.md)

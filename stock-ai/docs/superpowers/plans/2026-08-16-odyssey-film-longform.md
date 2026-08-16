# 《奥德赛》影视长图文 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成并直接写入微信公众号草稿箱一篇《奥德赛》完整剧透长图文，以奥德修斯的战争后遗症和归家困境为主线，配齐一张封面和五张可回溯公开剧照。

**Architecture:** 先把电影实际场面、原著背景和文章判断拆成证据台账，再把影片、正文和五个插图锚点接入现有 `tv_review` 缓存流水线。手工定稿是唯一正文真源，程序只负责规范化、插图、原创门禁、预演和最终微信草稿写入，不调用模型二次改写正文。

**Tech Stack:** 公开网页研究、Markdown、JSON、Python、pytest、Pillow、`scripts.tools.wechat_mp_tv_body_cache`、`scripts.tools.wechat_mp_draft --kind tv_review`。

## Global Constraints

- 正文第一行必须是完整剧情剧透预警。
- 标题暂定为 `《奥德赛》：回家不是凯旋`，最终标题长度不超过 20 个字符。
- 正文去空白后不少于 2200 字，目标 2400—2800 字。
- 正文使用纯段落，每段二至四句；不使用 Markdown 小标题、编号、项目符号、第一人称或一句一行排版。
- 至少包含五个可对应电影实际内容的完整剧情锚点；未被可靠材料确认的荷马原著情节不得写成诺兰电影场面。
- 核心判断是奥德修斯无法带着胜利者身份无损回家；佩涅洛佩和忒勒马科斯必须作为承受长期缺席后果的人物进入最后三分之一。
- 具体评分、片长、上映日、主创和票房仅在 2026-08-16 当天回源核验后使用。
- 配图为一张封面和五张正文图；不得重复、不得只是同一画面的不同裁切，不得使用 AI 生成的演员近似脸或伪造电影场面。
- 每张图片记录原页面、原图地址、来源名称、来源类型、场景与核验状态。
- 正文底部不声明栀夏或作者是 AI；发布环节由平台声明处理。
- 只有资料、正文、图片、原创度和本地预演全部通过，才允许执行不带 `--dry-run` 的微信草稿命令。

---

## File Structure

- Create: `stock-ai/output/odyssey_2026_research.md` — 电影剧情、主创信息、原著边界和图片候选台账。
- Create: `stock-ai/output/odyssey_2026_quality.json` — 五个剧情锚点、来源域、同作品发布历史与原创门禁输入。
- Modify: `stock-ai/scripts/tools/wechat_mp_tv_topics.py` — 注册 `The Odyssey` 的固定中文名、标题、题目键和研究来源。
- Modify: `stock-ai/scripts/tools/wechat_mp_tv_figures.py` — 注册 `the-odyssey-2026` 的五图锚点和图源说明。
- Modify: `stock-ai/tests/unit/test_wechat_mp_tv_trial.py` — 验证影片注册、显式选题和标题长度。
- Modify: `stock-ai/tests/unit/test_wechat_mp_tv_figures.py` — 验证五张图按剧情顺序注入且来源说明正确。
- Create: `stock-ai/data/wechat_mp_tv_review_golden/the-odyssey-2026.body_core.md` — 完整剧透正文金样。
- Create: `stock-ai/data/wechat_mp_tv_body_cache/the-odyssey-2026.json` — 标题、摘要、研究 URL 与正文缓存。
- Create: `stock-ai/assets/wechat_mp/inline-tv/the-odyssey-2026/figure_sources.json` — 六张图的来源记录。
- Create: `stock-ai/assets/wechat_mp/inline-tv/the-odyssey-2026/cover.jpg` — 横版封面。
- Create: `stock-ai/assets/wechat_mp/inline-tv/the-odyssey-2026/still-01.jpg` — 特洛伊战争余波。
- Create: `stock-ai/assets/wechat_mp/inline-tv/the-odyssey-2026/still-02.jpg` — 海上漂泊或独眼巨人段落。
- Create: `stock-ai/assets/wechat_mp/inline-tv/the-odyssey-2026/still-03.jpg` — 喀耳刻、卡吕普索或另一处被核验的停留场面。
- Create: `stock-ai/assets/wechat_mp/inline-tv/the-odyssey-2026/still-04.jpg` — 佩涅洛佩、忒勒马科斯与伊萨卡。
- Create: `stock-ai/assets/wechat_mp/inline-tv/the-odyssey-2026/still-05.jpg` — 返乡、复仇或重逢结局。
- Read: `stock-ai/docs/superpowers/specs/2026-08-16-odyssey-film-longform-design.md` — 已确认的文章设计。

### Task 1: 建立电影事实与剧情证据台账

**Files:**
- Create: `stock-ai/output/odyssey_2026_research.md`
- Create: `stock-ai/output/odyssey_2026_quality.json`

**Interfaces:**
- Consumes: 环球影业影片页与正式预告、中国电影报内地档期报道、AP 影片评论与角色指南、豆瓣电影条目和 TMDB 图片资料。
- Produces: 至少五个七字段完整剧情锚点、至少三个独立来源域、电影与原著的明确边界、六个图片槽位的候选 URL。

- [ ] **Step 1: 核验影片基础事实**

打开 `https://www.universalpictures.com/movies/the-odyssey`、`https://chinafilmnews.cn/mobile/Qnews.php?id=21279` 与环球正式预告 `https://www.youtube.com/watch?v=Mzw2ttJD2qQ`，记录导演、主演、内地上映日和官方故事定位。只有三个页面直接支持的事实才进入基础资料区。

- [ ] **Step 2: 核验电影实际剧情与改编结构**

打开 AP 影评 `https://apnews.com/article/fceb80683c5ecdc627f8e9221b833ca0`、角色指南 `https://apnews.com/article/d3ce9dcf33c66a58b74dca7d6654e484` 和幕后报道 `https://apnews.com/article/030ec686f8ba3d88a7abd2cd16008518`，记录电影如何交叉奥德修斯归途与忒勒马科斯寻父、特洛伊战争的倒叙、奥德修斯对屠城的愧疚、伊萨卡求婚者占据家园，以及电影对结尾复仇的处理。

- [ ] **Step 3: 建立五个完整剧情锚点**

为每个锚点写全 `scene`、`character`、`action`、`pressure`、`consequence`、`source_urls`、`film_or_poem` 七个字段。候选顺序固定为特洛伊木马与屠城、独眼巨人与船员代价、被核验的停留或诱惑、伊萨卡秩序真空、返乡复仇与夫妻重逢；任何只在原著资料中出现的候选必须标为 `poem_only` 并从正文锚点删除。

- [ ] **Step 4: 核验中文条目和公开图片入口**

从豆瓣新片榜进入《奥德赛》电影条目并记录 subject id、剧照页与当天评分；从 TMDB 的电影搜索接口或公开页定位 2026 年 Nolan 版本并记录 movie id、backdrop/poster 路径。豆瓣评分仅写入研究台账，不作为文章核心判断；图片候选必须能回到豆瓣照片页、TMDB 图片页、环球影片页或正式预告。

- [ ] **Step 5: 验证证据边界与台账完整性**

Run:

```bash
cd stock-ai
rg -n 'official_fact|film_plot|poem_only|article_inference|scene|character|action|pressure|consequence|source_urls|film_or_poem|https://' output/odyssey_2026_research.md output/odyssey_2026_quality.json
```

Expected: 四类证据边界均出现；质量 JSON 至少含五个 `film_or_poem="film"` 的七字段完整锚点和三个独立来源域，没有把 `poem_only` 项加入可写锚点。

### Task 2: 注册影片与五个插图锚点

**Files:**
- Modify: `stock-ai/scripts/tools/wechat_mp_tv_topics.py`
- Modify: `stock-ai/scripts/tools/wechat_mp_tv_figures.py`
- Modify: `stock-ai/tests/unit/test_wechat_mp_tv_trial.py`
- Modify: `stock-ai/tests/unit/test_wechat_mp_tv_figures.py`

**Interfaces:**
- Consumes: Task 1 已核验的 subject id、TMDB id、研究 URL 与五段剧情顺序。
- Produces: `CURATED_HOT` 中 `title_en="The Odyssey"` 的题目，以及 `CURATED_TV_STILLS["the-odyssey-2026"]` 的五图注入规则。

- [ ] **Step 1: 写影片注册失败测试**

在 `test_wechat_mp_tv_trial.py` 新增测试，查找 `title_en == "The Odyssey"` 的题目，并断言 `title_zh == "奥德赛"`、`cover_slug == "the-odyssey-2026"`、`type == "film"`、`year == "2026"`、`title_override == "《奥德赛》：回家不是凯旋"`，且标题长度不超过 20。

- [ ] **Step 2: 运行题目测试确认失败**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/python -m pytest tests/unit/test_wechat_mp_tv_trial.py -q`

Expected: FAIL，提示找不到 `The Odyssey`。

- [ ] **Step 3: 注册影片题目**

在 `_ZH_NAMES` 和 `CURATED_HOT` 添加影片，写入 Task 1 核验出的 `douban_subject_id`、`tmdb_id`、五个 `reference_angles`、正式来源 URL、`pick_on="2026-08-16"` 和足以让显式环境变量选中的有效期。评分字段保持为空，避免缓存动态分数。

- [ ] **Step 4: 写五图顺序失败测试**

在 `test_wechat_mp_tv_figures.py` 构造含五个最终锚点短语的正文，断言 `still-01.jpg` 至 `still-05.jpg` 均只注入一次、索引严格递增，且图注使用 Task 1 记录的豆瓣、TMDB 或环球来源，不统一伪称豆瓣。

- [ ] **Step 5: 运行五图测试确认失败**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/python -m pytest tests/unit/test_wechat_mp_tv_figures.py -q`

Expected: FAIL，当前没有 `the-odyssey-2026` 图片配置。

- [ ] **Step 6: 添加五图注入配置**

在 `CURATED_TV_STILLS` 添加混合公开来源配置。五个 `after_anchor` 使用 Task 1 和最终正文都会逐字出现的完整短语；每个槽位配置固定文件名和准确图注，不使用“回家”“战争”“家人”等可能误匹配的短词。

- [ ] **Step 7: 运行相关测试**

Run:

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/python -m pytest tests/unit/test_wechat_mp_tv_trial.py tests/unit/test_wechat_mp_tv_figures.py -q
```

Expected: 新增测试和既有影视测试全部 PASS。

### Task 3: 完成完整剧透正文金样与缓存

**Files:**
- Create: `stock-ai/data/wechat_mp_tv_review_golden/the-odyssey-2026.body_core.md`
- Create: `stock-ai/data/wechat_mp_tv_body_cache/the-odyssey-2026.json`

**Interfaces:**
- Consumes: Task 1 的电影剧情锚点、事实边界和核心判断。
- Produces: 可由 `normalize_tv_review_body()` 处理的纯段落正文，以及 `load_tv_body_cache(topic_key="the-odyssey-2026")` 可读取的缓存。

- [ ] **Step 1: 写剧透预警和战争余波开篇**

第一行固定为 `剧透预警：下文涉及《奥德赛》完整剧情与结局。`，随后从电影实际开场或特洛伊木马场面进入。写清奥德修斯的聪明如何结束战争，也如何把屠城、死亡和愧疚带上归途。

- [ ] **Step 2: 写海上选择和船员代价**

用被核验的独眼巨人、海难或船员死亡场面说明漂泊不是景点式闯关。每次脱险都同时写奥德修斯做了什么、同伴付出什么、这次后果如何改变下一次选择。

- [ ] **Step 3: 写停留与逃避**

只使用 Task 1 确认出现在电影中的喀耳刻、卡吕普索或其他停留段落。把诱惑写成奥德修斯既想回家又害怕面对归家后自己的矛盾，不使用脱离动作的“人性”“命运”“史诗感”空泛议论。

- [ ] **Step 4: 写伊萨卡家庭线与结局**

在最后三分之一写佩涅洛佩承受求婚者逼迫、忒勒马科斯寻父与成长、奥德修斯返乡后的复仇及夫妻重逢。落点是夺回房屋和王位并不自动修复关系，回来的人必须承认自己与离开时已经不同。

- [ ] **Step 5: 进行口吻、原创度和排版改写**

删除第一人称、影评腔、连续反问、导演履历起手、评分起手和万能职场类比。每段二至四句，正文必须在遮住片名和角色名后仍保留特洛伊木马、独眼巨人、伊萨卡求婚者、父子线和重逢等不可换片动作。

- [ ] **Step 6: 写入题目缓存**

调用 `save_tv_body_cache()` 保存标题 `《奥德赛》：回家不是凯旋`、摘要 `奥德修斯赢下战争，却用了十年才明白：夺回家园不等于修复家庭。诺兰把一场英雄归来，拍成了战争之后如何重新成为丈夫和父亲。`、正文和 Task 1 的研究 URL，确保 `topic_key` 为 `the-odyssey-2026`。

- [ ] **Step 7: 验证正文规格**

Run:

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/python -c 'import json,re; from pathlib import Path; p=Path("data/wechat_mp_tv_review_golden/the-odyssey-2026.body_core.md"); b=p.read_text(); ps=[x.strip() for x in b.split("\n\n") if x.strip()]; d=json.loads(Path("data/wechat_mp_tv_body_cache/the-odyssey-2026.json").read_text()); n=len(re.sub(r"\s+","",b)); print({"text_length":n,"paragraphs":len(ps),"max_paragraph":max(map(len,ps)),"title_length":len(d["title"])}); assert b.startswith("剧透预警：下文涉及《奥德赛》完整剧情与结局。"); assert 2400 <= n <= 2800; assert max(map(len,ps)) <= 220; assert len(d["title"]) <= 20'
rg -n '(^|\n)[#>]|^[-*+] |^[0-9]+[.、]|我看|我觉得|值得注意的是|真正的问题是|戏眼|意象|正向反馈|遮羞布|场面堆叠|综上所述' data/wechat_mp_tv_review_golden/the-odyssey-2026.body_core.md
```

Expected: 字数 2400—2800、第一行剧透预警、最长段不超过 220 字、标题不超过 20 字；禁用表达扫描无匹配。

### Task 4: 获取并核验封面与五张公开剧情图

**Files:**
- Create: `stock-ai/assets/wechat_mp/inline-tv/the-odyssey-2026/figure_sources.json`
- Create: `stock-ai/assets/wechat_mp/inline-tv/the-odyssey-2026/cover.jpg`
- Create: `stock-ai/assets/wechat_mp/inline-tv/the-odyssey-2026/still-01.jpg`
- Create: `stock-ai/assets/wechat_mp/inline-tv/the-odyssey-2026/still-02.jpg`
- Create: `stock-ai/assets/wechat_mp/inline-tv/the-odyssey-2026/still-03.jpg`
- Create: `stock-ai/assets/wechat_mp/inline-tv/the-odyssey-2026/still-04.jpg`
- Create: `stock-ai/assets/wechat_mp/inline-tv/the-odyssey-2026/still-05.jpg`

**Interfaces:**
- Consumes: Task 1 的豆瓣照片页、TMDB 图片页、环球官方物料和正式预告候选。
- Produces: 六张互不重复、能对应正文顺序且有来源记录的公开图片。

- [ ] **Step 1: 建立六图候选清单**

优先从豆瓣照片原页和 TMDB backdrop 原页选图，再用环球官方影片页或正式预告画面补足。`figure_sources.json` 每项写全 `file`、`page_url`、`image_url`、`source_name`、`source_type`、`scene`、`verified_at`、`verification_note`；搜索缩略图和无原页的转载图不得进入清单。

- [ ] **Step 2: 下载原图到固定文件名**

封面选择横版 key art 或可安全裁切的横版官方剧照。正文依次对应战争余波、海上/独眼巨人、停留段落、伊萨卡家庭、返乡/重逢；如果某槽位只能在预告中确认，使用官方预告原始画面并在来源记录中标注时间码。

- [ ] **Step 3: 逐张视觉检查**

检查文件是否是真实图片、裁切是否破坏主体、是否含其他公众号水印、场景是否与正文判断一致。封面和正文首图不能来自同一底图，五张正文图不能只是连拍或不同裁切。

- [ ] **Step 4: 验证文件、尺寸、哈希和来源字段**

Run:

```bash
cd stock-ai
shasum -a 256 assets/wechat_mp/inline-tv/the-odyssey-2026/cover.jpg assets/wechat_mp/inline-tv/the-odyssey-2026/still-0*.jpg
PYTHONPATH=. .venv/bin/python -c 'import json; from pathlib import Path; from PIL import Image; root=Path("assets/wechat_mp/inline-tv/the-odyssey-2026"); d=json.loads((root/"figure_sources.json").read_text()); fs=["cover.jpg"]+[f"still-{i:02d}.jpg" for i in range(1,6)]; assert [x["file"] for x in d["images"]]==fs; required=("page_url","image_url","source_name","source_type","scene","verified_at","verification_note"); assert all(all(x.get(k) for k in required) for x in d["images"]); sizes={f:Image.open(root/f).size for f in fs}; assert all(w>=900 and h>=500 for w,h in sizes.values()); print(sizes)'
```

Expected: 六个哈希均不同；每张图都有七个来源字段；图片均能由 Pillow 打开且至少 900×500。

### Task 5: 完整门禁、预演与微信草稿推送

**Files:**
- Read: `stock-ai/output/odyssey_2026_quality.json`
- Read: `stock-ai/data/wechat_mp_tv_body_cache/the-odyssey-2026.json`
- Read: `stock-ai/assets/wechat_mp/inline-tv/the-odyssey-2026/figure_sources.json`

**Interfaces:**
- Consumes: Task 1—4 的研究、题目注册、正文缓存与六图。
- Produces: 通过原创和排版门禁的微信影视草稿及成功返回的 `media_id`。

- [ ] **Step 1: 运行影视原创增量门禁**

读取 `odyssey_2026_quality.json` 的 `plot_anchors`、`history_posts` 与 `film_titles`，调用现有 `evaluate_film_longform()` 和 `format_originality_report()`。要求 `gate_passed == True`、正文不少于 2200 字、完整电影锚点不少于五个、`same_work_published_30d == False`；否则回到 Task 1 或 Task 3。

- [ ] **Step 2: 运行本地影视草稿预演**

Run:

```bash
cd stock-ai
WECHAT_MP_TV_TOPIC=奥德赛 WECHAT_MP_TV_RESEARCH=0 PYTHONPATH=. .venv/bin/python -m scripts.tools.wechat_mp_draft --kind tv_review --dry-run
```

Expected: 退出码为 0；标题为 `《奥德赛》：回家不是凯旋`；正文来自缓存；五个不同的 `[[fig:tv/the-odyssey-2026/still-` 标记按顺序出现；没有调用正文生成模型，也没有产生 `media_id`。

- [ ] **Step 3: 运行新鲜的最终验证**

重新执行 Task 2 的两组 pytest、Task 3 的正文规格检查、Task 4 的六图检查、Task 5 Step 1 的原创门禁和 Step 2 的 `--dry-run`。全部使用本轮新输出，不复用先前日志。

- [ ] **Step 4: 写入微信草稿箱**

Run:

```bash
cd stock-ai
WECHAT_MP_TV_TOPIC=奥德赛 WECHAT_MP_TV_RESEARCH=0 PYTHONPATH=. .venv/bin/python -m scripts.tools.wechat_mp_draft --kind tv_review
```

Expected: 微信接口返回成功和非空 `media_id`；标题、摘要、封面与五张正文图上传完成。若 access token、IP 白名单、素材上传或原创门禁失败，停止并报告原始错误，不重试绕过门禁。

- [ ] **Step 5: 向用户交付结果**

汇报最终标题、正文去空白字数、五个剧情锚点、六图来源状态、原创门禁结果和微信 `media_id`。明确内容已写入草稿箱但未发表。

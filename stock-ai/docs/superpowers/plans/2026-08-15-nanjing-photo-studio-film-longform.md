# 《南京照相馆》影视长图文 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成《南京照相馆》2400—3000 字影视长图文，以暗房显影、亲善照摆拍和底片转移构成剧情因果线，并通过来源、原创、排版与五图门禁，但不写入微信公众号草稿箱。

**Architecture:** 先建立史实、主创说法与影片剧情分层的研究台账，再把作品注册进现有 `tv_review` 题库与剧照锚点表。正文采用手工金样和按题缓存作为唯一真源，现有影视链路只负责规范化、插图与本地预演，不调用 DeepSeek 重写正文。

**Tech Stack:** 公开网页研究、Markdown、JSON、Python、pytest、`scripts.tools.wechat_mp_tv_body_cache`、`scripts.tools.wechat_mp_draft --kind tv_review`。

## Global Constraints

- 标题固定为 `《南京照相馆》：底片不能烧`，长度不超过 20 字。
- 正文去空白后控制在 2400—3000 字，硬门槛不低于 2000 字。
- 正文为纯段落，不使用 Markdown 小标题、编号、项目符号或问答模板。
- 每段二至四句，单段不超过约 220 字；禁止第一人称和一句一行排版。
- 剧情及其直接因果约占正文六成，至少包含两个不同阶段的完整剧情锚点。
- 1945 年 8 月 15 日与 9 月 2 日的历史含义必须准确区分。
- 具体台词只在影片、主创访谈或可信剧情复盘能够核验时使用引号，否则转述。
- 至少使用 3 个独立来源域，分别覆盖历史节点、主创资料和剧情复盘。
- 配图为 1 张封面和 5 张正文图；正文图按剧情顺序插入，封面不得与正文首图重复。
- 正文底部不声明栀夏或作者是 AI；发布环节由平台声明处理。
- 本轮只运行 `--dry-run`，未经用户明确说“推送”不得调用微信草稿写入接口。

---

## File Structure

- Create: `stock-ai/output/nanjing_photo_studio_research.md` — 史实、剧情锚点、台词与图片来源台账。
- Create: `stock-ai/output/nanjing_photo_studio_quality.json` — 原创判断、完整剧情锚点、来源 URL 和近 30 天作品检查输入。
- Modify: `stock-ai/scripts/tools/wechat_mp_tv_topics.py` — 注册 `Nanjing Photo Studio` 题目、中文名、标题、来源与写作角度。
- Modify: `stock-ai/scripts/tools/wechat_mp_tv_figures.py` — 注册 `nanjing-photo-studio` 的 5 个正文图锚点与统一图源说明。
- Modify: `stock-ai/tests/unit/test_wechat_mp_tv_trial.py` — 验证题目注册和 20 字标题。
- Modify: `stock-ai/tests/unit/test_wechat_mp_tv_figures.py` — 验证 5 张图按正文剧情锚点顺序注入。
- Create: `stock-ai/data/wechat_mp_tv_review_golden/nanjing-photo-studio.body_core.md` — 无评分、无插图标记的正文金样。
- Create: `stock-ai/data/wechat_mp_tv_body_cache/nanjing_photo_studio.json` — 标题、摘要和正文缓存，供预演与后续重推复用。
- Create: `stock-ai/assets/wechat_mp/inline-tv/nanjing-photo-studio/figure_sources.json` — 封面与 5 张正文图的原页、原图 URL、来源名、发布时间、用途与授权备注。
- Create: `stock-ai/assets/wechat_mp/inline-tv/nanjing-photo-studio/cover.jpg` — 暗房与底片主题封面。
- Create: `stock-ai/assets/wechat_mp/inline-tv/nanjing-photo-studio/still-01.jpg` — 照相馆与暗房场景。
- Create: `stock-ai/assets/wechat_mp/inline-tv/nanjing-photo-studio/still-02.jpg` — 显影液中逐渐出现照片的场景。
- Create: `stock-ai/assets/wechat_mp/inline-tv/nanjing-photo-studio/still-03.jpg` — 亲善照摆拍场景。
- Create: `stock-ai/assets/wechat_mp/inline-tv/nanjing-photo-studio/still-04.jpg` — 林毓秀与众人决定保存底片的场景。
- Create: `stock-ai/assets/wechat_mp/inline-tv/nanjing-photo-studio/still-05.jpg` — 底片藏匿或转移场景。
- Read: `stock-ai/docs/superpowers/specs/2026-08-15-nanjing-photo-studio-film-longform-design.md` — 已确认的文章设计与验收标准。

### Task 1: 建立事实与剧情证据台账

**Files:**
- Create: `stock-ai/output/nanjing_photo_studio_research.md`
- Create: `stock-ai/output/nanjing_photo_studio_quality.json`

**Interfaces:**
- Consumes: 外交部与新华网的 8 月 15 日史实页面、主创访谈、电影官方资料和可信剧情复盘。
- Produces: 至少 3 个独立来源域、3 个完整剧情锚点、可直接使用的台词清单和不可写成史实的电影虚构项。

- [ ] **Step 1: 核验历史节点**

打开外交部 `https://www.fmprc.gov.cn/ziliao_674904/historytoday_674971/200308/t20030815_7949130.shtml` 与新华网 `https://www.news.cn/world/2023-08/15/c_1129804447.htm`，记录 1945 年 8 月 15 日接受《波茨坦公告》、宣布无条件投降，以及 9 月 2 日正式签署投降书的区别。正文只把 8 月 15 日用作重看入口，不称影片当天有新宣发。

- [ ] **Step 2: 核验主创的影像资料准备**

打开上观新闻导演访谈 `https://export.shobserver.com/wx/detail.do?id=954698`，记录剧组查阅 5—6 本书、20 多部纪录片、整理 300—400 张历史照片并选取 100 多张代表照片的主创说法。该材料只用于说明创作准备，不据此断言影片中每个角色都有真实原型。

- [ ] **Step 3: 核验三个剧情锚点**

交叉打开解放日报 `https://www.jfdaily.com/wx/detail.do?id=954395`、澎湃新闻 `https://www.thepaper.cn/newsDetail_forward_31201917` 和新浪转引的大象新闻访谈 `https://finance.sina.com.cn/jjxw/2025-08-04/doc-infivrrr0065406.shtml`。分别记录暗房显影、亲善照摆拍、林毓秀提出“万一日本人输了呢”及底片缝入衣服或转移的场景；每个锚点写全 `scene`、`character`、`action`、`counterpart_or_pressure`、`consequence`、`source_url`、`stage` 七个字段。

- [ ] **Step 4: 写证据边界**

在研究台账中把每条材料标为 `history_fact`、`creator_statement`、`film_plot` 或 `article_inference`。角色关系、照相馆内部行动链和具体台词归入电影叙事；“底片把私人求生转化为对未来的责任”归入文章判断，不伪装成主创原话。

- [ ] **Step 5: 验证台账完整性**

Run:

```bash
cd stock-ai
rg -n 'history_fact|creator_statement|film_plot|article_inference|https://|scene|character|action|counterpart_or_pressure|consequence|stage' output/nanjing_photo_studio_research.md output/nanjing_photo_studio_quality.json
```

Expected: 四类证据边界均出现；质量 JSON 中有 3 个七字段完整的剧情锚点和不少于 3 个独立来源域。

### Task 2: 注册影片与五个插图锚点

**Files:**
- Modify: `stock-ai/scripts/tools/wechat_mp_tv_topics.py`
- Modify: `stock-ai/scripts/tools/wechat_mp_tv_figures.py`
- Modify: `stock-ai/tests/unit/test_wechat_mp_tv_trial.py`
- Modify: `stock-ai/tests/unit/test_wechat_mp_tv_figures.py`

**Interfaces:**
- Consumes: Task 1 已核验的片名、标题、研究 URL 和剧情顺序。
- Produces: `CURATED_HOT` 中 `title_en="Nanjing Photo Studio"` 的题目，以及 `CURATED_TV_STILLS["nanjing-photo-studio"]` 的五图注入规则。

- [ ] **Step 1: 写影片题目失败测试**

在 `test_wechat_mp_tv_trial.py` 新增测试，查找 `title_en == "Nanjing Photo Studio"` 的题目，并断言 `title_zh == "南京照相馆"`、`cover_slug == "nanjing-photo-studio"`、`type == "film"`、`title_override == "《南京照相馆》：底片不能烧"`、标题长度不超过 20。

- [ ] **Step 2: 运行题目测试确认失败**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/python -m pytest tests/unit/test_wechat_mp_tv_trial.py -q`

Expected: FAIL，提示找不到 `Nanjing Photo Studio`。

- [ ] **Step 3: 添加影片题目**

在 `CURATED_HOT` 添加 2025 年电影条目，固定 `title_en`、`title_zh`、`platform="院线电影"`、`type="film"`、`year="2025"`、`cover_slug`、`title_override`、核心判断、Task 1 的研究 URL 和 2026 年 8 月 15 日重看说明。评分字段留空，不注入未经当天核验的豆瓣或海外评分。

- [ ] **Step 4: 写五图顺序失败测试**

在 `test_wechat_mp_tv_figures.py` 构造包含“暗房里第一次看清”“摆拍的亲善照”“万一日本人输了”“把底片缝进衣服”“证据必须活下去”五个完整短语的正文，断言输出含 `still-01.jpg` 至 `still-05.jpg`，且五个 `[[fig:]]` 的索引严格递增。

- [ ] **Step 5: 运行五图测试确认失败**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/python -m pytest tests/unit/test_wechat_mp_tv_figures.py -q`

Expected: FAIL，当前没有 `nanjing-photo-studio` 的图片配置。

- [ ] **Step 6: 添加五图注入配置**

在 `CURATED_TV_STILLS` 添加 `source="local"`、统一图源说明和五个 `after_anchor` 槽位，锚点分别使用 Step 4 的完整短语。每个槽位只匹配一个剧情阶段，不使用“照片”“底片”等过短词语。

- [ ] **Step 7: 运行相关测试**

Run:

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/python -m pytest tests/unit/test_wechat_mp_tv_trial.py tests/unit/test_wechat_mp_tv_figures.py -q
```

Expected: 新增测试和既有影视测试全部 PASS。

### Task 3: 完成 2400—3000 字正文金样与缓存

**Files:**
- Create: `stock-ai/data/wechat_mp_tv_review_golden/nanjing-photo-studio.body_core.md`
- Create: `stock-ai/data/wechat_mp_tv_body_cache/nanjing_photo_studio.json`

**Interfaces:**
- Consumes: Task 1 的剧情锚点、历史边界和原创判断。
- Produces: 无小标题、无图片标记、可由 `normalize_tv_review_body()` 处理的正文，以及 `load_tv_body_cache(topic_key="nanjing-photo-studio")` 可读取的缓存。

- [ ] **Step 1: 写开篇和被迫冲洗段落**

首段用 8 月 15 日和暗房的红灯进入影片，不把文章写成纪念日宣讲。随后写普通人最初只想活下来、替日军冲洗照片的被迫处境，并落下完整短语“暗房里第一次看清”，交代图像显现如何改变人物对危险的理解。

- [ ] **Step 2: 写真假影像对照段落**

用至少 3 个自然段写照片显影、暴行内容被辨认、日军要求百姓配合摆拍，以及“摆拍的亲善照”如何与罪证照构成直接冲突。每个判断必须跟在具体动作之后，不把摄影写成脱离剧情的抽象象征。

- [ ] **Step 3: 写选择与代价段落**

写林毓秀提出“万一日本人输了”、众人从回避风险转向保存证据，以及“把底片缝进衣服”或转移底片增加的搜查和死亡风险。人物仍然害怕、犹豫和计算，不能突然变成无所畏惧的英雄。

- [ ] **Step 4: 写结尾**

以“证据必须活下去”回扣标题，说明底片既记录受害，也阻止施害者独占历史解释。结尾不使用万能职场类比、读者假共情、连续反问或口号式升华。

- [ ] **Step 5: 进行语言和排版改写**

删除“值得注意的是”“真正的问题是”“戏眼”“意象”“正向反馈”“遮羞布”“场面堆叠”“综上所述”等表达；保证每段二至四句、单段不超过约 220 字，正文中没有第一人称、Markdown 小标题、编号和项目符号。

- [ ] **Step 6: 生成题目缓存**

使用 `save_tv_body_cache()` 读取金样正文，写入标题 `《南京照相馆》：底片不能烧` 和摘要 `暗房里的底片，让只想活下来的普通人开始替未来保存证据。电影最有力量的不是突然无畏，而是明知害怕仍不让真相被烧掉。`。生成文件后检查 `topic_key` 为 `nanjing-photo-studio`。

- [ ] **Step 7: 验证正文规格**

Run:

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/python -c 'import json,re; from pathlib import Path; p=Path("data/wechat_mp_tv_review_golden/nanjing-photo-studio.body_core.md"); b=p.read_text(); ps=[x.strip() for x in b.split("\n\n") if x.strip()]; d=json.loads(Path("data/wechat_mp_tv_body_cache/nanjing_photo_studio.json").read_text()); print({"text_length":len(re.sub(r"\s+","",b)),"paragraphs":len(ps),"max_paragraph":max(map(len,ps)),"title_length":len(d["title"]),"anchors":sum(x in b for x in ["暗房里第一次看清","摆拍的亲善照","万一日本人输了","把底片缝进衣服","证据必须活下去"])}); assert 2400 <= len(re.sub(r"\s+","",b)) <= 3000; assert max(map(len,ps)) <= 220; assert len(d["title"]) <= 20'
rg -n '(^|\n)[#>]|^[-*+] |^[0-9]+[.、]|我看|我觉得|值得注意的是|真正的问题是|戏眼|意象|正向反馈|遮羞布|场面堆叠|综上所述' data/wechat_mp_tv_review_golden/nanjing-photo-studio.body_core.md
```

Expected: 字数 2400—3000、最长段不超过 220 字、5 个插图锚点均出现、标题不超过 20 字；禁用表达扫描无匹配。

### Task 4: 获取并核验封面与五张剧情图

**Files:**
- Create: `stock-ai/assets/wechat_mp/inline-tv/nanjing-photo-studio/figure_sources.json`
- Create: `stock-ai/assets/wechat_mp/inline-tv/nanjing-photo-studio/cover.jpg`
- Create: `stock-ai/assets/wechat_mp/inline-tv/nanjing-photo-studio/still-01.jpg`
- Create: `stock-ai/assets/wechat_mp/inline-tv/nanjing-photo-studio/still-02.jpg`
- Create: `stock-ai/assets/wechat_mp/inline-tv/nanjing-photo-studio/still-03.jpg`
- Create: `stock-ai/assets/wechat_mp/inline-tv/nanjing-photo-studio/still-04.jpg`
- Create: `stock-ai/assets/wechat_mp/inline-tv/nanjing-photo-studio/still-05.jpg`

**Interfaces:**
- Consumes: Task 1 核验过的官方电影物料、出品发行方页面和明确标注“电影提供”的媒体原页。
- Produces: 1 张封面、5 张互不重复且与锚点一致的正文图、每图一条可追溯来源记录。

- [ ] **Step 1: 建立候选图片清单**

从电影官方账号、出品发行方、主创访谈原页和明确标注电影提供的媒体页面提取候选图。`figure_sources.json` 为每张图记录 `file`、`page_url`、`image_url`、`source_name`、`published_at`、`scene`、`reuse_note`；媒体转载页若未说明图片来源，不作为唯一依据。

- [ ] **Step 2: 下载并检查原图**

逐张下载到固定文件名，检查 HTTP 状态、MIME 类型、像素尺寸和是否为真实图片。封面必须是横图或可安全裁成横图，正文图不得使用演员写真、重复海报或与剧情无关的路演照。

- [ ] **Step 3: 对缺失槽位使用原创解释图**

若某个剧情槽位没有可复用依据，生成不复刻演员面孔、不伪造档案照片的原创暗房解释图，并在 `figure_sources.json` 将 `source_name` 写为 `OpenAI ImageGen 原创解释图`、`reuse_note` 写明对应剧情概念。不得用生成图冒充电影镜头或历史现场。

- [ ] **Step 4: 逐张视觉检查**

使用图像查看工具检查裁切、压缩、人物畸变、错误文字、水印和场景对应关系。封面与 `still-01.jpg` 不能是同一底图的裁切版本；五张正文图必须按暗房建立、显影、摆拍、决定、转移的顺序成立。

- [ ] **Step 5: 验证文件、尺寸、哈希和来源字段**

Run:

```bash
cd stock-ai
shasum -a 256 assets/wechat_mp/inline-tv/nanjing-photo-studio/cover.jpg assets/wechat_mp/inline-tv/nanjing-photo-studio/still-0*.jpg
PYTHONPATH=. .venv/bin/python -c 'import json; from pathlib import Path; from PIL import Image; root=Path("assets/wechat_mp/inline-tv/nanjing-photo-studio"); d=json.loads((root/"figure_sources.json").read_text()); fs=["cover.jpg"]+[f"still-{i:02d}.jpg" for i in range(1,6)]; assert [x["file"] for x in d["images"]]==fs; assert all(x.get("source_name") and x.get("scene") and x.get("reuse_note") for x in d["images"]); print({f:Image.open(root/f).size for f in fs})'
```

Expected: 6 个哈希均不同；来源清单顺序与文件顺序一致；每张图都有来源名、场景和复用说明；图片均可由 Pillow 打开。

### Task 5: 原创门禁、影视预演与交付

**Files:**
- Read: `stock-ai/output/nanjing_photo_studio_quality.json`
- Read: `stock-ai/data/wechat_mp_tv_body_cache/nanjing_photo_studio.json`
- Read: `stock-ai/assets/wechat_mp/inline-tv/nanjing-photo-studio/figure_sources.json`

**Interfaces:**
- Consumes: Task 1—4 的研究、正文、缓存与六图。
- Produces: `film_longform` 原创增量报告、五图注入预演和用户可审阅的完整正文；不产生微信 `media_id`。

- [ ] **Step 1: 运行影视原创增量门禁**

读取 `nanjing_photo_studio_quality.json` 的 `plot_anchors`、`history_posts` 和 `film_titles`，调用 `evaluate_film_longform()`；正文使用金样全文，标题使用固定标题。打印 `format_originality_report()` 并要求 `gate_passed == True`、正文不少于 2400 字、完整锚点不少于 2、`same_work_published_30d == False`。

- [ ] **Step 2: 运行本地影视草稿预演**

Run:

```bash
cd stock-ai
WECHAT_MP_TV_TOPIC=南京照相馆 WECHAT_MP_TV_RESEARCH=0 PYTHONPATH=. .venv/bin/python -m scripts.tools.wechat_mp_draft --kind tv_review --dry-run
```

Expected: 命令退出码为 0；标题为 `《南京照相馆》：底片不能烧`；正文来自缓存；输出含 5 个不同的 `[[fig:tv/nanjing-photo-studio/still-` 标记；没有调用 DeepSeek，没有 `media_id`。

- [ ] **Step 3: 检查剧情占比和换片测试**

按自然段标记“剧情/直接因果”与“分析”，确认前者不少于全文约六成。再临时遮住片名和角色名检查正文，仍必须出现暗房、显影、亲善照、罪证底片、缝入衣服或转移等作品专属动作；若只剩可套用到其他历史片的判断，回到 Task 3 重写。

- [ ] **Step 4: 运行新鲜的最终验证**

重新执行 Task 2 的两组 pytest、Task 3 的规格检查、Task 4 的六图检查、Task 5 Step 1 的原创门禁和 Step 2 的 `--dry-run`。记录每项退出码，不复用此前结果。

- [ ] **Step 5: 向用户交付**

提供最终标题、完整正文、正文去空白字数、独立来源域数量、完整剧情锚点数量、原创增量报告和六图状态。明确“尚未写入公众号草稿箱”；只有用户明确说“推送”后，才允许执行不带 `--dry-run` 的影视草稿命令。

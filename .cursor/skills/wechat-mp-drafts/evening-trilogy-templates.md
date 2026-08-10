# 晚间两篇标准模板（evening batch 金标准）

> 导航 [INDEX.md](INDEX.md) · 改这两篇**只读本文件 + hotspot 节**，勿在 [templates.md](templates.md) 重复改结构。

> **适用范围（2026-07-13 起）**：A 股交易日 `evening` 批次 — **`news`（10 条热股快讯）** + **`hotspot`（每日热点深评）**。  
> `dragons` / `sector` / `market` 已移出定时，仅手动推稿。
> **地位**：2026-06-04 审阅定稿版（含 **· 轻过渡完读钩子**、段长/序号排版）；改 prompt / 排版 / 变现时**以此为准**，勿回退旧版（`往下看`/`→` 导流、标题进正文、分节末 CPS 等）。  
> **命令**：`uv run python -m scripts.tools.wechat_mp_draft_batch --batch evening`

五槽总表与 `news` / `workspace` 见 [templates.md](templates.md)；带货稿见 [wechat-mp-commerce-drafts](../wechat-mp-commerce-drafts/SKILL.md)。

---

## 一、三篇共用版式（定稿 UX）

| 项 | 标准样子 | 代码 |
|----|----------|------|
| 品牌头 | 顶栏 banner + 青框 slogan，无框底留白 | `masthead_html` |
| **彩色开篇** | **17px、加粗、居中、`#1a5276`**，仅**一段** | `opening_lede_paragraph_style` + `text_to_html(..., article_kind=)` |
| 分节标题 | `> 标题` 一行 → 居中 17px 节标题 | `ensure_blockquote_sections` → `blockquote_title_html` |
| 序号 | **禁止**「一、二、三」 | `demote_numbered_section_lines` |
| 插图 | **第一节标题之后**才插图；中段 max-height 200px；A股/科技/交易屏 | `inject_*_figures` |
| **返佣 CPS** | 正文约 **2/3** 处（对齐 `</p>`/`</section>` 块尾），**非**固定分节末 | `inject_cpsad_at_body_ratio` · `cps_injection_index` |
| 免责 | **仅 1 处**：文末红框居中 15px；正文内 LLM 免责段剥离 | `strip_inline_disclaimer_blocks` + `disclaimer_html` |
| 话题 | 免责前一行 `#A股 #…`（正文内，非「发布后加话题」说明） | `append_hashtag_inline_to_body` |
| 阅读原文 | **默认关闭**（勿链 home-hub） | `WECHAT_MP_READ_SOURCE_URL=0` |
| 研究员口吻 | 数字→机制→映射→验证 | `RESEARCHER_VOICE_RULE` · [researcher-voice.md](researcher-voice.md) |
| **段长** | 单段约 **≤120 字**（约半屏）；超长在句号/分号处拆段 | `wechat_mp_readability` · `WECHAT_MP_PARA_MAX_CHARS` |
| **序号列表** | `1. 2. 3.` **一行一项**；Top5 四字段各占一行 | `reflow_inline_numbered_lists` |
| **完读钩子** | 节间/股间/条间用 **`·` 短衔接句**（对比、验证口吻）；**禁止**「往下看」「→」 | `wechat_mp_read_hooks` · `*_polish.py` · `WECHAT_MP_READ_HOOKS=1` |
| emoji | 全无 | 硬约束 |

### 完读钩子 · 金标准（2026-06-04）

**原则**：像研究员手记里的自然过渡，**不要**导流腔（「往下看」「接着读」「→」）。

| kind | 代码 | 典型 `·` 句（成稿可补，LLM 宜自写同风格） |
|------|------|------------------------------------------|
| `sector` | `finalize_sector_body` | `· 价格在产业链上传导，往往比新闻标题慢半拍。` |
| `top5` | `finalize_top5_body` | `· 和上一只比，谁更贴主线，差别往往在量价。` |
| `dragons` | `finalize_dragons_body` | `· 下一只先盯板位，高度能不能稳住，比故事更重要。` |

**结构（top5 示例）**

```markdown
> 筛选名单
{彩色开篇：数据日 + 主线 + 阅读路径「逐只拆→组合→待验证」——勿复述标题句式}

名单扫一眼只解决「有谁」；逐只拆量价，才看得出结构与主线是否一致。

> 个股拆解
1. 甲（000001）
逻辑归属：…
量价结构：…
…

· 和上一只比，谁更贴主线、谁更像独立脉冲，差别往往在量价。

2. 乙（000002）
…

> 组合特征
…
五只放在一起看，强弱已露头；最后对照「待验证事项」——若主线缩量，谁先掉速会先在量能上给答案。

> 待验证事项
…
结构跟踪日若板块承接走弱，名单里谁先掉速，往往最先在换手与收盘位置上露馅。
```

**标题与正文分工**：标题可用「领衔N只！收盘信号出炉，明日盯啥？」；**正文禁止**同构问句（`strip_top5_title_echo`）。

### 彩色开篇 · 插入位置

| kind | 彩色段位置 | 正文来源 |
|------|------------|----------|
| `market` | `> 盘面速览` **之前**（2 句，含指数/涨跌家数） | `inject_market_opening_lede` → `finalize_market_body` |
| `top5` | `> 筛选名单` 下**第一段** | LLM / 模板首段（结论先行一句） |
| `dragons` | `> 情绪与盘面` 下**第一段** | LLM / 模板首段（炸板率/涨跌比等数字） |

---

## 二、`market` — 盘后收盘评论（close）

**定位**：盘面 + 外围 + 结构；**不含**要闻列表。与 `news` 标题钩子分离。

### 标题（close 池，≤32 字）

轮换：`wechat_mp_market_titles --edition close`；占位 `{wd}`、`{tags}`（正文提取，如 `油价+半导体`）。

**金标准句式（优先）**

```
收盘复盘：{tags}牵动哪些线？
A股收盘｜{tags}，结构怎么看？
指数涨、个股跌？{tags}怎么接
今日收盘三条线：{tags}
```

**定稿示例**

- `收盘复盘：油价+涨停潮牵动哪些线？`
- `A股收盘｜油价+半导体，结构怎么看？`

**禁止**：盘前/午间句式；无盘面支撑的「普跌/暴涨」；与当日 `news` 标题雷同。

### 正文骨架（Markdown 真源）

```markdown
{开篇 2 句：指数/涨跌家数 + 结构一句话 + 午后/明日验证导向}
← 渲染为彩色开篇段，不在「一、」或「>」下

> 盘面速览

{指数点位、涨跌家数、成交额、指数与广度是否共振——数字开头，短段}

[[fig:inline-*.jpg|]]   ← 仅在本节之后

> 外围与资金

{美股/恒指/油价/汇率 + 与 A 股传导一句}

> 结构判断

我们认为，{主线判断}。
值得关注的是，{暗线/背离}。
向后看，{1～2 个可跟踪指标}。
```

### 研究员好句（可仿写，勿照抄）

```
沪指收涨 0.22%，上涨家数仍明显少于下跌家数，指数与广度背离。
我们认为，当前矛盾在于存量博弈下的资金再分配：存储器涨价链条映射至半导体存储环节，尚待明日涨停家数验证情绪是否过热。
向后看，需跟踪恒生科技能否守住支撑、WTI 能否站稳 90 美元一线。
```

### 流水线（勿跳过）

`build_market_article` → `humanize_mp_text` → **`finalize_market_body`**（开篇 + 结构分段 + 长段拆分 + **· 节间钩子**）→ `align_market_title_mood` → `inject_market_figures` → `sanitize_public_mp_text` → `render_article_content_html(kind=market)` → **`attach_footer_product`**

### 自检

- [ ] 彩色开篇在「盘面速览」之上
- [ ] 「我们认为 / 值得关注的是 / 向后看」各一段
- [ ] CPS 在正文中后段（约 2/3），不在文首
- [ ] 免责仅文末 1 块

---

## 三、`sector` — 热点行业研究（东财行业榜）

**定位**：东财行业板块涨幅榜榜一/榜二 + 产业链五节；**数据日**与选股库最近交易日一致（非成稿日历「今天」）。  
**主题挖掘**：`discover_sector_hot_themes` · [sector-discovery.md](sector-discovery.md)

### 标题

**金标准句式**

```
A股行业｜{榜一+榜二}：产业链怎么拆？
热点行业｜{榜一}，向后看验证啥
```

### 正文骨架（Markdown 真源）

```markdown
{彩色开篇 1 段：首句必须含「{M}月{D}日收盘」，点明该日聚焦行业 + 机制判断 + 五节展开路径}
← 禁止用「今日」指代数据日

> 为什么现在看

{催化 + 为何是该数据日的主线；160～220 字；短段}

· 价格在产业链上传导，往往比新闻标题慢半拍，产业链拆开才看得清。

> 产业链怎么拆

{上中下游；280～380 字；短段}

· 谁在量价上表态，比概念名单更重要。

> 盘面里谁在用价格说话

{代表股/板块量价；240～320 字；**至少 2 只**样本股写清公司名+代码+量价事实，来自行业领涨/人气同行业/龙头池，非 top5 式名单}

· 行业强不等于个股强，指数情绪这一段值得对照着读。

> 和指数情绪怎么联动

{指数、涨跌家数；180～240 字}

· 向后看里留验证点，明日用什么数据证伪今天的判断。

> 向后看要验证什么

{2～3 个可跟踪指标；「我们认为」「值得关注的是」「向后看」各一段}
若…则…谁先…露馅式末句（成稿可补）
```

### 流水线

`build_sector_article` → `humanize_mp_text` → `ensure_blockquote_sections` → **`finalize_sector_body`** → `inject_market_figures` → `render` → `attach_footer_product`

### evening 同批分工（2026-06-18 · 与 news 去重）

| 篇 | 写什么 | sector 禁止 |
|----|--------|-------------|
| **news** 头条 | 东财人气 Top10 快讯 + AI 点评 | — |
| **dragons** 次条 | 情绪/连板 | — |
| **sector** 三条 | 东财**行业榜**榜一/榜二 + 产业链五节 | 再插「当日人气观察 Top10」；盘面节复述头条热股 |

**代码**：`WECHAT_MP_SECTOR_EVENING_DEDUP=1`（evening 批次自动）· `WECHAT_MP_SECTOR_HOT_WATCH_TOP_N=0` · 代表股避开 news 人气前 2（`WECHAT_MP_SECTOR_EXCLUDE_NEWS_HOT_N`）· 标题优先**行业领涨股**而非人气榜首。

### 摘要

```
【6月3日收盘 行业观察】{榜一+榜二}——东财行业榜挖掘 6月3日收盘 热点…
```

### 自检

- [ ] 开篇与摘要含 **「M月D日收盘」**（与 `report.trade_date` 一致）
- [ ] 正文无「今日」指代行情日
- [ ] 主线来自东财行业榜，非龙头池 `main_theme`
- [ ] 五节间有 `·` 过渡（无「往下看」「→」）；单段不过长

---

## 四、`top5` — 收盘选股结构拆解

**定位**：多策略 Top5；**客观结构**，非荐股、非打分操作建议。  
**搜一搜**：标题 **领衔股名** 前置；每只「逻辑归属」对齐当日 sector 主线（`wechat_mp_evening_align`）。**篇幅** 750～1200 字。

### 标题

**金标准句式**

```
A股选股{n}只｜{龙头名}领衔，明日盯啥？
{龙头名}领衔{n}只！收盘信号出炉，明日盯啥？
{周几}A股选股｜{A}领衔{n}只技术信号
```

**定稿示例**

- `A股选股5只｜金时科技领衔，明日盯啥？`

### 正文骨架

见上文 **「完读钩子 · 金标准」** 完整示例；要点：

- **标题**（字段）：`{龙头名}领衔{n}只！收盘信号出炉，明日盯啥？`（`_top5_title`）
- **正文首段**（彩色）：数据日 + 只数 + 行业主线 + 阅读路径；**勿**复述标题
- **进个股前**：一句「名单→逐只拆」桥接
- **每只之间**：`·` 对比/验证句（缺则 `finalize_top5_body` 补）
- **组合特征末**：引向待验证的悬念句
- **待验证末**：「若…则…谁先…露馅」硬验证

```markdown
> 筛选名单
{彩色开篇}
{名单→逐只拆桥接一句}

> 个股拆解
1. …
逻辑归属：
量价结构：
技术位置：
待核实：

· {过渡句}

2. …
…

> 组合特征
{… + 引向待验证}

> 待验证事项
{2～3 条 + 若则验证末句}
```

### 禁词（`sanitize_top5_analysis_text` / `strip_top5_title_echo`）

综合得分、操作建议、观察买入、持仓计划、82分、排名分；正文「XX领衔N只！收盘信号出炉，明日盯啥？」。

### 流水线

`build_top5_article` → LLM → `inject_top5_figures` → `humanize` → `ensure_blockquote_sections` → `sanitize_top5` → **`finalize_top5_body`** → `render` → `attach_footer_product`

### 自检

- [ ] 彩色开篇在「筛选名单」首段，**无标题句式**
- [ ] 每只四行字段**各占一行**；股间有 `·` 过渡（无「往下看」「→」）
- [ ] 单段不过长（约半屏）
- [ ] CPS 约 2/3

---

## 五、`dragons` — 情绪 + 龙头博弈

**定位**：情绪周期 + 龙头池（≤3 只 SOP）；游资复盘腔，**非**执行卡。  
**搜一搜金标准标题（优先）**：`情绪退潮怎么玩？{名}{n}板还在榜`（代码 `_dragon_title` 第一候选）。  
**完读优化**：正文深度写 **≤2 只**（`WECHAT_MP_DRAGON_WRITE_MAX=2`）；650～1100 字；开篇含炸板率/涨跌比（`inject_dragons_opening_lede`）+ **`·` 段间/股间钩子**（`finalize_dragons_body`）。

### 标题

**金标准句式**

```
情绪{阶段}怎么玩？{名}{n}板还在榜
情绪周期·{主线}龙头｜{名}{n}板？
{phase_hint}？{主线}+{龙头名}{n}板还在榜
```

**定稿示例**

- `情绪周期·动力煤龙头｜粤电力Ａ4板？`

### 正文骨架

```markdown
> 情绪与盘面

{阶段、涨停/跌停/炸板率、涨跌比——彩色开篇；正文路径「盘面→龙头→梯队→纪律」}

· 龙头拆解才是情绪真正的试金石。

> 龙头拆解

1. {名}（{代码}）
地位：…
量价资金：…
博弈：…
待核实：…

· 这只和上一只比，谁在接力、谁在掉队，一眼能分。

2. {名}（{代码}）
…

· 空间板断了以后，梯队怎么排，比单看高度更重要。

> 主线与梯队

{空间板、补涨、跟风梯队；短段}

· 明日盯什么信号，比今晚的口号更值得写进备忘录。

> 明日计划与纪律

{第三人称盘面跟踪 + 通用纪律}
若次日炸板率抬升、空间板断板且跟风走弱，退潮才算确认（成稿可补）
```

### 硬性禁止（全文）

`6/7`、`X/7`、`系统筛选用分`、`龙头确认`、`内部认可`、`checklist_pass` 进稿。

### 好句范例

```
退潮信号明确……炸板率高达 40.59%，亏钱效应已经开始蔓延。
这种结构不能急着接，要等缩量企稳。
情绪窗口期，3 板跟风票一旦龙头断板，往往最先被核。
```

### 流水线

`build_dragons_article` → LLM → **`finalize_dragons_body`**（数字开篇 + · 钩子 + 控长）→ `inject_dragons_figures` → `sanitize` → `render`

### 自检

- [ ] 彩色开篇在「情绪与盘面」首段
- [ ] 无 X/7、无内部认可话术
- [ ] 股间/节间有 `·` 过渡（无「往下看」「→」）
- [ ] CPS 约 2/3

---

## 三篇对照（晚间一眼表）

| | sector | top5 | dragons |
|---|--------|------|---------|
| 读者问题 | 该日哪些行业最热、产业链怎么拆？ | 筛出哪几只、结构怎么验证？ | 情绪在哪、龙头怎么博弈？ |
| 数据日表述 | **6月3日收盘**（禁「今日」） | 数据日 ISO + 结构跟踪日 | 情绪数据日 |
| 彩色开篇 | 五节路径 + 首段 | `筛选名单` 首段（非标题句） | `情绪与盘面` 首段 + 数字 |
| 完读衔接 | 节间 `·`（4 处） | 名单桥接 + 股间 `·` + 末段若则 | 节间 `·` + 股间 `·` + 纪律末句 |
| 节数 | 5 | 4 | 4 |
| 标题钩子 | 行业/产业链 | **仅标题栏**领衔股 | 情绪阶段 + 龙头板数（**正文禁止同构**） |
| CPS 关键词 | 充电宝等 | 支架/键盘 | 咖啡/台灯 |

---

## Agent 改稿流程

1. 只改 evening 三篇时，**先读本文 + [researcher-voice.md](researcher-voice.md)**
2. 改 `wechat_mp_*_article.py` / `wechat_mp_market_polish.py` / 排版相关
3. `pytest tests/unit/test_wechat_mp_*.py -q`
4. `uv run python -m scripts.tools.wechat_mp_draft_batch --batch evening`（覆写三槽）
5. mp.weixin.qq.com 草稿箱：彩色开篇、CPS 中后段、免责 1 块、banner 在顶

**勿回退清单**

- 勿把 CPS 改回「结构判断 / 待验证事项 / 明日计划」分节后插入
- 勿恢复文末双免责或 LLM 内联免责段
- 勿默认开启阅读原文外链
- 勿去掉彩色开篇 HTML
- 勿用 **「往下看」「→」** 做段间导流（改用 **`·` + 对比/验证**）
- 勿把 **标题「领衔…」句式**写进 top5 正文
- 勿把 **标题「情绪XX怎么玩？XX板还在榜」**写进 dragons 正文（`strip_dragon_title_echo`）

---

## 相关代码索引

| 能力 | 模块 |
|------|------|
| evening 批次 | `wechat_mp_draft_batch.py` → `SCHEDULE_BATCHES["evening"]` |
| 成稿 | `wechat_mp_content.build_article` |
| 段长/序号 | `wechat_mp_readability` · `finalize_public_body_text` |
| 完读钩子共享 | `wechat_mp_read_hooks.py`（`BRIDGE_MARK = "· "`） |
| sector 钩子 | `wechat_mp_sector_polish.finalize_sector_body` |
| top5 钩子 | `wechat_mp_top5_polish.finalize_top5_body` · `strip_top5_title_echo` |
| dragons 钩子 | `wechat_mp_dragons_polish.finalize_dragons_body` · `strip_dragon_title_echo` |
| market 钩子 | `wechat_mp_market_polish.finalize_market_body`（手动稿） |
| news 钩子 | `wechat_mp_news_polish.finalize_news_body`（手动稿） |
| HTML 开篇样式 | `wechat_mp_rich_html.opening_lede_paragraph_style` |
| CPS 2/3 | `wechat_mp_product.inject_cpsad_at_body_ratio` |
| 定时 | `stock-ai/docs/WECHAT_MP_SCHEDULING.md` |
| env | `WECHAT_MP_READ_HOOKS` · `WECHAT_MP_PARA_MAX_CHARS` · `WECHAT_MP_TOP5_READ_HOOKS` 等 |

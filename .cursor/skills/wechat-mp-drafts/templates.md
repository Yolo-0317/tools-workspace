# 日更五槽草稿模板（现行好稿参照）

> 导航 [INDEX.md](INDEX.md) · 不含 `temp`（见 `wechat_mp_temp_article.py`）。

**晚间三篇**（`sector` + `top5` + `dragons`）：**不要在本文件改结构** → 只读 **[evening-trilogy-templates.md](evening-trilogy-templates.md)**。

本文件只管 **`market` / `news` / `workspace`** 及五槽共用原则；改 prompt 勿回退旧腔。

## 总原则（五篇共用）

| 项 | 好稿样子 | 代码 |
|----|----------|------|
| 研究员口吻 | 正文像收盘备忘录：数字→机制→映射→验证；见 [researcher-voice.md](researcher-voice.md) | `RESEARCHER_VOICE_RULE` |
| 品牌头 | 顶栏 banner + 青框 slogan，框底无留白 | `wechat_mp_masthead.py` |
| 彩色开篇 | 晚间三篇：market 在 `盘面速览` 前；top5/dragons 在首节首段；17px 居中 `#1a5276` | `opening_lede_paragraph_style` · [evening-trilogy-templates.md](evening-trilogy-templates.md) |
| 分节 | `> 标题` 一行，渲染为居中 17px `#1a5276` | `ensure_blockquote_sections` |
| 序号 | **禁止**「一、二、三」；LLM 若写会自动 demote | `demote_numbered_section_lines` |
| 插图 | 第一节前不插图；中段图 max-height 200px；须 A股/科技/AI/交易屏 | `inject_*_figures` + `FIGURE_DOMAIN_TAGS` |
| 返佣 CPS | 正文约 **2/3** 处（非固定分节末） | `inject_cpsad_at_body_ratio` |
| 结尾 | 行情稿投资免责 **1 处**；技术稿工程说明；正文内 LLM 免责剥离 | `strip_inline_disclaimer_blocks` + `disclaimer_html` |
| **段长** | 单段约 ≤120 字（半屏）；成稿经 `polish_mobile_readability` | `WECHAT_MP_PARA_MAX_CHARS` |
| **序号** | `1. 2. 3.` 一行一项；Top5 四字段各占一行 | `wechat_mp_readability` |
| **完读钩子** | 节间/股间用 **`·` + 对比/验证**；禁「往下看」「→」 | `finalize_*_body` · [evening-trilogy-templates.md](evening-trilogy-templates.md) |
| emoji | 全无 | 硬约束 |

---

## 1. `market` — A 股评论（分时段）

**定位**：盘面 + 外围 + 结构，**不含**要闻列表。按 `edition` 发稿：**pre 盘前 / midday 午间 / close 盘后**。

**标题轮换表（各 20 条模板）**

完整列表见：

```bash
cd stock-ai
uv run python -m scripts.tools.wechat_mp_market_titles
uv run python -m scripts.tools.wechat_mp_market_titles --edition close --tags 创业板+半导体
```

占位符：`{wd}` 周几；`{tags}` 当日钩子（从正文自动提取，如 `油价+半导体`）。

**盘前 pre（节选）**

```
{wd}盘前｜{tags}，开局盯什么？
集合竞价前：{tags}定不调？
隔夜三件：{tags}怎么映射？
{wd}9:25前｜{tags}怎么接？
盘前速览：{tags}牵哪线？
…共 20 条，见 wechat_mp_market_titles.py
```

**午间 midday（节选）**

```
{wd}午间｜{tags}，午后怎么走？
涨指数不涨股？{tags}怎么读
上午主线：{tags}能延续吗？
双创强、个股弱？{tags}？
午后盯什么：{tags}？
…共 20 条
```

**盘后 close（节选）**

```
收盘复盘：{tags}牵动哪些线？
指数涨、个股跌？{tags}怎么接
今日收盘三条线：{tags}
涨少跌多？{tags}怎么读
收市结论：{tags}先看哪？
…共 20 条
```

**轮换规则**：按日期 + edition 偏移起序；避开近 7 日同 edition 已用标题；与 news 标题 `_titles_too_similar` 去重。

**现行示例**

- 盘前：`周三开盘前｜A50偏弱+A50期货先看哪条？`
- 午间：`半日结构：上午主线+半日结构怎么接？`
- 盘后：`收盘复盘：油价+半导体牵动哪些线？`

**正文骨架**（晚间 close 详见 [evening-trilogy-templates.md](evening-trilogy-templates.md)）

```
{开篇 2 句：彩色段，在 > 盘面速览 之前}

> 盘面速览
（指数点位、涨跌家数、成交额——数字开头，2～3 短段）

[[fig:…]]   ← 仅在第一节之后

> 外围与资金
（美股/恒指/油价/汇率，与 A 股传导一句）

> 结构判断
（主线、背离、机构 vs 广度；给结构不给买卖）
```

**研究员好句（close 示例）**

```
沪指收涨 0.22%，上涨家数仍明显少于下跌家数，指数与广度背离。
我们认为，当前矛盾在于存量博弈下的资金再分配：存储器涨价链条映射至半导体存储环节，尚待明日涨停家数验证情绪是否过热。
向后看，需跟踪恒生科技能否守住支撑、WTI 能否站稳 90 美元一线。
```

**禁词**：标题党（震惊/100倍）；勿与 news 同日雷同。**盘后勿写「普跌/暴涨」除非盘面属实**；少用「指数虚涨、个股踩踏」，改用「指数与广度背离」。

---

## 2. `news` — 要闻精选 + 走心 AI 点评

**定位**：近 36h Top10 快讯（互动热度排序），每条 **摘要 + AI点评**。

**标题模板**

```
今晚10条必读？{快讯钩子}与板块映射
{周几}10条快讯｜{钩子}逐条拆
7×24精选10条：{钩子}有何影响？
```

**与 market 去重**：钩子来自快讯列表，不得与当日 market 标题雷同（`_titles_too_similar`）。

**现行示例**

- 标题：`今晚10条必读？内塔尼亚胡与板块映射`

**单条格式（精华）**

```
1. [利好/利空/中性] {小标题 8–22 字，含热股名}
  {摘要 230–250 字：发生了什么、主体、与 A 股关联}
  AI点评：{120–220 字，像给同事发微信}
```

**去重（2026-06-18 · 禁止 10 条雷同）**

| 现象 | 根因 | 处理 |
|------|------|------|
| 10 条摘要尾段完全相同 | 热股无专属快讯 → 全 `synthetic`；`_SUMMARY_PAD` 统一垫到 230 字 | 代码：`wechat_mp_news_article._summary_pad_sentences` 按榜位/股名轮换垫句 |
| 多条 AI 点评一字不差 | fallback 仅 2 套通用话术 | 代码：`_hot_stock_fallback_comment` 按 code/rank/chg 分叉 |
| 小标题与摘要首句重复 | fallback 把 `title` 再拼进摘要 | 合成稿直接用 `item.summary`，不重复标题 |
| 整批无真实快讯 | OpenCLI 7×24 池空或匹配失败 | 推稿前看 stderr `⚠️ news 快讯摘要重复`；修 OpenCLI / `fetch_weekend_kuaixun_pool` |

**质检**：`generate_enriched_news_copy` 结束若 ≥3 条摘要或点评完全相同 → stderr 告警；人工发表前扫一眼第 1、5、10 条是否同构。

**AI 点评好句范例（从现行稿摘）**

- 地缘：`明早先看布伦特开盘是否跳涨，油服龙头如杰瑞股份、中油工程竞价放量程度决定当日弹性。`
- 黄金：`沪金夜盘率先反应，明日竞价看开采板块是否被砸开缺口。`
- 监管：`明日北向资金若持续流出……券商股如东方财富、中信证券可能跟随港股金融股走弱。`

**AI 点评禁套话**（`_AI_COMMENT_BANNED`，出现即删）

- 情绪定价、结构分化、主题脉冲、向后看建议跟踪、若与当前主线共振、结合成交额与梯队…

**摘要侧仍须 humanize**：部分 fallback 摘要若仍带旧垫句，改 prompt 或 `_SUMMARY_PAD` 时一并清理。

---

## 3. `top5` — 收盘选股结构拆解

**定位**：多策略合并 Top5，**客观结构分析**，非荐股、非打分操作建议。  
**金标准骨架/钩子**：见 [evening-trilogy-templates.md](evening-trilogy-templates.md)「完读钩子 · 金标准」。

**标题模板**（**仅标题栏**；正文勿复述）

```
{龙头名}领衔{n}只！收盘信号出炉，明日盯啥？
刚筛出{n}只｜{A}、{B}，明天怎么走？
{周几}盘后值得看：{名}等{n}只技术信号
```

**现行示例**

- 标题：`新安股份领衔5只！收盘信号出炉，明日盯啥？`

**正文骨架（要点）**

```
> 筛选名单
{彩色开篇：数据日 + 主线 + 阅读路径；勿写标题句式}
{名单→逐只拆 桥接一句}

> 个股拆解
1. {名}（{代码}）
逻辑归属：…
量价结构：…
技术位置：…
待核实：…

· 和上一只比，谁更贴主线，差别往往在量价。

2. …

> 组合特征
{… + 引向待验证的末句}

> 待验证事项
{2～3 条 + 若…则…验证末句}
```

**禁**：综合得分、操作建议、持仓计划；正文「领衔…收盘信号出炉…」；`strip_top5_title_echo` + `sanitize_top5_analysis_text`。

---

## 4. `dragons` — 情绪 + 龙头博弈

**定位**：情绪周期指标 + 龙头池（正文深写 ≤2 只），游资复盘腔，**非**内部执行卡。  
**金标准**：见 [evening-trilogy-templates.md](evening-trilogy-templates.md) § dragons。

**标题模板**

```
{phase_hint}？{主线}+{龙头名}{n}板还在榜
{周几}游资轨｜{主线}{龙头}{n}板，一文读懂
情绪{phase}怎么玩？{lead}{n}板还在榜
```

**现行示例**

- 标题：`情绪冰点怎么玩？郑州煤电3板还在榜`

**正文骨架（含 · 过渡）**

```
> 情绪与盘面
{彩色开篇 + 炸板率/涨跌比数字}

· 龙头拆解才是情绪真正的试金石。

> 龙头拆解
1. …
· 这只和上一只比，谁在接力、谁在掉队，一眼能分。
2. …

· 空间板断了以后，梯队怎么排，比单看高度更重要。

> 主线与梯队
· 明日盯什么信号，比今晚的口号更值得写进备忘录。

> 明日计划与纪律
{第三人称 + 若次日炸板率抬升…退潮才算确认}
```

**硬性禁止（正文、标题、摘要均不得出现）**

- `6/7`、`7/7`、`X/7`、`系统筛选用分`、`龙头确认`、`内部认可`、`系统认可`
- `checklist_pass` 仅脚本内部用，不进 LLM 素材与成稿（`sanitize_dragons_public_text` 剥离）

**好句范例**

- `退潮信号明确……炸板率高达40.59%，亏钱效应已经开始蔓延。`
- `这种结构不能急着接，要等缩量企稳。`
- `情绪窗口期，这种3板跟风票，一旦龙头断板，它就是最先被核的那一个。`

---

## 5. `workspace` — 工具工作区技术分享

**定位**：静态手写，**不调**行情 LLM，**不过** `humanize_mp_text`。

**标题模板（固定池）**

```
脚本越写越散？后来全收进了一个仓库
收盘推送和证书续签，原来在同一套 git 里？
```

**现行示例**

- 标题：`脚本越写越散？后来全收进了一个仓库`
- 开头：`收盘后大约一刻钟，固定会跑完一串事：日线进 MySQL……宏观、Top5、龙头、技术分享四条草稿各覆写一遍。`

**分块**

```
> 它是什么
> 里面分几块
> 和数据打交道
> 公众号草稿
> 微信和看板
```

**禁**：`tools-workspace` 目录名当品牌；系列副标题行；`月X日` 抬头。对外名：**工具工作区**。

---

## 改稿对照清单

改某一 kind 的 prompt 或 sanitize 后：

1. `uv run python -m scripts.tools.wechat_mp_draft --kind {kind} --dry-run`
2. 对照本文 **骨架 + 好句 + 禁词**
3. `pytest tests/unit/test_wechat_mp_*.py -q`
4. 推草稿 → mp.weixin.qq.com 看居中标题、插图、AI 点评行距

# 牛马也智能 · 微信公众号草稿 — 参考

**导航** [INDEX.md](INDEX.md) · 账号 [brand.md](brand.md) · 运营 [operations-sop.md](operations-sop.md)。  
写作 [writing-guide.md](writing-guide.md) · 晚间 [evening-trilogy-templates.md](evening-trilogy-templates.md) · 其他槽 [templates.md](templates.md) · 映射 [rules-implemented.md](rules-implemented.md)。

## 外部参考（非本仓库维护）

| 来源 | 用途 |
|------|------|
| [Qson8/wechat-writing-skill](https://github.com/Qson8/wechat-writing-skill) | 去 AI 味对照表、标题/结构模板（MIT，受众为独立开发者） |
| [微信公众号爆文方法论](https://xiangyugongzuoliu.com/wechat-article-creation-strategies-core-methodology/) | 标题 15–28 字、三三排版 |
| [刘润团队 2025 写作法则](https://news.qq.com/rain/a/20250801A055SU00) | 跳读、短段、标题即有收获 |
| [Cursor Skills 文档](https://cursor.com/docs/context/skills) | Skill 目录与 `paths` frontmatter |

## 槽位术语

| 概念 | kinds | 说明 |
|------|-------|------|
| **`--kind all`** | `sector`, `top5`, `dragons`, `workspace` | `DAILY_DRAFT_KINDS` |
| **手动槽** | `market`, `news` | 仅 `wechat_mp_draft --kind market\|news` |
| **临时槽** | `temp` | 变体在 `wechat_mp_temp_article.py`；`all` 不含 |
| **定时批次** | 见 `WECHAT_MP_SCHEDULING.md` | 交易日 `sector`+`top5`+`dragons`；休市 `news`（周日/节假日）；周六跳过 |

持久化：`data/wechat_mp_draft_slots.json`（日更五槽各一条 `media_id`，`temp` 同文件）。

## 模块文件表

| 文件 | 职责 |
|------|------|
| `scripts/tools/wechat_mp_draft.py` | CLI 入口（日更五槽 + `temp`） |
| `scripts/tools/wechat_mp_draft_batch.py` | 每日 19:00 `evening` / `weekend` |
| `scripts/tools/wechat_mp_draft_notify.py` | 批次成功 → 微信 + 飞书 |
| `scripts/tools/wechat_mp_draft_slots.py` | 日更五槽 `media_id` 持久化、upsert |
| `scripts/tools/wechat_mp_prune_drafts.py` | 清理重复草稿 |
| `scripts/tools/wechat_mp_masthead.py` | banner + slogan 品牌头 |
| `scripts/tools/wechat_mp_monetization.py` | 流量主：文末互动问句、留言开关；**不**留广告位标记 |
| `scripts/tools/wechat_mp_layout.py` | 首节间距、news 行距 |
| `scripts/tools/wechat_mp_figure_pool.py` | 插图池、日 dedup、`FIGURE_DOMAIN_TAGS` |
| `scripts/tools/wechat_mp_content.py` | 标题/摘要、`DISCLAIMER`/`TECH_DISCLAIMER`、`disclaimer_for_kind` |
| `scripts/tools/wechat_mp_client.py` | Token、草稿 CRUD、素材封面、`text_to_html` |
| `scripts/tools/wechat_mp_rich_html.py` | 着色、**居中**分节标题、AI 点评行 |
| `scripts/tools/wechat_mp_public.py` | `PUBLIC_MP_WRITER_RULE`、公开稿清洗 |
| `scripts/tools/wechat_mp_seo.py` | 摘要 SEO、`attach_publish_hints` |
| `scripts/tools/wechat_mp_prose.py` | `humanize_mp_text`、`ensure_blockquote_sections` |
| `scripts/tools/wechat_mp_figures.py` | `inject_market_figures` / `inject_news_figures` |
| `scripts/tools/wechat_mp_market_article.py` | A 股盘面正文（无要闻） |
| `scripts/tools/wechat_mp_market_edition.py` | `pre` / `midday` / `close` 时段标签 |
| `scripts/tools/wechat_mp_market_titles.py` | 盘面标题模板池、按日轮换（CLI 可打印） |
| `scripts/tools/wechat_mp_market_polish.py` | `finalize_market_body`、标题情绪对齐 |
| `scripts/tools/wechat_mp_news_article.py` | 要闻 Top10 + 逐条 AI 点评 |
| `scripts/tools/wechat_mp_top5_article.py` | Top5 交易员体例 + prompt |
| `scripts/tools/wechat_mp_dragons_article.py` | 龙头四节稿 |
| `scripts/tools/wechat_mp_workspace_article.py` | 工具工作区静态稿、`PROJECT_NAME` |
| `scripts/tools/wechat_mp_temp_article.py` | 临时槽变体注册（如 `lark_cli`） |
| `scripts/tools/wechat_mp_sop_fast.py` | 东财快采（公众号隔离） |
| `scripts/tools/wechat_mp_check_whitelist.py` | 公众平台 IP 白名单检查 |
| `scripts/tools/wechat_mp_eval.py` | 五维评分 + 合规 + AI 味 0–100 |
| `scripts/tools/wechat_mp_short_drama.py` | 长文短剧：`DramaSelect`、缓存、过滤排序、归因票据、`short-play` 组件与回读门禁 |
| `scripts/tools/wechat_mp_product.py` | 独立 `commerce` 普通返佣商品；长文禁止调用 |
| `data/wechat_mp_draft_slots.json` | 槽位状态（勿手删除非重建） |
| `data/wechat_mp_footer_product.json` | 返佣选品缓存（`daihuo` / `footer.product_key`） |
| `data/wechat_mp_short_drama_pool.json` | 短剧列表缓存，默认六小时，生成文件不提交 |
| `data/wechat_mp_short_drama_attribution.json` | 已验证短剧归因数据，含票据，生成文件不提交 |
| `data/wechat_mp_short_drama_usage.json` | 七天轮换使用记录，生成文件不提交 |

## 环境变量（摘自 `.env.example`）

```bash
WECHAT_MP_APPID=
WECHAT_MP_SECRET=
WECHAT_MP_WHITELIST_IP=          # 公众平台白名单
WECHAT_MP_PUBLIC_IP=             # 可选，跳过 ipify
WECHAT_MP_AUTHOR=R2D2
# WECHAT_MP_READ_SOURCE_URL=1     # 默认 0：不写「阅读原文」；为 1 时再配下面 URL
# WECHAT_MP_SOURCE_URL=           # 看板/要闻外链（仅 READ_SOURCE_URL=1 时写入草稿）
WECHAT_MP_NEED_OPEN_COMMENT=1    # 1=打开留言（默认开，促互动）
WECHAT_MP_ONLY_FANS_COMMENT=0    # 1=仅粉丝可留言
WECHAT_MP_MONETIZE=1             # 0=关闭文末问句等流量优化
WECHAT_MP_ENGAGEMENT_HOOK=1      # 0=不加文末互动问句
# WECHAT_MP_AD_CHECKPOINT=1      # 默认关；正文 · · · 标记（一般不需要，广告微信自动插）
# 原创声明、话题 #、合集：draft API 不支持 → mp.weixin.qq.com 发布/发布后手动
WECHAT_MP_AUTO_PUBLISH=0

# 成稿 LLM（与 SOP 解耦）：stock-ai/.env → LLM_BACKEND=cursor + agent login
# 东财 SOP 并发仍用 SOP_LLM_BACKEND=deepseek + DEEPSEEK_API_KEY（见 docs/DEEPSEEK_USAGE.md）

# 晚间封面留档见 stock-ai/assets/wechat_mp/COVER_THUMBS.md
# top5/dragons 默认上传 repo 亮色 *-dual.jpg（WECHAT_MP_KIND_THUMB_FROM_ASSETS=1）
WECHAT_MP_THUMB_NAME_SECTOR=封面-牛马品牌-双封面
WECHAT_MP_THUMB_NAME_MARKET=封面-交易所屏-双封面
WECHAT_MP_THUMB_NAME_NEWS=封面-显示器走势-双封面
WECHAT_MP_THUMB_NAME_TOP5=封面-财经亮屏-双封面
WECHAT_MP_THUMB_NAME_DRAGONS=封面-多屏亮行情-双封面
WECHAT_MP_THUMB_NAME_WORKSPACE=封面-数据大屏-双封面

WECHAT_MP_NEWS_HOURS=36
WECHAT_MP_NEWS_TOP=10
WECHAT_MP_NEWS_AI_MIN=120          # AI 点评下限（默认 120，非 190）
WECHAT_MP_NEWS_AI_MAX=220
WECHAT_MP_NEWS_SUMMARY_MIN=230
WECHAT_MP_NEWS_SUMMARY_MAX=250
WECHAT_MP_FIGURE_MAX_HEIGHT=200
WECHAT_MP_NEWS_SKIP_ENGAGEMENT=0   # 1=跳过 OpenCLI 抓评论数（仅测排版）
WECHAT_MP_SECTION_STYLE=compact    # compact=居中节标题；card=旧深色引用块
WECHAT_MP_LAYOUT=pulse             # pulse|brief|chapter|report
WECHAT_MP_RICH_HTML=1

# 长文短剧推广；探针预览和归因确认前必须保持 0
WECHAT_MP_SHORT_DRAMA=0
WECHAT_MP_DRAMA_KOL_ID=                 # 仅写本地 .env，不提交
WECHAT_MP_DRAMA_CACHE_TTL_HOURS=6
WECHAT_MP_DRAMA_MIN_VALID_DAYS=7
WECHAT_MP_DRAMA_REPEAT_DAYS=7

# 普通返佣商品仅供独立 commerce 稿
WECHAT_MP_FOOTER_PRODUCT=0
WECHAT_MP_DAIHUO_UIN=                   # Select 请求 uin（mp 编辑器 Network 复制）
WECHAT_MP_FOOTER_PRODUCT_AUTO_PICK=1
WECHAT_MP_FOOTER_PRODUCT_ID=            # 固定商品 id；auto-pick 开启时会被覆盖
WECHAT_MP_FOOTER_PICK_KEYWORD=          # 覆盖全部槽位搜索词（空格多词）
WECHAT_MP_FOOTER_PICK_KEYWORD_DEFAULT=充电宝
WECHAT_MP_FOOTER_PRODUCT_CARD_TYPE=1    # getcardinfo 探测用；CPS 正文不依赖 product_key
WECHAT_MP_FOOTER_PRODUCT_KINDS=         # commerce 垂直过滤；不得填长文 kind
```

### 短剧池与归因诊断

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/python -m scripts.tools.wechat_mp_short_drama --refresh --limit 40
PYTHONPATH=. .venv/bin/python -m scripts.tools.wechat_mp_short_drama --capture-sample-title "短剧组件测试-勿发"
PYTHONPATH=. .venv/bin/python -m scripts.tools.wechat_mp_short_drama --probe-component --drama-id 660409
```

`DramaSelect` 只提供剧目和计划列表，不等于可直接投放。只有 `drama_id`、`plan_id`、来源应用、播放应用和 `wxTicket` 与人工插卡样本完全匹配的候选才可生成组件。不得把其他剧目的票据复用到新剧，也不得访问点击跟踪 URL 伪造票据。

### Commerce 选品关键词（`PICK_KEYWORDS_BY_VERTICAL`）

| vertical | Select 搜索词（空格分隔，合并去重后按策略选择） |
|------|------|
| `tech` | 机械键盘 显示器 充电宝 路由器 |
| `home` | 收纳 置物架 厨房收纳 沥水篮 挂钩 |
| `mother` | 母婴 绘本 儿童 奶粉 |
| `outdoor` | 露营 防晒 户外 登山 |
| `office` | 工学椅 台灯 支架 鼠标垫 |

CLI：

```bash
uv run python -m scripts.tools.wechat_mp_product --search 机械键盘
uv run python -m scripts.tools.wechat_mp_product --pick --pick-keyword 充电宝
uv run python -m scripts.tools.wechat_mp_product --extract
uv run python -m scripts.tools.wechat_mp_product --verify <product_id>
```

## API 调用链（实现级）

```
get_access_token()
  → GET cgi-bin/token

pick_thumb_for_draft_kind(kind)
  → batchget_material / 缓存 thumb

build_article(kind) → dict(title, author, digest, content HTML)
  → CTA 与 SEO 重建完成
  → attach_short_drama（若 WECHAT_MP_SHORT_DRAMA=1）
      → DramaSelect 缓存 → 有效候选 → 同名去重 → 50/30/20 排序 → 七天轮换
      → 精确加载已验证 attribution → 正文约 2/3 插入 short-play
  → assert_longform_promotion_safe（写封面前）

upsert_draft_article:
  有 slots[kind].media_id → draft_update
  否则 → draft_add → 写入 slots json

verify_saved_short_drama(media_id)
  → 回读草稿 → 校验 short-play 数量与 drama_id
  → 通过后才记录轮换并允许后续发表

attach_cover_crop_fields(article, thumb_media_id)
  → 按素材宽高算 crop 字段（竖图→公众号头图比例）
```

错误码常见：`40001` token 失效（刷新 token）；`40164` IP；`45009` 接口限额。

## 工作区技术稿专用约定

- `PROJECT_NAME = "工具工作区"`，`SERIES_TAG` 仅用于代码标识，**不进**正文。
- 开头：用「收盘后一刻钟会跑完什么」切入，不用文件夹名。
- 分块：`> 它是什么`、`> 里面分几块` 等；正文无 `月X日`、无 `工具工作区技术分享 · 总览` 抬头。
- `build_workspace_article` 后处理链：

```python
strip_markdown_for_wechat → normalize_wechat_spacing → sanitize_public_mp_text
# 不经过 humanize_mp_text
```

## 行情三篇 LLM 提示要点

- System 注入：公开稿、非持仓、非荐股、非聊天机器人腔。
- **宏观**：三节 `> 盘面速览` / `> 外围与资金` / `> 结构判断`；标题永远收盘后视角；禁止「研究员札记 |」抬头。
- **Top5**：每只四行（逻辑归属/量价结构/技术位置/待核实），禁分数与操作建议；`sanitize_top5_analysis_text` 后处理。
- **龙头**：四节 + 每只四行（地位/量价资金/博弈/待核实）；**禁止** X/7 与内部认可；`checklist_pass` 不进 prompt。
- **要闻**：每条摘要 + AI 点评；AI 走心 prompt + `_AI_COMMENT_BANNED`；禁 `_AI_PAD` 垫句。
- 成稿后：`strip_journal_title_lines` 去掉历史抬头行；龙头/Top5/news 经 `sanitize_*_public_text`。

## 历史踩坑（对话沉淀）

1. **UTF-8 / HTML**：早期乱码 → 统一 `encoding=utf-8`，HTML 必须 `_escape_html` 再插标签。
2. **封面**：本地文件上传易尺寸不合 → 改素材库竖图 + 按 kind 匹配 + crop 字段。
3. **草稿爆炸**：每次 `draft_add` → 槽位 json + update 优先 + `prune_obsolete_drafts`。
4. **Top5 只读 combined 4 条** → 改多策略 merge + 按总分重选。
5. **快采拖慢 SOP** → 独立 `wechat_mp_sop_fast` 缓存目录。
6. **工作区走 humanize** → 语气更「模板」→ 工作区改静态 + 轻清洗。
7. **项目命名**：避免生僻绰号（如「盘后坞」）；统一「工具工作区」。
8. **标题随机到怪句** → 工作区标题池固定 4 条吸睛句，勿塞目录名。
9. **分块标题丑** → 引用块统一样式，`一、` 与 `>` 均识别。
10. **订阅号审阅**：脚本只写草稿箱，发布前人工在 mp.weixin.qq.com 看图文版式。
11. **market 标题「盘中复盘」**：按推送时刻出盘中/午间 → 已强制收盘/盘后（`_sanitize_market_title`）。
12. **要闻 AI 模板腔**：190 字垫句 + 情绪定价套话 → 120–220 + `_AI_COMMENT_BANNED` + 主题化 fallback。
13. **龙头 6/7 外泄**：曾改写为「系统筛选用分」→ 用户要求正文 **完全不出现** `/7`。
14. **插图**：首节叠图、图题、过高 → 首节不插图、无 caption、max-height 200px、领域 tags。
15. **market/news 标题撞车**：`_titles_too_similar` + 钩子来源分离（盘面 vs 快讯）。
16. **原创/话题标签**：`draft/add` 无 `is_original` / `#话题` 字段；脚本只写正文，**发布须在后台勾原创、发布后加 `#`**（见 writing-guide 发布前总检）。
17. **流量主广告位**：正文 `· · ·` 标记已取消；**微信自动插广告**，脚本保留完读 prompt + 文末问句 + 开留言。
18. **普通返佣 CPS 仅限 commerce**：`getcardinfo` + `footer product_key` 对部分 JD 返佣无效；正文商品卡使用 `<mp-common-cpsad data-pid="{warehouse}_{product_id}">`。该机制不得进入长文。
19. **commerce auto-pick**：`attach_footer_product` 仅接受 commerce 垂直，按 Select 结果选品；`cps_data_pid` 仅在缓存 `product_id` 匹配时用 `sku_id`。
20. **短剧列表不等于归因卡**：`DramaSelect` 没有可复用的 `wxTicket`；未捕获对应建卡归因时必须失败关闭，不得借用其他短剧票据或回退普通商品。

详见 [rules-implemented.md](rules-implemented.md)。

## launchd（Mac 本机）

`bash scripts/install-wechat-mp-launchd.sh` 安装：

| Label | 时间 | 命令 |
|-------|------|------|
| `com.user.wechat-mp-whitelist-check` | 每小时 | IP 白名单变更告警 |
| `com.user.wechat-mp-draft-scheduled` | 每日 19:00 | 交易日 `evening` 三篇 / 休市日 `weekend` 要闻 |

入口：`bash scripts/wechat_mp_draft_scheduled.sh`（无参数按日历）或 `wechat_mp_draft_batch --batch evening|weekend`。  
推送成功 → `wechat_mp_draft_notify`（微信 wechat-acp + 飞书）。安装时卸载旧 `morning`/`noon`/`evening`/`daily-draft`。

完整调度说明：`stock-ai/docs/WECHAT_MP_SCHEDULING.md`。

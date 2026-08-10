# 现行规则与代码映射（2026-06 沉淀）

导航 [INDEX.md](INDEX.md) · 晚间金标准 [evening-trilogy-templates.md](evening-trilogy-templates.md)

本文件记录 **用户审阅反馈 → 代码 enforcement → skill 写法** 的对应关系。Agent 改稿时先查此表，避免口头规则与实现脱节。

## 版式与品牌

| 规则 | 实现 | 测试 |
|------|------|------|
| 每篇顶栏 banner + slogan，框底无留白 | `wechat_mp_masthead.py`（img `line-height:0`） | `test_wechat_mp_masthead.py` |
| 追加 #话题 重建 HTML 不得丢 banner | `masthead` 读 upload 缓存；`sync_article_content_from_body` 与 shell 同上传策略 | `test_masthead_uses_banner_cache_*` · `test_sync_article_content_keeps_banner_img` |
| 分节标题居中 17px，禁止「一、二、三」 | `demote_numbered_section_lines` → `blockquote_title_html` | `test_wechat_mp_prose.py` |
| 第一节前不插图；图 max-height 200px | `wechat_mp_figures.py`（`skip_first_section`） | figures 相关单测 |
| 插图须 A股/科技/AI/交易屏 | `FIGURE_DOMAIN_TAGS` + `figure_matches_domain` | `test_wechat_mp_figure_pool.py` |
| 无图题 caption（用户要求去掉） | `inject_*` 传空 caption 或 manifest 无 title | — |
| `[[fig:]]` 须独占段落 | `split_wechat_body_blocks` | `test_wechat_mp_rich_html.py` |
| hotspot 优先可追溯现场实拍，微博/百度仅作发现入口 | `wechat_mp_discussion_research.figure_search_queries` + `wechat_mp_discussion_figures._verified_figure_source` | `test_wechat_mp_discussion_figures.py` |
| 明确禁止转载或普通用户微博图不自动进正式草稿 | `_page_restricts_reuse` + 微博账号身份提示校验 | `test_restricted_page_is_skipped_before_image_download` · `test_ordinary_weibo_page_is_not_automatically_verified` |
| 实拍图保存具体来源图注与追溯元数据 | `figure_sources.json` + `_figure_caption` | `test_downloaded_figure_persists_traceable_source_metadata` |
| 强制换图绕过 Codex ready，普通续跑仍不重复联网 | `ensure_discussion_figures` force-aware ready 分支 | `test_force_refetch_bypasses_codex_ready_marker` · `test_codex_ready_marker_skips_repeated_report_search` |

## 专业研究员口吻

| 规则 | 实现 | 测试 |
|------|------|------|
| 行情四槽共用口吻块 | `RESEARCHER_VOICE_RULE` in `wechat_mp_public.py`（含宏观政策 + 主观判断） | — |
| 注入 LLM prompt | `wechat_mp_market_article` / `top5` / `dragons` / `news` | — |
| Skill 细则 | `researcher-voice.md` · `wechat-mp-writing/depth-and-opinion.md` | — |

## 影视深度（立意 + 见解）

| 规则 | 实现 | 测试 |
|------|------|------|
| TV_DEPTH_RULE | `wechat_mp_tv_review_template.py` | — |
| 注入影视 LLM | `wechat_mp_tv_review_article.generate_tv_review_body` | — |
| Skill | `.cursor/skills/wechat-mp-writing/depth-and-opinion.md` | — |

## 摘要 SEO 与 #话题

| 规则 | 实现 | 测试 |
|------|------|------|
| 摘要嵌入稿型核心词 | `wechat_mp_seo.enrich_digest` | `test_wechat_mp_seo.py` |
| 推稿后打印推荐 #话题 | `attach_publish_hints` + 通知 `hashtags` | `test_wechat_mp_draft_notify.py` |
| 用户操作说明 | `stock-ai/docs/wechat_mp_seo_topics.md` | — |

## 标题与摘要

| 规则 | 实现 | 测试 |
|------|------|------|
| 标题 ≤32 字 | `_clip_wechat_title` | `test_wechat_mp_titles.py` |
| **market 按 edition 标题池** | `wechat_mp_market_titles.py`（各 20 条 + 按日轮换） | `test_wechat_mp_market_titles.py` |
| **market 按 edition 标题** | `_market_title` + `_market_publish_label` | `test_market_title_by_edition` |
| market 钩子来自 **market 正文**，非快讯 | `_compress_market_tags` / `_extract_market_hook` | — |
| news 钩子来自 **快讯列表** | `_news_title` ← `wechat_mp_news_titles` | `test_wechat_mp_news_titles.py` |
| **news 拒榜位元叙述当事件** | `_short_event_hook` 拒 `人气榜/榜首`；禁 `背景下`；单股不凑 `甲与甲` | `test_hot_stock_news_title_rejects_rank_meta_as_event` · `test_hot_stock_news_title_single_lead_no_pair_echo` |
| **hotspot 标题不砍半截人名** | `_GEO_SECTION_MAP` · `_title_hook` 冒号取前半 · `A股` 后缀前加顿号 | `test_build_hotspot_title_geo_no_mid_name_cut` |
| **news 10 条去重** | `_summary_pad_sentences` · `_hot_stock_fallback_comment` · `_warn_duplicate_news_copy` | `test_synthetic_batch_summaries_not_identical` |
| **sector evening 去重** | `sector_evening_dedup_enabled` · `news_hot_exclude_codes` · `sector_hot_watch_top_n=0` | `test_wechat_mp_sector_evening_dedup.py` |
| **market 与 news 同日勿雷同** | `_titles_too_similar`；`--kind all` 传 `peer_market_title` | `test_market_news_titles_differ` |
| digest ≤128 字 | 各 `_digest` 函数截断 | — |

## 平台推荐安全（财产风险 / 不适合推荐）

| 规则 | 实现 | 测试 |
|------|------|------|
| 标题禁 `怎么玩` `还在榜` `领衔` `热股` `投资日记` | `wechat_mp_public.sanitize_public_title` + `_TITLE_RISK_INLINE_REPLACEMENTS` | `test_sanitize_public_title_strips_old_winners` |
| 标题禁 `A股必读` `A股周末必读` | `PLATFORM_PROPERTY_RISK_CHECKS` · 标题池已移除 | `test_check_platform_property_risk_bidu_title` · `test_sanitize_public_title_strips_bidu` |
| 标题+摘要+正文推前审计 | `audit_recommendation_safety` ← `wechat_mp_draft_batch` | `test_check_platform_property_risk_in_title` |
| LLM prompt 平台红线 | `PLATFORM_PROPERTY_RISK_RULE` in sector/dragons/top5/market | — |
| 正文 prepend 信息说明 | `strip_information_notices` → `render_article_content_html` 只 prepend 一次 | `test_information_notice_not_duplicated_on_re_render` |
| 说明行不参与平台风险替换 | `sanitize_platform_property_risk` 跳过 `_INFORMATION_NOTICE_LINE_RE` | 同上 |
| 免责用「复盘笔记」非「投资日记」 | `wechat_mp_content.DISCLAIMER` | `test_disclaimer_whitelist` |
| SEO 标题池负分 risky 句式 | `title_sousou_hook_score` | `test_title_sousou_hook_score_prefers_search_winners` |
| **勿**改小节 `> 明日计划与纪律` | 正文 `_PLATFORM_RISK` 不含 `明日计划` 替换 | `test_generate_without_llm` |
| 限推后渠道复盘 | 页面 `--daily-series` · [content-analytics-sop.md](content-analytics-sop.md)；**勿用 API** | — |

记忆：`project-memory.mdc` §2026-06-12 · §2026-06-14 · §2026-06-16 · `memory-python.mdc` §2026-06-12 · §2026-06-14 · §2026-06-16。

| 规则 | 实现 | 测试 |
|------|------|------|
| Top10 按互动筛选；正文不写评论/阅读数 | `pick_top_news_by_attention` | — |
| 每条：摘要 230–250 + AI 点评 **120–220** | `WECHAT_MP_NEWS_*` env；`generate_enriched_news_copy` | `test_wechat_mp_news_article.py` |
| AI 点评走心：点名板块/龙头/验证动作 | LLM prompt + `_infer_news_angle` | — |
| AI 禁套话 | `_AI_COMMENT_BANNED` + `_sanitize_ai_comment` | `test_sanitize_ai_comment_strips_banned_phrases` |
| 不用 `_AI_PAD` 通用垫句 | `_stretch_ai_comment` 按标题补实质 | `test_finalize_ai_does_not_pad_with_template_cliches` |
| 排版：摘要 + `AI点评：` 两行 | `reflow_news_article_body` | — |

## Top5

| 规则 | 实现 | 测试 |
|------|------|------|
| 禁分数、操作建议、持仓暗示 | `sanitize_top5_analysis_text` | `test_wechat_mp_top5_article.py` |
| 节名：筛选名单 / 个股拆解 / 组合特征 / 待验证事项 | `TOP5_SECTION_TITLES` + prompt | — |
| 每只：逻辑归属 / 量价结构 / 技术位置 / 待核实 | prompt 四行块 | — |
| **标题「领衔N只」勿进正文** | `_top5_title` 仅写字段 title；`strip_top5_title_echo`；变现 prompt 禁止复述 | `test_strip_top5_title_echo_removes_title_line` |
| **标题「情绪XX怎么玩？还在榜」勿进 dragons 正文** | `_dragon_title` 仅写字段 title；`strip_dragon_title_echo`；`build_dragons_article` + LLM 后处理 | `test_strip_dragon_title_echo_removes_title_line` |
| **段长 + 序号一行一项** | `finalize_public_body_text` → `polish_mobile_readability` | `test_wechat_mp_readability.py` |
| **完读钩子（逐只吊读）** | `finalize_top5_body` in `wechat_mp_top5_polish.py` | `test_wechat_mp_top5_polish.py` |
| **完读钩子（晚间全稿型）** | `wechat_mp_read_hooks` + `*_polish` per kind | `test_wechat_mp_read_hooks.py` |

## 龙头 `dragons`

| 规则 | 实现 | 测试 |
|------|------|------|
| **全文禁止 X/7、系统筛选用分** | 不进 prompt；`sanitize_dragons_public_text` 剥离 | `test_wechat_mp_dragons_article.py` |
| 禁龙头确认、内部认可、推荐买入 | `_DRAGON_CHECKLIST_BAD_RE` + `_DRAGON_SCORE_FRACTION_RE` | `test_sanitize_dragons_strips_internal_approval_wording` |
| SOP 缓存隔离 | `output/wechat_mp_dragon_sop/` | `test_sop_cache_isolated` |

## 宏观 `market`

| 规则 | 实现 | 测试 |
|------|------|------|
| 三节：盘面速览 / 外围与资金 / 结构判断 | `MARKET_SECTION_TITLES` | — |
| **成稿优化链** | `finalize_market_body` → `align_market_title_mood` | `test_wechat_mp_market_polish.py` |
| 结论开头 + 长段拆分 | `inject_market_opening_lede` / `split_long_paragraphs` | 同上 |
| 标题与盘面对齐 | `detect_market_mood` + `align_market_title_mood` | 同上 |
| 标题池 60 条 + 按日轮换 | `wechat_mp_market_titles.py` | `test_wechat_mp_market_titles.py` |
| 不含要闻列表 | `wechat_mp_market_article.py` | — |

## 工作区 `workspace` / 临时 `temp`

| 规则 | 实现 | 测试 |
|------|------|------|
| 静态正文，禁止 humanize | `build_workspace_article` / `build_temp_article` | `test_wechat_mp_workspace_article.py` · `test_wechat_mp_temp_article.py` |
| 对外名「工具工作区」 | `PROJECT_NAME` | — |
| **禁止投资免责** | `disclaimer_for_kind` → `TECH_DISCLAIMER`；正文勿手写「不构成投资建议」 | `test_temp_uses_engineering_disclaimer_not_investment` |
| 代码块 | `prepare_static_mp_body` + `text_to_html` 围栏 | `test_wechat_mp_code_fence.py` |
| 禁止 Agent/槽位话术 | `sanitize_tech_mp_meta` + `KIND_SLOGANS[temp]` 读者向 | `test_wechat_mp_tech_meta.py` |

## 合规（全 kind）

| 规则 | 实现 |
|------|------|
| 无持仓、执行卡、敏感工具 | `sanitize_public_mp_text` |
| 无荐股/买卖暗示 | `strip_investment_advice` + `PUBLIC_COMPLIANCE_CHECKS` |
| 推稿前扫描 | `wechat_mp_draft` → `check_public_compliance`（默认 strict） |
| 免责声明 | 行情 `DISCLAIMER`；技术 `TECH_DISCLAIMER`（`disclaimer_for_kind`） |

## 流量主与阅读量

| 规则 | 实现 |
|------|------|
| 广告 | **微信发布时自动插**（底部/文中）；正文**不留** `· · ·` 标记 |
| 完读 / 垂直词 | `monetization_prompt_block()`（稿型【阅读/完读/垂直词】三段）+ `wechat_mp_traffic_checklist`（垂直≥`WECHAT_MP_VERTICAL_WORDS_MIN`、开篇数字） |
| 持续优化 SOP | `stock-ai/docs/wechat_mp_traffic_optimization.md` · `traffic-optimization.md` |
| 文末互动问句 | `append_engagement_hook()` |
| 留言默认开 | `comment_settings()` → `need_open_comment=1`（env 可关） |
| 摘要 SEO 分 edition | `enrich_digest(..., edition=)` + `market_digest_core` |
| **阅读量清单** | `wechat_mp_traffic_checklist.py`；`eval --traffic` / `draft --dry-run` |
| **推稿质量门禁** | `wechat_mp_push_quality_gate.py`；`draft_batch --batch evening` 推稿前自动跑（总分≥75、AI味≤20）；见 [eval-gates.md](../wechat-mp-writing/eval-gates.md) |
| 原创 / 话题 `#` / 推荐 ♡ | **API 不支持** → mp.weixin.qq.com 发布/发布后手动 |
| **起号 / 入池 / 发表必勾** | 运营 SOP：[cold-start-playbook.md](../wechat-mp-growth-ops/cold-start-playbook.md) §四（原创·允许推荐·合集） |

## 与带货（简选小电）隔离

| 规则 | 实现 |
|------|------|
| 草稿槽位 | 财经 `wechat_mp_draft_slots.json` ≠ 带货 `wechat_mp_commerce_slots.json` |
| 素材库共用 | 同一 AppID 下带货会 `add_permanent_image(avatar.png)`；财经 `pick_thumb_for_draft_kind` **排除 avatar/简选** 且 **禁止「最新一张」回退** |
| news 默认封面 | `封面-显示器走势-双封面`（库内须有；勿用不存在的「财经屏」名） |
| **top5 / dragons 封面** | 本地 `cover-financial-screen-dual.jpg` / `cover-multi-screen-dual.jpg`；留档 `stock-ai/assets/wechat_mp/COVER_THUMBS.md`（2026-06-04 定稿） |
| 正文插图 | `resolve_inline_path` 仅 `assets/wechat_mp/inline/`；带货图在 `inline-commerce/home/` |

## 彩色开篇（晚间三篇）

| 规则 | 实现 | 测试 |
|------|------|------|
| market 文首 2 句 | `inject_market_opening_lede` → `finalize_market_body` | `test_wechat_mp_market_polish.py` |
| top5/dragons 首节首段 | `text_to_html(..., article_kind=)` + `_want_opening_lede` | `test_wechat_mp_rich_html.py` |
| 17px 居中主题色 | `opening_lede_paragraph_style` | 同上 |

金标准文档：[evening-trilogy-templates.md](evening-trilogy-templates.md)（2026-06-04：**·** 轻过渡完读钩子、段长≤120、序号一行一项、top5 标题不进正文）

## 文末返佣商品（CPS）

| 规则 | 实现 | 测试 |
|------|------|------|
| 正文约 **2/3** 处插 CPS | `cps_injection_index` → `inject_cpsad_at_body_ratio` → `inject_cpsad_for_kind` | `test_cps_at_two_thirds_not_opening` |
| 兜底（无块边界） | `inject_cpsad_before_disclaimer` | `test_wechat_mp_product.py` |
| 构建 HTML | `build_cpsad_html` | `test_attach_footer_product_injects_cpsad` |
| 每篇自动 Select 最高佣金 | `auto_pick_footer_product` ← `attach_footer_product`（`build_article` 末步） | `test_auto_pick_footer_product_updates_env` |
| 槽位关键词 | `PICK_KEYWORDS_BY_KIND` + `pick_keywords_for_kind` | `test_pick_keywords_for_kind_*` |
| 仅部分槽位挂商品 | `WECHAT_MP_FOOTER_PRODUCT_KINDS` | `test_attach_footer_product_respects_kind_filter` |
| 固定商品（关 auto-pick） | `WECHAT_MP_FOOTER_PRODUCT_AUTO_PICK=0` + `FOOTER_PRODUCT_ID` | — |
| CPS 用 `data-pid` 非 product_key | `cps_data_pid`；`getcardinfo` 仅辅助 | — |
| 选品 API | `POST daihuo.qq.com/.../Select`（需 `WECHAT_MP_DAIHUO_UIN`，无需 Cookie） | `test_search_daihuo_requires_uin` |
| 缓存 | `data/wechat_mp_footer_product.json` | — |
| draft API 去本地字段 | `draft_article_payload` 剥 `body_text` | — |

**Agent 勿回退**：勿改用 `footer product_key` 单独挂 JD 返佣；勿在 `cps_data_pid` 无视 product_id 匹配就读缓存 sku。

## 推草稿命令

```bash
cd stock-ai
uv run python -m scripts.tools.wechat_mp_draft --dry-run
uv run python -m scripts.tools.wechat_mp_draft --kind news
uv run python -m scripts.tools.wechat_mp_eval --kind all --traffic   # 评分 + 阅读量清单
uv run python -m scripts.tools.wechat_mp_push_quality_gate --batch evening  # 推稿前门禁
```

推稿默认 **`WECHAT_MP_STRICT_COMPLIANCE=1`**：合规未过则**不写入**草稿箱（可设 `0` 仅告警）。evening 批次默认 **`WECHAT_MP_PUSH_QUALITY_GATE=1`**：质量门禁未过则不 upsert（`WECHAT_MP_QUALITY_GATE_STRICT=0` 仅告警）。

槽位状态：`data/wechat_mp_draft_slots.json`（update 优先，勿手删）。

## 本会话新增踩坑（勿回退）

1. **market 标题写「盘中复盘」**：曾按 `now.hour` 出「盘中/午间」→ 已改为 **edition 分时段**（pre/midday/close）。
2. **要闻 AI 点评模板化**：曾强制 190–210 字 + `_AI_PAD` → 已改走心 prompt + 禁套话 + 120–220。
3. **龙头 6/7 外泄**：曾写「系统筛选用分 X/7」→ 用户要求 **完全不出现** → 从 prompt/模板/sanitize 全删。
4. **插图首节叠图、图题、过高**：已限 200px、去 caption、首节不插图。
5. **market/news 标题撞车**：已 `_titles_too_similar` + 钩子来源分离。
6. **流量主广告位**：曾正文插 `· · ·` → 已取消；广告由微信自动插入，脚本只做完读/互动/留言。
7. **返佣 CPS**：`getcardinfo product_key` 对 JD 返佣无效 → 正文 `mp-common-cpsad data-pid`；每篇 `auto_pick` 按槽位 Select 最高佣金率（可 `AUTO_PICK=0` 固定 id）。
8. **CPS 位置**：曾按分节（结构判断/待验证事项）→ 已改为正文 **2/3**（`inject_cpsad_at_body_ratio`）。
9. **双免责**：曾 LLM 内联 + 文末框 → 已 `strip_inline_disclaimer_blocks` + 文末 1 块。
10. **彩色开篇**：market 在 `盘面速览` 前；top5/dragons 首节首段 → `opening_lede_paragraph_style`。
11. **阅读原文**：默认关（`WECHAT_MP_READ_SOURCE_URL=0`），勿链 home-hub。
12. **hotspot「今天深写什么」**（原「为什么选这一题」）：只写**本条事件**为何值得深读；**禁止**候选/同批素材等编审过程。旧节名 LLM 输出会 normalize 为新节名。
13. **搜一搜写稿规则（2026-07-12）**：官方教程 01/03 → `wechat-mp-writing/sousou-content-rules.md`（标题路牌完整、单主题、开篇一致、禁编审话术）；evening 审阅顺序 hotspot→news（定时两篇）。
14. **读者禁采集缺口话术（2026-07-12）**：禁止「数据未获取」「样本个股…未获取」「交易时段…未获取」；缺数写板块/指数现象。实现：`HOTSPOT_READER_DATA_RULE` + `sanitize_reader_data_gap()` + 合规项 `数据缺口元叙述` + eval/traffic `reader_no_data_gap_meta`。
15. **hotspot 节标题粘连（2026-07-12）**：`为什么选这一题`/`向后看` 须独立成行，禁止与正文同段。实现：`reflow_hotspot_body` + `ensure_blockquote_sections` 拆行；HTML 侧 `is_blockquote_title_line` 拒 glued 行。
16. **news/hotspot 怪标题（2026-07-28）**：禁把「XX人气榜首」当事件套 `背景下`；禁通稿冒号硬切半截人名；`A股` 后缀前加顿号。Skill：`sousou-content-rules.md` §标题硬禁；代码 `wechat_mp_news_titles` / `wechat_mp_hotspot_article`。
17. **hotspot 热搜选题（2026-07-30）**：默认 `WECHAT_MP_HOTSPOT_SOURCE=trends`（微博+百度）；`evening_mode=hotspot_only` 只推 1 篇；模块 `wechat_mp_hot_trends.py`。
18. **hotspot 参考仿写 + 纯段落（2026-07-30）**：东财搜索取材 →【参考文章·仿写】→ 二次仿写；纯段落无小标题；禁元叙述（`公开报道里…`）；事实标题 `build_hotspot_title_from_facts`；排版 `reflow_hotspot_layout`（≤130 字/段）。Skill：`wechat-mp-writing/hotspot-deep-review.md`；代码 `wechat_mp_hotspot_research.py` · `strip_hotspot_meta_commentary` · `dedupe_hotspot_index_mentions`。

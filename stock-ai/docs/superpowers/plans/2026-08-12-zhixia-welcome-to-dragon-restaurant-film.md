# 栀夏《欢迎来龙餐馆》影视贴图实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成一篇以徐福和“一顿热饭恢复生活秩序”为切口的高质量栀夏影视贴图，并通过 `virtual_lifestyle` 本地干跑。

**Architecture:** 先用当日热榜确认时效，再以电影官方账号、1905 电影网和主流媒体原页核验角色事实与宣传图片。将事实、观点和图片来源分别落入选题卡、正文及 `image-sources.json`，最后交给现有影视贴图流水线校验，不修改生产代码。

**Tech Stack:** JSON、UTF-8 文本、现有 `scripts.tools.wechat_mp_newspic_draft`、微信公众号影视贴图校验器

## Global Constraints

- 标题固定为 `《欢迎来龙餐馆》：沈腾先端上热饭`。
- 内容通道为 `popular_film`，剧透等级为 `S0`。
- 正文 450～550 个汉字，剧情事实不超过全文三分之一。
- 使用 4～5 张可追溯作品主题图，不生成演员近似脸，不重复海报凑数。
- 官方或媒体图不得添加栀夏水印。
- 本轮仅干跑，不写入公众号草稿箱。

---

### Task 1: 核验热度与事实

**Files:**
- Create: `output/zhixia-welcome-dragon-restaurant-topic-card.json`

**Interfaces:**
- Consumes: 2026-08-12 当日热榜、电影官方账号、1905 电影网及主流媒体页面。
- Produces: 字段完整、总分至少 70 且 `zhixia_observation` 至少 15 的影视选题卡。

- [x] **Step 1: 在首次观察后六小时内重新读取热榜**

运行 `uv run python -m scripts.tools.wechat_mp_hot_trends --limit 30`，确认《欢迎来龙餐馆》仍有当日热度信号。

- [x] **Step 2: 核验两项角色事实**

确认徐福由沈腾饰演、为养家还债远赴中东担任中餐馆主厨；马俊生由蒋奇明饰演，负责前台并与徐福共同经营餐馆。只采用可追溯原页。

- [x] **Step 3: 写入并校验选题卡**

选题卡必须包含 `topic`、`observed_at`、`discovery_platform`、`content_type`、`content_lane`、`fact_sources`、`contrast`、`zhixia_observation`、`click_reason`、`image_plan`、`risks`、`scores`、`character_image_policy`、`film_titles`、`spoiler_level`、`release_status` 和 `image_rights_status`。

### Task 2: 获取并登记作品图片

**Files:**
- Create: `assets/wechat_mp/virtual-lifestyle/2026-08-12-欢迎来龙餐馆徐福/01-*`
- Create: `assets/wechat_mp/virtual-lifestyle/2026-08-12-欢迎来龙餐馆徐福/02-*`
- Create: `assets/wechat_mp/virtual-lifestyle/2026-08-12-欢迎来龙餐馆徐福/03-*`
- Create: `assets/wechat_mp/virtual-lifestyle/2026-08-12-欢迎来龙餐馆徐福/04-*`
- Create if verified: `assets/wechat_mp/virtual-lifestyle/2026-08-12-欢迎来龙餐馆徐福/05-*`
- Create: `assets/wechat_mp/virtual-lifestyle/2026-08-12-欢迎来龙餐馆徐福/image-sources.json`

**Interfaces:**
- Consumes: Task 1 核验过的官方或媒体原页及页面图片。
- Produces: 4～5 张功能不重复的图片，以及逐张可追溯来源清单。

- [x] **Step 1: 下载首图、徐福角色图、餐馆图、双人图和收束图候选**

仅下载原页能够确认属于本片的图片。搜索结果缩略图、转载链不明图片和页面明确限制转载的图片不得使用。

- [x] **Step 2: 检查图片有效性与重复度**

逐张检查文件类型、尺寸、清晰度和画面内容；以图像指纹或肉眼排除同图不同裁剪、连续海报和错误人物。

- [x] **Step 3: 写入图片来源清单**

每张必须登记 `source_type`、`film_title`、`page_url`、`page_title`、`source_name`、`visual_role=topic`、`position_role` 和 `allow_zhixia_watermark=false`。

### Task 3: 写正文并运行本地内容断言

**Files:**
- Create: `output/zhixia-welcome-dragon-restaurant-copy.txt`

**Interfaces:**
- Consumes: Task 1 的事实边界与设计规格。
- Produces: 450～550 字、S0、短段排版的栀夏影视正文。

- [x] **Step 1: 写出六段正文**

依次完成早晨钩子、角色事实、笑料反差、生活秩序观察、观点边界和具体收束；不列小标题、不复述完整剧情、不虚构观影经历。

- [x] **Step 2: 执行本地断言**

解析选题卡，统计正文汉字与段落；确认完整片名、徐福、主厨、马俊生、“好好吃饭”等必要实体存在，并扫描“刚看完、电影院、亲测、提示词、评分规则、治愈一切”等禁用表达。

### Task 4: 执行影视贴图生产干跑

**Files:**
- Consume: Task 1～3 的选题卡、正文、图片和来源清单。

**Interfaces:**
- Consumes: `wechat_mp_newspic_draft --slot virtual_lifestyle --topic-card ... --title ... --content ... --images ... --image-sources ... --dry-run`。
- Produces: 不修改远端草稿箱的本地质量门禁结果。

- [x] **Step 1: 运行精确干跑命令**

使用最终 4～5 张图片的显式路径调用 `wechat_mp_newspic_draft`，必须保留 `--dry-run`。

- [x] **Step 2: 仅修复门禁指出的问题并重跑**

允许修正文案长度、选题卡字段、图片来源字段、图片重复或格式问题；不得降低门禁或改为不可追溯素材。

- [x] **Step 3: 汇报标题、字数、图数、来源和干跑状态**

明确说明尚未推送公众号，等待用户再次确认。

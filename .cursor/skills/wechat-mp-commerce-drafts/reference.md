# 带货公众号草稿 — 参考

**品牌**：**简选小电**（租屋全品类小电 · 买前对照）→ 见 [brand.md](brand.md)。  
**默认垂直**：`home`（正文可轮厨房/清洁/环境/个护，选品词见 brand 首月表）。  
| **预览 / 发表** | 独立号 AppID `wx47f3ff18739ab54a`；`WECHAT_MP_COMMERCE_AUTO_PUBLISH=1` 时推稿后 `freepublish` 直接发（无原创/#） |

写作见 [writing-guide.md](writing-guide.md)。**成稿 v1**：[template-jianxuan.md](template-jianxuan.md)。**发布 SOP**：[operations-sop.md](operations-sop.md)。JSON：`data/wechat_mp_commerce_template.json`（`publishing_rhythm`）。骨架见 [templates.md](templates.md)。  
财经五槽见 [wechat-mp-drafts/reference.md](../wechat-mp-drafts/reference.md)。

## 模块文件表

| 文件 | 职责 |
|------|------|
| `scripts/tools/wechat_mp_commerce_draft.py` | 带货稿 CLI：Markdown → HTML 草稿 |
| `scripts/tools/wechat_mp_commerce_slots.py` | 槽位 `guide` / `review` / `trend` upsert |
| `scripts/tools/wechat_mp_product.py` | CPS、`auto_pick`、`attach_footer_product` |
| `scripts/tools/wechat_mp_client.py` | Token、草稿 API、`text_to_html` |
| `scripts/tools/wechat_mp_monetization.py` | 完读问句、`comment_settings` |
| `scripts/tools/wechat_mp_rich_html.py` | 居中分节、着色 |
| `scripts/tools/wechat_mp_prose.py` | `ensure_blockquote_sections` |
| `scripts/tools/wechat_mp_masthead.py` | 可选品牌头（`WECHAT_MP_COMMERCE_MASTHEAD=1`） |
| `data/wechat_mp_commerce_slots.json` | 带货槽位 media_id |
| `assets/wechat_mp/inline-commerce/home/` | **带货插图**（与 `inline/` 财经图分离） |
| `assets/wechat_mp/inline-commerce/home/manifest.json` | home 图库清单 |
| `assets/wechat_mp/commerce/banner.png` | 正文顶栏（`masthead_html("commerce")`） |
| `assets/wechat_mp/commerce/avatar.png` | 草稿列表封面（`pick_commerce_thumb_media_id`） |

## 环境变量（带货 + 共用财经）

```bash
# —— 公众号凭证（带货独立号时换一套 APPID/SECRET）——
WECHAT_MP_COMMERCE_APPID=wx47f3ff18739ab54a
WECHAT_MP_COMMERCE_SECRET=
WECHAT_MP_COMMERCE_AUTHOR=简选小电

# —— 文末返佣（必填才能挂 CPS）——
WECHAT_MP_FOOTER_PRODUCT=1
WECHAT_MP_DAIHUO_UIN=                   # mp 编辑器 Network → Select 请求 uin
WECHAT_MP_FOOTER_PRODUCT_AUTO_PICK=1
WECHAT_MP_FOOTER_PRODUCT_ID=            # 固定 id；auto-pick 开时会被覆盖
WECHAT_MP_FOOTER_PICK_KEYWORD=          # 覆盖 --vertical 默认词
WECHAT_MP_FOOTER_PRODUCT_KINDS=         # 空=全部；带货 CLI 传 vertical 作 kind

# —— 流量主 / 互动 ——
WECHAT_MP_MONETIZE=1
WECHAT_MP_ENGAGEMENT_HOOK=1
WECHAT_MP_NEED_OPEN_COMMENT=1
WECHAT_MP_AD_CHECKPOINT=0               # 勿开；广告由微信自动插

# —— 版式 ——
WECHAT_MP_SECTION_STYLE=compact
WECHAT_MP_RICH_HTML=1
WECHAT_MP_FIGURE_MAX_HEIGHT=200

# —— 带货专用 ——
WECHAT_MP_COMMERCE_HUMANIZE=0           # 1=走 humanize（一般不需要）
WECHAT_MP_COMMERCE_MASTHEAD=1           # 简选 banner 顶栏（commerce/banner.png）
WECHAT_MP_COMMERCE_BANNER_PATH=         # 可选；默认同上或 ~/Pictures/简选小电banner.png
WECHAT_MP_COMMERCE_THUMB_PATH=          # 可选；默认 commerce/avatar.png 作草稿封面
WECHAT_MP_COMMERCE_ACCOUNT_NAME=简选小电
WECHAT_MP_COMMERCE_SEO=1                # 搜一搜词 + 文末 #话题（见 discovery.md）
WECHAT_MP_COMMERCE_THUMB=封面-财经屏-双封面     # 无本地 avatar 时回退素材库名
WECHAT_MP_COMMERCE_DEFAULT_VERTICAL=home       # 文档约定；CLI 已默认 --vertical home
```

## 垂直选品词（`PICK_KEYWORDS_BY_VERTICAL`）

实现于 `wechat_mp_commerce_draft.py`，`attach_footer_product(..., kind=vertical)` 传入 `wechat_mp_product.pick_keywords_for_kind`。

| vertical | Select 搜索词 |
|----------|----------------|
| tech | 机械键盘 显示器 充电宝 路由器 |
| home | 小家电 空气炸锅 收纳 厨房（按周可覆盖，见 [brand.md](brand.md) 首月表） |
| mother | 母婴 绘本 儿童 奶粉 |
| outdoor | 露营 防晒 户外 登山 |
| office | 工学椅 台灯 支架 鼠标垫 |
| beauty | 护肤 洗面奶 防晒 面膜 |

## API 调用链

```
build_commerce_article(title, digest, body_md, vertical)
  → prose / sanitize / disclaimer / monetization hook
  → text_to_html
  → attach_footer_product(article, kind=vertical)
  → pick_thumb (WECHAT_MP_COMMERCE_THUMB)
  → upsert_commerce_draft(slot)
```

## 与 `wechat-mp-drafts` 共用能力对照

| 能力 | 财经五槽 | 带货 skill |
|------|----------|------------|
| 草稿 API | `wechat_mp_draft` | `wechat_mp_commerce_draft` |
| 槽位文件 | `wechat_mp_draft_slots.json` | `wechat_mp_commerce_slots.json` |
| CPS | `attach_footer_product` | 同左，`kind=vertical` |
| 流量主广告 | 发布自动插 | 同左 |
| 合规 | `PUBLIC_MP_WRITER_RULE` | `sanitize_commerce_mp_text` |
| 定时 launchd | 早/午/晚批次 | **无**（手动或自写 plist） |
| SEO #话题 | `wechat_mp_seo_topics.md` | 人工选生活/数码类话题 |

## 第二公众号（独立主体）

1. 新 AppID/SECRET 写入 `.env`（或 `stock-ai/.env.commerce` 推稿前 `export`）
2. 公众平台配置 **同一服务器 IP 白名单**
3. 素材库重新上传封面；`WECHAT_MP_COMMERCE_THUMB` 指向新素材名
4. 返佣开通后重新抓 `WECHAT_MP_DAIHUO_UIN`（uin 可能不同）

个人主体 **1 身份证 1 号**；带货号常需家人主体或个体户（见对话结论，非本仓库代码）。

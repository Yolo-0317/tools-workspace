# 带货规则与代码映射

Agent 改带货链路时先查此表。**成稿 v1**：[template-jianxuan.md](template-jianxuan.md) · **发布 SOP**：[operations-sop.md](operations-sop.md) · JSON：`stock-ai/data/wechat_mp_commerce_template.json`。财经五槽见 [wechat-mp-drafts/rules-implemented.md](../wechat-mp-drafts/rules-implemented.md)。

## 简选小电 v1 定型（冻结 2026-06-03）

| 能力 | 模块 |
|------|------|
| 顶栏 | `masthead_html("commerce")` + `commerce/banner.png` |
| 正文 #话题 | `insert_hashtags_after_intro` → `commerce_hashtag_html` |
| 免责高亮 | `disclaimer_html(kind="commerce")` |
| 插图 | `HOME_COMMERCE_FIGURE_SLOTS` × `inline-commerce/home/` |
| SEO | `WECHAT_MP_COMMERCE_SEO=1` · `kind=commerce` in `wechat_mp_seo.py` |
| 封面 | `pick_commerce_thumb_media_id` → `commerce/avatar.png` |

改 v1 任一项版式 → 新版本号 + 更新 `wechat_mp_commerce_template.json`。

## 插图（home）

| 规则 | 实现 |
|------|------|
| **禁止**样板间/空台面棚拍 | 选图要「有碗筷沥水架调料瓶」；现 manifest 为 Unsplash 杂乱水槽 + Pexels 沥水/碗碟（人工验图） |
| **禁止**盲填 Pexels id 即信 CDN | 曾出现 id=厨房却下到货车/雪山；下载后必须肉眼核对 |
| 带货图下载 | `download_wechat_mp_commerce_figures.py`（Unsplash `unsplash_photo` / Pexels `pexels_id`） |
| 槽位固定文件 | `COMMERCE_HOME_FIGURE_BY_KEY` + `allocate_commerce_home_figure` |
| 节名对齐 | `HOME_COMMERCE_FIGURE_SLOTS` 与正文 `> ` 标题一致 |

换图：只改 `assets/wechat_mp/inline-commerce/home/*.jpg` + 该目录 `manifest.json`；**勿**放进 `assets/wechat_mp/inline/`。推稿前须重新 uploadimg（缓存键含文件 md5，`wechat_mp_figures.figure_upload_cache_key`）。

## 返佣 CPS

| 规则 | 实现 | 测试 |
|------|------|------|
| 免责前插 `mp-common-cpsad` | `inject_cpsad_before_disclaimer` | `test_wechat_mp_product.py` |
| 识别带货免责句 | `_DISCLAIMER_MARKS` 含「推广合作」 | `test_inject_cpsad_before_commerce_disclaimer` |
| auto-pick 按 vertical | `attach_footer_product(..., kind=vertical)` | commerce draft 测试 |
| 不用 product_key 挂 JD | `cps_data_pid` | 财经 skill 踩坑 #7 |

## 带货成稿

| 规则 | 实现 | 测试 |
|------|------|------|
| 推广披露 | `_ensure_disclosure` 仅补摘要句尾；正文不插模板；文末 `COMMERCE_DISCLAIMER` | `test_disclosure_only_in_digest_not_body` |
| 正文 #话题 | `insert_hashtags_after_intro` + `commerce_hashtag_html`（首段后） | `test_wechat_mp_commerce_layout.py` |
| 免责版式 | `disclaimer_html(..., kind=commerce)` 居中暖色高亮 | 同上 |
| 带货免责声明 | `COMMERCE_DISCLAIMER` | `test_build_commerce_article_has_disclaimer` |
| 禁荐股/敏感工具 | `sanitize_commerce_mp_text` 复用部分 public 规则 | — |
| 分节 `>` | `ensure_blockquote_sections` | — |
| 槽位 upsert | `wechat_mp_commerce_slots.upsert_commerce_draft` | `test_wechat_mp_commerce_draft.py` |

## 流量主

| 规则 | 实现 |
|------|------|
| 文末互动问句 | `append_engagement_hook(..., kind="commerce")` |
| 留言开关 | `comment_settings()` |
| 文中 `· · ·` | 默认关 |

## 边界（勿混）

| 规则 | 说明 |
|------|------|
| 不用 `wechat_mp_draft --kind market` 发带货长文 | 合规与 LLM 不同 |
| 不共用五槽 `draft_slots.json` | 避免 prune 误删；预览期可同 AppID |
| 默认垂直 **`home`** | CLI/skill 一致；auto-pick 用小家电词表 |
| 预览 ≠ 正式发布 | 财经号草稿箱仅看版式/CPS；勿当盘面稿发布 |

## 命令

```bash
cd stock-ai
uv run python -m scripts.tools.wechat_mp_commerce_draft --dry-run \
  --vertical tech --title "测试标题？三件数码好物" \
  --digest "数码清单对照，按需购买。（文内有合作推广。）" \
  --body-file path/to.md
```

# 简选小电 — 公众号视觉素材（模板 jianxuan-v1）

模板真源：`data/wechat_mp_commerce_template.json` · `.cursor/skills/wechat-mp-commerce-drafts/template-jianxuan.md`

| 文件 | 用途 |
|------|------|
| `banner.png` | 正文顶栏（`wechat_mp_commerce_draft` → `masthead_html("commerce")`） |
| `avatar.png` | 草稿箱列表封面（推稿时 `add_permanent_image`） |

源文件可放在 `~/Pictures/简选小电banner.png`、`简选小电头像.png`（或 `~/picture/` 同名），更新后复制到本目录并重新推稿。

换 banner 后会按文件 md5 重新 `uploadimg`（见 `wechat_mp_masthead.banner_cache_key`）。

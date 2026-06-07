# 公众号正文插图（inline）

Pexels 免费图（商用友好，见 [Pexels License](https://www.pexels.com/license/)）。宽 900px JPG。

## 图库

- **manifest**：`manifest.json`（36 张，`inline-p01.jpg` … `inline-p36.jpg`）
- **主题**：每张 tags 须含 `market|chart|trading|screen|tech|ai|finance|selection|emotion|workspace` 至少一项
- **带货图**：放在 `../inline-commerce/`，勿与本目录混放
- **下载**：`uv run python -m scripts.tools.download_wechat_mp_inline_figures`
- **核对**：Pexels `photos/{id}` 直链可能与预期不符；新增/改 `pexels_id` 后须 `--force` 重下并肉眼确认（禁花卉、生活照等非财经图）
- **当日去重**：`data/wechat_mp_figure_usage.json`（同天五槽位尽量不重复）

## 正文标记

`[[fig:文件名|图注]]`，由 `wechat_mp_figures.inject_*_figures` 按槽位插入：

| 稿 | 插图数 | 函数 |
|----|--------|------|
| market | 4 | `inject_market_figures` |
| news | 4 | `inject_news_figures` |
| top5 | 2 | `inject_top5_figures` |
| dragons | 2 | `inject_dragons_figures` |

分配逻辑：`wechat_mp_figure_pool.allocate_figure`（按 tag 匹配 + 当日 used 集合）。

##  legacy

旧 4 张 `inline-market-*.jpg` 仍可用作 fallback；新稿优先 manifest 池。

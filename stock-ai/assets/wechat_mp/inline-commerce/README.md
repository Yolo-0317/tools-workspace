# 带货公众号正文插图（与财经 inline 分离）

| 目录 | 用途 |
|------|------|
| `home/` | `--vertical home` 收纳/厨房稿（`wechat_mp_commerce_draft`） |

**勿**把带货图放进 `../inline/`（财经 market/news/top5/dragons/workspace 共用池）。

## home 图库

- manifest：`home/manifest.json`
- 文件：`01-compact-kitchen.jpg` …（**人工验图**后改名落盘）
- 选图原则：**贴近生活** — 有碗筷、沥水架、调料瓶、清洁用品等日常物；避免空台面样板间、杂志棚拍、纯效果图
- 来源：优先 Unsplash/Pexels 的 **messy / cluttered / small kitchen**；Pexels 勿盲信 `photos/{id}` 直链，下载后必须肉眼核对
- 下载：`uv run python -m scripts.tools.download_wechat_mp_commerce_figures --vertical home [--force]`
- 代码：`wechat_mp_figure_pool.allocate_commerce_home_figure` → `wechat_mp_figures.inject_commerce_figures`

换图：更新 manifest + 跑下载脚本验图，再 `wechat_mp_commerce_draft` 重推草稿。

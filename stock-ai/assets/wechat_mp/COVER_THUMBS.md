# 牛马也智能 · 晚间槽位封面留档

> 定稿：2026-07-13 · 代码真源：`scripts/tools/wechat_mp_client.py`（`_DEFAULT_KIND_THUMB_ASSETS` / `_DEFAULT_KIND_THUMB_NAMES`）

## evening 两篇默认封面（本地优先）

| kind | 本地文件（相对 `stock-ai/`） | 画面 | 素材库名（可选上传） |
|------|------------------------------|------|----------------------|
| **sector**（news 头条封面槽） | `assets/wechat_mp/banner.png` | 牛马品牌 | `封面-牛马品牌-双封面` |
| **dragons**（hotspot 次条封面槽） | `assets/wechat_mp/cover-multi-screen-dual.jpg` | 亮色多屏行情 | `封面-多屏亮行情-双封面` |
| **news** 正文 | 同上 sector 槽 | 牛马品牌 | — |
| **hotspot** 正文 | 同上 dragons 槽 | 多屏亮行情 | — |

**evening 同批群发**

| 群发位 | 正文 kind | 封面槽位（固定不变） |
|--------|-----------|----------------------|
| 1 头条 | `news` | **牛马品牌** |
| 2 次条 | `hotspot` | **多屏亮行情** |

封面槽位 1→2 永远 **牛马 → 多屏**，与正文 kind 解耦；代码见 `cover_kind_for_content()`。

## 手动槽位（非 evening 定时）

| kind | 本地文件 | 画面 |
|------|----------|------|
| **top5**（仅手动） | `assets/wechat_mp/cover-financial-screen-dual.jpg` | 亮色财经屏 |
| **dragons**（仅手动） | `assets/wechat_mp/cover-multi-screen-dual.jpg` | 多屏亮行情 |

**勿再用（已淘汰）**

- top5：`封面-手机看盘` / `cover-smartphone-chart`（可保留作 fallback）
- dragons：`封面-K线暗色` / `cover-candlestick-dark` / `cover-exchange-board`（交易所大屏，2026-06-04 试过后换多屏）

## 环境变量

```bash
# 默认开启本地封面（top5/dragons）
WECHAT_MP_KIND_THUMB_FROM_ASSETS=1

# 覆盖路径
# WECHAT_MP_THUMB_PATH_TOP5=assets/wechat_mp/cover-financial-screen-dual.jpg
# WECHAT_MP_THUMB_PATH_DRAGONS=assets/wechat_mp/cover-multi-screen-dual.jpg

# 覆盖素材库子串
# WECHAT_MP_THUMB_NAME_TOP5=封面-财经亮屏-双封面
# WECHAT_MP_THUMB_NAME_DRAGONS=封面-多屏亮行情-双封面
```

## 换图后必做

```bash
cd stock-ai
rm -f data/wechat_mp_thumb_top5.json data/wechat_mp_thumb_dragons.json
uv run python -m scripts.tools.wechat_mp_draft --kind top5    # 或 dragons
```

缓存按文件 md5；不换缓存会继续用旧 `thumb_media_id`。

## 备选亮色封面（仓库内）

| 文件 | 适用 |
|------|------|
| `cover-monitor-graph-dual.jpg` | 显示器 K 线 |
| `cover-smartphone-chart-dual.jpg` | 手机看盘 |
| `cover-tablet-monitor-dual.jpg` | 平板分析 |
| `cover-exchange-board-dual.jpg` | 交易所大屏（龙头已弃） |

源图：`*-src.jpg`；推送用 `*-dual.jpg`。

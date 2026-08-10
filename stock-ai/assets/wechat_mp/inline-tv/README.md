# 影视试跑 · 正文剧照

## 公众号对剧照的限制（实操结论）

微信**没有单独的「美剧剧照」条款**，但会按以下规则处理：

| 维度 | 平台/法律要求 | 对本号建议 |
|------|----------------|------------|
| **著作权** | 未经授权使用他人图片可被投诉删除（[侵权投诉标准](https://www.kancloud.cn/w469001293/wx_zh/1112574)） | 剧评引用：少量配图 + 文末来源说明；**不要**当「资源帖」发整季截图 |
| **原创声明** | 勾选「原创」指**文字**自创；配图仍须有使用权 | 原创分类选 **生活 / 娱乐**，勿选财经；正文标明「剧评引用」 |
| **肖像权** | 明星宣传照用于商业推广可能被诉 | 剧评语境、非代言口吻；避免裁剪成「封面八卦」 |
| **内容审核** | 《亢奋》属 R 级题材，**裸露/ drug / 血腥**易触发限流或删文 | 只用已人工筛过的**安全剧照**（见 `euphoria/`）；禁 bikini 合成海报、禁派对 drug 镜头 |
| **推荐流** | 低俗、标题党、无关图会降低推荐 | 图与文一致；一稿 **2–3 张** 即可 |

**比 HBO 官方授权更稳的做法**：向 `cliplicensing@hbo.com` 申请 still 许可（商业号长期发剧评时考虑）。短期试跑：TMDB 宣传素材 + 剧评引用说明 + 合规选图。

## 素材路径

- **定稿模板 tv_review_v1**：[`docs/WECHAT_MP_TV_REVIEW.md`](../../../docs/WECHAT_MP_TV_REVIEW.md) · [`data/wechat_mp_tv_review_template.json`](../../../data/wechat_mp_tv_review_template.json)
- 本地：`euphoria/douban-still-*.jpg`
- 正文标记：`[[fig:tv/euphoria/still-01.jpg|max-h=420;fit=contain]]`
- 注入：`wechat_mp_tv_figures.inject_tv_review_figures`
- 拉取：`ensure_tv_stills`（缺文件时从 TMDB CDN 补；`WECHAT_MP_TV_STILLS_FORCE=1` 强制重拉）

## TMDB 剧照（《铁拳教育》等）

| 方式 | 要不要注册 |
|------|------------|
| **默认（当前）** | **不用**。脚本抓取 TMDB 公开图片页 + 从 `image.tmdb.org` 下载宣传剧照 |
| **可选 API** | 在 [themoviedb.org](https://www.themoviedb.org/) 免费注册 → Settings → API → 申请 **Read Access Token**，写入 `stock-ai/.env` 的 `TMDB_READ_ACCESS_TOKEN` |

```bash
cd stock-ai
WECHAT_MP_TV_STILLS_FORCE=1 uv run python -m scripts.tools.wechat_mp_repush_tv_review_draft --title-en "Teach You a Lesson"
```

配图标记：`scene=` 桥段说明 + `cap=` 图源（两行展示）。

## 豆瓣剧照 / 评分截图？

| 做法 | 行不行 | 说明 |
|------|--------|------|
| **豆瓣条目里的剧照** | 能用，但**不比 TMDB 更「合法」** | 多为 HBO 宣传照或用户上传；豆瓣不提供转载授权 |
| **截豆瓣页面当图** | 业内有人做，**不推荐自动化** | 违反豆瓣 ToS；页面 UI 有著作权；易被压缩糊 |
| **截烂番茄页面当图** | 同上 | RT 商标 + 页面 UI；剧评写「约 42%」更安全 |
| **自制评分卡（本仓库默认）** | **推荐** | `wechat_mp_tv_ratings.py` 用公开数字画信息图，标注「非官方截图」 |

剧照与豆瓣海报多为**同一批宣传物料**；正文仍走 TMDB CDN + 人工筛图。评分在 `topic.ratings` 里维护，发稿前核对豆瓣 subject 与 RT 页面。

## TMDB

配图来自 [TMDB](https://www.themoviedb.org/tv/85552-euphoria) 公开图库路径；TMDB 不转让版权，仅便于识别作品。

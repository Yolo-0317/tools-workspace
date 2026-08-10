# 牛马也智能 · 影视试跑稿模板（tv_review_v2）

定稿真源：**《铁拳教育》**（2026-06-20 结构锁定，替代《亢奋》v1）。换片只换 topic、分集、评分与剧照锚点，**不重发明结构**。

## 真源文件（Agent 先读）

| 文件 | 用途 |
|------|------|
| [`.cursor/skills/wechat-mp-drafts/tv-review-template.md`](../.cursor/skills/wechat-mp-drafts/tv-review-template.md) | **Skill 金标准** |
| [`data/wechat_mp_tv_review_template.json`](../data/wechat_mp_tv_review_template.json) | 机器可读真源 |
| [`data/wechat_mp_tv_review_golden/teach_you_a_lesson.body_core.md`](../data/wechat_mp_tv_review_golden/teach_you_a_lesson.body_core.md) | 正文金样 |
| [`data/wechat_mp_tv_body_cache/`](../data/wechat_mp_tv_body_cache/) | 按 topic 分文件的定稿缓存 |

## 五节结构（v2）

| # | 示例（铁拳教育） | 内容 |
|---|------------------|------|
| 1 | 连夜刷完10集，半夜却有点发虚 | 个人观感 + 争议数据；评分插在第一段正文后 |
| 2 | 看着像揍人爽剧，其实是在写老师失了势 | 反差立意 + 背景 |
| 3 | 分集速写：10集几乎没废场 | **按集 bullet**；配图 `after_anchor` 紧跟对应集 |
| 4 | 爱这口的会熬夜… | 受众 / 劝退 |
| 5 | 拿不准就开前两集… | 试看建议 + 互动问句 |

口吻：**第一人称「我」**；参考网上真人剧评；禁《亢奋》照抄、禁小编体。

## 命令

```bash
cd stock-ai
uv run python -m scripts.tools.wechat_mp_repush_tv_review_draft --title-en "Teach You a Lesson"
uv run python -m scripts.tools.wechat_mp_draft_batch --batch tv_trial
```

《亢奋》金样仍备查：`data/wechat_mp_tv_review_golden/euphoria.body_core.md`（勿再作默认模板）。

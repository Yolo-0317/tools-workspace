# 《望庐山瀑布》公众号诗境贴图 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 生成《望庐山瀑布》四图贴图说明并覆盖 `virtual_lifestyle` 当前的《早发白帝城》草稿，写入后远程回读确认。

**Architecture:** 四张已有场景卡按编号组成同一条 `newspic` 滑动图集，纯文本文件只保存一个连续说明字段。选题卡与来源清单保存在 `stock-ai/output/`，先通过本地 dry-run，再用现有 `virtual_lifestyle` 槽位更新微信草稿；用户已明确允许覆盖当前白帝城草稿。

**Tech Stack:** Markdown、纯文本、JSON、现有 PNG 场景卡、`wechat_mp_newspic_draft`、微信公众号草稿 API。

## Global Constraints

- 只使用 `episodes/lushan/assets/scene-cards/` 中现有四张场景卡。
- 图片严格按 `01`、`02`、`03`、`04` 顺序使用。
- 不加字、不裁图、不加水印、不重新生成图片。
- 标题固定为 `瀑布还没出现，水声先到了`。
- 贴图说明为一个连续的 400～500 字字段，不出现逐图标题或编辑指令。
- 完整诗句与出处只出现一次。
- 结尾固定为 `完整原创视频已发布在视频号「栀夏与阿砚」。`
- 末尾保留 `原创虚构动画，画面由 AI 辅助生成。`
- 草稿使用 `virtual_lifestyle` 槽位；用户已确认允许覆盖该槽位当前的《早发白帝城》草稿。
- 本地《早发白帝城》文案和图片不得删除或修改。
- 只写草稿，不执行正式发表。

---

### Task 1: 完成庐山贴图说明

**Files:**
- Create: `zhixia-feihualing/episodes/lushan/wechat-poetry-copy.txt`
- Read: `zhixia-feihualing/episodes/lushan/assets/scene-cards/README.md`
- Read: `zhixia-feihualing/docs/superpowers/specs/2026-08-26-lushan-wechat-poetry-post-design.md`

**Interfaces:**
- Consumes: 四张场景卡的顺序、“声音先到”的核心观察、固定诗句与视频号指引。
- Produces: 可直接传给 `--content` 的 UTF-8 纯文本说明。

- [ ] **Step 1: 写连续说明**

按“水雾突袭 → 循声寻找 → 抬头 → 瀑布全貌 → 诗句 → 栀夏观察”的顺序写 400～500 字。正文必须包含：

```text
飞流直下三千尺，疑是银河落九天。

唐·李白《望庐山瀑布》

完整原创视频已发布在视频号「栀夏与阿砚」。

原创虚构动画，画面由 AI 辅助生成。
```

- [ ] **Step 2: 核对说明边界**

运行：

```bash
wc -m zhixia-feihualing/episodes/lushan/wechat-poetry-copy.txt
rg -c '^飞流直下三千尺，疑是银河落九天。$|^唐·李白《望庐山瀑布》$|^完整原创视频已发布在视频号「栀夏与阿砚」。$|^原创虚构动画，画面由 AI 辅助生成。$' zhixia-feihualing/episodes/lushan/wechat-poetry-copy.txt
```

预期：文件字符数处于平台允许范围，四条固定文本各出现一次；正文没有图片文件名、外链、二维码或“下面这条视频”。

- [ ] **Step 3: 提交成稿**

运行：

```bash
git diff --check -- zhixia-feihualing/episodes/lushan/wechat-poetry-copy.txt
git add -- zhixia-feihualing/episodes/lushan/wechat-poetry-copy.txt
git commit -m "文案：完成庐山瀑布公众号诗境贴图"
```

### Task 2: 准备草稿元数据并覆盖推送

**Files:**
- Create: `stock-ai/output/zhixia-lushan-topic-card.json`
- Create: `stock-ai/output/zhixia-lushan-image-sources.json`
- Read: `stock-ai/data/wechat_mp_virtual_lifestyle_pending.json`
- Modify externally: 微信公众号 `virtual_lifestyle` 草稿槽位

**Interfaces:**
- Consumes: Task 1 的纯文本说明和四张原创场景卡。
- Produces: 一条远程 `article_type=newspic` 的《望庐山瀑布》草稿，以及更新后的本地待发表记录。

- [ ] **Step 1: 创建选题卡**

使用 `content_type=B`、`content_lane=zhixia_daily`、`character_image_policy=story_multiple` 和 `ai_disclosure_mode=platform_publish`。`visual_exception` 明确四张卡共同承担水雾、循声、抬头和全貌揭示，不能缩减为单张角色锚点图。

- [ ] **Step 2: 创建来源清单**

为以下四个文件逐一登记 `source_type=original`、非空 `fallback_reason`、`visual_role=character`、`capture_mode=author_card` 和 `allow_zhixia_watermark=false`：

```text
01-mist-impact-close.png
02-listening-medium.png
03-look-up-low-angle.png
04-waterfall-ending-wide.png
```

位置角色依次使用 `hook`、`evidence`、`evidence`、`author`。

- [ ] **Step 3: 运行 dry-run**

从 `stock-ai/` 运行：

```bash
.venv/bin/python -m scripts.tools.wechat_mp_newspic_draft \
  --slot virtual_lifestyle \
  --topic-card output/zhixia-lushan-topic-card.json \
  --title '瀑布还没出现，水声先到了' \
  --content ../zhixia-feihualing/episodes/lushan/wechat-poetry-copy.txt \
  --images \
    ../zhixia-feihualing/episodes/lushan/assets/scene-cards/01-mist-impact-close.png \
    ../zhixia-feihualing/episodes/lushan/assets/scene-cards/02-listening-medium.png \
    ../zhixia-feihualing/episodes/lushan/assets/scene-cards/03-look-up-low-angle.png \
    ../zhixia-feihualing/episodes/lushan/assets/scene-cards/04-waterfall-ending-wide.png \
  --image-sources output/zhixia-lushan-image-sources.json \
  --watermark '' \
  --dry-run
```

预期：原创报告为 `PASS`，类型为 `B`，通道为 `zhixia_daily`，图片数为 4，重复图片数为 0。

- [ ] **Step 4: 覆盖当前草稿**

运行与 Step 3 相同的命令，但移除 `--dry-run`。预期输出 `OK [virtual_lifestyle] updated`，media ID 与覆盖前的槽位 ID 相同。

- [ ] **Step 5: 远程回读验证**

调用 `fetch_draft_news_item()` 回读当前 `virtual_lifestyle` media ID，只输出非敏感摘要。预期结果：

```text
article_type=newspic
title=瀑布还没出现，水声先到了
image_count=4
has_poem=true
has_video_account_cta=true
old_baidi_title_absent=true
```

确认 `data/wechat_mp_virtual_lifestyle_pending.json` 已更新为庐山标题与同一 media ID。草稿只停留在草稿箱，不调用正式发表接口。

# 《飞花令·风》公众号宣传稿 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成一篇宣传视频号《飞花令·风》的公众号文章，使用成片截图完成封面和正文配图，在公众号草稿中插入一次已发布的视频号作品卡片，并将互动引向视频评论区。

**Architecture:** 内容真源保存在《栀夏飞花令》项目内，正文、截图和来源清单分别管理。先从推荐成片提取并检查三张截图，再按已确认设计写稿和完成移动端排版；最后通过已登录的公众号后台创建草稿并人工选择已发布的《飞花令·风》视频号卡片，避免伪造卡片 HTML 或绕过后台归因数据。

**Tech Stack:** Markdown、FFmpeg/FFprobe、现有《栀夏飞花令》视频资产、公众号网页编辑器、Chrome 已登录会话

## Global Constraints

- 主标题固定为“风看不见，栀夏和阿砚把它拍了下来”。
- 全文约 900—1200 个汉字，以信息完整和移动端完读为先，不为凑字数重复解释诗意。
- 前 150 字内出现具体画面以及栀夏或阿砚，并建立“风如何被拍下”的悬念。
- 角色机制必须准确表述为“阿砚出题，栀夏接诗；汉字苏醒，诗境展开”。
- 视频号卡片只出现一次，位于角色机制介绍之后、三段诗境展开之前。
- 只使用《飞花令·风》现有成片截图，不生成新图。
- 正文只设置 2—3 处重点加粗。
- 结尾完整保留“风停了，诗还没停。第四句，你来接。”并邀请读者去视频评论区接一句含“风”的诗。
- 不虚构播放数据、读者反馈、创作花絮或成片中不存在的场景。
- 不加入立场免责声明，不插入商品、返佣商品或短剧推广组件。

---

## File Structure

- Create: `zhixia-feihualing/operations/wechat-promo/ep02-wind/article.md` — 公众号正文与卡片插入标记的单一内容真源。
- Create: `zhixia-feihualing/operations/wechat-promo/ep02-wind/figure-sources.json` — 三张截图的成片来源、时间点、用途和核验结果。
- Create: `zhixia-feihualing/assets/wechat-promo/ep02-wind/cover.jpg` — 栀夏与阿砚同框封面。
- Create: `zhixia-feihualing/assets/wechat-promo/ep02-wind/wind-visible.jpg` — “风怎样被看见”段落配图。
- Create: `zhixia-feihualing/assets/wechat-promo/ep02-wind/poem-transition.jpg` — 三段诗境情绪递进配图。
- Modify: `zhixia-feihualing/assets/inventory.csv` — 登记三张公众号截图资产。
- External draft: 微信公众号后台草稿箱 — 保存排版后的文章和一个视频号卡片，不自动发表。

### Task 1: 提取并核验三张成片截图

**Files:**
- Create: `zhixia-feihualing/assets/wechat-promo/ep02-wind/cover.jpg`
- Create: `zhixia-feihualing/assets/wechat-promo/ep02-wind/wind-visible.jpg`
- Create: `zhixia-feihualing/assets/wechat-promo/ep02-wind/poem-transition.jpg`
- Create: `zhixia-feihualing/operations/wechat-promo/ep02-wind/figure-sources.json`
- Modify: `zhixia-feihualing/assets/inventory.csv`

**Interfaces:**
- Consumes: `zhixia-feihualing/exports/ep02-wind-subtitled-v01.mp4`, duration `21.916667` seconds.
- Produces: three JPEG files usable by the article and a manifest with `file`, `source_video`, `timestamp_seconds`, `purpose`, and `verified` fields.

- [ ] **Step 1: Verify the source video and target timestamps**

Run:

```bash
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 zhixia-feihualing/exports/ep02-wind-subtitled-v01.mp4
```

Expected: output is approximately `21.916667`, so `5.0`, `9.8`, and `14.8` seconds all fall within the completed video.

- [ ] **Step 2: Extract the three frames**

Run:

```bash
mkdir -p zhixia-feihualing/assets/wechat-promo/ep02-wind
ffmpeg -y -ss 14.8 -i zhixia-feihualing/exports/ep02-wind-subtitled-v01.mp4 -frames:v 1 -q:v 2 zhixia-feihualing/assets/wechat-promo/ep02-wind/cover.jpg
ffmpeg -y -ss 5.0 -i zhixia-feihualing/exports/ep02-wind-subtitled-v01.mp4 -frames:v 1 -q:v 2 zhixia-feihualing/assets/wechat-promo/ep02-wind/wind-visible.jpg
ffmpeg -y -ss 9.8 -i zhixia-feihualing/exports/ep02-wind-subtitled-v01.mp4 -frames:v 1 -q:v 2 zhixia-feihualing/assets/wechat-promo/ep02-wind/poem-transition.jpg
```

Expected: all three files are valid JPEG images; `cover.jpg` shows 栀夏与阿砚同框，另外两张分别呈现江南风景和秋江诗境。

- [ ] **Step 3: Visually inspect all three images**

Open each image at original detail. Reject a frame if it contains a transition blur, blocked face,播放器控件, progress bar, malformed character, or unreadable unintended text. If rejected, move only that timestamp by `0.2` seconds and re-extract until the frame is clear.

- [ ] **Step 4: Record the source manifest**

Create `figure-sources.json` with this exact structure, updating a timestamp only if Step 3 required a `0.2`-second adjustment:

```json
{
  "source_video": "zhixia-feihualing/exports/ep02-wind-subtitled-v01.mp4",
  "figures": [
    {"file": "cover.jpg", "timestamp_seconds": 14.8, "purpose": "cover-zhixia-ayan-same-frame", "verified": true},
    {"file": "wind-visible.jpg", "timestamp_seconds": 5.0, "purpose": "body-visible-effects-of-wind", "verified": true},
    {"file": "poem-transition.jpg", "timestamp_seconds": 9.8, "purpose": "body-three-poem-emotional-transition", "verified": true}
  ]
}
```

- [ ] **Step 5: Register the assets and verify image dimensions**

Add one row per image to `assets/inventory.csv`, following the existing column order and naming pattern. Then run:

```bash
file zhixia-feihualing/assets/wechat-promo/ep02-wind/*.jpg
```

Expected: three JPEG files with the same vertical frame dimensions as the exported video.

- [ ] **Step 6: Commit the verified screenshots**

```bash
git add zhixia-feihualing/assets/wechat-promo/ep02-wind zhixia-feihualing/operations/wechat-promo/ep02-wind/figure-sources.json zhixia-feihualing/assets/inventory.csv
git commit -m "素材：补充飞花令风公众号截图"
```

### Task 2: 写成可直接排版的公众号正文

**Files:**
- Create: `zhixia-feihualing/operations/wechat-promo/ep02-wind/article.md`

**Interfaces:**
- Consumes: the approved design spec, the three poem lines in `episodes/ep02/one-character-three-poems.md`, and the three verified screenshots from Task 1.
- Produces: Markdown containing front matter fields `title`, `digest`, and `cover`, followed by the finished body and one `<!-- VIDEO_CARD: 飞花令·风 -->` marker.

- [ ] **Step 1: Create the article with fixed metadata**

Start the file with:

```markdown
---
title: 风看不见，栀夏和阿砚把它拍了下来
digest: 风没有形状，却会翻动书页、推开云海，也把一场飞花令送到屏幕外。第四句，等你来接。
cover: ../../../assets/wechat-promo/ep02-wind/cover.jpg
---
```

- [ ] **Step 2: Write the opening and character mechanism**

Write short paragraphs beginning exactly with “风看不见，栀夏和阿砚却想把它拍下来。” Within the first 150 Chinese characters include at least two visible effects among衣袖、书页、云层、帆影. Introduce the mechanism exactly once as “阿砚出题，栀夏接诗；汉字苏醒，诗境展开。”

- [ ] **Step 3: Place the first image and video-card marker**

After explaining how wind becomes visible, insert:

```markdown
![风经过江南诗境后留下的变化](../../../assets/wechat-promo/ep02-wind/wind-visible.jpg)
```

After the sentence “这一次，他们从一个‘风’字出发，走进了三种完全不同的诗境。” insert:

```html
<!-- VIDEO_CARD: 飞花令·风 -->
```

There must be exactly one such marker in the file.

- [ ] **Step 4: Write the three-poem emotional progression**

Use the exact three lines from `episodes/ep02/one-character-three-poems.md`. Connect them as an emotional movement from江南微风，到秋江急风，再到沧海长风. Do not explain every word or invent production anecdotes. Place `poem-transition.jpg` after the paragraph where the second wind changes the reader's emotional judgment.

- [ ] **Step 5: Finish with the comment invitation**

End the body with the exact sentence “风停了，诗还没停。第四句，你来接。” followed by one direct instruction to visit the video account work’s comment section and reply with a poem containing “风”. Do not append a disclaimer, product component, short-drama promotion, or generic follow request.

- [ ] **Step 6: Run structural checks**

Run:

```bash
python3 -c 'from pathlib import Path; import re; p=Path("zhixia-feihualing/operations/wechat-promo/ep02-wind/article.md"); s=p.read_text(); body=s.split("---",2)[-1]; n=len(re.sub(r"[\s#*!<>/=-]", "", body)); print({"body_chars":n,"video_markers":s.count("<!-- VIDEO_CARD: 飞花令·风 -->"),"images":s.count("!["),"bold_pairs":s.count("**")//2,"ending": "风停了，诗还没停。第四句，你来接。" in s})'
```

Expected: `body_chars` is between `900` and `1200`, `video_markers` is `1`, `images` is `2`, `bold_pairs` is between `2` and `3`, and `ending` is `True`.

- [ ] **Step 7: Perform editorial review**

Read the article from top to bottom and verify: no internal instruction is visible; no invented data or reaction appears; 阿砚 is a question-driving ink spirit rather than a pet; 栀夏 enters the poem rather than lecturing; each paragraph contains only one idea; the video marker interrupts neither a sentence nor a poem.

- [ ] **Step 8: Commit the finished article**

```bash
git add zhixia-feihualing/operations/wechat-promo/ep02-wind/article.md
git commit -m "文案：完成飞花令风公众号宣传稿"
```

### Task 3: 在公众号后台排版并插入视频号卡片

**Files:**
- Read: `zhixia-feihualing/operations/wechat-promo/ep02-wind/article.md`
- Read: `zhixia-feihualing/assets/wechat-promo/ep02-wind/cover.jpg`
- Read: `zhixia-feihualing/assets/wechat-promo/ep02-wind/wind-visible.jpg`
- Read: `zhixia-feihualing/assets/wechat-promo/ep02-wind/poem-transition.jpg`
- External modify: 微信公众号后台草稿

**Interfaces:**
- Consumes: approved article Markdown and the three verified images.
- Produces: one saved公众号草稿 containing the exact title, digest, cover, two inline images, 2—3 bold passages, and one genuine video account card linked to the published 《飞花令·风》.

- [ ] **Step 1: Open the authenticated公众号 editor**

Use the existing logged-in Chrome session to open the公众号图文编辑器. If the account is logged out or the editor requests authentication, stop and ask the user to log in; do not read cookies or automate login.

- [ ] **Step 2: Fill title, digest, body, and images**

Copy the exact title and digest from the front matter. Convert the Markdown body to mobile-friendly short paragraphs. Upload `wind-visible.jpg` and `poem-transition.jpg` at their markers, apply bold only to the 2—3 passages marked in the source, and choose `cover.jpg` as the cover.

- [ ] **Step 3: Insert the published video account work**

At `<!-- VIDEO_CARD: 飞花令·风 -->`, use the editor’s “视频号” component, choose the already-published work named 《飞花令·风》 from the bound 栀夏与阿砚 account, and insert it once. Remove the marker from visible content. If that exact work is not shown, stop and report the missing item rather than selecting another video.

- [ ] **Step 4: Verify forbidden components are absent**

Inspect the editor content and component list. Expected: one video account card; zero返佣商品 cards; zero short-play cards; zero duplicate video cards; zero visible Markdown image syntax or HTML comments.

- [ ] **Step 5: Save as draft without publishing**

Save the article to the draft box. Do not群发, schedule, or publish.

- [ ] **Step 6: Preview the saved draft on mobile layout**

Open the saved draft preview and verify the cover crop keeps both 栀夏 and 阿砚 visible, images are sharp, bold styling renders correctly, the video card opens 《飞花令·风》, and the final comment invitation is the last reader-facing block.

- [ ] **Step 7: Report the draft result**

Return the saved draft title, whether the video card opened the correct work, image count, and any manual action still required. If all checks pass, report that the draft is ready for the user’s final review, not that it has been published.

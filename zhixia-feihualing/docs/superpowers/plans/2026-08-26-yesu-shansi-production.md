# 《夜宿山寺》15秒诗词小故事 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成《夜宿山寺》四张写实场景卡、Seedance 15秒双角色视频、固定音色五句对白、结尾诗句字幕和最终成片。

**Architecture:** 先把已确认设计落成单集生产包和可验证的四张独立场景卡提示词，再逐张生成并锁定角色、木楼和空间连续性。Seedance负责全程双角色画面、自然说话动作、背景音乐和完整环境声；环境声验收通过后才进入固定音色TTS与字幕后期，后期不补建整套音效，只压低原声床并叠加对白和诗句。

**Tech Stack:** Markdown、JSON、ChatGPT Image Generation、Seedance 2.0、豆包TTS、Swift/AppKit、FFmpeg、ffprobe、zsh、Git

## Global Constraints

- 栀夏和阿砚必须在0—15秒每一个镜头中同时出现。
- 五句对白连续覆盖全片，最后一句延续到视频结束且不回答。
- Seedance不得生成可辨识对白、旁白、朗诵、唱诗或带人声音乐。
- Seedance必须生成与画面同步的高山风、衣料声、双角色脚步、木阶承重声和一次远处寺钟。
- 环境声缺失、不同步或只有泛化音乐时直接退回Seedance重做，不进入后期补音效。
- 后期使用栀夏、阿砚固定音色；正式付费TTS前必须先免费预览并再次取得用户确认。
- 完整诗句约11.5秒开始展示，只展示、不朗诵。
- 两个角色在结尾仍至少占画面高度约四分之一，不切纯风景或黑屏。
- 场景采用电影级半写实东方角色与高度写实自然环境，不出现仙侠化星空和悬空建筑。
- 所有用户可见内容和项目文档禁止emoji。
- 不覆盖旧资产，不提交`.env`、证书、订阅链接或其他项目改动。

## File Structure

- `episodes/yesu-shansi/README.md`：单集事实、时间轴、生产状态和验收门禁。
- `episodes/yesu-shansi/voice-lines.json`：五句后期配音清单。
- `episodes/yesu-shansi/prompts/scene-cards.md`：四张独立场景卡提示词。
- `episodes/yesu-shansi/prompts/seedance-video.md`：15秒连续视频与声音提示词。
- `episodes/yesu-shansi/assets/scene-cards/`：四张已确认场景卡。
- `episodes/yesu-shansi/assets/video/content-raw-v01.mp4`：保留Seedance原始下载视频。
- `episodes/yesu-shansi/subtitle-plan.json`：最终对白和诗句字幕清单。
- `assets/audio/yesu-shansi/`：五句固定音色TTS及元数据。
- `assets/subtitles/yesu-shansi/`：透明字幕卡。
- `scripts/build_yesu_shansi.sh`：只压低原声床、叠加对白和字幕的最终合成入口。
- `tests/test_yesu_shansi_assets.sh`：验证单集资产、角色同框抽帧与原片规格。
- `tests/test_yesu_shansi_video.sh`：验证最终成片规格、声音、字幕和完整解码。
- `exports/yesu-shansi-subtitled-v01.mp4`：最终发布成片。

---

### Task 1: 创建单集生产包与配音预览清单

**Files:**
- Create: `zhixia-feihualing/episodes/yesu-shansi/README.md`
- Create: `zhixia-feihualing/episodes/yesu-shansi/voice-lines.json`
- Create: `zhixia-feihualing/tests/test_yesu_shansi_assets.sh`
- Reference: `zhixia-feihualing/docs/superpowers/specs/2026-08-26-yesu-shansi-poem-story-design.md`

**Interfaces:**
- Consumes: 已确认的五句对白、四场景和全程双角色规则。
- Produces: 后续场景卡、Seedance与TTS共同引用的唯一单集事实源。

- [ ] **Step 1: 写失败的生产包测试**

创建 `tests/test_yesu_shansi_assets.sh`：

```zsh
#!/bin/zsh
set -euo pipefail
project_dir="$(cd "$(dirname "$0")/.." && pwd)"
episode="$project_dir/episodes/yesu-shansi"
for required in "$episode/README.md" "$episode/voice-lines.json"; do
  test -s "$required"
done
python3 - "$episode/voice-lines.json" <<'PY'
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
assert data["episode"] == "yesu-shansi"
assert data["audio_slug"] == "yesu-shansi"
lines = data["lines"]
assert len(lines) == 5
assert [line["role"] for line in lines] == ["ayan", "zhixia", "ayan", "zhixia", "ayan"]
assert [line["start_ms"] for line in lines] == [0, 3200, 6000, 9300, 12200]
assert lines[-1]["text"] == "那天上的人……也会听见吗？"
PY
echo "yesu shansi production package: PASS"
```

- [ ] **Step 2: 运行测试并确认缺少生产包**

Run: `zsh zhixia-feihualing/tests/test_yesu_shansi_assets.sh`

Expected: 因`episodes/yesu-shansi`生产文件尚不存在而失败。

- [ ] **Step 3: 创建精确配音清单**

创建 `episodes/yesu-shansi/voice-lines.json`：

```json
{
  "episode": "yesu-shansi",
  "theme": "夜宿山寺",
  "theme_slug": "yesu-shansi",
  "audio_slug": "yesu-shansi",
  "lines": [
    {"id": "01-ayan-dialogue", "role": "ayan", "text": "栀夏，这座楼怎么像是修进云里了？", "start_ms": 0},
    {"id": "02-zhixia-dialogue", "role": "zhixia", "text": "山已经很高，楼又站在山顶。", "start_ms": 3200},
    {"id": "03-ayan-dialogue", "role": "ayan", "text": "再上去一点，是不是就能碰到星星？", "start_ms": 6000},
    {"id": "04-zhixia-dialogue", "role": "zhixia", "text": "小声些，这里连风都听得很清楚。", "start_ms": 9300},
    {"id": "05-ayan-dialogue", "role": "ayan", "text": "那天上的人……也会听见吗？", "start_ms": 12200}
  ]
}
```

- [ ] **Step 4: 创建README单集事实源**

在README逐项记录：五句精确时间轴、四个场景边界、全程双角色、Seedance无可辨识人声、环境声硬门禁、11.5秒诗句展示、TTS付费确认门禁、输入输出路径与状态“设计已确认，待场景卡”。

- [ ] **Step 5: 免费预览TTS计划**

Run: `python3 zhixia-feihualing/scripts/generate_episode_audio.py --episode yesu-shansi`

Expected: 只显示5句文本、3句阿砚、2句栀夏、输出目录和预计5次API调用；不读取API Key、不访问网络、不创建MP3。

- [ ] **Step 6: 运行生产包测试并确认通过**

Run: `zsh zhixia-feihualing/tests/test_yesu_shansi_assets.sh`

Expected: `yesu shansi production package: PASS`。

- [ ] **Step 7: 提交单集事实与测试**

```bash
git add zhixia-feihualing/episodes/yesu-shansi/README.md \
  zhixia-feihualing/episodes/yesu-shansi/voice-lines.json \
  zhixia-feihualing/tests/test_yesu_shansi_assets.sh
git commit -m "文档：建立夜宿山寺生产包"
```

### Task 2: 编写并生成四张独立写实场景卡

**Files:**
- Create: `zhixia-feihualing/episodes/yesu-shansi/prompts/scene-cards.md`
- Create: `zhixia-feihualing/episodes/yesu-shansi/assets/scene-cards/01-mountain-temple-medium.png`
- Create: `zhixia-feihualing/episodes/yesu-shansi/assets/scene-cards/02-wooden-stairs-follow.png`
- Create: `zhixia-feihualing/episodes/yesu-shansi/assets/scene-cards/03-star-terrace-medium.png`
- Create: `zhixia-feihualing/episodes/yesu-shansi/assets/scene-cards/04-open-ending-two-shot.png`

**Interfaces:**
- Consumes: 栀夏身份主卡v02、栀夏全身比例卡v02、阿砚固定角色卡和Task 1单集事实。
- Produces: 可同时用于视觉确认和Seedance连续生成的四张9:16角色同框场景卡。

- [ ] **Step 1: 在测试中加入四卡失败检查**

在`test_yesu_shansi_assets.sh`加入：

```zsh
test -s "$episode/prompts/scene-cards.md"
for card in 01-mountain-temple-medium 02-wooden-stairs-follow 03-star-terrace-medium 04-open-ending-two-shot; do
  file="$episode/assets/scene-cards/$card.png"
  test -s "$file"
  dimensions="$(sips -g pixelWidth -g pixelHeight "$file" 2>/dev/null | awk '/pixelWidth/{w=$2}/pixelHeight/{h=$2}END{print w"x"h}')"
  test "$dimensions" = "720x1280" -o "$dimensions" = "941x1672"
done
```

- [ ] **Step 2: 运行测试并确认四卡缺失**

Run: `zsh zhixia-feihualing/tests/test_yesu_shansi_assets.sh`

Expected: 在第一张场景卡的`test -s`处失败。

- [ ] **Step 3: 写四段自包含提示词**

每段都必须逐字包含以下共同锚点：

```text
只输出一张独立9:16竖屏高清图片；画面从头到尾的故事设定只出现一个栀夏和一个阿砚；两者同时清楚可见；使用上传的栀夏身份主卡v02、全身比例卡v02和阿砚固定角色卡；电影级半写实东方角色与高度写实自然环境；真实木构、重力、接触阴影、空气透视和自然星空；不生成文字、字幕、诗句、印章或水印。
```

四段分别落实：

- 卡1：暮色石阶双角色中景，栀夏右、阿砚左，真实山顶木楼与低云，角色占画面主要面积。
- 卡2：木楼梯侧后方双角色跟拍构图，栀夏扶栏、阿砚紧随，台阶、栏杆、立柱和楼层结构连续。
- 卡3：高层露台双角色近中景，阿砚抬一只前爪、栀夏抬头，云海低于栏杆，真实尺度星空。
- 卡4：右下双角色背侧中远景，两者高度至少占画面四分之一；左侧与上方为诗句安全区；阿砚看栀夏、栀夏回看但不回答。

共同禁止：悬空塔、漂浮台阶、人物站在栏杆外、巨大月亮、极光、天宫、光门、神仙、魔法粒子、夸张银河、流星雨、角色单独出现、角色缩成小黑点、栀夏换脸或服装漂移、阿砚物种与配件漂移。

- [ ] **Step 4: 逐张生成并逐张确认**

使用Image Generation逐张生成。每张卡生成后检查双角色身份、人物大小、木楼结构和场景职责；当前卡未确认前不生成下一张。确认后的卡保存到上列固定路径，不覆盖返修前版本，返修使用`-v02`递增。

- [ ] **Step 5: 运行场景卡资产测试**

Run: `zsh zhixia-feihualing/tests/test_yesu_shansi_assets.sh`

Expected: 四张图片均存在且尺寸为720×1280或941×1672；测试继续到Seedance提示词检查。

- [ ] **Step 6: 提交场景卡提示词与确认图片**

```bash
git add zhixia-feihualing/episodes/yesu-shansi/prompts/scene-cards.md \
  zhixia-feihualing/episodes/yesu-shansi/assets/scene-cards
git commit -m "素材：完成夜宿山寺写实场景卡"
```

### Task 3: 编写Seedance连续视频与环境声提示词

**Files:**
- Create: `zhixia-feihualing/episodes/yesu-shansi/prompts/seedance-video.md`
- Modify: `zhixia-feihualing/tests/test_yesu_shansi_assets.sh`

**Interfaces:**
- Consumes: 四张确认场景卡和五句后期对白时间轴。
- Produces: 可直接生成15秒9:16视频的完整提示词与环境声验收清单。

- [ ] **Step 1: 在测试中加入提示词行为检查**

```zsh
seedance="$episode/prompts/seedance-video.md"
for phrase in \
  '栀夏和阿砚从第一帧到最后一帧始终同时出现在画面中' \
  '不得生成任何可辨识对白、旁白、朗诵、吟唱或带人声音乐' \
  '高山风' '衣料摩擦' '双角色脚步' '木阶承重' '一次远处寺钟' \
  '环境声缺失或不同步时不进入后期'; do
  rg -q "$phrase" "$seedance"
done
```

- [ ] **Step 2: 写15秒连续画面提示词**

完整写入五段动作：0—3.2秒石阶仰望、3.2—6.0秒穿云登楼、6.0—9.3秒阿砚抬爪问星星、9.3—12.2秒栀夏示意小声、12.2—15.0秒阿砚回头提问且栀夏不回答。每段同时写明另一个角色的反应，禁止纯风景空镜和单角色镜头。

- [ ] **Step 3: 写分空间环境声提示词**

```text
0—3.2秒：开阔高山风、衣带薄纱摩擦、阿砚一次爪垫落石声、极轻木檐或铜铃晃动。
3.2—6.0秒：栀夏稳步与阿砚轻快脚步分别同步木阶，榫卯低短吱响，风声进入半封闭木楼后变窄。
6.0—10.8秒：露台风声重新变宽，保留衣料和阿砚铃铛细响，山谷远端只出现一次低音量长尾寺钟。
10.8—15.0秒：高山风略降为对白让位，保留极轻木栏和衣带声，最后约0.1秒只有自然风声。
```

背景音乐固定为低存在感古琴、稀疏箫气声和克制弦乐，不使用鼓点、合唱、仙侠高潮或任何人声。

- [ ] **Step 4: 写失败门禁**

出现任一情况即整条退回Seedance重做：任一角色离开画面；角色小到不可辨认；木楼结构断裂或悬空；环境声只有音乐；缺少脚步、木阶或风声空间变化；寺钟连续敲击；出现人物原声、诗句朗诵、仙侠星空、文字或黑屏。

- [ ] **Step 5: 运行生产包测试**

Run: `zsh zhixia-feihualing/tests/test_yesu_shansi_assets.sh`

Expected: `yesu shansi production package: PASS`。

- [ ] **Step 6: 提交Seedance提示词**

```bash
git add zhixia-feihualing/episodes/yesu-shansi/prompts/seedance-video.md \
  zhixia-feihualing/tests/test_yesu_shansi_assets.sh
git commit -m "文档：完成夜宿山寺视频与环境声提示词"
```

### Task 4: 生成并验收Seedance原片

**Files:**
- Create: `zhixia-feihualing/episodes/yesu-shansi/assets/video/content-raw-v01.mp4`
- Create: `zhixia-feihualing/episodes/yesu-shansi/qa-notes.md`
- Modify: `zhixia-feihualing/tests/test_yesu_shansi_assets.sh`

**Interfaces:**
- Consumes: 两张角色主卡、四张场景卡和Task 3完整提示词。
- Produces: 画面与环境声均通过门禁的15秒原片；后期不得以补建音效掩盖原片失败。

- [ ] **Step 1: 付费生成前确认**

向用户展示Seedance模型、15秒、9:16、720P、生成1条和界面显示的实际费用；只有用户明确确认后才生成。

- [ ] **Step 2: 保存原始下载文件**

下载后不覆盖、不重编码，保存为`episodes/yesu-shansi/assets/video/content-raw-v01.mp4`。

- [ ] **Step 3: 扩展原片自动检查**

```zsh
raw="$episode/assets/video/content-raw-v01.mp4"
test -s "$raw"
test "$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=s=x:p=0 "$raw")" = "720x1280"
test "$(ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of csv=p=0 "$raw")" = "24/1"
test -n "$(ffprobe -v error -select_streams a:0 -show_entries stream=codec_name -of csv=p=0 "$raw")"
duration="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$raw")"
awk -v d="$duration" 'BEGIN { exit !(d >= 15.0 && d <= 15.2) }'
ffmpeg -v error -i "$raw" -f null -
```

- [ ] **Step 4: 抽帧检查双角色与结构**

抽取0.2、1.6、3.4、4.8、6.2、7.8、9.5、11.0、12.4、13.8、14.9秒。十一个时间点全部确认：栀夏与阿砚同时可见；身份稳定；人物没有缩成小点；木楼、栏杆和台阶连续；不存在纯风景或黑屏。

- [ ] **Step 5: 分轨试听环境声门禁**

依次试听0—3.2、3.2—6.0、6.0—10.8、10.8—15.0秒，逐项确认高山风、衣料、两类脚步、木阶承重、露台空间变化和一次远钟。若任何关键声源缺失或不同步，记录失败时间点并重新生成Seedance，不下载外部音效补救。

- [ ] **Step 6: 写QA记录并提交原片**

`qa-notes.md`逐项记录十一帧视觉检查和四段环境声结果；全部通过后提交：

```bash
git add zhixia-feihualing/episodes/yesu-shansi/assets/video/content-raw-v01.mp4 \
  zhixia-feihualing/episodes/yesu-shansi/qa-notes.md \
  zhixia-feihualing/tests/test_yesu_shansi_assets.sh
git commit -m "素材：归档夜宿山寺双角色原片"
```

### Task 5: 用户确认后生成固定音色对白

**Files:**
- Create: `zhixia-feihualing/assets/audio/yesu-shansi/*.mp3`
- Create: `zhixia-feihualing/assets/audio/yesu-shansi/audio-metadata.json`
- Create: `zhixia-feihualing/episodes/yesu-shansi/subtitles-yesu-shansi.json`

**Interfaces:**
- Consumes: Task 1的`voice-lines.json`和项目`config/voices.json`固定音色映射。
- Produces: 五句独立MP3、可信元数据和基于真实音频时长的字幕时间轴。

- [ ] **Step 1: 再次运行免费预览并交给用户确认**

Run: `python3 zhixia-feihualing/scripts/generate_episode_audio.py --episode yesu-shansi`

Expected: 五句、5次预计调用、3句阿砚、2句栀夏；不创建音频。

- [ ] **Step 2: 用户确认后执行付费生成**

Run: `python3 zhixia-feihualing/scripts/generate_episode_audio.py --episode yesu-shansi --generate`

手工输入：`GENERATE yesu-shansi`。未收到用户确认时不得输入。

- [ ] **Step 3: 验证真实时长不越界**

从`audio-metadata.json`读取五句真实时长，逐句验证结束时间分别不超过3200、6000、9300、12200和15000毫秒。任一句越界时只调整该句语速或文案版本并提高`revision`，不得压缩到不可理解。

- [ ] **Step 4: 人工试听五句角色一致性**

确认阿砚三句为同一固定音色、栀夏两句为同一固定音色；无错字、吞字、异常重音、断裂尾音和诗句朗诵。最后“吗”在自然语气中于约14.9秒结束。

- [ ] **Step 5: 提交确认后的配音资产**

```bash
git add zhixia-feihualing/assets/audio/yesu-shansi \
  zhixia-feihualing/episodes/yesu-shansi/subtitles-yesu-shansi.json
git commit -m "素材：生成夜宿山寺固定音色对白"
```

### Task 6: 测试先行实现字幕与最终合成

**Files:**
- Create: `zhixia-feihualing/episodes/yesu-shansi/subtitle-plan.json`
- Create: `zhixia-feihualing/scripts/build_yesu_shansi.sh`
- Create: `zhixia-feihualing/tests/test_yesu_shansi_video.sh`
- Create: `zhixia-feihualing/assets/subtitles/yesu-shansi/`
- Create: `zhixia-feihualing/exports/yesu-shansi-subtitled-v01.mp4`
- Modify: `zhixia-feihualing/assets/inventory.csv`

**Interfaces:**
- Consumes: 通过环境声门禁的原片、五句固定音色MP3和真实字幕时间轴。
- Produces: 保留Seedance环境声、无诗句朗诵、结尾显示完整诗句的最终发布成片。

- [ ] **Step 1: 写最终成片失败测试**

```zsh
#!/bin/zsh
set -euo pipefail
project_dir="$(cd "$(dirname "$0")/.." && pwd)"
raw="$project_dir/episodes/yesu-shansi/assets/video/content-raw-v01.mp4"
output="$project_dir/exports/yesu-shansi-subtitled-v01.mp4"
test -s "$output"
test "$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=s=x:p=0 "$output")" = "720x1280"
test "$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of csv=p=0 "$output")" = "h264"
test "$(ffprobe -v error -select_streams a:0 -show_entries stream=codec_name -of csv=p=0 "$output")" = "aac"
test "$(ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of csv=p=0 "$output")" = "24/1"
duration="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$output")"
awk -v d="$duration" 'BEGIN { exit !(d >= 15.0 && d <= 15.2) }'
raw_audio="$(ffmpeg -v error -i "$raw" -map 0:a:0 -f md5 - | sed 's/^MD5=//')"
final_audio="$(ffmpeg -v error -i "$output" -map 0:a:0 -f md5 - | sed 's/^MD5=//')"
test "$raw_audio" != "$final_audio"
ffmpeg -v error -i "$output" -f null -
echo "yesu shansi video: PASS (${duration}s)"
```

- [ ] **Step 2: 运行测试并确认最终成片不存在**

Run: `zsh zhixia-feihualing/tests/test_yesu_shansi_video.sh`

Expected: 在`test -s "$output"`处失败。

- [ ] **Step 3: 创建字幕清单**

五句对白使用`kind: dialogue`和Task 5真实时间轴；另加一项`kind: poem`，开始11500毫秒、结束15000毫秒，正文为`危楼高百尺，手可摘星辰。不敢高声语，恐惊天上人。`，出处为`唐·李白《夜宿山寺》`。诗句只生成透明卡，不关联任何音频。

- [ ] **Step 4: 实现最小合成脚本**

`build_yesu_shansi.sh`必须：调用共享故事字幕渲染器；保留原片视频顺序；将原片音轨全程作为声音床并统一压低到不遮挡对白；按真实时间轴延迟五句TTS；使用`amix`和`alimiter`混音；约11.5—15.0秒叠加完整诗句卡；视频H.264 CRF 18，音频AAC 192kbps，输出15.104秒。不得加入外部风声、脚步、木阶或寺钟音效。

- [ ] **Step 5: 构建并运行自动验证**

```bash
zsh zhixia-feihualing/scripts/build_yesu_shansi.sh
zsh zhixia-feihualing/tests/test_yesu_shansi_assets.sh
zsh zhixia-feihualing/tests/test_story_subtitle_cards.sh
zsh zhixia-feihualing/tests/test_yesu_shansi_video.sh
git diff --check -- zhixia-feihualing/episodes/yesu-shansi zhixia-feihualing/scripts/build_yesu_shansi.sh zhixia-feihualing/tests/test_yesu_shansi_video.sh
```

Expected: 三个测试均输出`PASS`，完整解码无错误，差异检查无输出。

- [ ] **Step 6: 关键帧与最终声音验收**

抽取1.0、4.5、7.5、10.5、12.8和14.9秒：两角色持续同框；对白字幕位于底部；11.5秒后完整诗句位于左侧安全区；诗句不遮挡角色；最后一帧不黑屏。分别用耳机与手机外放试听，确认五句清楚、原环境声仍具有四段空间变化、远钟只出现一次、没有诗句朗诵、最后一句与视频同步结束。

- [ ] **Step 7: 登记资产并提交最终成片**

在`assets/inventory.csv`登记四张场景卡、Seedance原片、五句TTS和最终成片；随后定向提交：

```bash
git add zhixia-feihualing/episodes/yesu-shansi/subtitle-plan.json \
  zhixia-feihualing/assets/subtitles/yesu-shansi \
  zhixia-feihualing/scripts/build_yesu_shansi.sh \
  zhixia-feihualing/tests/test_yesu_shansi_video.sh \
  zhixia-feihualing/assets/inventory.csv \
  zhixia-feihualing/exports/yesu-shansi-subtitled-v01.mp4
git commit -m "功能：完成夜宿山寺诗词小故事"
```

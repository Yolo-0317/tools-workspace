# 《望庐山瀑布》瀑布声混音 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 保留 Seedance 原片五段对白和现有音乐，为《望庐山瀑布》加入随镜头增强、朗诗时让位、结尾保留余韵的大型瀑布环境声，并输出可试听的混音预览。

**Architecture:** 原片归档后始终作为不可覆盖的声音床；瀑布录音作为独立输入，经高低频清理、人声频段避让、响度统一和时间包络处理后与原声混合。画面流直接复制，只有音频重新编码；自动测试负责资产、封装、画面不变和峰值安全，最终用耳机与手机外放完成主观验收。

**Tech Stack:** zsh、FFmpeg、ffprobe、awk、Python 3 标准库、Pixabay Content License 音效素材。

## Global Constraints

- 原始下载文件不得覆盖或原地重编码。
- 本版保留原片对白，不调用豆包 TTS，不做人声分离。
- 不在原片对白上叠加其他对白或朗诗。
- 原片归档路径固定为 `episodes/lushan/assets/video/content-raw-v01.mp4`。
- 瀑布素材路径固定为 `episodes/lushan/assets/audio/waterfall-large-alex-jauk-196149.mp3`。
- 混音预览路径固定为 `exports/lushan-waterfall-mix-preview-v01.mp4`。
- 预览保持 720×1280、24fps、15.104秒、H.264/AAC 立体声。
- 0—4秒水声保持远处感，4—9.7秒逐步增强，9.7—14.8秒相对揭示峰值降低约5dB，14.8秒后恢复并保留约0.3秒余韵。
- 不修改画面、镜头顺序、角色、封面或字幕。
- 所有用户可见文字与汇报禁止 emoji。
- 不提交 `.env`、证书、订阅链接或个人信息。

## File Structure

- `episodes/lushan/assets/video/content-raw-v01.mp4`：归档的 Seedance 原片，后续只读。
- `episodes/lushan/assets/audio/waterfall-large-alex-jauk-196149.mp3`：22秒大型瀑布原始录音。
- `episodes/lushan/assets/audio/waterfall-large-alex-jauk-196149-source.md`：素材页面、作者、许可与下载日期记录。
- `scripts/build_lushan_waterfall_mix.sh`：唯一混音入口，生成预览但不改写源文件。
- `tests/test_lushan_waterfall_assets.sh`：验证原片与瀑布素材可用。
- `tests/test_lushan_waterfall_mix.sh`：验证预览封装、时长、画面流一致和音频安全。
- `exports/lushan-waterfall-mix-preview-v01.mp4`：供用户试听确认的预览。
- `assets/inventory.csv`：登记原片、瀑布素材和混音预览。

---

### Task 1: 归档原片与合法瀑布素材

**Files:**
- Create: `zhixia-feihualing/tests/test_lushan_waterfall_assets.sh`
- Create: `zhixia-feihualing/episodes/lushan/assets/video/content-raw-v01.mp4`
- Create: `zhixia-feihualing/episodes/lushan/assets/audio/waterfall-large-alex-jauk-196149.mp3`
- Create: `zhixia-feihualing/episodes/lushan/assets/audio/waterfall-large-alex-jauk-196149-source.md`

**Interfaces:**
- Consumes: `/Users/huan.yu/Downloads/b163b653-44f6-4bdf-8e58-6815ff8bb0ad.mp4`；Pixabay 素材页 `https://pixabay.com/sound-effects/large-waterfall-sound-196149/`。
- Produces: 可被 Task 2 只读使用的 `content-raw-v01.mp4` 与 `waterfall-large-alex-jauk-196149.mp3`。

- [ ] **Step 1: 写资产失败测试**

使用 `apply_patch` 创建：

```zsh
#!/bin/zsh
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
raw="$project_dir/episodes/lushan/assets/video/content-raw-v01.mp4"
waterfall="$project_dir/episodes/lushan/assets/audio/waterfall-large-alex-jauk-196149.mp3"
source_note="$project_dir/episodes/lushan/assets/audio/waterfall-large-alex-jauk-196149-source.md"

test -s "$raw"
test -s "$waterfall"
test -s "$source_note"
test "$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=s=x:p=0 "$raw")" = "720x1280"
test "$(ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of csv=p=0 "$raw")" = "24/1"
raw_duration="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$raw")"
waterfall_duration="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$waterfall")"
awk -v d="$raw_duration" 'BEGIN { exit !(d >= 15.0 && d <= 15.2) }'
awk -v d="$waterfall_duration" 'BEGIN { exit !(d >= 15.104) }'
rg -q "Alex_Jauk" "$source_note"
rg -q "Pixabay Content License" "$source_note"
rg -q "https://pixabay.com/sound-effects/large-waterfall-sound-196149/" "$source_note"
echo "lushan waterfall assets: PASS"
```

- [ ] **Step 2: 运行测试并确认缺少归档资产**

Run: `zsh zhixia-feihualing/tests/test_lushan_waterfall_assets.sh`

Expected: FAIL at `test -s` because the archived raw video and waterfall asset do not yet exist.

- [ ] **Step 3: 无损归档用户提供的原片**

Run:

```bash
mkdir -p zhixia-feihualing/episodes/lushan/assets/video zhixia-feihualing/episodes/lushan/assets/audio
cp -p /Users/huan.yu/Downloads/b163b653-44f6-4bdf-8e58-6815ff8bb0ad.mp4 zhixia-feihualing/episodes/lushan/assets/video/content-raw-v01.mp4
shasum -a 256 /Users/huan.yu/Downloads/b163b653-44f6-4bdf-8e58-6815ff8bb0ad.mp4 zhixia-feihualing/episodes/lushan/assets/video/content-raw-v01.mp4
```

Expected: 两个 SHA-256 完全一致。

- [ ] **Step 4: 下载指定瀑布录音并记录授权**

通过 Pixabay 素材页 `https://pixabay.com/sound-effects/large-waterfall-sound-196149/` 下载作者 Alex_Jauk 的 22 秒 MP3，保存为：

`zhixia-feihualing/episodes/lushan/assets/audio/waterfall-large-alex-jauk-196149.mp3`

使用 `apply_patch` 创建授权记录，正文固定为：

```markdown
# Large Waterfall Sound 素材来源

- 标题：Large Waterfall Sound
- 作者：Alex_Jauk
- 来源：https://pixabay.com/sound-effects/large-waterfall-sound-196149/
- 许可：Pixabay Content License
- 页面标注：Free for use under the Pixabay Content License
- 下载日期：2026-08-26
- 项目用途：《望庐山瀑布》15秒混音中的大型瀑布环境声
- 本地文件：waterfall-large-alex-jauk-196149.mp3
```

- [ ] **Step 5: 运行资产测试并确认通过**

Run: `zsh zhixia-feihualing/tests/test_lushan_waterfall_assets.sh`

Expected: `lushan waterfall assets: PASS`

- [ ] **Step 6: 提交资产与测试**

```bash
git add zhixia-feihualing/tests/test_lushan_waterfall_assets.sh \
  zhixia-feihualing/episodes/lushan/assets/video/content-raw-v01.mp4 \
  zhixia-feihualing/episodes/lushan/assets/audio/waterfall-large-alex-jauk-196149.mp3 \
  zhixia-feihualing/episodes/lushan/assets/audio/waterfall-large-alex-jauk-196149-source.md
git commit -m "素材：归档庐山原片与瀑布音效"
```

### Task 2: 以测试先行实现分段瀑布混音

**Files:**
- Create: `zhixia-feihualing/tests/test_lushan_waterfall_mix.sh`
- Create: `zhixia-feihualing/scripts/build_lushan_waterfall_mix.sh`
- Create: `zhixia-feihualing/exports/lushan-waterfall-mix-preview-v01.mp4`

**Interfaces:**
- Consumes: Task 1 的原片和瀑布 MP3。
- Produces: 画面码流不变、音频加入瀑布包络的 `lushan-waterfall-mix-preview-v01.mp4`。

- [ ] **Step 1: 写混音失败测试**

使用 `apply_patch` 创建：

```zsh
#!/bin/zsh
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
raw="$project_dir/episodes/lushan/assets/video/content-raw-v01.mp4"
output="$project_dir/exports/lushan-waterfall-mix-preview-v01.mp4"

test -s "$output"
test "$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=s=x:p=0 "$output")" = "720x1280"
test "$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of csv=p=0 "$output")" = "h264"
test "$(ffprobe -v error -select_streams a:0 -show_entries stream=codec_name -of csv=p=0 "$output")" = "aac"
test "$(ffprobe -v error -select_streams a:0 -show_entries stream=sample_rate,channels -of csv=s=x:p=0 "$output")" = "48000x2"
test "$(ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of csv=p=0 "$output")" = "24/1"
duration="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$output")"
awk -v d="$duration" 'BEGIN { exit !(d >= 15.0 && d <= 15.2) }'

raw_video_md5="$(ffmpeg -v error -i "$raw" -map 0:v:0 -c copy -f md5 - | sed 's/^MD5=//')"
output_video_md5="$(ffmpeg -v error -i "$output" -map 0:v:0 -c copy -f md5 - | sed 's/^MD5=//')"
test "$raw_video_md5" = "$output_video_md5"

raw_audio_md5="$(ffmpeg -v error -i "$raw" -map 0:a:0 -f md5 - | sed 's/^MD5=//')"
output_audio_md5="$(ffmpeg -v error -i "$output" -map 0:a:0 -f md5 - | sed 's/^MD5=//')"
test "$raw_audio_md5" != "$output_audio_md5"

max_volume="$(ffmpeg -hide_banner -i "$output" -af volumedetect -f null - 2>&1 | awk '/max_volume:/ {print $(NF-1)}' | tail -1)"
awk -v v="$max_volume" 'BEGIN { exit !(v <= -0.3) }'
ffmpeg -v error -i "$output" -f null -
echo "lushan waterfall mix: PASS (${duration}s, max ${max_volume} dB)"
```

- [ ] **Step 2: 运行测试并确认预览不存在**

Run: `zsh zhixia-feihualing/tests/test_lushan_waterfall_mix.sh`

Expected: FAIL at `test -s` because `lushan-waterfall-mix-preview-v01.mp4` has not been built.

- [ ] **Step 3: 编写最小混音脚本**

使用 `apply_patch` 创建：

```zsh
#!/bin/zsh
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
raw="$project_dir/episodes/lushan/assets/video/content-raw-v01.mp4"
waterfall="$project_dir/episodes/lushan/assets/audio/waterfall-large-alex-jauk-196149.mp3"
output="$project_dir/exports/lushan-waterfall-mix-preview-v01.mp4"

for required in "$raw" "$waterfall"; do
  test -s "$required"
done
mkdir -p "$(dirname "$output")"

ffmpeg -hide_banner -loglevel error -y \
  -i "$raw" -i "$waterfall" \
  -filter_complex "\
    [0:a]aresample=48000[bed];\
    [1:a]atrim=start=0:end=15.104,asetpts=PTS-STARTPTS,aresample=48000,\
      highpass=f=70,lowpass=f=12000,\
      equalizer=f=2200:t=q:w=1.2:g=-4,\
      loudnorm=I=-18:TP=-3:LRA=5,\
      volume='if(lt(t,4),0.20+0.0625*t,if(lt(t,9.5),0.45+0.063636*(t-4),if(lt(t,9.7),0.80-1.75*(t-9.5),if(lt(t,14.8),0.45,0.45+1.151316*(t-14.8)))))':eval=frame,\
      afade=t=in:st=0:d=0.20[waterfall];\
    [bed][waterfall]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,\
      alimiter=limit=0.95:attack=5:release=50[aout]" \
  -map 0:v:0 -map "[aout]" -t 15.104 \
  -c:v copy -c:a aac -b:a 192k -ar 48000 -ac 2 \
  -movflags +faststart "$output"

echo "$output"
```

- [ ] **Step 4: 生成混音预览**

Run: `zsh zhixia-feihualing/scripts/build_lushan_waterfall_mix.sh`

Expected: 输出绝对或项目内预览路径，文件大小大于0。

- [ ] **Step 5: 运行混音测试并确认通过**

Run: `zsh zhixia-feihualing/tests/test_lushan_waterfall_mix.sh`

Expected: `lushan waterfall mix: PASS (15.104000s, max -0.4 dB)`；实际峰值可低于 -0.4dB，但不得高于 -0.3dB。

- [ ] **Step 6: 提交脚本、测试和预览**

```bash
git add zhixia-feihualing/scripts/build_lushan_waterfall_mix.sh \
  zhixia-feihualing/tests/test_lushan_waterfall_mix.sh \
  zhixia-feihualing/exports/lushan-waterfall-mix-preview-v01.mp4
git commit -m "功能：加入庐山瀑布分段混音"
```

### Task 3: 完成客观音频证据与用户试听验收

**Files:**
- Create: `zhixia-feihualing/episodes/lushan/qa-notes.md`
- Modify: `zhixia-feihualing/scripts/build_lushan_waterfall_mix.sh`
- Modify: `zhixia-feihualing/tests/test_lushan_waterfall_mix.sh`
- Regenerate: `zhixia-feihualing/exports/lushan-waterfall-mix-preview-v01.mp4`

**Interfaces:**
- Consumes: Task 2 的首版混音预览。
- Produces: 通过客观指标和用户耳机、手机外放验收的预览，以及可复现的 QA 记录。

- [ ] **Step 1: 生成波形与频谱诊断图**

Run:

```bash
ffmpeg -hide_banner -y -i zhixia-feihualing/exports/lushan-waterfall-mix-preview-v01.mp4 \
  -lavfi "showwavespic=s=1600x500:colors=white" -frames:v 1 /tmp/lushan-waterfall-mix-waveform.png
ffmpeg -hide_banner -y -i zhixia-feihualing/exports/lushan-waterfall-mix-preview-v01.mp4 \
  -lavfi "showspectrumpic=s=1600x700:legend=1:scale=log" -frames:v 1 /tmp/lushan-waterfall-mix-spectrum.png
```

Expected: 两张诊断图均存在且可打开；频谱在全片持续存在宽频水声，9.7秒后不覆盖清晰的人声谐波。

- [ ] **Step 2: 将预览交给用户分别用耳机和手机外放试听**

在 Codex 中播放本地预览：

`![《望庐山瀑布》瀑布声混音预览](/Users/huan.yu/dev/tools-workspace/zhixia-feihualing/exports/lushan-waterfall-mix-preview-v01.mp4)`

请用户按以下时间点试听，不跳项：

- 0.0—2.2秒：远处水声可感知，阿砚第一句清楚。
- 2.2—4.0秒：栀夏回应无双声或回声。
- 4.0—7.1秒：水声明显增强，阿砚“这么大的水声”仍清晰。
- 7.1—9.7秒：抬头时声场扩大，栀夏台词不被遮挡。
- 9.7—14.8秒：瀑布保持巨大感，同时完整听清两句诗。
- 14.8—15.104秒：保留约0.3秒自然余韵，无突然静音。

Expected: 用户明确确认六个检查点全部通过；任一失败只记录对应时间点，并进入 Step 3 调整瀑布层包络或均衡，不改原片声音床。

- [ ] **Step 3: 单变量修正并重跑测试**

若对白被遮挡，只将 `equalizer=f=2200:t=q:w=1.2:g=-4` 的 `g` 调整为 `-6`；若瀑布整体不足，只将 `loudnorm=I=-18` 调整为 `I=-16`。一次只改一个参数，每次执行：

```bash
zsh zhixia-feihualing/scripts/build_lushan_waterfall_mix.sh
zsh zhixia-feihualing/tests/test_lushan_waterfall_mix.sh
```

Expected: 自动测试继续通过，且失败的主观检查点改善；不得同时修改均衡与响度。

- [ ] **Step 4: 写 QA 记录**

使用 `apply_patch` 创建 `episodes/lushan/qa-notes.md`，记录以下固定内容和实际结果：

```markdown
# 《望庐山瀑布》混音质检

## 源文件

- 原片：`assets/video/content-raw-v01.mp4`
- 瀑布素材：`assets/audio/waterfall-large-alex-jauk-196149.mp3`
- 混音预览：`../../exports/lushan-waterfall-mix-preview-v01.mp4`

## 已确认策略

- 保留 Seedance 原片五段对白。
- 不调用豆包 TTS，不叠加第二套对白。
- 瀑布声按远处、增强、朗诗让位、结尾余韵四阶段处理。

## 自动验证

- 画面码流与原片一致：通过
- 输出规格 720×1280、24fps、H.264/AAC、15.104秒：通过
- 音频峰值不高于 -0.3dB：通过
- 完整解码：通过

## 人工试听

- 耳机：通过
- 手机外放：通过
- 五段对白无双声、回声或遮挡：通过
- 4—9.7秒水声增强与画面一致：通过
- 朗诗期间水声让位约5dB：通过
- 结尾约0.3秒瀑布余韵：通过
```

- [ ] **Step 5: 提交 QA 结论与必要的单变量修正**

```bash
git add zhixia-feihualing/episodes/lushan/qa-notes.md \
  zhixia-feihualing/scripts/build_lushan_waterfall_mix.sh \
  zhixia-feihualing/tests/test_lushan_waterfall_mix.sh \
  zhixia-feihualing/exports/lushan-waterfall-mix-preview-v01.mp4
git commit -m "质检：确认庐山瀑布混音预览"
```

### Task 4: 登记资产并交付预览

**Files:**
- Modify: `zhixia-feihualing/assets/inventory.csv`
- Test: `zhixia-feihualing/tests/test_lushan_waterfall_assets.sh`
- Test: `zhixia-feihualing/tests/test_lushan_waterfall_mix.sh`

**Interfaces:**
- Consumes: 已验收的原片、瀑布素材和混音预览。
- Produces: 三条唯一资产记录和用户可直接播放的预览文件。

- [ ] **Step 1: 写资产清单失败检查**

在 `tests/test_lushan_waterfall_assets.sh` 末尾加入：

```zsh
inventory="$project_dir/assets/inventory.csv"
python3 - "$inventory" <<'PY'
import csv
import sys

path = sys.argv[1]
with open(path, encoding="utf-8", newline="") as handle:
    rows = list(csv.DictReader(handle))

required = {
    "lushan-content-raw-v01",
    "lushan-waterfall-sfx-v01",
    "lushan-waterfall-mix-preview-v01",
}
ids = [row["asset_id"] for row in rows]
missing = required.difference(ids)
assert not missing, f"missing inventory rows: {sorted(missing)}"
for asset_id in required:
    assert ids.count(asset_id) == 1, f"duplicate inventory row: {asset_id}"
PY
```

- [ ] **Step 2: 运行资产测试并确认缺少登记**

Run: `zsh zhixia-feihualing/tests/test_lushan_waterfall_assets.sh`

Expected: FAIL with `missing inventory rows`.

- [ ] **Step 3: 添加三条资产记录**

使用 `apply_patch` 向 `assets/inventory.csv` 追加：

```csv
lushan-content-raw-v01,video,望庐山瀑布,content,episodes/lushan/assets/video/content-raw-v01.mp4,available,Seedance,user-generated via web,720×1280；24fps；15.104秒；含五段原片对白、背景音乐与较弱环境声；本版保留原对白
lushan-waterfall-sfx-v01,audio,望庐山瀑布,waterfall-ambience,episodes/lushan/assets/audio/waterfall-large-alex-jauk-196149.mp3,available,Pixabay / Alex_Jauk,Pixabay Content License,22秒大型瀑布环境声；用于远处、增强、朗诗让位与结尾余韵四阶段混音
lushan-waterfall-mix-preview-v01,video,望庐山瀑布,mix-preview,exports/lushan-waterfall-mix-preview-v01.mp4,review,local FFmpeg mix,original project video plus licensed sound effect,720×1280；24fps；15.104秒；保留Seedance原对白与音乐；新增分段大型瀑布声；朗诗期间水声降低约5dB
```

- [ ] **Step 4: 运行全部相关验证**

Run:

```bash
zsh zhixia-feihualing/tests/test_lushan_waterfall_assets.sh
zsh zhixia-feihualing/tests/test_lushan_waterfall_mix.sh
git diff --check -- zhixia-feihualing
```

Expected: 两个测试均输出 `PASS`，`git diff --check` 无输出并返回0。

- [ ] **Step 5: 提交资产登记**

```bash
git add zhixia-feihualing/assets/inventory.csv zhixia-feihualing/tests/test_lushan_waterfall_assets.sh
git commit -m "文档：登记庐山原片与瀑布混音资产"
```

- [ ] **Step 6: 交付试听预览**

向用户提供：

`/Users/huan.yu/dev/tools-workspace/zhixia-feihualing/exports/lushan-waterfall-mix-preview-v01.mp4`

只报告已经由测试和试听证据确认的结果，并明确预览尚未加入最终字幕。

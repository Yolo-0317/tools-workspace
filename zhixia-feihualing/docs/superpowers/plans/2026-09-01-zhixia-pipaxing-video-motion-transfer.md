# 栀夏《琵琶行》参考视频动作迁移 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 生成一段可上传 Seedance 的十五秒无声动作参考视频，并交付以敦煌 v03 栀夏替换参考人物、保留整段动作顺序的迁移版提示词。

**Architecture:**  tracked shell 脚本负责把任意同规格录屏裁边、等比变速、缩放补边并移除音轨；真实参考输出写入已忽略的单集视频目录。独立测试使用本地合成视频验证处理结果，另一个文本测试验证图片与视频职责、空手零乐器边界和纯文字 v01 的非破坏保留。

**Tech Stack:** Zsh、FFmpeg、ffprobe、Python 标准库、Markdown、CSV、ripgrep、Seedance 2.0。

## Global Constraints

- 图片 1 只锁定敦煌十六舞 v03 栀夏的身份、身体比例和全部固定服化道。
- 视频 1 只提供全身动作顺序、落脚、换重、胸腰方向、高低层次、手臂大轨迹、转身、抬腿和节奏。
- 输出动作参考为 720×1280、30 fps、H.264、约 15 秒、无音轨。
- 完整 17.766667 秒参考动作等比例压缩到 15.000 秒，不截断首尾、不插帧、不补帧、不重排动作。
- 裁取区域固定为 `536×1072`、起点 `x=0, y=80`；缩放至 `640×1280` 后左右各补 40 像素黑边。
- 不迁移参考人物、红青服装、背景、视频号界面、字幕、账号、音乐或声音。
- 栀夏全程空手，画面零乐器；蓝橙双层飘带只连接左右上臂后外侧。
- 保留纯文字 `seedance-v01.md` 作为基础级历史方案，新建迁移版，不覆盖旧文件。
- 不调用 Seedance、TTS 或其他付费服务。
- 工作区已有其他改动；每次只显式暂存本计划列出的文件，不使用 `git add .` 或 `git add -A`。

---

### Task 1: 用失败测试定义动作参考处理接口

**Files:**
- Create: `zhixia-feihualing/tests/test_prepare_pipaxing_motion_reference.sh`
- Planned create: `zhixia-feihualing/scripts/prepare_pipaxing_motion_reference.sh`

**Interfaces:**
- Consumes: 命令行参数 `<input-video> <output-video> [target-duration]`。
- Produces: 720×1280、30 fps、H.264、无音轨的视频；目标时长默认为 15 秒，测试可传入 1 秒。

- [ ] **Step 1: 写入真实 FFmpeg 行为测试**

```zsh
#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
script="$project_dir/scripts/prepare_pipaxing_motion_reference.sh"
[[ -x "$script" ]] || { print -u2 -r -- "FAIL: missing executable $script"; exit 1; }

work_dir="$(mktemp -d)"
trap 'rm -rf "$work_dir"' EXIT
input="$work_dir/input.mp4"
output="$work_dir/output.mp4"

ffmpeg -hide_banner -loglevel error \
  -f lavfi -i 'testsrc2=size=592x1280:rate=30:duration=1.2' \
  -f lavfi -i 'sine=frequency=440:sample_rate=44100:duration=1.2' \
  -c:v libx264 -pix_fmt yuv420p -c:a aac -shortest "$input"

"$script" "$input" "$output" 1

python3 - "$output" <<'PY'
import json
from pathlib import Path
import subprocess
import sys

path = Path(sys.argv[1])
assert path.is_file() and path.stat().st_size > 0, "output video missing"
probe = json.loads(subprocess.check_output([
    "ffprobe", "-v", "error", "-show_entries",
    "format=duration:stream=codec_type,codec_name,width,height,r_frame_rate",
    "-of", "json", str(path),
], text=True))
streams = probe["streams"]
video = [stream for stream in streams if stream["codec_type"] == "video"]
audio = [stream for stream in streams if stream["codec_type"] == "audio"]
assert len(video) == 1, "expected exactly one video stream"
assert not audio, "motion reference must not contain audio"
assert video[0]["codec_name"] == "h264", video[0]
assert (video[0]["width"], video[0]["height"]) == (720, 1280), video[0]
assert video[0]["r_frame_rate"] == "30/1", video[0]
duration = float(probe["format"]["duration"])
assert 0.95 <= duration <= 1.05, duration
print("PASS: motion reference preprocessing is reproducible")
PY
```

- [ ] **Step 2: 运行测试确认脚本缺失**

Run:

```bash
chmod +x zhixia-feihualing/tests/test_prepare_pipaxing_motion_reference.sh
zsh zhixia-feihualing/tests/test_prepare_pipaxing_motion_reference.sh
```

Expected: FAIL，错误为缺少可执行的 `scripts/prepare_pipaxing_motion_reference.sh`。

### Task 2: 实现并验证参考视频预处理

**Files:**
- Create: `zhixia-feihualing/scripts/prepare_pipaxing_motion_reference.sh`
- Test: `zhixia-feihualing/tests/test_prepare_pipaxing_motion_reference.sh`
- Local output, ignored: `zhixia-feihualing/episodes/pipaxing-empty-hand-15s/assets/video/motion-reference-v01.mp4`

**Interfaces:**
- Consumes: Task 1 的三个参数和 ffprobe/FFmpeg 可执行文件。
- Produces: 可重复生成且经过流、尺寸、帧率和时长校验的动作参考文件。

- [ ] **Step 1: 写入最小处理脚本**

```zsh
#!/bin/zsh
set -euo pipefail

if (( $# < 2 || $# > 3 )); then
  print -u2 -r -- "usage: $0 <input-video> <output-video> [target-duration]"
  exit 2
fi

input="$1"
output="$2"
target_duration="${3:-15}"
[[ -f "$input" ]] || { print -u2 -r -- "input video not found: $input"; exit 2; }

source_duration="$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$input")"
setpts_factor="$(python3 - "$source_duration" "$target_duration" <<'PY'
import sys
source = float(sys.argv[1])
target = float(sys.argv[2])
if source <= 0 or target <= 0:
    raise SystemExit("durations must be positive")
print(f"{target / source:.9f}")
PY
)"

mkdir -p "${output:h}"
ffmpeg -hide_banner -loglevel error -y -i "$input" -an \
  -vf "crop=536:1072:0:80,setpts=${setpts_factor}*PTS,scale=640:1280:flags=lanczos,pad=720:1280:40:0:black,fps=30" \
  -t "$target_duration" -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p \
  -movflags +faststart "$output"
```

- [ ] **Step 2: 运行合成视频测试确认转绿**

Run:

```bash
chmod +x zhixia-feihualing/scripts/prepare_pipaxing_motion_reference.sh
zsh zhixia-feihualing/tests/test_prepare_pipaxing_motion_reference.sh
```

Expected: `PASS: motion reference preprocessing is reproducible`。

- [ ] **Step 3: 使用用户提供的 AI 视频生成本地十五秒参考文件**

Run:

```bash
zsh zhixia-feihualing/scripts/prepare_pipaxing_motion_reference.sh \
  '/Users/huan.yu/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/wxid_bz3pb6ogfq5t52_505d/msg/video/2026-09/38be6f1db204d8c478a61ae7a042229a.mp4' \
  zhixia-feihualing/episodes/pipaxing-empty-hand-15s/assets/video/motion-reference-v01.mp4 \
  15
```

- [ ] **Step 4: 回读真实输出并确认未进入 Git**

Run:

```bash
ffprobe -v error -show_entries \
  format=duration:stream=codec_type,codec_name,width,height,r_frame_rate \
  -of json \
  zhixia-feihualing/episodes/pipaxing-empty-hand-15s/assets/video/motion-reference-v01.mp4
git check-ignore -v \
  zhixia-feihualing/episodes/pipaxing-empty-hand-15s/assets/video/motion-reference-v01.mp4
```

Expected: 一个 H.264 视频流、720×1280、30/1 fps、时长 14.95—15.05 秒、没有音频流；`git check-ignore` 命中 `episodes/*/assets/video/`。

- [ ] **Step 5: 提交脚本与测试**

```bash
git add zhixia-feihualing/scripts/prepare_pipaxing_motion_reference.sh \
  zhixia-feihualing/tests/test_prepare_pipaxing_motion_reference.sh
git diff --cached --check
git commit -m "功能：增加琵琶行动作参考预处理"
```

### Task 3: 用失败测试定义迁移提示词职责

**Files:**
- Create: `zhixia-feihualing/tests/test_pipaxing_motion_transfer_prompt.sh`
- Planned create: `zhixia-feihualing/episodes/pipaxing-empty-hand-15s/prompts/seedance-motion-transfer-v01.md`
- Planned modify: `zhixia-feihualing/episodes/pipaxing-empty-hand-15s/README.md`
- Planned modify: `zhixia-feihualing/operations/dance-design-history.csv`

**Interfaces:**
- Consumes: 已确认迁移设计中的图片 1、视频 1、保留项、替换项和零乐器边界。
- Produces: 同时检查迁移正文、单集当前状态和台账状态的回归门禁。

- [ ] **Step 1: 写入迁移提示词测试**

```zsh
#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
prompt="$project_dir/episodes/pipaxing-empty-hand-15s/prompts/seedance-motion-transfer-v01.md"
readme="$project_dir/episodes/pipaxing-empty-hand-15s/README.md"
history="$project_dir/operations/dance-design-history.csv"

for required in "$prompt" "$readme" "$history"; do
  [[ -s "$required" ]] || { print -u2 -r -- "FAIL: missing motion-transfer component $required"; exit 1; }
done

python3 - "$prompt" "$readme" "$history" <<'PY'
from pathlib import Path
import csv
import sys

prompt_text = Path(sys.argv[1]).read_text(encoding="utf-8")
readme = Path(sys.argv[2]).read_text(encoding="utf-8")
start = "<!-- SEEDANCE_PROMPT_START -->"
end = "<!-- SEEDANCE_PROMPT_END -->"
assert prompt_text.count(start) == 1
assert prompt_text.count(end) == 1
seedance = prompt_text.split(start, 1)[1].split(end, 1)[0]

required_prompt = [
    "@图片1与@视频1均为AI生成素材",
    "@图片1只提供栀夏的身份与敦煌服化道",
    "@视频1只提供完整动作顺序",
    "落脚、换重、胸腰方向、高低层次、手臂大轨迹、转身、抬腿和节奏",
    "尽量保持@视频1从开场到结尾的动作先后关系",
    "不继承@视频1中的人物",
    "双手全程清楚空置",
    "画面内不出现琵琶或其他乐器",
    "左右上臂后外侧",
    "不生成任何可辨识人声",
]
for phrase in required_prompt:
    assert phrase in seedance, f"missing transfer requirement: {phrase}"

for forbidden in [
    "38be6f1db204d8c478a61ae7a042229a",
    "/Users/",
    "0.000—1.800秒",
    "纵向惊弦",
    "横向回澜",
    "斜向裂帛",
]:
    assert forbidden not in seedance, f"pure-text or local detail leaked: {forbidden}"

assert "当前生成方案：迁移级" in readme
assert "motion-reference-v01.mp4" in readme
assert "seedance-v01.md` 保留为基础级历史方案" in readme

with Path(sys.argv[3]).open(encoding="utf-8", newline="") as handle:
    rows = list(csv.DictReader(handle))
matches = [row for row in rows if row["episode"] == "pipaxing-empty-hand-15s"]
assert len(matches) == 1
row = matches[0]
assert row["climax_family"] == "参考视频整段动作迁移"
assert "迁移级当前方案" in row["notes"]
print("PASS: Pipaxing motion-transfer prompt is ready")
PY
```

- [ ] **Step 2: 运行测试确认迁移提示词缺失**

Run:

```bash
chmod +x zhixia-feihualing/tests/test_pipaxing_motion_transfer_prompt.sh
zsh zhixia-feihualing/tests/test_pipaxing_motion_transfer_prompt.sh
```

Expected: FAIL，首个错误为缺少 `seedance-motion-transfer-v01.md`。

### Task 4: 编写迁移提示词并切换单集当前方案

**Files:**
- Create: `zhixia-feihualing/episodes/pipaxing-empty-hand-15s/prompts/seedance-motion-transfer-v01.md`
- Modify: `zhixia-feihualing/episodes/pipaxing-empty-hand-15s/README.md`
- Modify: `zhixia-feihualing/operations/dance-design-history.csv`
- Test: `zhixia-feihualing/tests/test_pipaxing_motion_transfer_prompt.sh`

**Interfaces:**
- Consumes: Task 2 的 `motion-reference-v01.mp4` 与 Task 3 的固定职责门禁。
- Produces: 可复制的迁移正文、准确的单集当前状态和唯一台账记录。

- [ ] **Step 1: 写入迁移版提示词文件**

文件的使用说明固定为：上传图片 1 的敦煌 v03 栀夏卡和视频 1 的 `motion-reference-v01.mp4`，不上传其他素材；只复制标记之间正文。正文使用以下完整内容：

```text
@图片1与@视频1均为AI生成素材。生成15秒、9:16竖屏、一镜到底的电影级高写实东方舞蹈短片。@图片1只提供栀夏的身份与敦煌服化道；@视频1只提供完整动作顺序、落脚、换重、胸腰方向、高低层次、手臂大轨迹、转身、抬腿和节奏。

使用@图片1中的原创虚构角色栀夏替换@视频1的舞者。栀夏全片保持同一张脸、十八岁年龄感、自然修长身体比例、双环敦煌高髻、莲焰旧金冠、朱砂莲瓣花钿、孔雀蓝与琥珀橙织锦舞衣、象牙白内裙、浅青玉配饰和舞履。蓝橙双层飘带始终稳定连接在左右上臂后外侧，双手全程清楚空置，掌腕舒展自然。

严格参考@视频1的整段身体表演，尽量保持@视频1从开场到结尾的动作先后关系、每次落脚和换重、胸腰方向、侧腰幅度、连续改面、穿手、转身、抬腿、手臂大轨迹和整体节奏。动作迁移优先级依次为落脚与重心、躯干方向、腿部剪影、手臂大轨迹和节奏；细小手指允许为保持自然人体而简化。不要重新编排另一套三高潮动作，不把动作改成普通走路、持续奔跑、原地摆臂或无落脚的连续转圈。

不继承@视频1中的人物、脸、身体特征、发型、冠饰、红青服装、长绸、背景、灯光、文字、字幕、账号、按钮、界面、logo、水印、音乐或声音。@视频1中的衣料轨迹不作为栀夏飘带连接方式；只迁移身体动作，栀夏的上臂双层飘带按照@图片1的固定根部和真实布料惯性自然响应。

最终场景为同一座盛唐殿廊夜景。深红漆木柱列、赭褐石地、两侧低亮暖金油灯和少量旧纱幔形成稳定纵深，中央舞区净空。摄影机保持@视频1以正面和三分之四面为主的稳定中全景、人物占比和连续跟随节奏，同时完整显示栀夏头顶、双手、裙摆、鞋履和脚下承重；不继承录屏界面造成的遮挡或裁切。

栀夏从凝神聆听转为明亮专注，不直视镜头互动。皮肤保留自然毛孔和细小绒毛，发丝、织锦、薄罗、旧金、石地和油灯具有真实材质、重量、惯性、碰撞与环境光响应。转身和抬腿后保持同一人物身份、妆发、冠饰、服装、人体结构、手脚数量和真实承重。

声音只生成原创、非现成歌曲旋律的清亮弹拨音色、克制低频鼓点、衣料声、落脚声和殿廊空间回响，为后期栀夏朗诵保留中频空间。不生成任何可辨识人声、对白、旁白、诗词朗诵、吟唱、歌词、耳语或连续说话口型，不继承@视频1的原音频。

画面内不出现琵琶或其他乐器，不出现乐伎、演奏者、乐器剪影、乐器陈设、弹奏、抱琴或拨弦动作。栀夏不抓握飘带、袖口或裙片；上臂飘带不缠腕、不穿掌、不增生、不换色、不变成手持长绸。全片保持一个人物、一个殿廊空间和连续动作，不出现第二人物、第二场景、琴弦形光线、法阵、符文、粒子爆炸、字幕、标题、印章、界面、logo或水印。
```

- [ ] **Step 2: 更新 README 的当前输入与状态**

在“单集定位”中把状态改为：

```markdown
- 当前生成方案：迁移级；敦煌 v03 栀夏图片锁身份，十五秒无声 AI 舞蹈视频迁移动作。
- 状态：迁移版提示词和本地动作参考均已准备；尚未付费生成视频。
```

把“唯一上传图”改为“当前上传素材”，明确：

```markdown
1. 图片 1：当前有效的栀夏敦煌十六舞 v03 Seedance 上传版，只锁身份与服化道。
2. 视频 1：`assets/video/motion-reference-v01.mp4`，只提供动作顺序、重心、肢体轨迹和节奏。

`prompts/seedance-v01.md` 保留为基础级历史方案；当前使用 `prompts/seedance-motion-transfer-v01.md`。
```

把“参考视频只供人工观察、不上传”替换为：

```markdown
- 参考视频为用户确认的 AI 生成素材，预处理后只迁移动作；不继承人物、服装、背景、界面、字幕或音轨。
```

- [ ] **Step 3: 更新唯一舞蹈台账记录**

在 `pipaxing-empty-hand-15s` 这一行只修改以下字段，其余空手、服装和承接物字段保持原值：

```text
movement=按视频1迁移连续改面、侧腰、穿手、转身、抬腿与完整节奏
climax_family=参考视频整段动作迁移
rotation=随视频1原动作迁移；保持清楚落脚与承重
body_level=随视频1高低层次迁移
opening_silhouette=视频1开场高低臂全身轮廓替换为栀夏
arm_path=随视频1手臂大轨迹迁移；细小手指自然简化
leg_silhouette=随视频1落脚、换重、抬腿与转身迁移
climax_window=完整15秒动作序列
camera_reaction=参考视频稳定正面与三分之四面中全景
camera_climax=随视频1连续跟随节奏
ending=按视频1结尾动作余势结束
notes=迁移级当前方案；敦煌v03图片锁身份；无声AI视频只迁移动作；单人空手；画面零乐器；无阿砚；纯文字v01保留为历史方案
peak_sequence=视频1完整动作顺序
peak_directions=随视频1方向变化
peak_windows=完整15秒
carrier_trajectories=上臂双带只响应迁移后的身体动作；不继承参考长绸
camera_peak_reactions=随视频1稳定中全景与连续节奏
```

- [ ] **Step 4: 让旧门禁只验证基础级历史文件**

在 `test_pipaxing_empty_hand_15s_prompt.sh` 中保留 `seedance-v01.md` 的全部正文、诗句、空手和零乐器断言；共享台账部分删除下面两条已经被迁移方案覆盖的旧动作断言：

```python
assert row["peak_sequence"] == "纵向惊弦；横向回澜；斜向裂帛"
assert row["peak_directions"] == "纵向；横向；斜向纵深"
```

共享台账部分最终只保留：

```python
assert row["status"] == "designed", "Pipaxing status must be designed"
assert row["carrier"] == "蓝橙双层飘带与真实长影"
```

- [ ] **Step 5: 运行新旧门禁与公共规则**

Run:

```bash
zsh zhixia-feihualing/tests/test_prepare_pipaxing_motion_reference.sh
zsh zhixia-feihualing/tests/test_pipaxing_motion_transfer_prompt.sh
zsh zhixia-feihualing/tests/test_pipaxing_empty_hand_15s_prompt.sh
zsh zhixia-feihualing/tests/test_three_equal_climaxes_rules.sh
zsh zhixia-feihualing/tests/test_zhixia_dance_not_running_rules.sh
awk -F, 'NF != 25 { print NR ":" NF; bad=1 } END { exit bad }' \
  zhixia-feihualing/operations/dance-design-history.csv
```

Expected: 五个测试均输出 PASS；CSV 列数检查无输出。

- [ ] **Step 6: 提交迁移提示词、状态与门禁**

```bash
git add zhixia-feihualing/tests/test_pipaxing_motion_transfer_prompt.sh \
  zhixia-feihualing/tests/test_pipaxing_empty_hand_15s_prompt.sh \
  zhixia-feihualing/episodes/pipaxing-empty-hand-15s/README.md \
  zhixia-feihualing/episodes/pipaxing-empty-hand-15s/prompts/seedance-motion-transfer-v01.md \
  zhixia-feihualing/operations/dance-design-history.csv
git diff --cached --check
git diff --cached --name-only
git commit -m "内容：升级琵琶行参考视频动作迁移"
```

- [ ] **Step 7: 最终回读与用户交付**

Run:

```bash
ffprobe -v error -show_entries \
  format=duration:stream=codec_type,codec_name,width,height,r_frame_rate \
  -of json \
  zhixia-feihualing/episodes/pipaxing-empty-hand-15s/assets/video/motion-reference-v01.mp4
zsh zhixia-feihualing/tests/test_pipaxing_motion_transfer_prompt.sh
git log -2 --oneline
git status --short -- \
  zhixia-feihualing/scripts/prepare_pipaxing_motion_reference.sh \
  zhixia-feihualing/tests/test_prepare_pipaxing_motion_reference.sh \
  zhixia-feihualing/tests/test_pipaxing_motion_transfer_prompt.sh \
  zhixia-feihualing/tests/test_pipaxing_empty_hand_15s_prompt.sh \
  zhixia-feihualing/episodes/pipaxing-empty-hand-15s \
  zhixia-feihualing/operations/dance-design-history.csv
```

Expected: 参考视频规格正确；迁移提示词测试 PASS；两个提交分别对应视频预处理和迁移内容；所有 tracked 任务文件干净。向用户提供动作参考视频、迁移提示词和 README 的可点击路径，并明确尚未调用 Seedance 或其他付费服务。

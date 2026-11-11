# 栀夏《琵琶行》十五秒空手舞 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付一套可直接用于 Seedance 的《琵琶行》十五秒栀夏原创空手舞单集说明、正式提示词、自动验证和舞蹈去重登记。

**Architecture:** 单集目录保存对人可读的定位与对模型可复制的提示词，独立 shell 测试锁定角色、时间窗、空手和零乐器边界，公共 CSV 登记视觉指纹并避免与近期敦煌舞重复。只完成文字生产包，不上传参考视频、不生成付费视频，也不制作后期音频与字幕。

**Tech Stack:** Markdown、Zsh、Python 标准库、CSV、ripgrep、Seedance 2.0。

## Global Constraints

- 采用栀夏敦煌十六舞 v03 固定身份与服化道，唯一角色输入为当前有效的敦煌 v03 Seedance 上传版。
- 竖屏、单人、十五秒、同一连续空间，不安排阿砚或其他人物。
- 栀夏双手全程空着；画面内不出现琵琶或其他乐器，也不出现演奏者、乐器剪影或乐器陈设。
- 蓝橙双层飘带只连接左右上臂后外侧；不得抓握、缠腕、穿掌、增生或变成手持长绸。
- 第一秒进入主体舞句；三次高潮固定为 0.000—1.800、4.800—7.000、10.000—13.200 秒。
- 三次高潮分别形成纵向、横向和斜向纵深轮廓；不以走路、奔跑、原地摆臂或连续转圈替代舞蹈。
- 只吸收参考视频的抽象节奏和全身构图经验，不复刻具体动作顺序、人物、画面、运镜或音轨。
- 只完成文字、测试和台账，不调用 Seedance、TTS 或其他付费服务。
- 工作区存在其他未提交改动；每次只显式暂存本计划列出的文件，不使用 `git add .` 或 `git add -A`。

---

### Task 1: 建立单集提示词回归门禁

**Files:**
- Create: `zhixia-feihualing/tests/test_pipaxing_empty_hand_15s_prompt.sh`
- Reference: `zhixia-feihualing/docs/superpowers/specs/2026-09-01-zhixia-pipaxing-empty-hand-dance-design.md`

**Interfaces:**
- Consumes: 已确认设计中的角色版本、六段时间结构、零乐器边界和参考视频使用边界。
- Produces: 退出码为 0/1 的单集校验入口；Task 2 和 Task 3 均通过它验收。

- [ ] **Step 1: 写入初始失败测试**

创建可执行测试文件，写入以下内容：

```zsh
#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
readme="$project_dir/episodes/pipaxing-empty-hand-15s/README.md"
prompt="$project_dir/episodes/pipaxing-empty-hand-15s/prompts/seedance-v01.md"

for required in "$readme" "$prompt"; do
  [[ -s "$required" ]] || { print -u2 -r -- "FAIL: missing Pipaxing component $required"; exit 1; }
done

python3 - "$readme" "$prompt" <<'PY'
from pathlib import Path
import sys

readme = Path(sys.argv[1]).read_text(encoding="utf-8")
text = Path(sys.argv[2]).read_text(encoding="utf-8")
start_marker = "<!-- SEEDANCE_PROMPT_START -->"
end_marker = "<!-- SEEDANCE_PROMPT_END -->"

assert text.count(start_marker) == 1, "prompt must contain one start marker"
assert text.count(end_marker) == 1, "prompt must contain one end marker"
seedance = text.split(start_marker, 1)[1].split(end_marker, 1)[0]

required_prompt = [
    "原创虚构角色栀夏",
    "15秒、9:16竖屏、一镜到底",
    "左右上臂后外侧",
    "双手全程清楚空置",
    "0.000—1.800秒",
    "0.300秒内踏步换重",
    "1.800—4.800秒",
    "4.800—7.000秒",
    "7.000—10.000秒",
    "10.000—13.200秒",
    "13.200—15.000秒",
    "纵向提展",
    "横向反向弧",
    "前低后高的斜向纵深长线",
    "真实长影",
    "画面内不出现琵琶或其他乐器",
    "不生成任何可辨识人声",
]
for phrase in required_prompt:
    assert phrase in seedance, f"missing requirement: {phrase}"

required_readme = [
    "唐·白居易《琵琶行》",
    "大弦嘈嘈如急雨",
    "大珠小珠落玉盘",
    "敦煌十六舞 v03",
    "双手全程空着",
    "画面零乐器",
]
for phrase in required_readme:
    assert phrase in readme, f"README missing requirement: {phrase}"

for forbidden in [
    "38be6f1db204d8c478a61ae7a042229a",
    "微信视频号",
    "复刻热门舞蹈",
    "照着参考视频跳",
    "@视频1",
    "assets/characters/",
    ".jpg",
    ".png",
]:
    assert forbidden not in seedance, f"reference or internal detail leaked: {forbidden}"

print("PASS: Pipaxing prompt package is complete")
PY
```

- [ ] **Step 2: 增加可执行权限并运行测试，确认缺失单集文件**

Run:

```bash
chmod +x zhixia-feihualing/tests/test_pipaxing_empty_hand_15s_prompt.sh
zsh zhixia-feihualing/tests/test_pipaxing_empty_hand_15s_prompt.sh
```

Expected: FAIL，首个错误为缺少 `episodes/pipaxing-empty-hand-15s/README.md`。

- [ ] **Step 3: 提交初始失败门禁**

```bash
git add zhixia-feihualing/tests/test_pipaxing_empty_hand_15s_prompt.sh
git diff --cached --check
git commit -m "测试：建立琵琶行空手舞提示词门禁"
```

### Task 2: 建立单集说明与 Seedance 正式提示词

**Files:**
- Create: `zhixia-feihualing/episodes/pipaxing-empty-hand-15s/README.md`
- Create: `zhixia-feihualing/episodes/pipaxing-empty-hand-15s/prompts/seedance-v01.md`
- Test: `zhixia-feihualing/tests/test_pipaxing_empty_hand_15s_prompt.sh`

**Interfaces:**
- Consumes: Task 1 的固定短语门禁和设计稿的动作结构。
- Produces: 可供人工核对的单集真源，以及标记之间可直接复制到 Seedance 的正文。

- [ ] **Step 1: 写入单集 README**

README 必须按下面结构写成完整文本，不加入生成结果或尚未发生的状态：

```markdown
# 《琵琶行》15 秒空手舞

## 单集定位

- 作品：唐·白居易《琵琶行》意象原创诗舞。
- 角色：栀夏，使用敦煌十六舞 v03 固定身份与服化道。
- 规格：15 秒、9:16 竖屏、单人、一镜到底、三次同等强度高潮。
- 状态：设计已确认，正式 Seedance 提示词已准备；尚未付费生成视频。
- 核心边界：双手全程空着，画面零乐器，不安排阿砚或其他人物。

## 后期诗文

唐·白居易《琵琶行》：

> 大弦嘈嘈如急雨，小弦切切如私语。
>
> 嘈嘈切切错杂弹，大珠小珠落玉盘。

诗句只用于后期栀夏朗诵和竖排字幕，不转译成弹琴、抱琴或拨弦动作。

## 唯一上传图

只上传当前有效的栀夏敦煌十六舞 v03 Seedance 上传版。不得同时上传敦煌 v01、v02、日常 v04、九歌角色卡、动作图、场景图或用户提供的热门视频。

## 诗舞事件

无形弦声使静止的灯影和人物长影逐层苏醒。栀夏以纵向提展、横向回弹和斜向提转推动长影从向上拉长、向侧方展开到沿地面纵深扩散；舞后留下仍未停尽的身体与长影余势。

## 三次高潮

| 时间 | 身体高潮 | 长影反馈 | 镜头反馈 |
| --- | --- | --- | --- |
| 0.000—1.800 秒 | 高低臂蓄势经踏步换重形成纵向提展 | 向上拉长 | 轻微抬升 |
| 4.800—7.000 秒 | 宽侧弓、胸腰拧倾与双臂横向反向展开 | 向侧方展开后回收 | 有限横移 |
| 10.000—13.200 秒 | 落脚承重后斜向提转，形成前低后高纵深长线 | 沿地面向画面深处扩散 | 短促微推 |

13.200—15.000 秒继续落脚换重和一次非对称高低臂变化，在动作余势中结束。

## 生成边界

- 画面内不出现琵琶或其他乐器、乐伎、演奏者、乐器剪影或陈设。
- 栀夏双手全程空着，不抓飘带、袖口或裙片，不模拟弹奏、抱琴或拨弦。
- 蓝橙双层飘带始终固定在左右上臂后外侧，不缠腕、不穿掌、不增生、不变成手持长绸。
- 不持续走路、奔跑、原地摆臂或连续转圈；每次改面后都有清楚落脚与承重。
- 参考视频只供人工观察抽象节奏和全身构图，不上传、不复制具体动作顺序和音轨。
- Seedance 原片无人声；四句诗、字幕、封面和发布文案均在原片通过后另行制作。
```

- [ ] **Step 2: 写入正式提示词文件与使用说明**

文件开头写明只上传敦煌 v03 唯一角色图；正文必须置于唯一一对 `SEEDANCE_PROMPT_START` 与 `SEEDANCE_PROMPT_END` 标记之间。正文使用下面的完整内容：

```text
生成15秒、9:16竖屏、一镜到底的电影级高写实东方诗舞短片。原创虚构角色栀夏是全片持续可见的唯一人物，参考上传图片保持同一张脸、十八岁年龄感、自然修长比例、双环敦煌高髻、莲焰旧金冠、朱砂莲瓣花钿、孔雀蓝与琥珀橙织锦舞衣、象牙白内裙、浅青玉配饰和舞履。蓝橙双层飘带全程稳定连接在左右上臂后外侧，双手全程清楚空置，掌腕舒展自然。

全片发生在同一座盛唐殿廊夜景。深红漆木柱列与墙地交界形成固定纵深锚点，赭褐石地完整承接栀夏双脚和接触阴影，少量暖金油灯固定分布在两侧远处，旧纱幔保持低亮静止，中央舞区净空。第一帧已经显示栀夏完整全身、脚下落点、柱列纵深和由油灯形成的真实长影。长影是全片唯一变化象征，初始贴近人物脚下，最终沿石地向画面深处延伸。

0.000—1.800秒，第一帧栀夏处于尚未完成的高低臂斜向蓄势，一臂继续向上打开，另一臂从胸腰外侧向下展开，前腿承重，后腿轻点，三分之四正面脸部清楚可见。0.300秒内踏步换重，腿部蹬地和胸腰提起共同带动双臂形成上下错层大弧；0.800秒内形成完整抓眼轮廓，1.000秒内进入纵向提展主体舞句。真实长影在动作发生后向上拉长，摄影机从略低正面中全景轻微抬升并回到完整全身基准，人物高度约为画面的65%—72%。

1.800—4.800秒，栀夏只用一至两步交叉换重离开纵向长线，胸腰先拧转，头部与视线随后跟进，双臂从上下错层收为身前交叉弧再向左右分开。落脚、承重、脸部和双手持续可见，身体不断流动，不站住等待。

4.800—7.000秒，栀夏落入宽幅侧弓，重心清楚下沉，胸腰向侧后方拧倾，双臂一前一后形成横向反向弧，再由承重腿反蹬带动身体回弹。腿部承重、胸腰侧倾与双臂同时形成第二个完整全身高潮。真实长影在动作之后向侧方展开再回收，两侧旧纱幔只产生一次低幅横向摆动；摄影机沿同一主路径作有限横移后回到中全景。

7.000—10.000秒，栀夏从侧弓回正，以一次落脚换重接半圈以内的连续翻身，翻身进入和离开两个节点面部可辨；随后前腿提起形成短暂的不对称腿部剪影，再以清楚落脚和承重转入第三高潮。长影只沿刚才的真实光照关系继续变化，不产生新的特效机制。

10.000—13.200秒，前腿落地后立即蹬地，栀夏以一屈一展的腿部关系完成斜向提转，胸腰从收束转为大开幅，双臂形成前低后高的斜向纵深长线。落脚、承重、提转和打开组成第三个完整发力链，主要爆发在12.800秒前形成。蓝橙双层飘带产生前后错层的真实衣料轨迹，真实长影在身体动作之后沿石地向画面深处扩散；摄影机沿原轴短促微推，人物不缩小，第三高潮强度不低于前两次。

13.200—15.000秒，栀夏在第三高潮余势中再次落脚换重，双臂改变一次高低方向，目光跟随斜上方手臂轨迹。身体、裙摆、上臂飘带和真实长影保持自然惯性，最后0.300秒才接近未完全闭合的斜向舞姿，在动作未尽时结束。

人物从凝神聆听转为明亮专注，视线依次落在高低臂轨迹、侧方长影和斜向纵深方向，不直视镜头互动。摄影机始终沿略低正面中全景的同轴小范围伴随路径运动，三次高潮分别轻微抬升、有限横移和短促微推，每次反应后都恢复完整全身、双脚和地面接触可见。皮肤保留自然毛孔和细小绒毛，发丝、织锦、薄罗、旧金、石地、油灯和阴影具有真实材质、重量、惯性、碰撞与环境光响应。

声音使用原创、非现成歌曲旋律的清亮弹拨音色与克制低频鼓点，三次身体高潮各有一次同等强度动作重音；保留衣料声、落脚声、微弱灯火声和殿廊空间回响，音乐为后期栀夏朗诵保留中频空间。不生成任何可辨识人声、对白、旁白、诗词朗诵、吟唱、歌词、耳语或连续说话口型。

画面内不出现琵琶或其他乐器，不出现乐伎、演奏者、乐器剪影、乐器陈设、弹奏、抱琴或拨弦动作。栀夏不抓握飘带、袖口或裙片；上臂飘带不缠腕、不穿掌、不增生、不换色、不变成手持长绸。全片保持一个人物、一个殿廊空间、一种真实长影变化和一条摄影机主路径；不出现普通走路、持续奔跑、连续原地转圈、无因光效、琴弦形光线、乐器轮廓、法阵、符文、粒子爆炸、第二事件、第二场景、字幕、标题、印章、界面、logo或水印。
```

- [ ] **Step 3: 运行单集测试并确认通过**

Run:

```bash
zsh zhixia-feihualing/tests/test_pipaxing_empty_hand_15s_prompt.sh
git diff --check -- \
  zhixia-feihualing/episodes/pipaxing-empty-hand-15s/README.md \
  zhixia-feihualing/episodes/pipaxing-empty-hand-15s/prompts/seedance-v01.md
```

Expected: `PASS: Pipaxing prompt package is complete`；格式检查无输出。

- [ ] **Step 4: 提交单集说明与提示词**

```bash
git add zhixia-feihualing/episodes/pipaxing-empty-hand-15s/README.md \
  zhixia-feihualing/episodes/pipaxing-empty-hand-15s/prompts/seedance-v01.md
git diff --cached --check
git commit -m "内容：编写栀夏琵琶行空手舞提示词"
```

### Task 3: 登记舞蹈视觉指纹并完成总验收

**Files:**
- Modify: `zhixia-feihualing/tests/test_pipaxing_empty_hand_15s_prompt.sh`
- Modify: `zhixia-feihualing/operations/dance-design-history.csv`
- Verify: `zhixia-feihualing/episodes/pipaxing-empty-hand-15s/README.md`
- Verify: `zhixia-feihualing/episodes/pipaxing-empty-hand-15s/prompts/seedance-v01.md`

**Interfaces:**
- Consumes: Task 2 的最终三高潮动作、承接物轨迹和摄影机反馈。
- Produces: 公共去重台账中的唯一 `pipaxing-empty-hand-15s` 记录，以及覆盖整个制作包的最终验证证据。

- [ ] **Step 1: 扩展测试以校验 CSV 唯一记录**

在 Task 1 的 Python 检查后追加第三个参数 `history_file`，并加入以下校验：

```python
import csv

with Path(sys.argv[3]).open(encoding="utf-8", newline="") as handle:
    rows = list(csv.DictReader(handle))
matches = [row for row in rows if row["episode"] == "pipaxing-empty-hand-15s"]
assert len(matches) == 1, "dance history must contain one Pipaxing entry"
row = matches[0]
assert row["status"] == "designed", "Pipaxing status must be designed"
assert row["peak_sequence"] == "纵向惊弦；横向回澜；斜向裂帛"
assert row["peak_directions"] == "纵向；横向；斜向纵深"
assert row["carrier"] == "蓝橙双层飘带与真实长影"
```

同步把 shell 调用改为：

```zsh
history_file="$project_dir/operations/dance-design-history.csv"
python3 - "$readme" "$prompt" "$history_file" <<'PY'
```

- [ ] **Step 2: 运行扩展测试，确认台账记录缺失**

Run:

```bash
zsh zhixia-feihualing/tests/test_pipaxing_empty_hand_15s_prompt.sh
```

Expected: FAIL，错误为 `dance history must contain one Pipaxing entry`。

- [ ] **Step 3: 在公共台账末尾追加唯一记录**

追加下面这一行，不修改表头或既有记录：

```csv
pipaxing-empty-hand-15s,白居易《琵琶行》,高低臂斜向蓄势踏步提展,一至两步交叉换重转侧弓再半圈翻身提腿,三高潮空手舞序列,一次半圈以内翻身；零连续原地旋转,低位向上；宽侧弓下沉；斜向提转,三分之四正面高低臂斜线转纵向提展,上下错层大弧；横向反向弧；前低后高纵深长线,前腿承重后腿轻点；宽侧弓；一屈一展斜向提转,蓝橙双层飘带与真实长影,纵向上扬；横向展开；斜向纵深错层,真实灯影和人物长影,向上拉长；侧方展开；向纵深扩散,0.000—1.800秒；4.800—7.000秒；10.000—13.200秒,略低正面中全景同轴小范围伴随,轻微抬升；有限横移；短促微推,落脚换重与高低臂余势中切断,designed,敦煌v03单人空手；画面零乐器；无阿砚；参考视频只作人工抽象研究,纵向惊弦；横向回澜；斜向裂帛,纵向；横向；斜向纵深,0.000—1.800秒；4.800—7.000秒；10.000—13.200秒,双带上扬与长影拉长；双臂反向与长影侧展；双带纵深与长影深扩,轻微抬升；有限横移；短促微推
```

- [ ] **Step 4: 运行完整验证并检查只改动目标文件**

Run:

```bash
zsh zhixia-feihualing/tests/test_pipaxing_empty_hand_15s_prompt.sh
awk -F, 'NF != 25 { print NR ":" NF; bad=1 } END { exit bad }' zhixia-feihualing/operations/dance-design-history.csv
git diff --check -- \
  zhixia-feihualing/tests/test_pipaxing_empty_hand_15s_prompt.sh \
  zhixia-feihualing/operations/dance-design-history.csv \
  zhixia-feihualing/episodes/pipaxing-empty-hand-15s/README.md \
  zhixia-feihualing/episodes/pipaxing-empty-hand-15s/prompts/seedance-v01.md
git status --short
```

Expected: 单集测试输出 `PASS: Pipaxing prompt package is complete`；CSV 列数检查和格式检查无输出；`git status` 中允许存在用户原有改动，但本任务新增或修改项只包含上述四个文件。

- [ ] **Step 5: 提交台账与最终门禁**

```bash
git add zhixia-feihualing/tests/test_pipaxing_empty_hand_15s_prompt.sh \
  zhixia-feihualing/operations/dance-design-history.csv
git diff --cached --check
git diff --cached --name-only
git commit -m "维护：登记琵琶行空手舞视觉指纹"
```

- [ ] **Step 6: 回读提交与交付范围**

Run:

```bash
git log -3 --oneline
git show --stat --oneline HEAD
zsh zhixia-feihualing/tests/test_pipaxing_empty_hand_15s_prompt.sh
```

Expected: 最近三次提交分别对应测试门禁、单集提示词和视觉指纹；最终测试再次输出 PASS。向用户提供 README 与 `seedance-v01.md` 的可点击路径，并明确尚未执行付费生成、配音、字幕、封面或发布。

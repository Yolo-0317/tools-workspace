# 栀夏专属古典舞动作库 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立可复用的栀夏中国古典舞动作库，把舞蹈调用门禁接入电影级写实视觉规范，并为“忽如一夜春风来，千树万树梨花开”完成 D01“雪醒梨开”单集选型与三张状态卡提示词。

**Architecture:** 使用一份通用舞蹈库作为动作单一事实源，`realistic-visual-style.md` 只保存调用入口和全局门禁；当前雪诗目录只引用 D01 并记录当集环境、动作适配和状态卡，不复制整份通用规则。用一个独立 zsh 测试验证动作库结构、视觉规范入口、单集选型和三张状态卡的关键约束。

**Tech Stack:** Markdown、zsh、ripgrep、现有 `zhixia-feihualing/tests/*.sh` 文档规则测试模式。

## Global Constraints

- 用户可见内容、文档标题和测试输出禁止 emoji。
- 舞蹈限定为中国古典舞；以身韵为骨架、汉唐气韵为人物风格，不混入现代舞、芭蕾组合、敦煌飞天、胡旋舞或民族民间舞语汇。
- 单条 10 秒诗镜只选择一个连续舞蹈母题、一个 Mxx 镜头母题、一个 Hxx 主特效和唯一视觉承接物。
- 专业术语必须转译为可见的身体部位、运动路径、速度、角度、重心和结束位置，不能只写动作名称。
- 栀夏最多完成两次换重、两至三步和一次不超过 180 度的连续转身；默认转身范围为 90 至 135 度。
- 栀夏现有薄罗大袖衫不是专业水袖；永久禁止抛袖、抓袖、绕袖、甩长水袖、双袖持续遮镜和衣袖无限延长。
- 栀夏与阿砚身份、结构、材质和角色占比优先于舞蹈、景观、雪粒和运镜。
- Seedance 只生成画面、背景音乐和自然环境声；不生成可辨识人声、对白、朗诵、吟唱或中文文字。
- 本计划只创建和修改文档与规则测试，不生成图片、视频、TTS 或付费素材，不修改已经发布的成片。
- 每个 Git 提交只包含当前任务列出的文件，提交信息使用中文。

---

### Task 1: 建立舞蹈库文档规则测试

**Files:**
- Create: `zhixia-feihualing/tests/test_classical_dance_library_rules.sh`
- Reference: `zhixia-feihualing/tests/test_realistic_visual_style_rules.sh`
- Reference: `zhixia-feihualing/tests/test_cinematic_vfx_library_rules.sh`

**Interfaces:**
- Consumes: 项目根目录解析模式 `${0:A:h:h}` 和 `rg -qF` 文档断言模式。
- Produces: 可单独运行的 `tests/test_classical_dance_library_rules.sh`，后续任务逐步使其从失败变为通过。

- [ ] **Step 1: 创建首版失败测试**

创建以下完整测试文件，只先约束通用动作库本身；此时 `docs/zhixia-classical-dance-library.md` 尚不存在，测试必须失败。

```zsh
#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
library="$project_dir/docs/zhixia-classical-dance-library.md"

test -s "$library"
test "$(rg -c '^### D[0-9]{2} ' "$library")" = "12"

for phrase in \
  "中国古典舞身韵" \
  "身韵为骨、汉唐气韵为神" \
  "提、沉、冲、靠、含、腆、移、仰" \
  "平圆、立圆、八字圆" \
  "每支诗镜只选择一个动作母题" \
  "最多完成两次换重、两至三步" \
  "不超过 180 度" \
  "不是专业水袖" \
  "专业术语转译" \
  "Seedance 正向提示词" \
  "三张状态卡" \
  "失败降级"; do
  rg -qF "$phrase" "$library"
done

for phrase in \
  "### D01 雪醒梨开" \
  "一片真实雪花" \
  "沉转提" \
  "圆场小步" \
  "约 135 度" \
  "简化云手" \
  "阿砚回应" \
  "脸部安全区"; do
  rg -qF "$phrase" "$library"
done

if rg -n "😀|🎬|✨" "$library"; then
  exit 1
fi

echo "PASS: Zhixia classical dance library rules are enforced"
```

- [ ] **Step 2: 赋予测试执行权限**

Run: `chmod +x zhixia-feihualing/tests/test_classical_dance_library_rules.sh`

- [ ] **Step 3: 运行测试并确认按预期失败**

Run: `zhixia-feihualing/tests/test_classical_dance_library_rules.sh`

Expected: FAIL at `test -s` because `docs/zhixia-classical-dance-library.md` does not exist.

- [ ] **Step 4: 提交失败测试**

```bash
git add zhixia-feihualing/tests/test_classical_dance_library_rules.sh
git commit -m "测试栀夏古典舞动作库规则"
```

### Task 2: 创建通用古典舞动作库

**Files:**
- Create: `zhixia-feihualing/docs/zhixia-classical-dance-library.md`
- Test: `zhixia-feihualing/tests/test_classical_dance_library_rules.sh`
- Reference: `zhixia-feihualing/docs/superpowers/specs/2026-08-28-zhixia-classical-dance-library-design.md`
- Reference: `zhixia-feihualing/docs/realistic-visual-style.md`
- Reference: `zhixia-feihualing/docs/cinematic-vfx-library.md`

**Interfaces:**
- Consumes: M01—M04 镜头编号、H01—H08 主特效编号、栀夏与阿砚现有身份门禁。
- Produces: 通用动作母题编号 D01—D12；后续单集只通过编号和链接引用。

- [ ] **Step 1: 写入动作库的定位、调用规则和安全边界**

文件开头必须使用以下结构和关键正文：

```markdown
# 栀夏专属中国古典舞动作库

## 定位

本库是《栀夏飞花令》10 秒单诗诗镜的古典舞动作单一事实源。整体方向固定为“身韵为骨、汉唐气韵为神”：使用中国古典舞身韵的提、沉、冲、靠、含、腆、移、仰，以及平圆、立圆、八字圆组织呼吸、目光、腰身、手臂与步法；不复制现成剧目或完整编舞。

## 调用门禁

- 每支诗镜只选择一个动作母题，不串联两个 Dxx。
- 舞蹈、Mxx 运镜、Hxx 主特效共享同一个视觉承接物、运动方向和揭示目标。
- 专业术语转译为可见的身体路径；提示词必须写清重心、承重脚、步数、转身角度、手臂路线、目光和结束位置。
- 栀夏最多完成两次换重、两至三步和一次不超过 180 度的连续转身，默认 90 至 135 度。
- 每条正式动作包含 Seedance 正向提示词、三张状态卡和失败降级。
```

- [ ] **Step 2: 写入身韵、手臂、步法、服装和阿砚规则**

必须覆盖以下可执行约束：

```markdown
## 通用身体规则

- 身韵：动作由呼吸、脊柱、腰身和重心发起，目光先于身体确认诗意物象。
- 手臂：安全手位为自然掌、按掌、山膀和简化托掌；安全路径为单侧穿手、简化云手、单次摇臂、平圆或立圆展开。
- 步法：只使用慢步、圆场小步、踏步转身、弧线移步和稳定收步。
- 服装：栀夏的薄罗大袖衫不是专业水袖。衣袖只能由肩肘真实带动，并在动作之后产生惯性余摆；禁止抛袖、抓袖、绕袖、甩长水袖和双袖持续遮镜。
- 阿砚回应：阿砚只承担领镜、追随、停步、抬头和唯一墨尾回应，不模仿人的手臂舞姿，不抢占栀夏表演。
```

- [ ] **Step 3: 建立 D01—D12 索引**

使用十二个三级标题，确保测试计数准确：

```markdown
### D01 雪醒梨开
### D02 临风舒云
### D03 月下回澜
### D04 花间寻香
### D05 听雨敛袖
### D06 山河展卷
### D07 落叶知秋
### D08 流水回身
### D09 星河仰望
### D10 灯影含笑
### D11 长路送别
### D12 晴空引鹤
```

D02—D12 分别写明“主要诗意、核心身韵、推荐镜头、允许动作、禁止动作”五项，不写成空标题。内容严格采用已确认设计表中的诗意、身韵和 Mxx 映射。

具体映射固定为：

| 编号 | 主要诗意 | 核心身韵 | 推荐镜头 |
| --- | --- | --- | --- |
| D02 | 风、云、开阔、自由 | 横移、仰、立圆展臂 | M04 |
| D03 | 月夜、相思、回望 | 含仰、横拧、平圆回身 | M04 |
| D04 | 花、春日、轻灵 | 旁提、圆场小步、单侧穿手 | M02 |
| D05 | 雨、静夜、等待 | 沉、含、按掌、慢步 | M02 |
| D06 | 山河、壮阔、坚定 | 提、靠、山膀、弧线移步 | M01 |
| D07 | 秋、流逝、怅惘 | 移、横拧、单次摇臂 | M01 |
| D08 | 江河、清泉、时间 | 提沉、八字圆手臂、踏步转身 | M04 |
| D09 | 星、登高、梦境 | 提、仰、立圆托掌 | M03 |
| D10 | 灯火、团聚、温暖 | 含转提、平圆云手、慢步 | M02 |
| D11 | 远行、离别、克制 | 沉、移、回身收掌 | M03 |
| D12 | 明朗、昂扬、上升 | 提、冲、旁提、弧线展臂 | M03 |

“允许动作”只从通用身体规则中选择与该行动律一致的一个手臂路径和一至两种步法；“禁止动作”至少包含与当前情绪冲突的炫技动作、专业水袖动作、连续高速旋转和复杂逐指变化。

- [ ] **Step 4: 写入 D01“雪醒梨开”完整动作条目**

D01 必须包含以下小节和确定内容：

```markdown
#### 适用与选型

- 适用：雪、花开、惊喜和由安静转向开阔的诗句。
- 核心身韵：沉转提、旁提、简化云手。
- 推荐镜头：M02。
- 推荐主特效：H05。
- 唯一视觉承接物：一片真实雪花。

#### 动作短句

起势由后脚承重、前脚轻点，栀夏呼气微沉并低头看雪。第一阶段重心沿小弧线移向前脚，脊柱随吸气自然提起，目光先向上，腰身轻微横拧；右臂沿立圆展开，左手保持按掌。第二阶段以两至三步圆场小步侧移，由承重脚带动约 135 度连续转身，同时完成一次不遮脸的简化云手。收势为三分之四正面中景，一臂侧上方形成简化山膀，另一臂在胸腹之间自然收住，双脚落点和重心明确。

#### 阿砚回应

阿砚先低位追随雪花，再在栀夏转身外侧停步抬头；结束时位于栀夏侧前方，形成一高一低三角构图。全程保持双耳、四足、朱砂额印、暖金纹样、纸墨材质和唯一开放式 S 形墨尾。

#### Seedance 正向提示词

栀夏完成一段连续、克制的中国古典舞身韵短句。动作由呼吸与重心发起，不是原地摆手；目光先行，腰、肩、肘、手臂和脚下重心逐级传递。衣袖、裙摆和高马尾只在身体发力与真实风场之后产生不同重量的惯性余摆。唯一雪花从脸侧安全区经过，不遮挡眼睛；栀夏始终保持正面或三分之四正面可辨识状态。

#### 三张状态卡

1. 起始：雪晶微距、栀夏侧身沉势、阿砚低位发现雪花。
2. 转折：栀夏完成提与立圆展臂，双角色处于中近景。
3. 结束：栀夏完成约 135 度转身和山膀收势，阿砚在侧前方停步，远处雪林完成揭示。

#### 失败降级

- 手腕或手指畸变：从云手降级为整臂平圆展开。
- 转身换脸：从约 135 度降级为 90 度，并在中点重锚三分之四脸。
- 袖布吞没肢体：减小手臂高度并降低风力，保持肩、肘、腕持续可见。
- 脚底滑移：减少为一步侧移，明确承重脚、落点和接触阴影。
- 雪粒遮脸：只保留唯一引导雪花，删除辅助飘雪。
```

- [ ] **Step 5: 运行舞蹈库规则测试**

Run: `zhixia-feihualing/tests/test_classical_dance_library_rules.sh`

Expected: PASS with `PASS: Zhixia classical dance library rules are enforced`.

- [ ] **Step 6: 检查 Markdown 和禁用表情**

Run: `git diff --check -- zhixia-feihualing/docs/zhixia-classical-dance-library.md`

Expected: exit 0.

Run: `! rg -n "😀|🎬|✨" zhixia-feihualing/docs/zhixia-classical-dance-library.md`

Expected: exit 0.

- [ ] **Step 7: 提交通用动作库**

```bash
git add zhixia-feihualing/docs/zhixia-classical-dance-library.md
git commit -m "建立栀夏古典舞动作库"
```

### Task 3: 将动作库接入电影级写实视觉规范

**Files:**
- Modify: `zhixia-feihualing/tests/test_classical_dance_library_rules.sh`
- Modify: `zhixia-feihualing/docs/realistic-visual-style.md:29`
- Test: `zhixia-feihualing/tests/test_classical_dance_library_rules.sh`

**Interfaces:**
- Consumes: `docs/zhixia-classical-dance-library.md` 的 Dxx 编号、调用门禁和失败降级规则。
- Produces: 所有后续诗镜必须引用动作库的项目级入口。

- [ ] **Step 1: 扩展测试并制造失败**

在测试文件的 `library` 变量后加入：

```zsh
style_rules="$project_dir/docs/realistic-visual-style.md"
test -s "$style_rules"
```

在最终表情检查之前加入：

```zsh
for phrase in \
  "zhixia-classical-dance-library.md" \
  "只选择一个 Dxx 动作母题" \
  "专业舞蹈术语必须转译" \
  "承重脚" \
  "不是专业水袖"; do
  rg -qF "$phrase" "$style_rules"
done
```

- [ ] **Step 2: 运行测试并确认缺少规范入口**

Run: `zhixia-feihualing/tests/test_classical_dance_library_rules.sh`

Expected: FAIL because `realistic-visual-style.md` does not yet contain `zhixia-classical-dance-library.md`.

- [ ] **Step 3: 在人物与角色章节加入动作库调用门禁**

紧接现有“栀夏在诗句表演期间必须保持持续、可读且与情绪相连的身体表达”条目之后加入：

```markdown
- 栀夏的古典舞动作单一事实源为 [`zhixia-classical-dance-library.md`](zhixia-classical-dance-library.md)。每条 10 秒诗镜只选择一个 Dxx 动作母题，并让它与当集唯一 Mxx 运镜、Hxx 主特效和视觉承接物共享运动方向与揭示目标。专业舞蹈术语必须转译为眼神、腰身、手臂路径、承重脚、步数、转身角度和结束位置；不能只写“云手”“圆场”或“古典舞”。
- 栀夏的浅水青薄罗大袖衫不是专业水袖。动作只允许由肩、肘、手腕和重心真实带动袖摆，并在身体发力后保留自然余摆；永久禁止抛袖、抓袖、绕袖、甩长水袖、双袖持续遮脸和无发力来源的衣袖自动飞舞。
```

- [ ] **Step 4: 运行舞蹈库规则测试和现有视觉规范测试**

Run: `zhixia-feihualing/tests/test_classical_dance_library_rules.sh`

Expected: PASS.

Run: `zhixia-feihualing/tests/test_realistic_visual_style_rules.sh`

Expected: PASS with `PASS: cinematic style and hook camera rules are enforced`.

- [ ] **Step 5: 提交视觉规范入口**

```bash
git add zhixia-feihualing/tests/test_classical_dance_library_rules.sh zhixia-feihualing/docs/realistic-visual-style.md
git commit -m "接入古典舞动作库门禁"
```

### Task 4: 建立雪诗单集和三张状态卡提示词

**Files:**
- Modify: `zhixia-feihualing/tests/test_classical_dance_library_rules.sh`
- Create: `zhixia-feihualing/episodes/baixue/README.md`
- Create: `zhixia-feihualing/episodes/baixue/prompts/scene-cards.md`
- Test: `zhixia-feihualing/tests/test_classical_dance_library_rules.sh`
- Reference: `zhixia-feihualing/assets/characters/栀夏角色母板-v04-Seedance固定说明.md`
- Reference: `zhixia-feihualing/assets/characters/阿砚角色母板-v01-Seedance固定说明.md`
- Reference: `zhixia-feihualing/episodes/denggao-10s/prompts/scene-cards.md`

**Interfaces:**
- Consumes: D01“雪醒梨开”、M02、H05、栀夏与阿砚最新 Seedance 上传版角色母板。
- Produces: `episodes/baixue/README.md` 单集事实源和三张可供人工审阅的状态卡提示词；不产生实际图片。

- [ ] **Step 1: 扩展测试并制造单集缺失失败**

在测试变量区加入：

```zsh
episode="$project_dir/episodes/baixue/README.md"
scene_cards="$project_dir/episodes/baixue/prompts/scene-cards.md"

test -s "$episode"
test -s "$scene_cards"
```

在视觉规范断言之后加入：

```zsh
for phrase in \
  "忽如一夜春风来，千树万树梨花开" \
  "D01“雪醒梨开”" \
  "M02" \
  "H05" \
  "一片真实雪花" \
  "不生成图片或视频"; do
  rg -qF "$phrase" "$episode"
done

test "$(rg -c '^## 状态图 0[1-3]：' "$scene_cards")" = "3"

for phrase in \
  "栀夏角色母板高写实CG-v04-完整档案增彩版-Seedance上传版.jpg" \
  "阿砚角色母板高写实CG-v01-最终版-Seedance上传版.jpg" \
  "同一处雪林边缘" \
  "同一右后方暖金晨光" \
  "唯一引导雪花" \
  "沉转提" \
  "约 135 度" \
  "脸部安全区" \
  "不得自动生成图片"; do
  rg -qF "$phrase" "$scene_cards"
done
```

- [ ] **Step 2: 运行测试并确认因雪诗目录缺失而失败**

Run: `zhixia-feihualing/tests/test_classical_dance_library_rules.sh`

Expected: FAIL at `test -s "$episode"`.

- [ ] **Step 3: 创建雪诗单集事实源**

`episodes/baixue/README.md` 写入以下确定内容：

```markdown
# 《白雪歌送武判官归京》10 秒诗镜

## 取句

- 诗句：忽如一夜春风来，千树万树梨花开。
- 作者：唐·岑参。
- 形式：10 秒、9:16、电影级高写实 CG、一镜到底。

## 当集选型

- 动作：D01“雪醒梨开”。
- 镜头：M02“微距物象—人物眼神—空间拉开”。
- 主特效：H05“诗意元素领舞生成世界”。
- 唯一视觉承接物：一片真实雪花。
- 情绪：由安静发现转向明亮惊喜和开阔赞叹。

## 当前状态

本阶段只完成动作选型和三张状态卡提示词。讨论、审阅和计划执行期间不生成图片或视频；只有用户明确确认当次输入并发出生成指令后，才允许调用生成工具。
```

同时链接：

- `../../docs/zhixia-classical-dance-library.md#d01-雪醒梨开`
- `../../docs/realistic-visual-style.md`
- `prompts/scene-cards.md`

- [ ] **Step 4: 创建三张状态卡的共同锁定规则**

`episodes/baixue/prompts/scene-cards.md` 开头必须声明：

```markdown
# 《白雪歌送武判官归京》10 秒诗镜状态图提示词

## 使用规则

- 本文件只用于审阅三张状态图提示词；不得自动生成图片。
- 只有收到用户当次明确的“生成图片”指令，并确认输入、数量和费用后，才可逐张执行。
- 栀夏输入：`assets/characters/栀夏角色母板高写实CG-v04-完整档案增彩版-Seedance上传版.jpg`。
- 阿砚输入：`assets/characters/阿砚角色母板高写实CG-v01-最终版-Seedance上传版.jpg`。
- 两张角色母板只锁定身份、比例、服装、发冠、物种结构、标记和材质，不复刻档案卡布局或文字。

## 三张共同锁定

- 场景是同一处雪林边缘：近处深色松枝、开阔积雪地、远处层叠树林和低缓雪岭的拓扑固定。
- 单一主光源是同一右后方暖金晨光；雪地反射形成克制冷色补光，三张卡光向不变。
- 唯一引导雪花具有真实六角晶体、环境反光和空气阻力；辅助飘雪保持极少量，不形成粒子风暴。
- 栀夏、阿砚、雪花、衣袖、裙摆、高马尾和唯一墨尾接受同一风向。
- 电影级高写实 CG；真实皮肤、独立发丝、薄罗丝织、纸墨纤维、雪晶、树皮、接触阴影和电影镜头光学。
- 栀夏身份、阿砚双耳四足单尾结构和角色占比优先于舞蹈、雪林尺度与雪粒。
- 禁止专业水袖动作、实体梨花、文字、额外人物、额外动物、普通猫、雪粒人形、廉价仙侠光效和灰雾脏调色。
```

- [ ] **Step 5: 写入三张状态卡提示词**

三个二级标题固定为：

```markdown
## 状态图 01：雪晶沉势钩子
## 状态图 02：立圆展臂转折
## 状态图 03：雪林山膀收势
```

每张状态卡都包含“输入、生成提示词、验收重点”。具体画面必须满足：

- 01：M02 雪晶微距起镜；栀夏三分之四侧身，后脚承重、前脚轻点、呼气微沉；阿砚低位发现唯一引导雪花。栀夏和阿砚仍清楚可辨，不做纯雪晶空镜。
- 02：第一行末尾的中近景；栀夏重心移向前脚、脊柱提起、目光先行、腰身横拧、右臂沿立圆展开、左手按掌；唯一雪花从脸部安全区经过。肩、肘、腕和双手数量清楚。
- 03：第二行末尾；栀夏经过两至三步圆场小步和约 135 度连续转身，三分之四正面完成简化山膀收势；阿砚在侧前方停步抬头；摄影机拉开揭示真实积雪覆盖的远林，不生成实体梨花。

每张卡都重复最短必要的栀夏和阿砚正向身份锚点，并分别写清人物景别、画面区域、相对尺度和最低可辨识特征。

- [ ] **Step 6: 运行舞蹈库规则测试**

Run: `zhixia-feihualing/tests/test_classical_dance_library_rules.sh`

Expected: PASS.

- [ ] **Step 7: 运行现有相关规则测试**

Run: `zhixia-feihualing/tests/test_realistic_visual_style_rules.sh`

Expected: PASS.

Run: `zhixia-feihualing/tests/test_cinematic_vfx_library_rules.sh`

Expected: PASS with `PASS: cinematic VFX library rules are enforced`.

- [ ] **Step 8: 提交雪诗单集与测试**

```bash
git add zhixia-feihualing/tests/test_classical_dance_library_rules.sh zhixia-feihualing/episodes/baixue/README.md zhixia-feihualing/episodes/baixue/prompts/scene-cards.md
git commit -m "设计白雪诗镜古典舞状态卡"
```

### Task 5: 完成全量文档验证

**Files:**
- Verify: `zhixia-feihualing/docs/zhixia-classical-dance-library.md`
- Verify: `zhixia-feihualing/docs/realistic-visual-style.md`
- Verify: `zhixia-feihualing/episodes/baixue/README.md`
- Verify: `zhixia-feihualing/episodes/baixue/prompts/scene-cards.md`
- Verify: `zhixia-feihualing/tests/test_classical_dance_library_rules.sh`

**Interfaces:**
- Consumes: Tasks 1—4 的全部文档与测试。
- Produces: 可供用户审阅、但尚未生成任何付费素材的第一阶段完整交付。

- [ ] **Step 1: 运行三项相关规则测试**

```bash
zhixia-feihualing/tests/test_classical_dance_library_rules.sh
zhixia-feihualing/tests/test_realistic_visual_style_rules.sh
zhixia-feihualing/tests/test_cinematic_vfx_library_rules.sh
```

Expected: three PASS messages, zero failures.

- [ ] **Step 2: 检查 Markdown 格式和禁止表情**

Run:

```bash
git diff --check HEAD~4..HEAD
! rg -n "😀|🎬|✨" \
  zhixia-feihualing/docs/zhixia-classical-dance-library.md \
  zhixia-feihualing/docs/realistic-visual-style.md \
  zhixia-feihualing/episodes/baixue/README.md \
  zhixia-feihualing/episodes/baixue/prompts/scene-cards.md \
  zhixia-feihualing/tests/test_classical_dance_library_rules.sh
```

Expected: exit 0 with no matches.

- [ ] **Step 3: 检查实际提交范围**

Run: `git log -4 --stat --oneline`

Expected: only the five planned files appear across the four implementation commits; no generated image, video, audio, `.env` or unrelated project file is included.

- [ ] **Step 4: 检查工作区但不清理用户改动**

Run: `git status --short`

Expected: any pre-existing unrelated changes remain untouched; do not reset, delete or include them in a new commit.

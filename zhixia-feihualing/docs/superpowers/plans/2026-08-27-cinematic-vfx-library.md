# 15秒诗镜电影级特效库 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立一份可直接用于15秒诗镜选型和提示词编写的电影级特效库，并将其接入现有全写实视觉规范和梦境长镜头运镜库。

**Architecture:** 新建 `docs/cinematic-vfx-library.md` 作为特效条目单一事实源，以镜头功能为主索引、材质和制作阶段为标签，固定收录8个生成期主特效、7个生成期辅助特效和6个后期增强条目。现有视觉规范负责全局风格和生成门禁，运镜库负责摄影机路径，生产流程只提供入口链接；shell测试检查条目数量、字段完整性、用量上限、角色遮挡门槛和跨文档链接。

**Tech Stack:** Markdown、zsh、ripgrep

**Execution directory:** 除测试脚本内部自行定位项目根目录外，所有命令均从工作区根目录 `/Users/huan.yu/dev/tools-workspace` 运行。

## Global Constraints

- 一条15秒诗镜只能使用一个 `generation-hero` 主特效。
- 一条15秒诗镜最多使用一个 `generation-support` 辅助特效。
- `post-enhancement` 只修饰光、雾、景深、颗粒、字幕和调色，不修复换脸、物种漂移、骨骼畸变或空间断裂。
- 栀夏与阿砚保持电影级全写实外观；角色卡只锁定身份设计。
- 人物和镜头运动可以不遵循现实物理，但身份、形体、服装、毛发、阿砚物种结构和材质必须逐帧稳定。
- 特效连续遮挡任一角色脸部不得超过0.5秒。
- 每个S级主特效必须先制作起始、转折、结尾三张状态卡，并通过4至5秒低成本测试。
- 特效库不得使用 emoji；动漫速度线、魔法阵、无来源全屏粒子、RGB故障和短视频模板转场只能出现在禁用清单中，不得作为推荐效果或正向提示词。
- 不修改与本特效库无关的用户现有工作区改动。

---

### Task 1: 建立特效库结构回归测试

**Files:**
- Create: `tests/test_cinematic_vfx_library_rules.sh`
- Test: `tests/test_cinematic_vfx_library_rules.sh`

**Interfaces:**
- Consumes: 设计稿 `docs/superpowers/specs/2026-08-27-cinematic-vfx-library-design.md` 中的条目数量、字段和门禁。
- Produces: 对 `docs/cinematic-vfx-library.md` 及其三个入口文档的可重复校验。

- [x] **Step 1: 创建失败测试**

使用以下完整内容创建 `tests/test_cinematic_vfx_library_rules.sh`：

```zsh
#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
library="$project_dir/docs/cinematic-vfx-library.md"
style_rules="$project_dir/docs/realistic-visual-style.md"
camera_library="$project_dir/docs/cinematic-15s-oner-camera-library.md"
workflow="$project_dir/docs/production-workflow.md"

test -s "$library"

test "$(rg -c '^### H[0-9]{2} ' "$library")" = "8"
test "$(rg -c '^### S[0-9]{2} ' "$library")" = "7"
test "$(rg -c '^### P[0-9]{2} ' "$library")" = "6"

for phrase in \
  "一个生成期主特效＋最多一个生成期辅助特效＋少量后期增强" \
  "generation-hero" \
  "generation-support" \
  "post-enhancement" \
  "不超过0.5秒" \
  "三张状态卡" \
  "4至5秒低成本测试" \
  "角色共舞方式" \
  "视觉承接物" \
  "身份漂移风险" \
  "全写实提示词" \
  "禁用效果" \
  "动漫速度线" \
  "RGB故障" \
  "特效选型卡"; do
  rg -qF "$phrase" "$library"
done

for entry in "$style_rules" "$camera_library" "$workflow"; do
  rg -qF "cinematic-vfx-library.md" "$entry"
done

if rg -n "😀|🎬|✨" "$library"; then
  exit 1
fi

echo "PASS: cinematic VFX library rules are enforced"
```

- [x] **Step 2: 运行测试并确认失败原因正确**

Run: `zsh zhixia-feihualing/tests/test_cinematic_vfx_library_rules.sh`

Expected: FAIL at `test -s "$library"` because `docs/cinematic-vfx-library.md` does not exist.

- [x] **Step 3: 检查测试脚本语法**

Run: `zsh -n zhixia-feihualing/tests/test_cinematic_vfx_library_rules.sh`

Expected: exit 0 with no output.

### Task 2: 建立电影级特效库正文

**Files:**
- Create: `docs/cinematic-vfx-library.md`
- Test: `tests/test_cinematic_vfx_library_rules.sh`

**Interfaces:**
- Consumes: 设计稿中的功能分类、材质标签、制作阶段标签、15秒节奏和失败处理规则。
- Produces: 供单集特效选型卡和视频提示词直接引用的21个固定条目。

- [x] **Step 1: 写入库级规则和条目模板**

文件开头必须依次包含：

1. 定位与固定公式：`一个生成期主特效＋最多一个生成期辅助特效＋少量后期增强`。
2. 五类镜头功能：钩子、牵引、转场、揭示、落点。
3. 七类材质标签：水与液体、云雾与体积、布料与毛发、颗粒与群体、光与光学、墨与书写、地貌与环境。
4. 三类制作阶段：`generation-hero`、`generation-support`、`post-enhancement`。
5. 每个主特效使用以下固定字段，字段名不得改写：

```markdown
**阶段：**
**等级：**
**镜头功能：**
**材质标签：**
**适用诗意：**
**建议运镜：**
**15秒位置：**
**视觉承接物：**
**角色共舞方式：**
**形象展示：**
**全写实提示词：**
**禁用项：**
**身份漂移风险：**
**4至5秒测试：**
```

- [x] **Step 2: 写入8个生成期主特效**

使用以下固定编号和标题，每个条目完整填写Step 1的全部字段：

1. `H01 水面折叠成天空`
2. `H02 瀑布逆流化为银河`
3. `H03 栀夏衣袖延展成诗境`
4. `H04 阿砚墨尾生成山河`
5. `H05 诗意元素领舞生成世界`
6. `H06 微观物象展开宏大空间`
7. `H07 季节昼夜与地貌连续转化`
8. `H08 写实颗粒聚合并散开成景`

每个 `Hxx` 条目必须满足：

- `阶段` 固定为 `generation-hero`。
- `等级` 只能是S或A。
- `15秒位置` 明确覆盖钩子、牵引、转化、揭示和落点中的至少两个相邻阶段。
- `视觉承接物` 只能有一个主导物象。
- `角色共舞方式` 同时写明栀夏与阿砚怎样随镜头或特效移动。
- `形象展示` 至少安排一次两位角色同时清楚可辨的中近景或近景。
- `全写实提示词` 同时描述真实材质、环境光响应、前后景交互和禁止动漫化。
- `身份漂移风险` 指定一个最可能发生的角色错误和对应生成前约束。
- S级条目的测试必须引用三张状态卡；所有条目均提供4至5秒低成本测试。

- [x] **Step 3: 写入7个生成期辅助特效**

使用以下固定编号和标题，每个条目至少记录阶段、材质标签、适用主特效、提示词短语、角色安全区和禁用项：

1. `S01 体积雾与克制光束`
2. `S02 水雾飞沫与空气湿度`
3. `S03 稀疏雪叶花瓣与墨粒`
4. `S04 水面焦散倒影与折射扰动`
5. `S05 灯火月光局部辉光与环境反射`
6. `S06 衣料发丝毛发与墨尾风场响应`
7. `S07 显示镜头轨迹的稀薄雾线`

所有 `Sxx` 条目的阶段固定为 `generation-support`，并明确“一条视频最多选择一个”。

- [x] **Step 4: 写入6个后期增强条目**

使用以下固定编号和标题，每个条目至少记录阶段、用途、适用时段、参数边界、人物遮罩要求和禁止用途：

1. `P01 克制辉光与高光扩散`
2. `P02 局部体积雾与空气透视`
3. `P03 有限景深与轻微运动模糊`
4. `P04 焦外光斑与镜头光晕`
5. `P05 电影颗粒暗角与色彩统一`
6. `P06 诗句字幕淡入与逐句高光`

所有 `Pxx` 条目的阶段固定为 `post-enhancement`，并明确不得修补换脸、物种漂移、骨骼畸变、服装变化或空间断裂。

- [x] **Step 5: 写入禁用效果、失败处理和特效选型卡**

禁用效果完整包含：无来源全屏粒子、魔法阵、能量环、持续光柱、动漫速度线、分身残影、夸张拖影、RGB故障、随机色散、模板转场、大面积闪白、频闪和同时出现两种以上群体粒子。

特效选型卡使用以下字段：

```markdown
| 诗句 | |
| 核心意象 | |
| 主特效 | 一个 Hxx |
| 辅助特效 | 零个或一个 Sxx |
| 后期增强 | 必要的 Pxx |
| 核心运镜 | 一个 S级、A级或B级运镜模板 |
| 视觉承接物 | |
| 角色共舞 | |
| 形象展示 | |
| 遮挡门槛 | 不超过0.5秒 |
| 三张状态卡 | |
| 测试方案 | 4至5秒低成本测试 |
```

选型卡之后写明：主特效超过一个、辅助特效超过一个、没有视觉承接物、没有角色形象展示段或缺少测试方案时，不得进入提示词编写和付费生成。

- [x] **Step 6: 运行测试，确认只因入口链接缺失而失败**

Run: `zsh zhixia-feihualing/tests/test_cinematic_vfx_library_rules.sh`

Expected: FAIL in the loop that checks `cinematic-vfx-library.md` links inside the three entry documents; the library body and entry counts already pass.

### Task 3: 接入视觉规范、运镜库和生产流程

**Files:**
- Modify: `docs/realistic-visual-style.md`
- Modify: `docs/cinematic-15s-oner-camera-library.md`
- Modify: `docs/production-workflow.md`
- Test: `tests/test_cinematic_vfx_library_rules.sh`

**Interfaces:**
- Consumes: Task 2 的 `docs/cinematic-vfx-library.md` 路径、Hxx/Sxx/Pxx编号和选型门禁。
- Produces: 从全局风格、运镜选型和生产流程均可到达特效库的三个稳定入口。

- [x] **Step 1: 在全写实视觉规范中增加特效边界**

在 `docs/realistic-visual-style.md` 的“摄影与剪辑”之后增加“电影级特效”小节，明确：

- 特效库单一事实源为 `[电影级特效库](cinematic-vfx-library.md)`。
- 每条诗镜使用一个Hxx、零个或一个Sxx和必要Pxx。
- 特效不能遮挡任一角色脸部超过0.5秒。
- 生成期特效失败导致身份或材质漂移时必须重做原片，不能后期修脸。

- [x] **Step 2: 在一镜到底运镜库中增加联动字段**

在 `docs/cinematic-15s-oner-camera-library.md` 的每集选型卡加入：

```markdown
| 主特效 | 特效库中的一个 Hxx |
| 辅助特效 | 零个或一个 Sxx |
| 后期增强 | 必要的 Pxx |
```

并在选型卡前增加 `[电影级特效库](cinematic-vfx-library.md)` 链接，说明运镜模板决定摄影机路径，特效条目决定空间与材质变化，两者不得各自设置互相竞争的视觉机关。

- [x] **Step 3: 在生产流程中增加入口和生成前检查**

在 `docs/production-workflow.md` 的默认视觉风格基线段落增加 `[电影级特效库](cinematic-vfx-library.md)` 链接；在视频生成检查中增加主特效、辅助特效、后期增强、遮挡门槛和短测试五项，不改动其他已有生产规则。

- [x] **Step 4: 运行规则测试并确认通过**

Run: `zsh zhixia-feihualing/tests/test_cinematic_vfx_library_rules.sh`

Expected: PASS with `PASS: cinematic VFX library rules are enforced`.

- [x] **Step 5: 提交特效库、测试和入口文档**

```bash
git add \
  zhixia-feihualing/docs/cinematic-vfx-library.md \
  zhixia-feihualing/docs/realistic-visual-style.md \
  zhixia-feihualing/docs/cinematic-15s-oner-camera-library.md \
  zhixia-feihualing/docs/production-workflow.md \
  zhixia-feihualing/tests/test_cinematic_vfx_library_rules.sh
git commit -m "建立十五秒诗镜电影级特效库"
```

提交前使用 `git diff --cached --name-only` 确认暂存区只包含上述五个文件；若 `docs/production-workflow.md` 含有用户先前修改，必须逐块暂存本任务新增的特效库入口，不能覆盖或误提交其他修改。

### Task 4: 完整验证与计划回填

**Files:**
- Modify: `docs/superpowers/plans/2026-08-27-cinematic-vfx-library.md`
- Test: `tests/test_cinematic_vfx_library_rules.sh`
- Test: `tests/test_realistic_visual_style_rules.sh`

**Interfaces:**
- Consumes: Tasks 1至3的全部文件。
- Produces: 两套规则测试结果、无占位符的特效库和已完成的实施清单。

- [x] **Step 1: 运行特效库规则测试**

Run: `zsh zhixia-feihualing/tests/test_cinematic_vfx_library_rules.sh`

Expected: PASS with one PASS line and no warnings.

- [x] **Step 2: 运行既有全写实与梦境运镜规则测试**

Run: `zsh zhixia-feihualing/tests/test_realistic_visual_style_rules.sh`

Expected: PASS with `PASS: cinematic style and hook camera rules are enforced`.

- [x] **Step 3: 检查文档占位符和格式**

Run:

```bash
if rg -n "TBD|TODO|待补|待定|implement later|fill in details" \
  zhixia-feihualing/docs/cinematic-vfx-library.md \
  zhixia-feihualing/docs/realistic-visual-style.md \
  zhixia-feihualing/docs/cinematic-15s-oner-camera-library.md \
  zhixia-feihualing/docs/production-workflow.md; then
  exit 1
fi
```

Expected: exit 0 with no output.

- [x] **Step 4: 检查差异和工作区边界**

Run:

```bash
git status --short -- \
  zhixia-feihualing/docs/cinematic-vfx-library.md \
  zhixia-feihualing/docs/realistic-visual-style.md \
  zhixia-feihualing/docs/cinematic-15s-oner-camera-library.md \
  zhixia-feihualing/docs/production-workflow.md \
  zhixia-feihualing/tests/test_cinematic_vfx_library_rules.sh \
  zhixia-feihualing/docs/superpowers/plans/2026-08-27-cinematic-vfx-library.md
```

Expected: 只显示计划允许的文件；任何其他路径均不纳入本任务提交。

- [x] **Step 5: 回填计划完成状态并提交计划**

将本计划实际完成的复选框改为 `[x]`，未执行的付费生成保持不在本计划范围内，然后运行：

```bash
git add zhixia-feihualing/docs/superpowers/plans/2026-08-27-cinematic-vfx-library.md
git commit -m "记录电影级特效库实施计划"
```

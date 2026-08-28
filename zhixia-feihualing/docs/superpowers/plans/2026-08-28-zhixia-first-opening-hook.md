# 栀夏优先诗境开场 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将“栀夏先动、首帧可辨认、0.5秒内清楚展示面部”写入全局制作规范，并把尚未生成的“白雪”10秒诗境改为由栀夏驱动的开场。

**Architecture:** `docs/realistic-visual-style.md` 与 `docs/production-workflow.md` 保存所有新诗境必须遵守的开场契约；“白雪”README、单状态卡提示词和最终 Seedance 提示词负责单集落地。新增独立 Zsh 静态规则测试，先建立失败门禁，再逐层更新全局规范与单集文件；历史结构稿不用于生成，保持原样。

**Tech Stack:** Markdown、Zsh、Ripgrep、现有静态规则测试。

## Global Constraints

- 每支诗境的第一个可感知动作必须来自栀夏。
- 首帧必须已经能辨认栀夏，0.5秒内必须清楚呈现她未被遮挡的面部与固定形象。
- 不得以纯风景、纯意象、阿砚单独画面或角色缺席的空镜开场。
- 开场微动作只负责建立人物并引出诗境，不预编具体舞蹈动作。
- 舞蹈约束完整且仅为：`中国古典舞身韵、轻盈克制、连续自然、不遮脸`；具体动作、连接与收势由 Seedance 自由发挥。
- 每支诗境仍只保留一张开场状态卡，状态卡以栀夏为第一视觉主体。
- “白雪”现有状态卡继续通过；只改当前文字规范和视频提示词，不重新生成图片或视频。
- 阿砚足底至耳尖约40厘米，肩高约24至28厘米，躯干长度约40至45厘米（不含尾巴）；与栀夏同框时耳尖位于小腿中下段并低于膝盖。
- “白雪”四段后期音频起点继续为0.500、1.850、3.600、6.200秒，不修改音频、字幕或TTS清单。
- 当前开场设计优先于旧“微距雪晶先动”和旧M02选型；“白雪”改用M04“侧向贴身滑行—小幅环绕—拉开收束”。
- 不修改历史文件 `episodes/baixue/prompts/seedance-structure-v01.md`；它已明确标注为历史参考且不得用于生成。
- 全部用户可见内容、文档和提交信息不使用 emoji；Git提交信息使用中文。
- 显式限定每次暂存与提交的计划内路径，保留 `.cursor/rules/`、`stock-ai/` 和其他既有未提交改动。

---

### Task 1: 建立栀夏优先开场的失败门禁

**Files:**

- Create: `zhixia-feihualing/tests/test_zhixia_first_opening_rules.sh`
- Reference: `zhixia-feihualing/docs/superpowers/specs/2026-08-28-zhixia-first-opening-hook-design.md`
- Reference: `zhixia-feihualing/docs/character-bible.md`

**Interfaces:**

- Consumes: 已确认设计规范中的首动作、0.5秒、单状态卡和40厘米规则。
- Produces: 一个退出码为0才表示全局规范与“白雪”当前生成文件均符合新规则的静态门禁。

- [ ] **Step 1: Create the policy test with exact positive and negative assertions**

写入以下完整测试骨架：

```zsh
#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
style="$project_dir/docs/realistic-visual-style.md"
workflow="$project_dir/docs/production-workflow.md"
character="$project_dir/docs/character-bible.md"
episode="$project_dir/episodes/baixue/README.md"
scene_cards="$project_dir/episodes/baixue/prompts/scene-cards.md"
final_prompt="$project_dir/episodes/baixue/prompts/seedance-v01.md"

for path in "$style" "$workflow" "$character" "$episode" "$scene_cards" "$final_prompt"; do
  test -s "$path"
done

for phrase in \
  "第一个可感知动作必须来自栀夏" \
  "首帧必须已经能辨认栀夏" \
  "0.5秒内" \
  "不得以纯风景、纯意象、阿砚单独画面或角色缺席的空镜开场"; do
  rg -qF "$phrase" "$style"
done

for phrase in \
  "第一秒先看见谁、谁先动" \
  "第一个动作来自栀夏" \
  "0.5秒内清楚展示她的脸"; do
  rg -qF "$phrase" "$workflow"
done

for phrase in \
  "足底至耳尖的站立总高度约40厘米" \
  "肩高约24至28厘米" \
  "躯干长度约40至45厘米"; do
  rg -qF "$phrase" "$character"
done

test "$(rg -c '^## 状态图 01：' "$scene_cards")" = "1"
test "$(rg -c '^## 状态图 0[2-9]：' "$scene_cards" || echo 0)" = "0"

for phrase in \
  "栀夏优先开场" \
  "栀夏是第一视觉主体" \
  "阿砚足底至耳尖约40厘米"; do
  rg -qF "$phrase" "$scene_cards"
done

prompt_block="$(sed -n '/<!-- SEEDANCE_PROMPT_START -->/,/<!-- SEEDANCE_PROMPT_END -->/p' "$final_prompt")"
for phrase in \
  "0.000—0.500 秒，栀夏先动钩子" \
  "0.500—1.724 秒，阿砚无声疑问口型" \
  "M04" \
  "阿砚足底至耳尖约40厘米" \
  "中国古典舞身韵、轻盈克制、连续自然、不遮脸"; do
  print -r -- "$prompt_block" | rg -qF "$phrase"
done

for current_file in "$episode" "$scene_cards" "$final_prompt"; do
  if rg -n "8至10厘米|8 至 10 厘米|8—10厘米|微距雪晶钩子" "$current_file"; then
    exit 1
  fi
done

if rg -n "😀|🎬|✨" "$style" "$workflow" "$episode" "$scene_cards" "$final_prompt"; then
  exit 1
fi

echo "PASS: Zhixia-first opening and Baixue 40cm rules are enforced"
```

- [ ] **Step 2: Make the test executable**

```bash
chmod +x zhixia-feihualing/tests/test_zhixia_first_opening_rules.sh
```

- [ ] **Step 3: Run the test and verify the expected red state**

```bash
zsh zhixia-feihualing/tests/test_zhixia_first_opening_rules.sh
```

Expected: exit code non-zero，因为全局视觉规范和当前“白雪”文件尚未包含新短语，且仍存在M02、微距雪晶先动与8至10厘米旧值。

- [ ] **Step 4: Commit only the red test**

```bash
git add zhixia-feihualing/tests/test_zhixia_first_opening_rules.sh
git diff --cached --check
git commit -m "测试：增加栀夏优先开场规则门禁"
```

### Task 2: 锁定阿砚尺寸并写入全局开场规范

**Files:**

- Modify: `zhixia-feihualing/docs/realistic-visual-style.md`
- Modify: `zhixia-feihualing/docs/production-workflow.md`
- Modify: `zhixia-feihualing/docs/character-bible.md`
- Test: `zhixia-feihualing/tests/test_zhixia_first_opening_rules.sh`
- Test: `zhixia-feihualing/tests/test_realistic_visual_style_rules.sh`

**Interfaces:**

- Consumes: Task 1的静态门禁与已确认设计稿。
- Produces: 阿砚40厘米的角色单一事实源，以及所有尚未生成的新诗境都能直接引用的首帧、首动作和0.5秒人物展示契约。

- [ ] **Step 1: Preserve and verify the approved 40cm character-bible correction**

保留当前工作区已经通过审核的阿砚修正，并确认“最终身份”与“Seedance母板使用规则”明确包含：

```markdown
足底至耳尖的站立总高度约40厘米
肩高约24至28厘米
躯干长度约40至45厘米（不含尾巴）
耳尖通常位于栀夏小腿中下段并明确低于膝盖
```

权威母版继续使用 `assets/characters/阿砚角色母板高写实CG-v01-最终版-Seedance上传版.jpg`；旧归档PNG中的约9厘米标注只作历史追溯，不得用于生成。

- [ ] **Step 2: Add a dedicated opening section to the visual style guide**

在第一秒视觉钩子规则之前加入“栀夏优先开场”小节，写入以下规范：

```markdown
### 栀夏优先开场

- 每支诗境的第一个可感知动作必须来自栀夏。
- 首帧必须已经能辨认栀夏，0.5秒内清楚呈现她未被遮挡的脸、18岁成年少女感、固定发型发冠和当集服装主色。
- 不得以纯风景、纯意象、阿砚单独画面或角色缺席的空镜开场；诗意元素可以入画，但在栀夏首次动作前只能保持静止或作为次级环境运动。
- 栀夏的开场微动作只负责建立人物并引出诗境，不预编具体舞蹈动作；镜头沿她的视线或动作带出阿砚、唯一诗意承接物与环境变化。
- 阿砚可以在后期音频中先说话，但画面先建立栀夏，并在对应音频开始前或开始时把清晰焦点交给阿砚。
```

- [ ] **Step 3: Add the pre-production question to production-workflow.md**

在“能拍不能只画”检查中，将第一秒检查扩展为：

```markdown
- 第一秒先看见谁、谁先动：默认首帧已经能辨认栀夏，第一个动作来自栀夏，并在0.5秒内清楚展示她的脸。
- 栀夏的视线或自然微动作如何带出阿砚、唯一诗意承接物与诗境变化。
```

保留“第一秒发生了什么，而不是画面里有什么”的原检查，不重复建立另一套时间轴。

- [ ] **Step 4: Run the focused tests and verify partial progress**

```bash
zsh zhixia-feihualing/tests/test_realistic_visual_style_rules.sh
zsh zhixia-feihualing/tests/test_zhixia_first_opening_rules.sh
```

Expected: `test_realistic_visual_style_rules.sh`通过；新测试仍因“白雪”当前文件保留旧开场与旧尺寸而失败。

- [ ] **Step 5: Commit only the character source and global documentation**

```bash
git add zhixia-feihualing/docs/character-bible.md zhixia-feihualing/docs/realistic-visual-style.md zhixia-feihualing/docs/production-workflow.md
git diff --cached --check
git commit -m "文档：统一角色尺度与栀夏优先开场规则"
```

### Task 3: 重写“白雪”单状态卡与单集说明

**Files:**

- Modify: `zhixia-feihualing/episodes/baixue/prompts/scene-cards.md`
- Modify: `zhixia-feihualing/episodes/baixue/README.md`
- Modify: `zhixia-feihualing/tests/test_classical_dance_library_rules.sh`
- Test: `zhixia-feihualing/tests/test_zhixia_first_opening_rules.sh`
- Test: `zhixia-feihualing/tests/test_classical_dance_library_rules.sh`

**Interfaces:**

- Consumes: 当前已人工通过的雪林状态图、M04镜头路径、阿砚40厘米角色圣经与既有四段音频时间轴。
- Produces: 一张以栀夏为第一视觉主体的开场状态卡文字真源，以及与最终提示词一致的单集说明。

- [ ] **Step 1: Rename and rewrite the single opening state**

将标题改为：

```markdown
## 状态图 01：栀夏优先开场
```

保留现有雪林、右后方晨光、统一风向、唯一雪花、角色服装和高写实材质。将生成提示词改为以当前通过图片为准的构图：栀夏位于右侧并成为第一视觉主体，首帧已经看清面部；阿砚位于左下，保持成年家猫尺度；前景松枝和唯一雪花只负责空间层次，不以雪晶微距主导起镜。

必须加入以下精确约束：

```markdown
- 栀夏是第一视觉主体，首帧已经能辨认她的脸、固定发型发冠和服装主色。
- 状态卡为栀夏的第一个自然微动作留下视线和重心方向，不预设具体舞姿。
- 阿砚足底至耳尖约40厘米，耳尖位于栀夏小腿中下段并低于膝盖；不得用前后景错位压缩为微型生物。
```

删除85mm雪晶微距起镜、雪花作为第一帧主钩子、8至10厘米和阿砚占画面18%至22%的旧规则。

- [ ] **Step 2: Update the episode README selection and timeline**

- 将镜头从M02改为M04“侧向贴身滑行—小幅环绕—拉开收束”。
- 将角色规则改为阿砚足底至耳尖约40厘米，并写明与栀夏的小腿关系。
- 将0.000—0.500秒改为“栀夏先动并在首帧建立形象，唯一雪花作为视线承接物”。
- 保持后续八个时间节点与四段音频起点不变。
- 在关联文档中新增已确认的 `2026-08-28-zhixia-first-opening-hook-design.md`。
- 保留“未授权生成图片或视频”的付费门禁。

- [ ] **Step 3: Update the existing free-dance test for the new camera selection**

在 `test_classical_dance_library_rules.sh` 的白雪README正向短语列表中，将 `M02` 替换为 `M04`；保留H05、唯一真实雪花、单状态卡和自由舞蹈断言。该测试只验证舞蹈与状态卡规则，不再把旧镜头母题锁死。

- [ ] **Step 4: Run the current rule tests**

```bash
zsh zhixia-feihualing/tests/test_classical_dance_library_rules.sh
zsh zhixia-feihualing/tests/test_zhixia_first_opening_rules.sh
```

Expected: 自由舞蹈测试继续通过；新开场测试仍只因最终Seedance提示词尚未改写而失败。

- [ ] **Step 5: Commit only the state-card prompt, episode README and adjusted test**

```bash
git add zhixia-feihualing/episodes/baixue/prompts/scene-cards.md zhixia-feihualing/episodes/baixue/README.md zhixia-feihualing/tests/test_classical_dance_library_rules.sh
git diff --cached --check
git commit -m "文档：调整白雪栀夏优先开场状态"
```

### Task 4: 重排“白雪”10秒 Seedance 开场

**Files:**

- Modify: `zhixia-feihualing/episodes/baixue/prompts/seedance-v01.md`
- Test: `zhixia-feihualing/tests/test_zhixia_first_opening_rules.sh`
- Test: `zhixia-feihualing/tests/test_classical_dance_library_rules.sh`
- Test: `zhixia-feihualing/tests/test_baixue_10s_assets.sh`

**Interfaces:**

- Consumes: Task 3的状态卡构图、既有字幕/TTS时间点、唯一雪花、H05雪林揭示和自由舞蹈规则。
- Produces: 可在后续取得付费生成授权后直接使用的当前Seedance文字提示词；不在本任务中调用生成服务。

- [ ] **Step 1: Replace the camera contract and the first 0.5 seconds**

将全片核心镜头改为M04，首段使用以下职责，不加入命名舞步：

```text
0.000—0.500 秒，栀夏先动钩子：首帧已经清楚看见右侧中景的栀夏。全片第一个可感知动作来自栀夏，她先以一次自然眨眼和极轻呼吸建立鲜活人物感，视线随即落向左下方的唯一雪花；摄影机沿她外侧做极短、稳定的贴身侧滑，保持面部和双眼清楚。唯一雪花只作为视线承接物，不抢先运动，不做纯雪景或雪晶微距空镜。
```

- [ ] **Step 2: Preserve the Ayan dialogue handoff and correct his scale**

0.500—1.724秒继续对应阿砚的1.224秒无声疑问口型。摄影机只做连续移焦，不切镜；局部身份重锚改为：

```text
阿砚足底至耳尖约40厘米、肩高约24至28厘米、躯干长度约40至45厘米且不含尾巴，耳尖位于栀夏小腿中下段并低于膝盖。
```

保留双耳、四足、朱砂印、暖金纹样、纸墨纤维和唯一开放式S形墨尾，不保留任何8至10厘米描述。

- [ ] **Step 3: Adapt the middle camera movement without constraining the dance**

- 1.724—3.600秒保留阿砚闭唇、视线交接、栀夏无声回应和入舞呼吸。
- 3.600—9.032秒继续只写两次精确短语 `中国古典舞身韵、轻盈克制、连续自然、不遮脸`，不得加入手位、脚位、转身角度、动作名称或固定收势。
- 将原“85mm微距拉到50mm”的M02描述改为M04沿栀夏外侧小幅侧滑，并在第一句诗期间完成唯一一次由人物中近景向双角色中景的景别变化。
- 6.048—6.200秒继续保留唯一方向变化；6.200—9.032秒由唯一雪花带出积雪向远林展开，但雪花只在栀夏开场之后成为领舞元素。
- 9.032—10.000秒保留双角色稳定结尾和无人声边界。

- [ ] **Step 4: Run all focused verification commands**

```bash
zsh zhixia-feihualing/tests/test_zhixia_first_opening_rules.sh
zsh zhixia-feihualing/tests/test_classical_dance_library_rules.sh
zsh zhixia-feihualing/tests/test_realistic_visual_style_rules.sh
zsh zhixia-feihualing/tests/test_baixue_10s_assets.sh
git diff --check -- zhixia-feihualing/docs/realistic-visual-style.md zhixia-feihualing/docs/production-workflow.md zhixia-feihualing/episodes/baixue/README.md zhixia-feihualing/episodes/baixue/prompts/scene-cards.md zhixia-feihualing/episodes/baixue/prompts/seedance-v01.md zhixia-feihualing/tests/test_zhixia_first_opening_rules.sh
```

Expected: 四个测试均输出PASS并以0退出；`git diff --check`无输出。

- [ ] **Step 5: Audit active Baixue files for superseded rules**

```bash
rg -n "8至10厘米|8 至 10 厘米|8—10厘米|微距雪晶钩子|M02" zhixia-feihualing/episodes/baixue/README.md zhixia-feihualing/episodes/baixue/prompts/scene-cards.md zhixia-feihualing/episodes/baixue/prompts/seedance-v01.md
```

Expected: 无匹配。历史文件 `seedance-structure-v01.md` 不在本次扫描范围内。

- [ ] **Step 6: Commit only the final Seedance prompt**

```bash
git add zhixia-feihualing/episodes/baixue/prompts/seedance-v01.md
git diff --cached --check
git commit -m "文档：重排白雪栀夏优先开场提示词"
```

### Task 5: 最终一致性复核

**Files:**

- Verify: `zhixia-feihualing/docs/superpowers/specs/2026-08-28-zhixia-first-opening-hook-design.md`
- Verify: `zhixia-feihualing/docs/character-bible.md`
- Verify: Task 1至Task 4的全部计划内文件。

**Interfaces:**

- Consumes: 已提交的规则测试、全局规范、单状态卡和最终提示词。
- Produces: 一份不调用任何生成服务的文字交付证据。

- [ ] **Step 1: Re-run the complete focused test set from a clean command invocation**

```bash
zsh zhixia-feihualing/tests/test_zhixia_first_opening_rules.sh
zsh zhixia-feihualing/tests/test_classical_dance_library_rules.sh
zsh zhixia-feihualing/tests/test_realistic_visual_style_rules.sh
zsh zhixia-feihualing/tests/test_baixue_10s_assets.sh
```

Expected: 四条命令均输出PASS并以0退出。

- [ ] **Step 2: Confirm task commits and preserve unrelated changes**

```bash
git log -5 --oneline
git status --short
```

Expected: 能看到四个本计划中文提交；工作区中原有的 `.cursor/rules/`、`stock-ai/` 或角色圣经改动仍保持原状，没有被暂存、还原或混入计划提交。

- [ ] **Step 3: Report the exact deliverable boundary**

汇报全局开场规范、“白雪”单状态卡文本、最终Seedance提示词与测试结果；明确本轮没有调用TTS、图片或视频生成，也没有产生费用。下一步只有在用户再次明确授权付费视频生成，并确认模型、时长、分辨率、数量和预计费用后才能执行生成。

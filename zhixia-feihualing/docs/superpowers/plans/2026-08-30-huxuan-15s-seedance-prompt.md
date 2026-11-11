# 《回雪胡旋》15 秒 Seedance 提示词 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 生成《栀夏·敦煌十六舞》第三支《回雪胡旋》的单集说明、可直接提交 Seedance 的 15 秒完整提示词和跨集三高潮去重记录。

**Architecture:** 单集目录保存内容真源与可复制提示词，提示词只使用图片 1 栀夏敦煌 v03，按 0—15 秒六段动作顺序展开。独立 Shell 验证脚本检查参考图边界、三组异轴旋转、幡幔三方向反馈、人物画面占比、无人声要求、提示词标记和历史台账唯一记录。

**Tech Stack:** Markdown、CSV、zsh、ripgrep、awk、Git。

## Global Constraints

- 设计真源为 `docs/superpowers/specs/2026-08-30-huxuan-15s-dance-design.md`。
- 15 秒、9:16、一镜到底，三次同等强度高潮分别位于 0.000—1.800、4.800—7.000、10.000—13.200 秒。
- 只上传图片 1 栀夏敦煌 v03 单张大脸锁定角色母板，不上传动作图、道具卡、场景图、旧角色卡或其他人物图。
- 全片手中无道具，只有一个栀夏，无阿砚、伴舞、乐师、观众和飞天群像。
- 三次旋转固定为立轴疾旋骤停、贴地低旋反折、斜向腾跃换轴；每组有独立进入、急停和离开，禁止连续原地转圈。
- 唯一环境机制为固定织锦幡幔受旋转气流牵引，依次纵向扬起、横向卷开、沿景深逐层掠动；不生成真实雪花、沙尘或发光粒子。
- 摄影机只有侧前方低位斜向后退主路径；三次反馈为短促微推并降低、有限侧弧移并降低、短撤并轻微抬升；第三段人物不小于画面高度约一半。
- 生成阶段无人声、无诗句、无字幕、无标题和无水印；白居易《胡旋女》四句后期另行加入。
- 只提交本次计划、单集文件、验证脚本和历史台账中的唯一新增行，保留工作区其他改动。

---

### Task 1: 建立失败验证

**Files:**
- Create: `zhixia-feihualing/tests/test_huxuan_15s_prompt.sh`
- Test: `zhixia-feihualing/episodes/huxuan-15s/README.md`
- Test: `zhixia-feihualing/episodes/huxuan-15s/prompts/seedance-v01.md`
- Test: `zhixia-feihualing/operations/dance-design-history.csv`

**Interfaces:**
- Consumes: 设计规范和预期文件路径。
- Produces: 一个可执行验收入口，验证正式提示词、单集说明和台账记录。

- [x] **Step 1: 写失败测试**

```zsh
#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
readme="$project_dir/episodes/huxuan-15s/README.md"
prompt="$project_dir/episodes/huxuan-15s/prompts/seedance-v01.md"
history_file="$project_dir/operations/dance-design-history.csv"

for required in "$readme" "$prompt" "$history_file"; do
  [[ -s "$required" ]] || { print -u2 -r -- "FAIL: missing required Huxuan component $required"; exit 1; }
done

for required_text in \
  '@图片1是本项目原创虚构数字角色栀夏' \
  '0.000—1.800秒' \
  '4.800—7.000秒' \
  '10.000—13.200秒' \
  '立轴疾旋' \
  '贴地低位枢轴旋转' \
  '斜向景深完成两次短促腾跃换轴' \
  '近处幡幔只向上纵向扬起一次' \
  '两侧幡幔只向左右横向卷开' \
  '后方幡幔由近向远逐层掠动一次' \
  '全片手中无道具' \
  '人物不得小于画面高度的约一半' \
  '不生成对白、旁白、诗歌朗诵、吟唱、歌声、歌词'; do
  rg -qF "$required_text" "$prompt" || { print -u2 -r -- "FAIL: prompt lacks $required_text"; exit 1; }
done

rg -qF '<!-- SEEDANCE_PROMPT_START -->' "$prompt" || { print -u2 "FAIL: prompt start marker missing"; exit 1; }
rg -qF '<!-- SEEDANCE_PROMPT_END -->' "$prompt" || { print -u2 "FAIL: prompt end marker missing"; exit 1; }
rg -qF '弦鼓一声双袖举' "$readme" || { print -u2 "FAIL: README lacks poem"; exit 1; }
rg -qF '千匝万周无已时' "$readme" || { print -u2 "FAIL: README lacks final poem line"; exit 1; }

awk -F, 'NF != 25 { print NR ":" NF; bad=1 } END { exit bad }' "$history_file"
[[ "$(rg -c '^huxuan-15s,' "$history_file")" == "1" ]] || { print -u2 "FAIL: Huxuan history row is missing or duplicated"; exit 1; }

prompt_body="$(sed -n '/SEEDANCE_PROMPT_START/,/SEEDANCE_PROMPT_END/p' "$prompt")"
for forbidden in 'D01' 'M01' 'H01' 'S01' '图片2' '琵琶道具卡'; do
  [[ "$prompt_body" != *"$forbidden"* ]] || { print -u2 -r -- "FAIL: prompt body contains forbidden token $forbidden"; exit 1; }
done

print -r -- "PASS: Huxuan 15s prompt and history are complete"
```

- [x] **Step 2: 运行测试确认失败**

Run: `cd zhixia-feihualing && zsh tests/test_huxuan_15s_prompt.sh`

Expected: FAIL，报告缺少 `episodes/huxuan-15s/README.md`，而不是 shell 语法错误。

### Task 2: 建立单集说明与正式提示词

**Files:**
- Create: `zhixia-feihualing/episodes/huxuan-15s/README.md`
- Create: `zhixia-feihualing/episodes/huxuan-15s/prompts/seedance-v01.md`

**Interfaces:**
- Consumes: 已确认设计规范和栀夏敦煌 v03 上传版。
- Produces: 单集定位与一段位于 `SEEDANCE_PROMPT_START/END` 标记之间、可直接提交 Seedance 的正式提示词正文。

- [x] **Step 1: 写单集 README**

README 固定包含以下信息：系列编号 03、标题《回雪胡旋》、15 秒 9:16 一镜到底、白居易《胡旋女》四句、唯一上传图路径、三高潮表、无道具与无人声边界、原片验收重点，以及当前状态“提示词已完成，等待生成原片”。四句文本准确写为：

```text
弦鼓一声双袖举，
回雪飘飖转蓬舞。
左旋右转不知疲，
千匝万周无已时。
```

- [x] **Step 2: 写参考图映射、总目标和场景**

提示词正文第一句固定为：

```text
@图片1是本项目原创虚构数字角色栀夏，不对应任何现实人物、艺人、影视动漫角色或现成舞剧资产。
```

紧接着写图片 1 只锁定 v03 大脸身份、年龄感、妆发、服装、配饰、鞋履和蓝橙双层飘带固定点，不复制角色卡排版。随后建立同一处蓝调暮色敦煌石窟前庭、赭石岩壁、朱砂旧金低舞台、固定织锦幡幔、少量油灯和单一暮光主光源，并明确不出现长城、月轮、沙漠、飞雪、沙尘、画鼓、佛像特写和现代舞台。

- [x] **Step 3: 写 0—10 秒动作链**

按以下四段顺序写清落脚、承重、躯干、手臂、腿部、飘带、幡幔和镜头反应：

1. `0.000—1.800秒`：未完成立轴疾旋截入，0.200 秒内换重加速，上下错层双螺旋，纵向急停，镜头短促微推并降低，近处幡幔只纵向扬起一次。
2. `1.800—4.800秒`：一至两步小范围弧形圆场、重心下降、双臂前后回收，不站定、不奔跑、不追加完整旋转。
3. `4.800—7.000秒`：前脚横踏、后膝接近地面、贴地低位枢轴旋转、外倾反折、低位宽三角、横向急停，镜头有限侧弧移并降低，两侧幡幔只横向卷开。
4. `7.000—10.000秒`：提身后斜向交叉舞步、一次不超过 90 度改面、双臂形成前后长斜线，为腾跃换轴蓄势。

- [x] **Step 4: 写 10—15 秒动作链**

`10.000—13.200秒` 写沿斜向景深完成两次短促腾跃换轴：第一次落地换脚承重，第二次反向转体并落地即刹停；最终形成一屈一伸、前后错层的纵深长线。镜头只短撤并轻微抬升，人物不得小于画面高度约一半；后方幡幔由近向远逐层掠动一次。

`13.200—15.000秒` 写第三次落地余势中的前后换重和上肢反向展开，飘带自然回落，最后一帧仍在有效舞动中切断，不站定谢幕、不拉成大远景。

- [x] **Step 5: 写连续性、运镜、声音与禁止项**

集中锁定一个栀夏、v03 同一张脸、固定服化道、唯一一组上臂固定蓝橙飘带、固定幡幔悬挂点和单一侧前低位斜向后退镜头路径。声音使用无人声的快速西域乐舞配乐、连续短音弦拨、手鼓与小框鼓节拍、真实脚步和衣料破风；明确不生成对白、旁白、诗歌朗诵、吟唱、歌声、歌词、字幕、标题、水印和 logo。禁止连续原地转圈、旋转镜头伪造动作、道具、其他人物、雪花、沙尘、发光粒子、多肢、脚底滑行、飘带或幡幔穿体。

- [x] **Step 6: 运行测试观察下一处预期失败**

Run: `cd zhixia-feihualing && zsh tests/test_huxuan_15s_prompt.sh`

Expected: README 与提示词检查通过，仅因 `operations/dance-design-history.csv` 尚无唯一 `huxuan-15s` 行而失败。

### Task 3: 登记去重台账并完成验证

**Files:**
- Modify: `zhixia-feihualing/operations/dance-design-history.csv`
- Modify: `zhixia-feihualing/docs/superpowers/plans/2026-08-30-huxuan-15s-seedance-prompt.md`

**Interfaces:**
- Consumes: Task 2 已固化的三高潮顺序、承接物轨迹和镜头反馈。
- Produces: 唯一 `huxuan-15s` 去重记录、已完成计划和通过验证的正式提示词。

- [x] **Step 1: 追加唯一历史记录**

在 CSV 末尾追加以下完整 25 列记录，不修改已有行：

```csv
huxuan-15s,白居易《胡旋女》,未完成立轴疾旋双袖错层上挑,小范围弧形圆场转斜向交叉舞步,三高潮异轴旋转,一组立轴疾旋；一组贴地低旋；两次斜向腾跃换轴且落地即刹停,直立窄轴；低位外倾；腾跃换轴,三分之四侧脸立轴疾旋转一高一低纵向急停,上挑与斜下错层；贴地宽扫与侧上反折；前后长斜线,收合落脚；低位宽三角；一屈一伸前后线,蓝橙双层飘带与固定织锦幡幔,上下错层双螺旋；低位横向宽扇；前后错层纵深长线,织锦幡幔受旋转气流牵引,近处纵向扬起；两侧横向卷开；由近向远逐层掠动,0.000—1.800秒；4.800—7.000秒；10.000—13.200秒,侧前低位斜向后退主路径三次反应,短促微推并降低；有限侧弧移并降低；短撤并轻微抬升,反向落地刹停后继续换重并在余势中切断,designed,敦煌十六舞03；仅上传栀夏v03；无阿砚无道具；四句诗后期加入；禁止真实雪花和连续原地转圈,立轴疾旋骤停；贴地低旋反折；斜向腾跃换轴,纵向；横向；斜向纵深,0.000—1.800秒；4.800—7.000秒；10.000—13.200秒,双带上下错层双螺旋；贴地横向宽扇；前后错层纵深长线,短促微推并降低；有限侧弧移并降低；短撤并轻微抬升
```

- [x] **Step 2: 标记计划完成并运行最终验证**

将本计划的所有 checkbox 改为 `[x]`，然后运行：

```bash
cd zhixia-feihualing
zsh tests/test_huxuan_15s_prompt.sh
awk -F, 'NF != 25 { print NR ":" NF; bad=1 } END { exit bad }' operations/dance-design-history.csv
test "$(rg -c '^huxuan-15s,' operations/dance-design-history.csv)" = "1"
git diff --check -- episodes/huxuan-15s tests/test_huxuan_15s_prompt.sh operations/dance-design-history.csv docs/superpowers/plans/2026-08-30-huxuan-15s-seedance-prompt.md
```

Expected: 专用测试输出 PASS；CSV 每行 25 列；`huxuan-15s` 仅一行；差异检查无错误。

- [x] **Step 3: 提交提示词**

只暂存本计划、单集 README、正式提示词、验证脚本和历史台账中的 `huxuan-15s` 新增行，使用中文提交：

```bash
git commit -m '制作敦煌回雪胡旋视频提示词'
```

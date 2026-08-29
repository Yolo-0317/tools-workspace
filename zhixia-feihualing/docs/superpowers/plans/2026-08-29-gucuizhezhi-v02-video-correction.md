# 《鼓催柘枝》Seedance v02 成片问题修正 Implementation Plan

> **For agentic workers:** 按 TDD 顺序执行：先建立并观察 v02 缺失导致的失败，再生成提示词和复盘说明，最后运行 v01/v02 与三高潮相关回归测试。

**Goal:** 产出一份仍只上传单张栀夏角色卡、但针对首轮成片六项问题重新排序和量化的 Seedance v02 提示词。

**Architecture:** 保留 v01 作为首轮生成追溯，新建 v02 可复制区块。新测试解析 v02 区块，验证首帧低位、七秒后零旋转、第三高潮纵深沉提、三种互斥沙迹、手带空气间隙和末段人物最小画面占比；README 记录首轮问题并把 v02 设为下一次生成入口。

**Tech Stack:** Markdown、Zsh、Python 标准库、现有 shell 测试套件。

## Global Constraints

- 仍只上传 `@图片1` 一张栀夏敦煌角色卡，不新增动作卡或参考视频。
- 保留 v01，不回写首轮提示词。
- 第一可见帧即低位交叉弓步，0.000—0.200 秒开始爆发。
- 全片只有 4.800—7.000 秒一次改面翻身，7.000 秒后零次完整或接近完整旋转。
- 第三高潮是零旋转的纵深强踏、急沉、后腿延伸和前后轴提展。
- 三种细沙分别为垂直窄柱、单侧贴地直线、贴地纵深楔形。
- 手掌、手指与飘带始终保留可见空气间隙。
- 结尾栀夏全身高度始终不低于画面 55%。

---

### Task 1: 建立 v02 生成契约失败测试

**Files:**
- Create: `zhixia-feihualing/tests/test_gucuizhezhi_15s_seedance_v02_correction.sh`
- Test: `zhixia-feihualing/episodes/gucuizhezhi-15s/prompts/seedance-v02.md`
- Test: `zhixia-feihualing/episodes/gucuizhezhi-15s/README.md`

**Interfaces:**
- Consumes: 唯一 START/END 标记之间的 Seedance 正文。
- Produces: 可重复执行的 v02 结构验收，防止六项问题再次进入下一轮提示词。

- [x] **Step 1: 写入失败测试**

测试解析正文并验证：只有 `@图片1`；六段时窗各一次；首帧含 `从动作中段直接截入`、`髋部明显低于正常站姿`、`0.000—0.200 秒`；第三段含 `零旋转`、`深弓步`、`前后轴强力提展`；七秒后含 `骨盆和胸口不得完成 180 度转向`；三种沙迹、手带空气间隙、70%/65%/60%/55% 占比完整；正文不含诗句、`@图片2`、`不完整半转` 或内部文件路径。

- [x] **Step 2: 运行测试确认失败**

Run:

```bash
zsh zhixia-feihualing/tests/test_gucuizhezhi_15s_seedance_v02_correction.sh
```

Expected: FAIL，明确报告缺少 `seedance-v02.md`。

### Task 2: 生成结构重写后的 v02 提示词

**Files:**
- Create: `zhixia-feihualing/episodes/gucuizhezhi-15s/prompts/seedance-v02.md`
- Reference: `zhixia-feihualing/docs/superpowers/specs/2026-08-29-gucuizhezhi-v02-video-correction-design.md`

**Interfaces:**
- Consumes: 六项修正规范与现有 v01 的身份、服化道、场景和声音边界。
- Produces: 单图输入、可直接复制的 v02 Seedance 正文。

- [x] **Step 1: 重排提示词优先级**

正文按“原创身份声明 → 第一可见帧 → 六段动作 → 镜头占比 → 飘带连接 → 三种细沙 → 服化道与场景 → 声音和共同禁止项”组织，避免长场景描述挤占开场动作优先级。

- [x] **Step 2: 写入六项量化修正**

取消结尾半转；第二高潮后全部零旋转；第三高潮使用深弓步与前后轴提展；第二段细沙固定向画面右侧直线扫出，第三段固定为从画面下方近景指向后侧画鼓的贴地楔形；所有关键帧保持手带空气间隙；结尾人物高度不低于 55%。

- [x] **Step 3: 运行定向测试转绿**

Run:

```bash
zsh zhixia-feihualing/tests/test_gucuizhezhi_15s_seedance_v02_correction.sh
```

Expected: PASS。

### Task 3: 更新单集复盘并回归验证

**Files:**
- Modify: `zhixia-feihualing/episodes/gucuizhezhi-15s/README.md`
- Test: `zhixia-feihualing/tests/test_gucuizhezhi_15s_seedance_prompt.sh`
- Test: `zhixia-feihualing/tests/test_three_equal_climaxes_rules.sh`

**Interfaces:**
- Consumes: 首轮视频逐帧复盘和已通过的 v02 提示词。
- Produces: 清楚标明 v01 首轮问题、v02 下一次生成入口与待生成状态的单集说明。

- [x] **Step 1: 更新 README**

保留诗句与输入说明，新增“首轮成片复盘”和“下一次生成”两节，逐项记录六个问题并链接 `prompts/seedance-v02.md`。不得声称 v02 视频已经生成。

- [x] **Step 2: 运行定向与相关回归测试**

Run:

```bash
zsh zhixia-feihualing/tests/test_gucuizhezhi_15s_seedance_v02_correction.sh
zsh zhixia-feihualing/tests/test_gucuizhezhi_15s_seedance_prompt.sh
zsh zhixia-feihualing/tests/test_three_equal_climaxes_rules.sh
```

Expected: 三项全部 PASS。

- [x] **Step 3: 检查并提交**

运行 `git diff --check`，仅暂存 v02 规范、计划、提示词、README 与新测试，中文提交信息：

```bash
git commit -m '修正鼓催柘枝首轮成片六项问题'
```

# 《天宫热舞》栀夏与阿砚双人卡点摇 10 秒 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 产出一份可直接提交 Seedance 的栀夏与阿砚双人 10 秒卡点摇提示词，以及与之匹配的纯音乐结构和首轮生成验收清单。

**Architecture:** 在新的独立 episode 目录中分别保存视频提示词、音乐结构和验收清单，避免与上一条单人天宫恰恰混写。提示词以两张已确认角色母板分别锁定身份，以单镜头时间线约束双人动作；音乐文件只定义 10 秒节拍结构；验收文件负责决定候选片保留、局部补救或整条重做。

**Tech Stack:** Markdown、Seedance 2.0 中文结构化提示词、原创电子国风音乐描述、`rg`、Git。

## Global Constraints

- 新 episode 目录固定为 `zhixia-feihualing/episodes/tiangong-hot-dance-zhixia-ayan-duet-10s/`，不得覆盖既有单人恰恰 episode。
- 视频固定为竖屏 9:16、10 秒、1080p、写实电影感、单一连续镜头；第一帧即开始跳舞，人物运动持续至约 9.75 秒。
- 只使用纯音乐，不加入朗诵、人声、现代祝福、诗句或正文字幕。
- 音乐约 124 BPM，0 秒直接落拍，3.2 秒附近提拉，5.3 秒进入最强段落，9.7 秒最后重拍，10.0 秒同步结束。
- 栀夏固定 168 厘米并担任主舞；阿砚固定 162 厘米并担任灵动小女伴。两人必须保持脸型、身高、妆发、服装和气质差异。
- 上传图固定为 `assets/characters/栀夏天宫探戈角色母板-v02-真人面容修复-Seedance上传版.jpg` 与阿砚天宫限定人形角色母板的确认上传版；实际实施前先从阿砚固定说明中解析其精确文件名，不得凭空新建或替换角色卡。
- 阿砚始终是成年女性人形，严格两只笔锋猫耳、两条宽飘带和一条连接尾骨的开放 S 形墨尾，不变回四足猫形。
- 动作采用双人卡点摇与轻爵士融合；只允许一次单手牵引换位，不使用地板动作、翻滚、高踢腿、跳跃落地、快速 360 度旋转或反复身体接触。
- 场景采用前景英雄式天宫，两人约占画面高度 70%，全程完整显示脚步；不切特写、不环绕、不高速甩镜。
- 本计划只创建文本资产并执行文本验证，不调用 Seedance、不生成视频、不使用任何付费服务。

---

### Task 1: 建立 episode 与双角色 Seedance 提示词

**Files:**
- Reference: `zhixia-feihualing/docs/superpowers/specs/2026-09-02-heavenly-hot-dance-duet-10s-design.md`
- Reference: `zhixia-feihualing/assets/characters/栀夏天宫探戈角色母板-v02-真人面容修复-Seedance固定说明.md`
- Reference: `zhixia-feihualing/assets/characters/阿砚天宫限定人形角色母板-v01-Seedance固定说明.md`
- Create: `zhixia-feihualing/episodes/tiangong-hot-dance-zhixia-ayan-duet-10s/prompt.md`

**Interfaces:**
- Consumes: 已确认的 10 秒动作设计与两份角色固定说明。
- Produces: 一份含上传顺序、角色身份、场景、逐段动作、摄影、禁止项、参数和付费门禁的完整中文 Seedance 提示词。

- [ ] **Step 1: 解析两张实际上传图路径**

Run:

```bash
rg -n "上传版|唯一上传|上传图片" zhixia-feihualing/assets/characters/栀夏天宫探戈角色母板-v02-真人面容修复-Seedance固定说明.md zhixia-feihualing/assets/characters/阿砚天宫限定人形角色母板-v01-Seedance固定说明.md
rg --files zhixia-feihualing/assets/characters | rg "栀夏天宫探戈角色母板-v02.*Seedance上传版|阿砚天宫限定人形角色母板-v01.*Seedance上传版"
```

Expected: 栀夏与阿砚各解析出一张真实存在的 Seedance 上传版文件；若阿砚没有独立上传版，则停止在文本实施阶段，不调用 Seedance，也不自行选用候选图。

- [ ] **Step 2: 建立提示词文件头和上传规则**

在 `prompt.md` 开头写明：

```text
# 《天宫双姝·步步生风》Seedance 双人 10 秒提示词

## 当前状态
- 设计已确认，等待首轮低成本生成。
- 本文件只固化提示词，不代表已经授权或执行外部付费生成。

## 上传图片
- 图 1：栀夏 v02 真人面容修复 Seedance 上传版，用于锁定栀夏。
- 图 2：阿砚天宫限定人形 v01 Seedance 上传版，用于锁定阿砚。
- 不上传其他栀夏、阿砚单人照、旧角色卡、视频首帧或第三张参考图。
```

把 Step 1 得到的两个精确相对路径写进对应条目，并声明“图 1 只对应栀夏，图 2 只对应阿砚，不得平均或融合两张脸”。

- [ ] **Step 3: 写入双角色身份段**

身份段必须完整包含：

```text
图1中的栀夏与图2中的阿砚是两位面容、身高、妆发、服装和气质清楚不同的原创成年女性角色。栀夏固定168cm并担任主舞；阿砚固定162cm并担任灵动小女伴。分别严格读取两张角色卡右侧唯一大型“面部基准 / FACE IDENTITY”，不得互换、平均、融合或把两人生成成双胞胎。
```

随后分别复制两份固定说明中的角色身份、比例与造型约束：栀夏保留自然成年骨相、九天仙家云髻、白玉仙冠、月白浅心形无肩带抹胸、右侧唯一高开衩、严格两片宽飘带和 5.5 厘米包头舞鞋；阿砚保留短圆鹅蛋脸、及肩墨发、严格两只笔锋猫耳、中央朱砂额印、白墨不对称舞衣、严格两条宽飘带、唯一开放 S 形墨尾和 5.5 厘米包头舞鞋。不得复制栀夏单人固定说明中的“全片只有栀夏一人”等旧视频范围句，本片人物范围以本计划的栀夏与阿砚双人关系为准。

- [ ] **Step 4: 写入场景、表演总则和摄影段**

场景与摄影使用以下完整骨架：

```text
竖屏9:16，写实电影感仙境。两位角色站在前景白玉天阶，身后是恢宏金色天门、层叠天宫与云海纵深，朝阳从天门后方穿过，地面只有克制流动金光。两人约占画面高度70%，栀夏略靠近镜头，阿砚略靠侧后方；完整头顶到鞋底始终在画面内，人物不能为了展示建筑而缩小。

单一连续镜头，正面偏约15度的四分之三方向，摄影机只做稳定而克制的轻微推进。第一帧两人已经开始运动，不站立等待，不使用环境空镜；不切特写、不环绕、不高速甩镜、不突然俯拍或仰拍，全程清楚显示两人的完整脚步。
```

表演总则明确：栀夏动作先发且幅度略大；阿砚使用晚半拍镜像、较小幅度和不同层次呼应；两人自然欢喜、松弛自信，阿砚可更俏皮，但都不持续直视、不露齿营业笑、不夸张媚态。

- [ ] **Step 5: 写入 10 秒动作时间线**

使用五段精确边界，不改变设计稿的动作关系：

```text
0.000—1.200秒：第一帧即开跳。栀夏斜前侧跨，肩与胯连续两次清楚卡点；阿砚在侧后方晚半拍镜像呼应。
1.200—3.200秒：栀夏向前完成轻快交叉步，手臂沿斜线打开，髋部左右切换；阿砚用较小交错步和反方向手臂路线呼应，两人不接触。
3.200—5.300秒：全片唯一一次单手牵引换位。栀夏回身伸出靠内侧的手，阿砚接手后沿开阔弧线绕至另一侧，完成换位立即松手；不双手缠绕、不连续转圈、不互相遮挡。
5.300—7.800秒：两人并排完成侧步、肩部hit、髋部切换和手腕甩点；栀夏幅度略大，阿砚在一个重拍加入小幅踮步。两道宽飘带分别成弧，墨尾自然扬起但不扫过栀夏。
7.800—10.000秒：栀夏前跨半步，以抬臂和身体上提压住最后两个重拍；阿砚退到侧后方踮步转半身。人物持续运动至约9.75秒，9.7秒最后重拍后只保留约0.25秒稳定画面，视频在10.0秒结束。
```

- [ ] **Step 6: 写入禁止项、参数与门禁**

禁止项至少覆盖：第三位人物、换脸、双胞胎脸、身份融合、身高互换、额外手脚、手指粘连、人物互穿、服装交换、飘带穿体或变细、猫耳增减、尾巴分叉或消失、四足猫形、网红脸、塑料皮肤、玻璃大眼、固定数字微笑、脚步漂移、浮脚、低角度窥视、胸部特写、地板动作、翻滚、高踢腿、跳跃落地、快速 360 度旋转和反复牵手。

参数固定写成：

```text
- 画幅：9:16
- 时长：10秒
- 清晰度：1080p
- 镜头：单一连续镜头
- 音频：关闭模型人声；视频生成阶段可无声，后期配入独立纯音乐
- 生成策略：每轮只生成1条候选，先验收人物身份、手部、尾巴和首秒动作，再决定是否继续
- 门禁：任何外部付费生成必须获得用户当次明确确认
```

- [ ] **Step 7: 验证并提交提示词**

Run:

```bash
rg -n "图1只对应栀夏|图2只对应阿砚|168cm|162cm|两只笔锋猫耳|一条.*开放S形墨尾|第一帧即开跳|唯一一次单手牵引换位|9\.75秒|约占画面高度70%|任何外部付费生成" zhixia-feihualing/episodes/tiangong-hot-dance-zhixia-ayan-duet-10s/prompt.md
git diff --no-index --check /dev/null zhixia-feihualing/episodes/tiangong-hot-dance-zhixia-ayan-duet-10s/prompt.md
test $? -le 1
```

Expected: 每项约束至少命中一次，`git diff --check` 退出码为 0。

显式只暂存 `prompt.md` 并提交：

```text
文档：增加天宫双人热舞提示词
```

### Task 2: 创建 10 秒原创纯音乐结构

**Files:**
- Reference: `zhixia-feihualing/docs/superpowers/specs/2026-09-02-heavenly-hot-dance-duet-10s-design.md`
- Create: `zhixia-feihualing/episodes/tiangong-hot-dance-zhixia-ayan-duet-10s/music-structure.md`

**Interfaces:**
- Consumes: Prompt 中五段动作时间线。
- Produces: 可用于生成原创音乐或后期剪辑的节拍、配器、能量和结束点说明。

- [ ] **Step 1: 写入音乐生成描述**

使用以下核心文案：

```text
10秒原创电子国风舞曲，约124 BPM，明亮、热烈、轻快但不幼稚。清晰四拍电子鼓、弹性贝斯、短促琵琶拨弦与少量编钟点缀；无歌词、无念白、无可辨识人声采样。0秒直接落第一拍，没有前奏和渐入；3.2秒附近短提拉，对应单手牵引换位；5.3秒进入最强鼓点；9.7秒落下最后一个明确重拍；10.0秒干净结束，无拖尾、无淡出。
```

- [ ] **Step 2: 写入动作同步表**

表格必须包含 `0.0–1.2`、`1.2–3.2`、`3.2–5.3`、`5.3–7.8`、`7.8–10.0` 五个时间段，并逐一对应首秒肩胯卡点、交叉步、牵手换位、并排强卡点和高低错层结尾。

- [ ] **Step 3: 写入音频验收条件**

验收条件必须包含：起始 0.2 秒内可听见明确舞蹈重拍；3.2 秒和 5.3 秒存在可辨识能量变化；9.7 秒最后重拍清楚；10.0 秒无残响拖尾；全片无人声；不得听起来像古风抒情前奏或电影环境配乐。

- [ ] **Step 4: 验证并提交音乐结构**

Run:

```bash
rg -n "124 BPM|0秒直接|3\.2秒|5\.3秒|9\.7秒|10\.0秒|无歌词|无淡出" zhixia-feihualing/episodes/tiangong-hot-dance-zhixia-ayan-duet-10s/music-structure.md
git diff --no-index --check /dev/null zhixia-feihualing/episodes/tiangong-hot-dance-zhixia-ayan-duet-10s/music-structure.md
test $? -le 1
```

Expected: 所有音乐节点与无声约束均命中，空白检查退出码为 0。

显式只暂存 `music-structure.md` 并提交：

```text
文档：固化天宫双人热舞音乐结构
```

### Task 3: 创建首轮生成验收与止损清单

**Files:**
- Reference: `zhixia-feihualing/docs/superpowers/specs/2026-09-02-heavenly-hot-dance-duet-10s-design.md`
- Reference: `zhixia-feihualing/episodes/tiangong-hot-dance-zhixia-ayan-duet-10s/prompt.md`
- Create: `zhixia-feihualing/episodes/tiangong-hot-dance-zhixia-ayan-duet-10s/qa-checklist.md`

**Interfaces:**
- Consumes: Task 1 的生成提示词和 Task 2 的音乐节点。
- Produces: 一份逐段验收表，以及“直接淘汰、可剪辑保留、可进入后期”的明确决策规则。

- [ ] **Step 1: 写入逐段检查表**

按五段时间线分别检查：首秒是否开跳；主从交错是否清楚；唯一牵手换位是否无手部融合；并排段是否踩中强拍；最后是否运动到 9.75 秒并与音乐同时结束。

- [ ] **Step 2: 写入角色与技术硬门槛**

以下任一情况直接淘汰整条候选，不进入后期：

```text
- 栀夏或阿砚换脸、融合、明显网红脸，或两人变成近似双胞胎。
- 阿砚不是严格两只猫耳、唯一一条连接尾骨的开放S形墨尾，或中途变成四足猫形。
- 出现第三人、额外肢体、明显手指粘连、人物互穿、服装交换或严重脚步漂移。
- 前1秒没有舞蹈动作，牵手换位超过一次，或人物在9秒前已经停舞。
- 人物过小、脚部长期出画，或镜头变成面部、胸部、腿部特写。
```

- [ ] **Step 3: 写入可剪辑保留标准**

只有在角色身份、手部、尾巴和完整脚步全部合格时，才允许用剪辑处理轻微问题。可剪辑问题仅限：开头或结尾不超过 0.2 秒的空余、音乐响度不均、轻微色温偏差、天宫背景局部闪烁但不碰人物轮廓。任何角色结构错误不能靠剪辑掩盖。

- [ ] **Step 4: 写入首轮策略和验证命令**

首轮只生成一条候选；先静音检查画面，再对照音乐节点检查节拍。若硬门槛失败，记录失败段和单一主要原因，下一轮只修改对应约束，不同时重写舞种、场景和摄影。

Run:

```bash
rg -n "直接淘汰|两只猫耳|开放S形墨尾|前1秒|9秒前|可剪辑|只生成一条|单一主要原因" zhixia-feihualing/episodes/tiangong-hot-dance-zhixia-ayan-duet-10s/qa-checklist.md
git diff --no-index --check /dev/null zhixia-feihualing/episodes/tiangong-hot-dance-zhixia-ayan-duet-10s/qa-checklist.md
test $? -le 1
```

Expected: 硬门槛、可剪辑范围和止损策略均命中，空白检查退出码为 0。

显式只暂存 `qa-checklist.md` 并提交：

```text
文档：增加天宫双人热舞首轮验收清单
```

### Task 4: 全套文本一致性与非回归验证

**Files:**
- Inspect: `zhixia-feihualing/episodes/tiangong-hot-dance-zhixia-ayan-duet-10s/prompt.md`
- Inspect: `zhixia-feihualing/episodes/tiangong-hot-dance-zhixia-ayan-duet-10s/music-structure.md`
- Inspect: `zhixia-feihualing/episodes/tiangong-hot-dance-zhixia-ayan-duet-10s/qa-checklist.md`

**Interfaces:**
- Consumes: Tasks 1–3 的三个文本产物。
- Produces: 时间节点、人物身份、生成参数和付费门禁一致的可执行素材包。

- [ ] **Step 1: 检查三份文件时间节点一致**

Run:

```bash
for file in prompt.md music-structure.md qa-checklist.md; do rg -n "0|1\.2|3\.2|5\.3|7\.8|9\.7|10" "zhixia-feihualing/episodes/tiangong-hot-dance-zhixia-ayan-duet-10s/$file"; done
```

Expected: 三份文件都覆盖 10 秒边界；`prompt.md` 和 `music-structure.md` 完整覆盖五段动作节点，`qa-checklist.md` 至少覆盖首秒、牵手段、强卡点段和结尾节点。

- [ ] **Step 2: 检查纯音乐与无字幕边界**

Run:

```bash
rg -n "纯音乐|无歌词|无人声|不加入朗诵|不加入.*字幕|关闭模型人声" zhixia-feihualing/episodes/tiangong-hot-dance-zhixia-ayan-duet-10s/{prompt.md,music-structure.md,qa-checklist.md}
```

Expected: 提示词明确关闭模型人声并排除朗诵字幕，音乐结构明确无人声，验收清单不要求朗诵或正文字幕。

- [ ] **Step 3: 检查旧单人恰恰文件未被修改**

Run:

```bash
git diff --exit-code -- zhixia-feihualing/episodes/yiwu-yiyuan-huanxi-cha-cha-10s/prompt.md zhixia-feihualing/episodes/yiwu-yiyuan-huanxi-cha-cha-10s/prompt-natural-face-v02.md
```

Expected: 命令退出码为 0，无差异输出。

- [ ] **Step 4: 检查工作区与提交范围**

Run:

```bash
git status --short -- zhixia-feihualing/episodes/tiangong-hot-dance-zhixia-ayan-duet-10s zhixia-feihualing/docs/superpowers/specs/2026-09-02-heavenly-hot-dance-duet-10s-design.md
git log -4 --oneline -- zhixia-feihualing/episodes/tiangong-hot-dance-zhixia-ayan-duet-10s
```

Expected: episode 三个计划产物均已各自提交，设计稿保持已提交状态；没有把工作区其他现有改动带入这些提交。不推送、不调用 Seedance。

# 《一舞一愿》天宫恰恰自然面容提示词 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不覆盖旧成片原始提示词的前提下，生成一份使用天宫角色卡 v02、保持自然欢喜且系统规避网红脸的 10 秒天宫恰恰完整 Seedance 提示词。

**Architecture:** 以现有 `prompt.md` 为动作、场景、音乐和参数基线，创建独立的 `prompt-natural-face-v02.md` 保存下一轮提示词，确保旧成片仍可追溯。新版本只替换唯一上传图、面容身份、表情视线、面部光线、摄影限制和验收项，不改变舞步时间线、天宫构图、音乐、时长或付费门禁。

**Tech Stack:** Markdown、Seedance 2.0 中文结构化提示词、`rg`、Git。

## Global Constraints

- 旧 `episodes/yiwu-yiyuan-huanxi-cha-cha-10s/prompt.md` 保持不变，继续记录 v01 原片的真实生成输入。
- 新建 `episodes/yiwu-yiyuan-huanxi-cha-cha-10s/prompt-natural-face-v02.md`，不得覆盖旧文件。
- 唯一上传图改为 `assets/characters/栀夏天宫探戈角色母板-v02-真人面容修复-Seedance上传版.jpg`；该资产未正式归档前不得实际调用 Seedance。
- 保持 9:16、10 秒、1080p、单镜头、前景英雄式天宫、人物高度 70%—75%、原恰恰舞步时间线、约 124 BPM 器乐和后期朗诵分工不变。
- 栀夏保持自然欢喜、松弛自信；嘴唇自然闭合，只在踩中重拍时短暂轻扬嘴角。
- 视线主要跟随脚步、转身和手臂轨迹，只允许偶尔自然掠过镜头；禁止持续直视、露齿甜笑、眨眼卖萌、回眸营业和固定微笑。
- 面部保持成年骨相、自然下颌宽度、正常虹膜与眼白比例、轻微左右不对称和真实皮肤明暗；禁止网红脸、大瞳孔、尖下巴、瓷白磨皮、蜡像油光和无影美颜光。
- 主要保持四分之三正面，摄影机保持完整全身至中全景，不增加脸部或胸部特写。
- 本任务只写提示词并进行文本验证，不生成视频、不调用付费服务。

---

### Task 1: 创建自然面容 v02 完整提示词

**Files:**
- Reference: `zhixia-feihualing/episodes/yiwu-yiyuan-huanxi-cha-cha-10s/prompt.md`
- Reference: `zhixia-feihualing/docs/superpowers/specs/2026-09-02-yiwu-yiyuan-heavenly-cha-cha-natural-face-prompt-design.md`
- Create: `zhixia-feihualing/episodes/yiwu-yiyuan-huanxi-cha-cha-10s/prompt-natural-face-v02.md`

**Interfaces:**
- Consumes: 旧版完整 Seedance 正文、已确认的自然面容设计规范。
- Produces: 一份可复制、可文本验收、等待 v02 角色卡正式归档后使用的完整 Seedance 提示词。

- [ ] **Step 1: 复制结构并更新状态与唯一上传图**

新文件保留旧文件的“当前状态、唯一上传图片、Seedance 可复制正文、生成参数与门禁、第一轮验收”结构。当前状态明确写成：

```text
- 自然面容 v02 提示词设计已确认。
- 本文件用于 v02 角色卡低成本对照测试和后续同方向新视频。
- 只写提示词，不代表已经授权或执行外部付费生成。
```

唯一上传图固定为：

```text
assets/characters/栀夏天宫探戈角色母板-v02-真人面容修复-Seedance上传版.jpg
```

同时声明该文件正式归档前不得调用 Seedance，不同时上传单人照、v01 角色卡或其他栀夏母板。

- [ ] **Step 2: 重写角色身份首段**

角色身份首段保留服装、身高与角色卡排版排除项，并加入以下完整面容段：

```text
面部严格沿用角色卡右侧唯一大型正面“面部基准 / FACE IDENTITY”，全片保持同一位18岁成年栀夏。保持自然成年骨相、自然下颌宽度、正常眼球与虹膜比例、清楚眼白、克制眼部高光和轻微左右不对称；皮肤保留细微纹理、自然肤色变化以及眼下、鼻翼、面颊和唇周的真实明暗过渡。禁止放大黑亮瞳孔、玻璃眼、动漫眼、尖锐V脸、网红脸、幼态脸、瓷白磨皮、蜡像油光、塑料皮肤、美颜滤镜和五官漂移。
```

- [ ] **Step 3: 重写场景面部光线**

保留白玉天宫、暖金日光、人物大小和背景纵深，删除会把脸照成平面的“明亮暖金日光照亮”泛化表达，改为：

```text
侧前方暖金自然日光照亮月白丝缎和淡金边饰，并在脸部形成柔和但明确的明暗交界，保留眼窝、鼻翼、面颊和下颌转折；另一侧只有克制的环境反光，不把全脸均匀提亮。禁止正面无影美颜光、环形灯效果、过曝白雾和皮肤高光带。
```

- [ ] **Step 4: 重写表演总则**

删除“神态明亮亲切，带少量自然俏皮地回应镜头”，替换为：

```text
她具有资深舞者随音乐即兴起舞的松弛自信：踩点准确、轻快有弹性，神态自然欢喜。嘴唇自然闭合，只在踩中重拍时短暂轻扬嘴角；视线主要跟随脚步方向、转身路线和手臂轨迹，偶尔自然掠过镜头但不持续直视，不露齿甜笑、不眨眼卖萌、不做固定营业表情，不过度媚态，不做竞技比赛式夸张表演。
```

- [ ] **Step 5: 逐段替换表情和视线指令**

四个时间段保持原舞步与时间边界，只替换表情指令：

```text
0.000—2.500秒：检查步启动时看向行进斜前方，嘴唇自然闭合，不从正面凝视镜头开始。
2.500—4.400秒：纽约步转向时，视线随交叉检查与手臂打开看向动作方向，回收时自然回到三分之四正面。
4.400—7.500秒：锁步时看向推进方向；定点转身中头部最后跟随身体，转完视线自然回正，只从镜头方向短暂掠过。
7.500—10.000秒：取消“轻快回眸”；最后一次换重时头部随身体方向自然回到三分之四正面，重拍处嘴角短暂轻扬，闭口结束，不对镜头定格甜笑。
```

- [ ] **Step 6: 加强摄影与禁止项**

摄影段加入：

```text
人物主要保持四分之三正面，正脸只在舞步自然回正时短暂出现；不长时间形成证件照式正面凝视。摄影机保持完整全身至中全景，不增加脸部或胸部特写，不让面部占满画面。
```

最终禁止项加入：

```text
不得生成持续直视镜头、露齿甜笑、眨眼卖萌、回眸营业、固定数字微笑、放大黑亮瞳孔、玻璃眼、尖锐V脸、网红妆感、瓷白磨皮、蜡像油光、塑料皮肤、正面无影美颜光、环形灯效果或全脸均匀提亮。
```

- [ ] **Step 7: 扩展第一轮验收**

保留旧版八项验收，并新增：

```text
9. 面部保持角色卡中的成年骨相、自然下颌、正常虹膜和眼白比例，皮肤有真实明暗；表情自然欢喜但没有持续直视、露齿甜笑、眨眼卖萌、回眸营业或固定微笑。
```

### Task 2: 文本一致性与非回归验证

**Files:**
- Inspect: `zhixia-feihualing/episodes/yiwu-yiyuan-huanxi-cha-cha-10s/prompt.md`
- Inspect: `zhixia-feihualing/episodes/yiwu-yiyuan-huanxi-cha-cha-10s/prompt-natural-face-v02.md`

**Interfaces:**
- Consumes: Task 1 的完整 v02 提示词。
- Produces: 旧版未变、新版关键约束齐全且无旧风险措辞的验证结果。

- [ ] **Step 1: 验证新版包含全部关键约束**

Run:

```bash
rg -n "v02-真人面容修复-Seedance上传版|自然成年骨相|正常眼球与虹膜比例|自然欢喜|不持续直视|侧前方暖金自然日光|四分之三正面|不得生成持续直视镜头|^9\. 面部保持" zhixia-feihualing/episodes/yiwu-yiyuan-huanxi-cha-cha-10s/prompt-natural-face-v02.md
```

Expected: 每个模式至少命中一次，覆盖上传图、身份、表情、光线、摄影、禁止项和验收项。

- [ ] **Step 2: 验证旧风险措辞已从新版移除**

Run:

```bash
! rg -n "明亮亲切|自然俏皮地回应镜头|神态亲切明亮|表情转为更轻快、更自信|轻快回眸" zhixia-feihualing/episodes/yiwu-yiyuan-huanxi-cha-cha-10s/prompt-natural-face-v02.md
```

Expected: 命令退出码为 0，无匹配输出。

- [ ] **Step 3: 验证旧提示词没有被修改**

Run:

```bash
git diff --exit-code -- zhixia-feihualing/episodes/yiwu-yiyuan-huanxi-cha-cha-10s/prompt.md
```

Expected: 命令退出码为 0，无差异输出。

- [ ] **Step 4: 检查 Markdown 差异**

Run:

```bash
git diff --check -- zhixia-feihualing/episodes/yiwu-yiyuan-huanxi-cha-cha-10s/prompt-natural-face-v02.md
```

Expected: 命令退出码为 0，无空白错误。

- [ ] **Step 5: 只提交计划内文件**

显式暂存新提示词文件，不暂存旧提示词或工作区其他改动。提交信息：

```text
文档：增加天宫恰恰自然面容提示词
```

提交后回读 SHA、文件统计和文件名；不推送、不调用 Seedance。

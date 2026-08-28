# 《登高》10 秒 Seedance 提示词 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 产出一份以已确认自然 TTS 时长、临江山脊石台和三张人工确认状态卡为依据、可直接提交 Seedance 的《登高》10 秒无声人物诗镜提示词。

**Architecture:** 已完成的四段 TTS 作为唯一声音时间轴；文字阶段先把三张状态卡和 Seedance 正式提示词全部改为“石阶贴地追叶—掠过双角色—越肩抬升揭江”。图片与视频生成分别设置明确用户指令门禁，讨论或审稿期间不调用生成工具。

**Tech Stack:** JSON 配音清单、豆包 TTS 元数据、Markdown 状态卡提示词、ImageGen 状态卡、Seedance 2.0 提示词、`rg`、`ffprobe`、Git。

## Global Constraints

- 输出固定为 10 秒、9:16 竖屏、完全连续的一镜到底。
- 诗句固定为“无边落木萧萧下，不尽长江滚滚来”。
- 极短互动固定为阿砚“风起了！”、栀夏“看江上。”。
- 真实声音区间固定为 `0.600—2.064`、`2.160—3.624`、`3.740—6.572`、`6.690—8.946` 秒。
- 全片只使用 M01“石阶贴地追叶—掠过双角色—越肩连续抬升揭江”、H05 单片枯叶引镜和 S03 极少量真实落叶。
- 场景固定为宽阔安全的临江山脊石台，不出现船、码头或现代建筑。
- 角色输入只使用栀夏与阿砚最新完整高写实 CG 母版；母版只锁定身份、结构和材质，不复刻档案卡排版或文字。
- 阿砚始终严格两只笔锋耳、四足、朱砂额印、浅暖金纹样和唯一开放式 S 形墨尾。
- Seedance 提示词正文不得出现具体对白、诗句原文、字幕、Logo 或水印。
- Seedance 允许生成背景音乐和环境声，永久禁止对白、朗诵、旁白、吟唱、耳语和任何可辨识人声。
- 讨论、选方案、修改创意和审阅提示词期间不得生成图片或视频；必须取得“生成图片”或“生成视频”的当次明确指令。
- 正式付费视频生成前记录模型、分辨率、时长、生成数量和预计费用，并取得当次确认。

---

### Task 1: 建立带上下文情绪的配音清单

**Files:**
- Created: `zhixia-feihualing/episodes/denggao-10s/voice-lines.json`

**Interfaces:**
- Consumes: `zhixia-feihualing/config/voices.json` 中的 `ayan` 与 `zhixia` 固定音色映射。
- Produces: 四段带 `context_texts` 的台词 ID：`01-ayan-hook`、`02-zhixia-hook`、`03-zhixia-poem-one`、`04-zhixia-poem-two`。

- [x] **Step 1: 写入四段配音清单和连续情绪导演指令**

情绪弧线固定为“发现风势的灵动—温柔引向江面—开阔沉静与轻微苍茫—壮阔坚定”。

- [x] **Step 2: 运行免费预览并确认四次调用**

Run: `cd zhixia-feihualing && python3 scripts/generate_episode_audio.py --episode denggao-10s`

Expected: 预览四句调用，不在预览阶段请求语音接口。

- [x] **Step 3: 提交配音清单**

Commit: `ca8ef69 建立《登高》十秒诗镜配音清单`

### Task 2: 生成 TTS 并按真实时长锁定时间轴

**Files:**
- Created: `zhixia-feihualing/assets/audio/denggao-10s/*.mp3`
- Created: `zhixia-feihualing/assets/audio/denggao-10s/audio-metadata.json`
- Modified: `zhixia-feihualing/episodes/denggao-10s/voice-lines.json`

**Interfaces:**
- Consumes: Task 1 的四段台词清单与用户对四次实际 TTS 调用的当次确认。
- Produces: 四段已就绪音频和最终 `start_ms`：`600`、`2160`、`3740`、`6690`。

- [x] **Step 1: 经当次确认后生成四段 TTS**

四个 MP3 均已生成，元数据四行均为 `status: ready`。

- [x] **Step 2: 核对音频编码与真实时长**

结果固定为 MP3、24000 Hz、单声道；时长依次为 `1.464`、`1.464`、`2.832`、`2.256` 秒。

- [x] **Step 3: 用真实时长重排绝对起点**

最终区间为 `0.600—2.064`、`2.160—3.624`、`3.740—6.572`、`6.690—8.946` 秒，末尾保留 `1.054` 秒稳定构图。

- [x] **Step 4: 验证时间轴无重叠并提交**

Commit: `f4aef6b 锁定《登高》十秒诗镜声音时间轴`

### Task 3: 改写无船版三张状态卡提示词

**Files:**
- Modify: `zhixia-feihualing/episodes/denggao-10s/prompts/scene-cards.md`

**Interfaces:**
- Consumes: 已确认无船版设计、Task 2 真实时间节点、两张最新完整角色母版。
- Produces: 三份不触发生成的文字提示词，分别描述石阶起始、石栏转折和长江揭示。

- [ ] **Step 1: 锁定最新完整角色母版路径**

栀夏固定为 `zhixia-feihualing/assets/characters/归档/栀夏角色母板高写实CG-v04-完整档案增彩版.png`；阿砚固定为 `zhixia-feihualing/assets/characters/归档/阿砚角色母板高写实CG-v01-最终版.png`。明确只参考身份、结构、比例和材质，不复刻母版排版、分栏或文字。

- [ ] **Step 2: 写入状态卡 01“石阶枯叶钩子”**

固定为离地约 10 厘米、24mm 广角、赭黄引导叶极近前景、风化石阶强透视、阿砚前景追叶、栀夏远端中景闭嘴倾听。画面必须无船、无码头、无文字。

- [ ] **Step 3: 写入状态卡 02“石栏抬升转折”**

固定为同一石台和光向、35mm 中近景、栀夏三分之四侧面望向江面、阿砚脚边仰望、引导叶刚被上升气流托起；人物仍是主体。

- [ ] **Step 4: 写入状态卡 03“大江双角色揭示”**

固定为摄影机升至肩侧并向外侧绕约 45 度、50mm 镜头、栀夏和阿砚前景至中景三分之四正面、蓝绿色长江和层叠秋山完整展开；角色不得缩成远景小点。

- [ ] **Step 5: 验证无船约束与格式**

Run: `rg -n '最新完整母版|石阶枯叶钩子|石栏抬升转折|大江双角色揭示|禁止.*船' zhixia-feihualing/episodes/denggao-10s/prompts/scene-cards.md`

Expected: 五项均有输出。

Run: `rg -n '三桅|甲板|船头|船舷|航向|船体' zhixia-feihualing/episodes/denggao-10s/prompts/scene-cards.md`

Expected: 无输出。

### Task 4: 编写并验证无船版 Seedance 正式提示词

**Files:**
- Create: `zhixia-feihualing/episodes/denggao-10s/prompts/seedance-v01.md`

**Interfaces:**
- Consumes: Task 2 最终时间节点、Task 3 三张状态卡提示词和已确认设计稿。
- Produces: `SEEDANCE_PROMPT_START` 与 `SEEDANCE_PROMPT_END` 之间可直接提交 Seedance 的无船版提示词，以及标记区外的后期对白和字幕时间轴。

- [ ] **Step 1: 写入参考资产映射与最高优先级约束**

上传顺序预留为：栀夏最新完整母版、阿砚最新完整母版、起始卡、转折卡、结尾卡。明确完整母版只锁定角色，三张状态卡锁定同一石台、石栏、秋树、江流方向、主光源、清透调色和 M01 连续空间。

- [ ] **Step 2: 写入真实音频节点对应的视觉时间轴**

按 `0.000—0.600`、`0.600—2.064`、`2.064—2.160`、`2.160—3.624`、`3.624—3.740`、`3.740—6.572`、`6.572—6.690`、`6.690—8.946`、`8.946—10.000` 秒分段。标记区内只描述无声口型、镜头、叶片、人物和环境，不写具体对白与诗句。

- [ ] **Step 3: 写入背景音乐与环境声**

配乐固定为低音古琴、轻弦乐和克制低频鼓点；`6.690` 秒抬升揭示形成唯一小高潮，`8.946` 秒后自然收住。环境声固定为江流、山风掠叶、衣料轻响和枯叶擦过石阶，不出现船体或帆布声音，也不出现人声采样、吟唱或喊声。

- [ ] **Step 4: 写入核心禁止项**

禁止任何可辨识人声、口型触发声音、具体中文文字、切镜、360 度旋转、多次甩镜、角色消失、栀夏换脸换装、阿砚猫狐化或多尾、船与码头、石台结构跳变、江流方向反转、落叶风暴、动漫化、游戏 CG、塑料皮肤、灰雾脏画面和全屏粒子。

- [ ] **Step 5: 验证结构、原文泄漏和无船约束**

Run: `rg -n 'SEEDANCE_PROMPT_START|SEEDANCE_PROMPT_END|最高优先级|M01|H05|S03|永久禁止人声|背景音乐与环境声|核心禁止项' zhixia-feihualing/episodes/denggao-10s/prompts/seedance-v01.md`

Expected: 每个固定区块均至少出现一次。

Run: `sed -n '/SEEDANCE_PROMPT_START/,/SEEDANCE_PROMPT_END/p' zhixia-feihualing/episodes/denggao-10s/prompts/seedance-v01.md | rg '风起了|看江上|无边落木|不尽长江'`

Expected: 无输出；具体对白与诗句只存在于标记区外的后期清单。

Run: `rg -n '三桅|甲板|船头|船舷|航向|船体|帆布' zhixia-feihualing/episodes/denggao-10s/prompts/seedance-v01.md`

Expected: 无输出。

- [ ] **Step 6: 检查格式并提交文字提示词**

Run: `git diff --check -- zhixia-feihualing/episodes/denggao-10s/prompts/scene-cards.md zhixia-feihualing/episodes/denggao-10s/prompts/seedance-v01.md`

Expected: 退出码为 0，无空白错误。

```bash
git add zhixia-feihualing/episodes/denggao-10s/prompts/scene-cards.md zhixia-feihualing/episodes/denggao-10s/prompts/seedance-v01.md
git commit -m "改写《登高》无船版生成提示词"
```

### Task 5: 经明确指令后生成并验收三张状态卡

**Files:**
- Create after explicit approval: `zhixia-feihualing/episodes/denggao-10s/assets/scene-cards/01-stone-step-leaf-hook-v01.png`
- Create after explicit approval: `zhixia-feihualing/episodes/denggao-10s/assets/scene-cards/02-terrace-rise-turn-v01.png`
- Create after explicit approval: `zhixia-feihualing/episodes/denggao-10s/assets/scene-cards/03-river-double-reveal-v01.png`

**Interfaces:**
- Consumes: Task 3 提示词、两张最新完整角色母版，以及用户当次明确的“生成图片”指令。
- Produces: 一套同石台、同江向、同光源、同角色身份的起始、转折和结尾状态卡。

- [ ] **Step 1: 等待并记录图片生成指令**

没有用户明确的“生成图片”指令时，本任务保持未执行，不调用 ImageGen。

- [ ] **Step 2: 分别生成三张 9:16 状态卡**

每次生成上传栀夏、阿砚最新完整母版；第二张与第三张额外引用前一张已确认状态卡保持空间连续。每张单独生成，不覆盖其他剧集资产。

- [ ] **Step 3: 按固定顺序人工验收**

检查角色身份与数量、栀夏脸和服装、阿砚两耳四足单尾、同一石阶石栏秋树、江流方向、角色占比、单一光源、电影级材质、枯叶数量与方向、无船、无文字。任一项失败时只修改对应状态卡提示词，并在再次明确同意后重生成该卡。

- [ ] **Step 4: 经用户确认后登记正式资产**

只有用户确认三张图片后，才把路径写入正式 Seedance 输入清单并提交状态卡资产。

### Task 6: 经明确付费确认后生成视频

**Files:**
- Create after explicit approval: `zhixia-feihualing/episodes/denggao-10s/assets/video/content-raw-v01.mp4`

**Interfaces:**
- Consumes: Task 4 正式提示词、Task 5 已确认状态卡，以及用户对当次模型、规格、数量和预计费用的明确确认。
- Produces: 10 秒、9:16、无模型人声与文字的 Seedance 原始视频。

- [ ] **Step 1: 展示当次付费预览**

记录模型、10 秒时长、9:16 分辨率、生成数量、预计费用和输入资产，不执行生成。

- [ ] **Step 2: 等待明确“生成视频”确认**

未取得当次确认时不调用视频生成。

- [ ] **Step 3: 生成并按设计节点验收**

抽检第一帧、`2.160`、`3.740`、`6.690`、`8.946` 秒和最终帧；任一角色、空间、材质、文字或人声门禁失败时不进入后期。

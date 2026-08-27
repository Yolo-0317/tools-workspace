# 《夜宿山寺》真人电影化半写实提示词升级 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 产出一份可直接粘贴到 Seedance 2.0 的《夜宿山寺》15 秒真人电影化半写实梦境长镜头提示词，并用自动检查防止角色卡遗漏、动画风格回潮和人声错序问题。

**Architecture:** 在本集 `prompts/` 下新增独立的 Seedance v02 提示词文档，不覆盖现有场景卡和已归档原片。测试脚本只检查付费生成前不可缺失的硬规则；对白、两句诗和字幕作为后期音频清单保存在同一文档的 Seedance 提示词区块之外，保证视频模型不会接触可辨识台词文本。

**Tech Stack:** Markdown、zsh、Python 3 标准库、现有角色卡与 Seedance 2.0。

## Global Constraints

- 角色卡只锁定栀夏与阿砚的身份和造型，不继承二维动画、插画或游戏 CG 材质。
- 最终画面采用真人电影化半写实东方奇幻；人物材质和摄影语言真实，位移、重力与空间轨迹允许超现实。
- 全片只有一个核心运镜机关：摄影机在双角色前方倒退领飞，并在高潮处停止坠落、反向上升。
- Seedance 只生成画面、东方奇幻背景音乐和环境声，不生成对白、朗诵、耳语、字幕或其他可辨识人声。
- 栀夏、阿砚对白与栀夏朗诵的两句诗全部后期加入；每句文本只在后期音频清单中出现一次。
- 不重新制作全写实角色照片，不执行额外付费视频测试。

---

### Task 1: 建立提示词硬规则回归测试

**Files:**
- Create: `zhixia-feihualing/tests/test_yesu_shansi_seedance_v02_prompt.sh`
- Test: `zhixia-feihualing/episodes/yesu-shansi/prompts/seedance-v02-live-action-oner.md`

**Interfaces:**
- Consumes: 升级设计中的资产映射、风格锁、运镜、声音与禁止项要求。
- Produces: 一个退出码为 0/1 的独立门禁脚本；后续提示词修改必须通过该脚本。

- [ ] **Step 1: 新建失败测试，检查目标文件和 Seedance 区块**

测试脚本使用 Python 3 读取目标 Markdown，并以 `<!-- SEEDANCE_PROMPT_START -->` 和 `<!-- SEEDANCE_PROMPT_END -->` 截取真正提交给 Seedance 的文本。脚本逐项断言以下字符串存在：

```text
栀夏角色卡
阿砚角色卡
只锁定身份与造型
真人电影化半写实
真实皮肤微纹理
真实眼球湿润反光
独立发丝
真实丝织衣料
真实幻想生物毛发
前方倒退领飞
停止坠落并反向上升
一镜到底
不生成可辨识人声
不生成字幕、诗句、标题、Logo或水印
```

脚本还要断言 Seedance 区块不包含下列可辨识文本：

```text
栀夏，跟紧我
明明是你跟紧我
阿砚，那是星星吗
伸手就知道了
危楼高百尺
手可摘星辰
```

- [ ] **Step 2: 运行测试并确认因目标提示词不存在而失败**

Run: `cd zhixia-feihualing && bash tests/test_yesu_shansi_seedance_v02_prompt.sh`

Expected: FAIL，明确报告 `episodes/yesu-shansi/prompts/seedance-v02-live-action-oner.md` 不存在。

- [ ] **Step 3: 提交测试门禁**

```bash
git add zhixia-feihualing/tests/test_yesu_shansi_seedance_v02_prompt.sh
git commit -m "增加夜宿山寺提示词风格门禁"
```

### Task 2: 编写 Seedance 2.0 完整视频提示词

**Files:**
- Create: `zhixia-feihualing/episodes/yesu-shansi/prompts/seedance-v02-live-action-oner.md`
- Test: `zhixia-feihualing/tests/test_yesu_shansi_seedance_v02_prompt.sh`

**Interfaces:**
- Consumes: 栀夏、阿砚角色卡，四张本集场景卡，以及 Task 1 的固定区块标记和检查字符串。
- Produces: 一个可直接复制的 Seedance 提示词区块，以及不提交给 Seedance 的后期声音时间轴。

- [ ] **Step 1: 写入参考资产映射与最高优先级风格锁**

提示词开头逐张定义：栀夏角色卡只负责栀夏身份与服装；阿砚角色卡只负责阿砚物种与纹样；场景卡只负责高塔、云海、星空、人物位置和色调。明确所有参考图均不限制最终真人电影材质。

- [ ] **Step 2: 写入四段 15 秒一镜到底时间轴**

```text
0.0—3.0秒：强视差双角色中近景，镜头已在前方倒退领飞。
3.0—9.5秒：双角色从低处远方持续飞向高塔，镜头保持前方倒退领飞。
9.5—12.0秒：镜头停止坠落并反向上升，贴塔抬升揭示塔顶星空。
12.0—15.0秒：两人抵达塔顶接近星辰，镜头减速但保持轻微上升与弧线运动。
```

每段只允许一个摄影机主动作、栀夏一个主动作、阿砚一个主动作和一个环境变化；所有段落连续衔接，不写切镜。

- [ ] **Step 3: 写入背景音乐、环境声和核心禁止项**

生成音轨只包含克制东方奇幻音乐、持续风声、一次远处铜铃、踏云的柔和低频和一次触星的清透高频。明确不生成人声；禁止项压缩为动画化、游戏 CG、角色漂移、随机切镜、错误文字五类。

- [ ] **Step 4: 在 Seedance 区块外写入后期声音清单**

后期清单按唯一顺序记录四句短对白和两句诗：

```text
D1 阿砚：栀夏，跟紧我。
D2 栀夏：明明是你跟紧我。
D3 栀夏：阿砚，那是星星吗？
D4 阿砚：伸手就知道了。
P1 栀夏：危楼高百尺。
P2 栀夏：手可摘星辰。
```

每句只出现一次；若总时长冲突，优先删除 D3、D4，不压缩或打乱 P1、P2。

- [ ] **Step 5: 运行提示词门禁并确认通过**

Run: `cd zhixia-feihualing && bash tests/test_yesu_shansi_seedance_v02_prompt.sh`

Expected: PASS，输出角色卡映射、真人电影化半写实风格、核心运镜、人声隔离和诗词隔离全部通过。

- [ ] **Step 6: 提交完整提示词**

```bash
git add zhixia-feihualing/episodes/yesu-shansi/prompts/seedance-v02-live-action-oner.md
git commit -m "升级夜宿山寺真人电影化提示词"
```

### Task 3: 最终一致性验证与用户交付

**Files:**
- Verify: `zhixia-feihualing/episodes/yesu-shansi/prompts/seedance-v02-live-action-oner.md`
- Verify: `zhixia-feihualing/tests/test_yesu_shansi_seedance_v02_prompt.sh`
- Verify: `zhixia-feihualing/docs/superpowers/specs/2026-08-27-yesu-shansi-live-action-semi-real-prompt-upgrade-design.md`

**Interfaces:**
- Consumes: Task 1 的门禁和 Task 2 的完整提示词。
- Produces: 可直接复制的 Seedance 提示词、独立后期声音清单和验证结论。

- [ ] **Step 1: 检查设计覆盖与文本重复**

运行 Python 检查四句对白和两句诗在整份文档中各出现一次，并确认它们全部位于 `SEEDANCE_PROMPT_END` 之后。

- [ ] **Step 2: 运行完整验证**

```bash
cd zhixia-feihualing
bash tests/test_yesu_shansi_seedance_v02_prompt.sh
git diff --check -- episodes/yesu-shansi/prompts/seedance-v02-live-action-oner.md tests/test_yesu_shansi_seedance_v02_prompt.sh
```

Expected: 测试退出码 0，`git diff --check` 无输出。

- [ ] **Step 3: 向用户交付**

提供提示词文件的可点击链接，并在对话中复制完整 Seedance 区块；另外标明后期对白与两句诗不要粘贴进 Seedance。

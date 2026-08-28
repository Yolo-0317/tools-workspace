# 《白雪歌》层次舞蹈与动作触发运镜提示词 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把《白雪歌》最终 Seedance 2.0 提示词从“舞蹈完全自由＋简单侧移”重写为可观察的层次舞蹈短句与一条主路径上的两次动作触发运镜反应。

**Architecture:** 保持基础级输入，只使用栀夏与阿砚两张角色母版。先用单集回归测试锁定动作、摄影、角色和声音边界，再重写可复制提示词及 README 概述；不修改全局规范、状态卡或后期声音文件。

**Tech Stack:** Markdown、Zsh、ripgrep、Git。

## Global Constraints

- 图片1为原创虚拟角色栀夏，图片2为原创虚拟东方墨灵阿砚；正文第一句保留固定原创虚构角色声明。
- 不上传状态卡、场景图或动作参考视频。
- 栀夏首帧可辨认，0.5 秒内产生第一个清楚动作；阿砚保持约 40 厘米成年猫尺度与原创结构。
- 舞蹈必须包含弧线移动、两次换重、方向或高低层次、上肢与衣料反馈及稳定收势，不写内部动作代码、剧目名称、逐拍编舞或精确角度。
- 摄影机只有一条侧向贴身跟随并逐渐拉开的主路径，最多两次由可见动作触发的小幅反应，并写清前景视差和最终构图。
- Seedance 不生成对白、朗诵、吟唱、字幕或精确说话口型；阿砚“梨花？”、栀夏“是新雪。”及诗句均由后期完成。
- 本次不生成图片或视频，不产生付费素材。

---

### Task 1: 建立《白雪歌》新版提示词回归门禁

**Files:**
- Create: `zhixia-feihualing/tests/test_baixue_layered_dance_camera_prompt.sh`
- Test: `zhixia-feihualing/episodes/baixue/prompts/seedance-v01.md`
- Test: `zhixia-feihualing/episodes/baixue/README.md`

**Interfaces:**
- Consumes: `docs/realistic-visual-style.md` 中的基础级输入、可观察舞蹈条件和主路径规则。
- Produces: 一个检查最终可复制正文与 README 是否符合本集设计的 Zsh 回归测试。

- [ ] **Step 1: 写失败测试**

测试必须要求提示词正文包含：`0.5 秒内`、`沿小弧线迈步`、`重心由后脚平滑移向前脚`、`第二次换重`、`由微沉进入提起`、`高低错落的连续圆弧`、`一条主路径`、`第一次动作触发反应`、`第二次动作触发反应`、`前景视差`、`约40厘米`。同时拒绝：`具体动作、连接与收势由 Seedance 自由发挥`、`摄影机始终位于`、内部 `Dxx/Mxx` 代码、真实梨花和可辨识人声。

```zsh
#!/bin/zsh
set -euo pipefail
project_dir="${0:A:h:h}"
prompt="$project_dir/episodes/baixue/prompts/seedance-v01.md"
readme="$project_dir/episodes/baixue/README.md"
prompt_block="$(sed -n '/<!-- SEEDANCE_PROMPT_START -->/,/<!-- SEEDANCE_PROMPT_END -->/p' "$prompt")"
for phrase in "0.5 秒内" "沿小弧线迈步" "重心由后脚平滑移向前脚" "第二次换重" "由微沉进入提起" "高低错落的连续圆弧" "一条主路径" "第一次动作触发反应" "第二次动作触发反应" "前景视差" "约40厘米"; do
  print -r -- "$prompt_block" | rg -qF "$phrase"
done
if print -r -- "$prompt_block" | rg -q '具体动作、连接与收势由 Seedance 自由发挥|摄影机始终位于|(^|[^[:alnum:]])[DM][0-9]{2}([^[:alnum:]]|$)'; then exit 1; fi
rg -qF "两次动作触发反应" "$readme"
```

- [ ] **Step 2: 运行测试并确认旧提示词失败**

Run: `zsh zhixia-feihualing/tests/test_baixue_layered_dance_camera_prompt.sh`

Expected: FAIL，因为旧提示词缺少弧线移动、两次换重和两次动作触发反应。

### Task 2: 重写最终提示词与单集概述

**Files:**
- Modify: `zhixia-feihualing/episodes/baixue/prompts/seedance-v01.md`
- Modify: `zhixia-feihualing/episodes/baixue/README.md`
- Test: `zhixia-feihualing/tests/test_baixue_layered_dance_camera_prompt.sh`

**Interfaces:**
- Consumes: `docs/superpowers/specs/2026-08-28-baixue-layered-dance-camera-prompt-design.md`。
- Produces: 可直接复制给 Seedance 2.0 的新版正文，以及与正文一致的单集说明。

- [ ] **Step 1: 重写舞蹈短句**

正文按自然顺序写清：稳定站姿起势、沿小弧线迈步、第一次重心转移、侧向弧移、第二次换重、微沉至提起、转向覆雪松枝、双臂高低错落圆弧、衣袖与裙摆延迟反馈、三分之四正面稳定收势。保留“中国古典舞身韵、轻盈克制、连续自然、不遮脸”，删除完全自由发挥句。

- [ ] **Step 2: 重写摄影机主路径**

正文写成：正面偏侧中全景起始；近处覆雪松针形成前景视差；沿侧向贴身跟随并逐渐拉开的一条主路径；栀夏微沉换重时摄影机小幅降低；落雪显现时沿原路径向侧后方有限弧移并拉开；最终停在较宽三分之四正面双角色构图。

- [ ] **Step 3: 同步角色、环境和声音边界**

保留固定原创声明、两张图片唯一用途、栀夏 0.5 秒内首动作、阿砚约 40 厘米、冬季雪景、自然落雪、无人声声音边界和少量高风险禁止项。README 删除“具体动作自由发挥”和“简单连续侧移”的旧概述，改为本设计的动作与运镜摘要。

- [ ] **Step 4: 运行单集测试并确认通过**

Run: `zsh zhixia-feihualing/tests/test_baixue_layered_dance_camera_prompt.sh`

Expected: `PASS: Baixue layered dance and action-triggered camera prompt is enforced`

### Task 3: 回归验证与提交

**Files:**
- Verify: `zhixia-feihualing/episodes/baixue/prompts/seedance-v01.md`
- Verify: `zhixia-feihualing/episodes/baixue/README.md`
- Verify: `zhixia-feihualing/tests/test_baixue_layered_dance_camera_prompt.sh`

**Interfaces:**
- Consumes: Task 1 的新测试和 Task 2 的新提示词。
- Produces: 经全局与单集规则共同验证的《白雪歌》最终提示词。

- [ ] **Step 1: 运行全部相关测试**

```zsh
zsh zhixia-feihualing/tests/test_baixue_layered_dance_camera_prompt.sh
zsh zhixia-feihualing/tests/test_seedance_evidence_tiered_prompt_rules.sh
zsh zhixia-feihualing/tests/test_zhixia_first_opening_rules.sh
zsh zhixia-feihualing/tests/test_classical_dance_library_rules.sh
git diff --check
```

Expected: 所有测试输出 `PASS`，`git diff --check` 无输出并返回 0。

- [ ] **Step 2: 检查提示词正文边界**

确认正文没有状态卡、资产路径、内部代码、真实梨花、可辨识人声、精确口型或逐毫秒 TTS 节点；确认 README 仍明确本次不生成图片或视频。

- [ ] **Step 3: 提交实现**

```zsh
git add zhixia-feihualing/episodes/baixue/prompts/seedance-v01.md zhixia-feihualing/episodes/baixue/README.md zhixia-feihualing/tests/test_baixue_layered_dance_camera_prompt.sh
git commit -m "重写白雪歌舞蹈运镜提示词"
```

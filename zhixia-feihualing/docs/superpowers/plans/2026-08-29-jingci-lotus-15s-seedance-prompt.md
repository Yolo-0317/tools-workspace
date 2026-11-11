# 《晓出净慈寺送林子方》15 秒 Seedance 提示词 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 生成一份可直接提交给 Seedance 2.0 的 15 秒全诗舞蹈诗境提示词，并登记单集说明与编舞指纹。

**Architecture:** `seedance-v01.md` 用标记区分外层制作说明和可复制提示词正文；正文只包含两张原创角色母版映射、15 秒诗景、舞蹈、环境因果、摄影机、角色稳定和声音边界。单集 README 保存全诗与后期朗诵策略，去重台账追加最终采用的视觉指纹；一个 Zsh/Python 门禁只检查可复制正文和台账结果。

**Tech Stack:** Markdown、Zsh、Python 标准库、ripgrep

## Global Constraints

- 输入仅为栀夏和阿砚两张原创虚拟角色母版与纯文字提示词。
- 输出为 15 秒、9:16、一镜到底、电影级高写实东方幻想 CG。
- 栀夏第一帧为尚未完成但可发力的低位蓄势，1 秒内进入第一个主体舞句。
- 栀夏不得持续奔跑；单次位移只用一至两步连接舞句，每个主要舞句至少组合两类中国古典舞动作要素。
- 主高潮动作家族为低位扫展，不使用完整旋转作为主体。
- 唯一主要视觉效果为水纹推动荷叶舒展与红荷由近及远连续盛开。
- 摄影机沿水面附近缓慢后退并逐渐抬升，不追赶奔跑人物，不以真实前景遮脸。
- 阿砚保持约 40 厘米和外扩纸纤维，以四足短跑与一次短距离避让动态跟随。
- Seedance 不生成人声、诗句、字幕或口型；四句全诗由栀夏后期朗诵并分布在完整 15 秒。

---

### Task 1: 建立单集提示词失败门禁

**Files:**
- Create: `tests/test_jingci_lotus_15s_seedance_prompt.sh`
- Test: `episodes/jingci-lotus-15s/prompts/seedance-v01.md`
- Test: `operations/dance-design-history.csv`

**Interfaces:**
- Consumes: 提示词标记区和编舞台账。
- Produces: 缺少关键动作、误含诗句人声、出现内部代码或未登记指纹时退出非零的门禁。

- [x] **Step 1: 写入会失败的门禁**

测试要求提示词恰好包含一个 `SEEDANCE_PROMPT_START` 与一个 `SEEDANCE_PROMPT_END`，并在标记区内检查原创角色声明、`15 秒`、`9:16`、`一镜到底`、`尚未完成但可发力`、`低位扫展`、`一至两步`、`不得持续奔跑`、`水纹`、`荷叶`、`红荷`、`摄影机围绕舞姿`、`阿砚可以奔跑跟随`、`不生成任何可辨识人声`。同时拒绝四句诗文、内部编号、资产路径和状态卡术语。

- [x] **Step 2: 运行门禁确认红灯**

Run: `zsh tests/test_jingci_lotus_15s_seedance_prompt.sh`

Expected: FAIL，提示单集提示词不存在。

### Task 2: 编写单集提示词并登记视觉指纹

**Files:**
- Create: `episodes/jingci-lotus-15s/prompts/seedance-v01.md`
- Create: `episodes/jingci-lotus-15s/README.md`
- Modify: `operations/dance-design-history.csv`
- Test: `tests/test_jingci_lotus_15s_seedance_prompt.sh`

**Interfaces:**
- Consumes: 已确认的单集设计和两张角色母版。
- Produces: 可复制 Seedance 提示词、单集说明和一行去重指纹。

- [x] **Step 1: 编写外层说明与可复制正文**

外层说明列出输入图片和后期全诗朗诵边界；标记区正文以原创虚构角色声明开头，按 0—1 秒、1—5 秒、5—10 秒、10—15 秒四个宽时间段写可观察动作链，并以声音隔离结尾。正文不粘贴诗句，不写内部动作家族代码、文件路径、状态卡编号或验收说明。

- [x] **Step 2: 写入单集 README**

README 保存杨万里全诗、15 秒朗诵策略、双角色输入、低位扫展舞蹈、荷叶红荷因果、摄影机路径、阿砚动态参与和提示词链接。

- [x] **Step 3: 追加去重台账**

向 `operations/dance-design-history.csv` 追加 `jingci-lotus-15s` 一行，登记低位蓄势、一至两步弧形连接、低位扫展、无完整旋转、线性水纹与荷花开放、9—14 秒高潮、抬升拉开和运动中切断。

- [x] **Step 4: 运行门禁确认绿灯**

Run: `zsh tests/test_jingci_lotus_15s_seedance_prompt.sh`

Expected: `PASS: Jingci lotus 15s Seedance prompt is ready`

- [x] **Step 5: 运行相关规则回归**

Run: `zsh tests/test_zhixia_dance_not_running_rules.sh && zsh tests/test_choreography_diversity_v2_rules.sh && zsh tests/test_ayan_dynamic_participation_rules.sh`

Expected: 三组活动规范门禁全部通过。

- [x] **Step 6: 检查差异并提交**

Run: `git diff --check`

```bash
git add zhixia-feihualing/docs/superpowers/plans/2026-08-29-jingci-lotus-15s-seedance-prompt.md \
  zhixia-feihualing/tests/test_jingci_lotus_15s_seedance_prompt.sh \
  zhixia-feihualing/episodes/jingci-lotus-15s \
  zhixia-feihualing/operations/dance-design-history.csv
git commit -m "编写净慈寺荷花十五秒提示词"
```

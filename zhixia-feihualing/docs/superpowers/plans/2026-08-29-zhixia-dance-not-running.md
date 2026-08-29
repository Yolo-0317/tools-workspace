# 栀夏舞蹈防跑步化规则 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将“栀夏不得以持续奔跑代替舞蹈”同步到自动编舞、生产流程、视觉规范和长期记忆，并建立跨文档一致性门禁。

**Architecture:** 三份活动规范分别约束编舞选择、提示词生产和视觉验收；长期记忆保存用户确认的稳定偏好。一个轻量 Zsh 门禁检查三份活动规范均包含禁止持续奔跑、限制连接位移、舞蹈动作主体、镜头围绕舞姿和阿砚可奔跑跟随五类核心约束。

**Tech Stack:** Markdown、Zsh、ripgrep

## Global Constraints

- 栀夏不得把持续奔跑、连续疾行、长距离赶路或普通走路作为舞蹈主体。
- 单次连接位移默认一至两步，连接前后必须形成清楚舞句变化。
- 每个主要舞句至少包含两类可观察的中国古典舞动作要素。
- 衣袖、裙摆、特效和摄影机运动不得替代身体舞蹈。
- 开场第一秒呈现快速起舞过程，不允许第一帧已经停在完成姿态后只继续平移。
- 阿砚仍可真实四足奔跑跟随，但不得抢栀夏舞蹈主体。

---

### Task 1: 建立跨文档规则门禁

**Files:**
- Create: `tests/test_zhixia_dance_not_running_rules.sh`
- Test: `docs/zhixia-poetry-dance-composer.md`
- Test: `docs/production-workflow.md`
- Test: `docs/realistic-visual-style.md`

**Interfaces:**
- Consumes: 三份活动规范。
- Produces: 当任一规范缺少核心约束时退出非零的同步门禁。

- [ ] **Step 1: 写入失败门禁**

脚本逐份检查“不得以持续奔跑代替舞蹈”“一至两步连接舞句”“至少两类中国古典舞动作”“摄影机围绕舞姿”和“阿砚可以奔跑跟随”等等价明确表达，并输出缺失文件与规则名称。

- [ ] **Step 2: 运行门禁确认红灯**

Run: `zsh tests/test_zhixia_dance_not_running_rules.sh`

Expected: FAIL，因为当前规范仍允许“进入主体移动路线”，且没有限制连接步数或明确禁止跑步化。

### Task 2: 更新活动规范与长期记忆

**Files:**
- Modify: `docs/zhixia-poetry-dance-composer.md`
- Modify: `docs/production-workflow.md`
- Modify: `docs/realistic-visual-style.md`
- Modify: `../.cursor/rules/memory-workspace.mdc`
- Test: `tests/test_zhixia_dance_not_running_rules.sh`

**Interfaces:**
- Consumes: Task 1 门禁与已确认设计。
- Produces: 后续新诗境默认采用的防跑步化编舞规则和长期偏好记录。

- [ ] **Step 1: 更新自动编舞组合器**

增加独立“舞蹈不得退化为奔跑”门禁：位移仅以一至两步连接舞句；每个主要舞句至少选择两类古典舞要素；高冲击力来自重心、躯干、翻身、旋转、甩袖、云手或腾跃，不来自连续跑动。

- [ ] **Step 2: 更新生产流程与开场规则**

将“第一帧已是完整抓眼姿态”的歧义改为“第一帧为未完成的可发力蓄势，第一秒清楚呈现动作发展”；禁止用离开初始落点、疾行或持续推进冒充舞蹈启动。加入生成后两秒窗口抽检。

- [ ] **Step 3: 更新视觉规范**

明确镜头围绕舞姿和重心变化运动；前景不得遮脸；长距离空间变化需要用舞步、翻身、旋转、腾跃或重心转换完成，不允许普通跑步循环。

- [ ] **Step 4: 更新长期记忆**

在 Memory 路由索引加入“栀夏舞蹈防跑步化”，并新增 `2026-08-29-zhixia-dance-not-running` 条目，记录《山行》偏差、正式规则、阿砚例外和执行真源。

- [ ] **Step 5: 运行门禁确认绿灯**

Run: `zsh tests/test_zhixia_dance_not_running_rules.sh`

Expected: `PASS: Zhixia dance rules prevent running from replacing choreography`

- [ ] **Step 6: 运行相关规则回归**

Run: `zsh tests/test_high_impact_poetry_dance_rules.sh && zsh tests/test_choreography_diversity_v2_rules.sh && zsh tests/test_ayan_dynamic_participation_rules.sh`

Expected: 三组既有门禁全部通过，阿砚动态跟随规则保持有效。

- [ ] **Step 7: 检查差异并提交**

Run: `git diff --check`

```bash
git add zhixia-feihualing/docs/superpowers/plans/2026-08-29-zhixia-dance-not-running.md \
  zhixia-feihualing/tests/test_zhixia_dance_not_running_rules.sh \
  zhixia-feihualing/docs/zhixia-poetry-dance-composer.md \
  zhixia-feihualing/docs/production-workflow.md \
  zhixia-feihualing/docs/realistic-visual-style.md
git commit -m "落实栀夏舞蹈防跑步化规则"
```

长期记忆文件包含工作区其他用户改动时只做局部保存，不整文件暂存。

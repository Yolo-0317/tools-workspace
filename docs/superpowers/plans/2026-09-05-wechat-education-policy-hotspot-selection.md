# 公众号教育政策热点选题规则 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将近期公众号热点候选限定为全国教育政策与升学规则，并允许高讨论度地方新政在明确适用范围后进入候选。

**Architecture:** 只修改热点深评写作真源和项目记忆，不新增程序逻辑。`hotspot-deep-review.md` 保存可执行的选题范围、候选字段和事实边界，`memory-python.mdc` 只保存简短用户偏好并指向写作真源。

**Tech Stack:** Markdown、Cursor 项目规则、Git

## Global Constraints

- 近期热点候选只返回教育政策、招生考试和升学规则。
- 全国政策优先；地方政策只有在讨论度高、影响人群明确或具有推广讨论价值时纳入。
- 地方政策必须醒目标注实施地区，不得写成全国执行。
- 专家建议、机构研究和媒体解读不得写成正式政策。
- 不新增自动任务，不改变 DeepSeek 手工交接、抖音真实配图、双确认和推送授权。
- 不修改或提交工作区内与本任务无关的现有改动。

---

### Task 1: 固化教育政策热点选题偏好

**Files:**
- Modify: `.cursor/skills/wechat-mp-writing/hotspot-deep-review.md`
- Modify: `.cursor/rules/memory-python.mdc`

**Interfaces:**
- Consumes: `docs/superpowers/specs/2026-09-05-wechat-education-policy-hotspot-selection-design.md` 中已确认的选题范围与事实边界。
- Produces: 后续热点候选请求可直接执行的教育政策选题规则，以及指向该规则的项目记忆条目。

- [ ] **Step 1: 在热点写作真源中增加近期选题范围**

在 `.cursor/skills/wechat-mp-writing/hotspot-deep-review.md` 的「用户选题偏好」附近增加独立小节，写明以下内容：

```markdown
### 用户近期选题偏好：全国教育政策与升学规则

用户于 2026-09-05 确认：近期主动热点候选只聚焦教育政策、招生考试和升学规则。全国统一政策优先；只在当地实施但全网讨论度高、影响人群明确或具有推广讨论价值的地方教育新政也可纳入，必须醒目标注实施地区和适用人群。

- 优先国务院、教育部、各省教育厅和教育考试院发布的正式文件，重点关注中考分流、普高学位、指标到校、随迁子女入学、选科要求、志愿投档、教育收费和学生管理。
- 普通校园纠纷、师生私德、泛教育鸡汤和仅靠专家个人观点支撑的内容暂不纳入；事件背后存在明确制度或政策问题时除外。
- 每个候选说明政策发布主体、发布时间、原始文件、适用地区、影响人群、当前热度、家庭成本、争议点和事实风险。
- 候选按热度、家庭相关性、政策确定性和评论空间综合排序，不因标题更焦虑而提高优先级。
- 对比例、人数、实施年份及“全面取消”“统一实施”“强制要求”等强结论回到官方原文核验；明确区分已发布、即将实施、征求意见和个人建议。
- 沿用现有 DeepSeek 手工交接、事实核验、抖音真实配图和双确认流程。
```

- [ ] **Step 2: 在项目记忆中增加短索引**

在 `.cursor/rules/memory-python.mdc` 的公众号社会热点相关段落增加：

```markdown
- **2026-09-05 近期选题范围**：用户要求近期热点候选只写全国教育政策、招生考试和升学规则；高讨论度地方教育新政可纳入，但必须标明实施地区、适用人群和政策状态。优先官方原文，禁止把地方试点写成全国政策或把专家建议写成正式政策。执行真源：`.cursor/skills/wechat-mp-writing/hotspot-deep-review.md`「用户近期选题偏好：全国教育政策与升学规则」。
```

- [ ] **Step 3: 检查规则内容和工作区边界**

运行：

```bash
rg -n "用户近期选题偏好：全国教育政策与升学规则|2026-09-05 近期选题范围|地方教育新政|专家建议" \
  .cursor/skills/wechat-mp-writing/hotspot-deep-review.md \
  .cursor/rules/memory-python.mdc
git diff --check -- \
  .cursor/skills/wechat-mp-writing/hotspot-deep-review.md \
  .cursor/rules/memory-python.mdc
git diff -- \
  .cursor/skills/wechat-mp-writing/hotspot-deep-review.md \
  .cursor/rules/memory-python.mdc
```

预期：两处规则均可检索到；`git diff --check` 无输出；差异只包含本任务新增的教育政策选题条目，不覆盖已有公众号规则和用户未提交改动。

- [ ] **Step 4: 提交本次规则更新**

只暂存本任务修改的两个文件，并在提交前核对暂存差异：

```bash
git add -- \
  .cursor/skills/wechat-mp-writing/hotspot-deep-review.md \
  .cursor/rules/memory-python.mdc
git diff --cached --check
git diff --cached --stat
git commit -m "规则：聚焦教育政策热点选题"
```

预期：提交仅包含上述两个文件中的教育政策选题规则；不得带入工作区其他修改。

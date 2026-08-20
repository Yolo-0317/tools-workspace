# stock-ai Research Checkpoint Memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `stock-ai` 专项工程记忆中安全追加一条公开短线挑战者真实研究检查点。

**Architecture:** 只修改现有 `.cursor/rules/memory-python.mdc`，在“记忆条目”末尾追加一个日期化条目。以真实研究 JSON 为事实来源，保留目标文件已有未提交修改，并通过定向搜索和差异检查验证内容与隐私边界。

**Tech Stack:** Markdown、Git、`rg`、`git diff`

## Global Constraints

- 不记录数据库账号密码、完整连接串、持仓、个人交易决策、股票代码或个人投顾记忆。
- 不覆盖或重写 `.cursor/rules/memory-python.mdc` 的现有未提交修改。
- 只记录稳定工程事实；真实研究产物继续保留在 Git 忽略的 `output/` 下。
- 不执行 `freeze` 或一次性 `test`。
- 因目标文件预先为 dirty，本次不暂存或提交该 Memory 文件，避免夹带用户原有改动。

---

### Task 1: 追加并验证研究检查点

**Files:**
- Modify: `.cursor/rules/memory-python.mdc`
- Reference: `stock-ai/output/research/public_short_term_challenger/public-short-term-challenger-research-035b409a3d67c97091acd2587f6217e1b96e0bd1894f66ad5848508e4d350580.json`
- Reference: `docs/superpowers/specs/2026-08-20-stock-ai-research-checkpoint-memory-design.md`

**Interfaces:**
- Consumes: 真实研究 JSON 中的切分、三轨指标、完整性标志和权限状态。
- Produces: 标题为 `2026-08-20 公开短线挑战者真实研究检查点` 的单一 Markdown 记忆条目。

- [ ] **Step 1: 记录修改前状态**

Run: `git diff -- .cursor/rules/memory-python.mdc`

Expected: 输出目标文件已有未提交差异；保存为比对依据，不修改、不暂存。

- [ ] **Step 2: 使用 apply_patch 追加检查点**

追加以下信息：

```markdown
### 2026-08-20 公开短线挑战者真实研究检查点

- 能力边界：公开短线挑战者支持 `research`、`freeze`、一次性 `test` 三阶段；当前只完成真实 `research`，交易权限保持 `NO-TRADE`。
- 真实窗口：2024-01-10 至 2026-08-18，共 630 个确认交易日；训练、验证、测试切分为 378/126/126。
- 完整性：`point_in_time_complete=true`，`test_outcomes_read=false`；测试日期已冻结但测试结果未读取。
- 验证结论：公开反转参考、残差反转核心、回收确认执行三轨均未达标，验证资格和晋级资格均为 false。
- 核心指标：三轨验证期净期望分别约 -0.87%、-0.16%、-0.53%；Profit Factor 分别约 0.73、0.95、0.78；最大回撤分别约 71.95%、56.43%、17.81%。执行轨仅 22 个已解决样本，止损率约 45.45%。
- 已知缺陷：研究阶段复用比较器时把验证指标错误标记为 `TEST`；比较器只用有信号日期重算正收益窗口，未使用完整 126 日验证日历；V3 对照缺失，因此 assessment 为 `INCONCLUSIVE`。独立三轨指标使用完整验证日历，全部不合格的结论不受上述标签问题影响。
- 数据连接：真实运行使用项目环境配置的外网 MySQL；不得再强制改写为旧内网地址，且 Memory 不保存主机、账号、密码或完整连接串。
- 下一步：先修复比较器的阶段标签与验证日历传递，接入 V3 可比产物，再重跑 `research`；在验证门槛满足且人工确认前，不执行 `freeze` 或一次性 `test`。
- 产物身份：`035b409a3d67c97091acd2587f6217e1b96e0bd1894f66ad5848508e4d350580`；产物仅在本地忽略目录中留存。
```

- [ ] **Step 3: 验证单一条目与关键状态**

Run: `rg -n -C 12 '2026-08-20 公开短线挑战者真实研究检查点|test_outcomes_read=false|trade_permission|NO-TRADE|035b409a' .cursor/rules/memory-python.mdc`

Expected: 新标题只出现一次；输出包含 `test_outcomes_read=false`、`NO-TRADE` 和正确产物身份。

- [ ] **Step 4: 验证隐私边界与差异范围**

Run: `git diff --check -- .cursor/rules/memory-python.mdc`

Expected: 退出码为 0。

Run: `git status --short -- .cursor/rules/memory-python.mdc`

Expected: 目标文件仍显示为已修改；不进入暂存区，不提交，保留修改前已有差异与新追加条目。

- [ ] **Step 5: 汇报但不提交 dirty Memory**

汇报新条目的绝对文件链接、验证结果，以及“目标文件在本次操作前已有未提交修改，因此未暂存或提交”。

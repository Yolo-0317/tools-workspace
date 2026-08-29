# 《鼓催柘枝》15 秒试播集 Implementation Plan

> **For agentic workers:** 按 TDD 顺序执行：先建立并观察失败测试，再补齐试播集交付物，最后运行相关回归测试并提交。

**Goal:** 将已确认的《鼓催柘枝》设计规范落实为一份可直接提交 Seedance 2.0 的 15 秒提示词、单集说明和唯一一条三高潮历史记录。

**Architecture:** 单集目录保存面向生成与后期的说明，提示词文件用唯一 START/END 标记提供可复制正文；舞蹈历史 CSV 记录该集三次高潮的动作方向、时窗、飘带轨迹和镜头反馈。自动测试从标记中提取真实提交正文，并把 CSV 当作结构化数据解析，验证上传边界、三段动作时序、无人声约束和唯一台账记录。

**Tech Stack:** Markdown、CSV、Zsh、Python 标准库、现有 shell 测试套件。

## Global Constraints

- 本次只使用栀夏敦煌角色母板 v02 上传版作为 `@图片1`，不上传阿砚、道具、其他角色卡或参考视频。
- 参考图只锁定栀夏身份、妆造、服装、六项固定配饰和双层飘带，不复制角色卡版式与文字。
- 15 秒内保持纵向、横向、纵深三次同等强度高潮，严格使用已确认的六段时窗。
- 全片只有一条低位斜向后退摄影机主路径；真实金色细沙是唯一核心视觉元素。
- 白居易《柘枝妓》四句只进入 README 与后期，不进入 Seedance 可复制正文，不生成任何可辨识人声。
- 不声称视频已经生成；交付状态为“设计与提示词完成，待生成视频”。
- 不改写既有集数与历史行，不触碰工作区内无关改动。

---

### Task 1: 建立试播集交付契约测试

**Files:**
- Create: `zhixia-feihualing/tests/test_gucuizhezhi_15s_seedance_prompt.sh`
- Test: `zhixia-feihualing/episodes/gucuizhezhi-15s/prompts/seedance-v01.md`
- Test: `zhixia-feihualing/episodes/gucuizhezhi-15s/README.md`
- Test: `zhixia-feihualing/operations/dance-design-history.csv`

- [x] **Step 1: 写入失败测试**

测试以 Python 标准库解析 Markdown 标记区和 CSV，而不是把整份文档当作快照。它验证：正文可唯一提取、首行原创角色声明正确、只有 `@图片1`、六段时窗各出现一次、三高潮和单一路径可执行、诗句与内部制作术语不会泄漏到提交正文、台账中只有一条 `gucuizhezhi-15s` 且为 25 列。

- [x] **Step 2: 观察预期失败**

Run:

```bash
zsh zhixia-feihualing/tests/test_gucuizhezhi_15s_seedance_prompt.sh
```

Expected: FAIL，明确报告缺少 `seedance-v01.md`，证明测试能拦截未交付的试播集。

### Task 2: 生成单集说明与 Seedance 最终提示词

**Files:**
- Create: `zhixia-feihualing/episodes/gucuizhezhi-15s/README.md`
- Create: `zhixia-feihualing/episodes/gucuizhezhi-15s/prompts/seedance-v01.md`
- Reference: `zhixia-feihualing/docs/superpowers/specs/2026-08-29-gucuizhezhi-15s-pilot-design.md`

- [x] **Step 1: 编写 README**

记录试播定位、白居易《柘枝妓》四句、唯一上传图、生成规格、舞蹈与场景概览、后期诗句处理、关联文件和真实当前状态。

- [x] **Step 2: 编写可复制提示词**

正文第一行声明原创虚构角色和唯一上传图；之后按人物锁定、场景、六段时间轴、单一细沙机制、单一路径镜头、声音与禁止项组织自然中文提示。诗句不进入标记区，手中明确无道具，服装保持 v02 孔雀蓝与琥珀橙体系。

### Task 3: 追加唯一历史记录并转绿

**Files:**
- Modify: `zhixia-feihualing/operations/dance-design-history.csv`
- Test: `zhixia-feihualing/tests/test_gucuizhezhi_15s_seedance_prompt.sh`

- [x] **Step 1: 追加 25 列台账记录**

追加 `gucuizhezhi-15s` 一行，记录三高潮序列、纵向/横向/纵深方向、三个时窗、三种飘带轨迹、三次镜头反馈和 `designed` 状态；不得重复追加。

- [x] **Step 2: 运行定向测试**

Run:

```bash
zsh zhixia-feihualing/tests/test_gucuizhezhi_15s_seedance_prompt.sh
```

Expected: PASS。

### Task 4: 回归验证与提交

**Files:**
- Test: `zhixia-feihualing/tests/test_three_equal_climaxes_rules.sh`
- Test: other tests that parse `dance-design-history.csv`

- [x] **Step 1: 运行相关测试**

运行新测试、三高潮规则测试，以及所有引用舞蹈历史台账的 shell 测试。Expected: 全部 PASS。

- [x] **Step 2: 检查交付物**

检查 Markdown 标记、CSV 25 列、诗句隔离、文件差异和 `git diff --check`，确认无无关文件被纳入。

- [x] **Step 3: 中文提交**

仅暂存本计划、试播规范、单集 README、Seedance 提示词、测试与台账行，提交信息：

```bash
git commit -m '制作鼓催柘枝十五秒试播集提示词'
```

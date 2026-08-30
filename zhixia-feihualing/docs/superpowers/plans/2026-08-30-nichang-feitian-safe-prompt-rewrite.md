# 《霓裳飞天》安全精简提示词实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将《霓裳飞天》正式提示词改写为更短、更中性的安全版，同时完整保留三次同强度高潮及关键生成约束。

**Architecture:** 先扩充现有 shell 门禁，使其验证安全版正文不含已识别的高风险表达；确认旧正文会触发测试失败后，再仅替换提示词标记之间的正文。单集说明、舞蹈历史和已批准设计保持不变。

**Tech Stack:** Markdown、POSIX shell、`awk`、`grep`、Git。

## Global Constraints

- 保留 15 秒、9:16、一镜到底、单人栀夏和双手空置。
- 三个高潮时间窗固定为 0.000—1.800 秒、4.800—7.000 秒、10.000—13.200 秒。
- 动作依次为纵向离地提展、横向 S 形腾移、斜前低位延伸再向上提展。
- 莲瓣依次纵向扬起、左右分开、由远向近斜向掠动。
- 第三高潮人物高度至少约 60%，13—15 秒至少约 55%，镜头不后撤。
- 飘带固定在左右上臂后外侧，双手不抓飘带。
- 正文删除具体年龄数字、现实人物身份声明和伤害式人体否定词。
- 平台是否通过审核只以用户实际提交结果为准，不把本地文本检查描述为平台审核通过。

---

### Task 1: 建立安全措辞回归门禁

**Files:**
- Modify: `zhixia-feihualing/tests/test_nichang_feitian_15s_prompt.sh`
- Test: `zhixia-feihualing/tests/test_nichang_feitian_15s_prompt.sh`

**Interfaces:**
- Consumes: `<!-- SEEDANCE_PROMPT_START -->` 与 `<!-- SEEDANCE_PROMPT_END -->` 之间的正文。
- Produces: 对保留约束和删除词汇的自动检查；退出码 0 表示本地结构验证通过。

- [ ] **Step 1: 扩充测试中的必需表达**

在 `required_prompt_text` 中保留既有时间窗、莲瓣方向、镜头占比和飘带连接检查，并将第三动作要求改成安全表达：

```sh
'斜前低位延伸再向上提展'
'第三高潮人物高度至少约60%'
'13—15秒人物高度不得低于约55%'
'第三高潮保持或微推，禁止后撤'
```

- [ ] **Step 2: 增加安全正文禁用词检查**

从标记之间提取正文，并加入以下循环：

```sh
for forbidden in '18岁' '现实人物' '艺人' '俯冲' '撞击' '反关节' '穿体'; do
  if grep -Fq "$forbidden" <<<"$prompt_body"; then
    fail "safe prompt body contains risky expression: $forbidden"
  fi
done
```

- [ ] **Step 3: 运行测试并确认旧正文失败**

Run:

```bash
zsh zhixia-feihualing/tests/test_nichang_feitian_15s_prompt.sh
```

Expected: FAIL，至少报告旧正文包含 `18岁` 或缺少 `斜前低位延伸再向上提展`。

### Task 2: 替换为安全精简提示词

**Files:**
- Modify: `zhixia-feihualing/episodes/nichang-feitian-15s/prompts/seedance-v01.md`
- Test: `zhixia-feihualing/tests/test_nichang_feitian_15s_prompt.sh`

**Interfaces:**
- Consumes: 图片 1 中栀夏固定造型，以及 Task 1 的文本门禁。
- Produces: 一段可直接提交 Seedance 的安全精简正文。

- [ ] **Step 1: 保留使用说明并替换标记正文**

正文采用以下十段结构，所有句子均为中性制作指令：

1. 图片 1 只用于保持同一原创虚构角色的脸型、妆发、服装、配饰和飘带连接，不复制角色卡排版。
2. 生成 15 秒、9:16、一镜到底的单人敦煌飞天舞；栀夏双手空着。
3. 场景固定为蓝金暮色敦煌石窟莲池前庭；真实莲瓣是唯一环境反馈。
4. 0.000—1.800 秒从低位交叉步直接蹬起，完成纵向离地提展；莲瓣只向上扬起。
5. 1.800—4.800 秒用两次落脚换重转入横向路线，不增加完整旋转。
6. 4.800—7.000 秒完成左右两个方向的横向 S 形腾移；莲瓣只向左右分开。
7. 7.000—10.000 秒由横向落脚改为斜前接近，双臂和飘带形成前后长线。
8. 10.000—13.200 秒完成斜前低位延伸再向上提展；莲瓣只由远向近掠动，人物至少约 60%，镜头保持或微推。
9. 13.200—15.000 秒继续换重和反向展开，人物不低于约 55%，在动作余势中结束。
10. 结尾集中说明面部服装稳定、飘带固定、镜头不后撤、无人声和无文字。

- [ ] **Step 2: 运行提示词门禁**

Run:

```bash
zsh zhixia-feihualing/tests/test_nichang_feitian_15s_prompt.sh
```

Expected:

```text
PASS: Nichang Feitian 15s prompt and history are complete
```

- [ ] **Step 3: 检查格式和正文长度**

Run:

```bash
git diff --check -- zhixia-feihualing/episodes/nichang-feitian-15s/prompts/seedance-v01.md zhixia-feihualing/tests/test_nichang_feitian_15s_prompt.sh
awk '/SEEDANCE_PROMPT_START/{on=1;next}/SEEDANCE_PROMPT_END/{on=0}on' zhixia-feihualing/episodes/nichang-feitian-15s/prompts/seedance-v01.md | wc -m
```

Expected: `git diff --check` 无输出；安全版正文字符数明显少于旧版。

- [ ] **Step 4: 提交实现**

```bash
git add zhixia-feihualing/episodes/nichang-feitian-15s/prompts/seedance-v01.md zhixia-feihualing/tests/test_nichang_feitian_15s_prompt.sh
git commit -m "精简霓裳飞天安全提示词"
```

### Task 3: 提交后复验与交付

**Files:**
- Verify: `zhixia-feihualing/episodes/nichang-feitian-15s/prompts/seedance-v01.md`
- Verify: `zhixia-feihualing/tests/test_nichang_feitian_15s_prompt.sh`

**Interfaces:**
- Consumes: Task 2 已提交的安全精简正文。
- Produces: 测试证据、提交号和供用户复制的完整提示词。

- [ ] **Step 1: 提交后重新运行测试**

```bash
zsh zhixia-feihualing/tests/test_nichang_feitian_15s_prompt.sh
git status --short -- zhixia-feihualing/episodes/nichang-feitian-15s/prompts/seedance-v01.md zhixia-feihualing/tests/test_nichang_feitian_15s_prompt.sh
```

Expected: 测试 PASS；两个目标文件无未提交变更。

- [ ] **Step 2: 向用户交付完整正文**

回复中明确说明本地安全词与动作结构检查通过，但平台审核需要用户实际提交验证；同时提供正式提示词文件链接和完整可复制正文。

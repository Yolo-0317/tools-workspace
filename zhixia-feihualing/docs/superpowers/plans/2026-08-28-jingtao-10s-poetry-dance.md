# 《乱石穿空》10 秒诗境舞蹈提示词实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 产出可直接复制到 Seedance 2.0 的《乱石穿空》10 秒高冲击力诗境舞蹈提示词，并登记本集舞蹈组合用于后续去重。

**Architecture:** 单集目录保存输入说明、画面事实和最终提示词；Shell 规则测试验证可复制正文的原创声明、诗景、舞蹈链、特效因果、摄影机路径、阿砚母版特征、声音边界和内部代码清除。舞蹈去重台账只登记最终确认采用的一套组合。

**Tech Stack:** Markdown、CSV、Zsh + ripgrep、Git。

## Global Constraints

- 10 秒、9:16 竖屏、电影级高写实 CG、一镜到底。
- 正式生成只上传栀夏与阿砚两张原创虚拟角色母版，不上传状态卡、动作分镜或参考视频。
- 赤壁、奔涌大江、湿黑乱石和拍岸巨浪是诗景核心，不得退化为通用舞台背景。
- 栀夏必须完成斜向空间移动、两次重心变化、沉身提转、一次完整旋转和一个视觉高潮。
- 唯一主要特效是由动作触发并跟随衣袖弧线的真实水雾与白色浪沫；浪沫不是雪。
- 摄影机沿一条低位斜向后退路径运动，只在旋转与巨浪高潮处产生两次有因反应。
- 阿砚约 40 厘米并保持外扩纸纤维、笔锋双耳、四足、单尾、朱砂印与暖金纹样；不强制特写。
- 结尾揭示赤壁、大江与人物关系，不强制封面定格。
- Seedance 不生成对白、朗诵、吟唱、字幕或其他可辨识人声。
- 最终正文不得包含项目内部代码、文件路径、版本号、状态卡编号或诗句文字。

---

### Task 1: 建立单集提示词失败测试

**Files:**
- Create: `zhixia-feihualing/tests/test_jingtao_10s_prompt.sh`
- Test: `zhixia-feihualing/tests/test_jingtao_10s_prompt.sh`

**Interfaces:**
- Consumes: `docs/superpowers/specs/2026-08-28-jingtao-10s-poetry-dance-design.md`。
- Produces: 对 `episodes/jingtao/prompts/seedance-v01.md` 可复制正文的执行契约。

- [ ] **Step 1: 编写失败测试**

测试必须先要求单集 README 和提示词文件存在，然后提取标记块：

```zsh
prompt_block="$(sed -n '/<!-- SEEDANCE_PROMPT_START -->/,/<!-- SEEDANCE_PROMPT_END -->/p' "$prompt")"
first_prompt_line="$(sed -n '/<!-- SEEDANCE_PROMPT_START -->/{n;p;q;}' "$prompt")"
test "$first_prompt_line" = "@图片1与@图片2均为本项目原创虚拟角色，均为虚构数字角色，不对应任何现实人物、艺人、真实动物或既有影视动漫角色。"
```

正向断言至少包括：

```text
本次输入仅有图片1与图片2
10 秒
9:16
湿黑乱石
奔涌大江
高耸赤壁
动作舒展有力、节奏鲜明、连续自然
两次重心变化
完整旋转
视觉高潮
白色浪沫
不是雪
摄影机采用一条低位斜向后退主路径
第一次动作触发反应
第二次动作触发反应
阿砚足底至耳尖约40厘米
外扩纸纤维
不强制安排阿砚单独特写
不得生成任何可辨识人声
```

负向断言必须拒绝：

```regex
(^|[^[:alnum:]])[MHDS][0-9]{2}([^[:alnum:]]|$)|assets/|\.png|\.jpg|状态图|轻盈克制|乱石穿空|惊涛拍岸|卷起千堆雪
```

- [ ] **Step 2: 运行测试并确认正确失败**

Run:

```bash
zsh zhixia-feihualing/tests/test_jingtao_10s_prompt.sh
```

Expected: FAIL，报告缺少 `episodes/jingtao/prompts/seedance-v01.md`，而不是 Shell 语法错误。

- [ ] **Step 3: 提交测试**

```bash
git add zhixia-feihualing/tests/test_jingtao_10s_prompt.sh
git commit -m "新增乱石穿空诗境提示词测试"
```

### Task 2: 编写单集文档与最终 Seedance 提示词

**Files:**
- Create: `zhixia-feihualing/episodes/jingtao/README.md`
- Create: `zhixia-feihualing/episodes/jingtao/prompts/seedance-v01.md`
- Modify: `zhixia-feihualing/operations/dance-design-history.csv`

**Interfaces:**
- Consumes: Task 1 的提示词执行契约和已确认单集设计。
- Produces: 可直接复制的 `SEEDANCE_PROMPT_START/END` 正文，以及去重台账一行。

- [ ] **Step 1: 创建单集 README**

README 记录取句、两张角色母版输入、三个宽时间段、摄影机路径、阿砚约束、声音边界和提示词链接。明确现有阶段只有设计与提示词，尚未付费生成视频。

- [ ] **Step 2: 编写最终提示词**

提示词正文按以下自然顺序展开，不写内部编号：

1. 原创虚拟角色声明与两张图片映射。
2. 10 秒、9:16、赤壁江岸、主光源和电影级高写实 CG。
3. 0—3 秒斜向踏步和第一次换重。
4. 3—7 秒第二次换重、沉身提转、完整旋转、水雾跟随。
5. 7—10 秒跨步倾身、巨浪拍岸、白色浪沫高潮和赤壁揭示。
6. 低位斜向后退主路径、旋转反应和巨浪反应。
7. 栀夏、阿砚、衣料、水体和空间稳定要求。
8. 无人声音乐、环境声与禁止项。

- [ ] **Step 3: 登记舞蹈组合**

在台账追加：

```csv
jingtao,苏轼《念奴娇·赤壁怀古》,斜向踏步大幅展臂,湿黑礁石侧前方斜向移动,沉身蓄力后提转并继续跨步,两次换重与由低到高展开,衣袖与裙摆,水雾和白色浪沫,低位斜向后退；旋转同向弧移；巨浪时抬升拉开,保持动作余势并揭示赤壁大江,designed,纯文字原创舞蹈；白色浪沫不是雪
```

- [ ] **Step 4: 运行提示词和全局规则检查**

Run:

```bash
zsh zhixia-feihualing/tests/test_jingtao_10s_prompt.sh
zsh zhixia-feihualing/tests/test_high_impact_poetry_dance_rules.sh
git diff --check
```

Expected: 两个测试均输出 `PASS`，`git diff --check` 无输出并返回 0。

- [ ] **Step 5: 提交单集提示词**

```bash
git add zhixia-feihualing/episodes/jingtao/README.md zhixia-feihualing/episodes/jingtao/prompts/seedance-v01.md zhixia-feihualing/operations/dance-design-history.csv
git commit -m "编写乱石穿空高冲击力诗境提示词"
```

- [ ] **Step 6: 提交后复验**

重新运行 Step 4 的全部命令，检查 `git status --short`，不得暂存或提交工作区中既有的公众号和 Python 记忆改动。

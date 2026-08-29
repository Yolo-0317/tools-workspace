# 栀夏诗境编舞多样性 v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 取消新诗境“每集必须完整旋转”的固定模板，引入七种主高潮动作家族、九项视觉指纹和可执行的连续去重门禁。

**Architecture:** `zhixia-poetry-dance-composer.md` 作为编舞选择与去重真源，`realistic-visual-style.md` 和 `production-workflow.md` 只同步生成及验收边界，`dance-design-history.csv` 保存可比较的视觉指纹。新增回归测试锁定主高潮家族、三项重复门槛、水景解耦和台账结构，并同步更新仍断言“完整旋转”为全局必选项的旧规则测试。

**Tech Stack:** Markdown、CSV、Zsh、ripgrep、Git。

## Global Constraints

- 两张角色母版加纯文字的基础级输入方式不变，不新增状态卡、动作分镜或参考视频。
- 每集具有清楚空间移动、至少两次重心或高低层次变化、中国古典舞身韵和一个视觉高潮，但完整旋转不再是必选项。
- 主高潮动作家族固定为行进旋转、腾跃展开、低位扫展、倾身穿行、回身展臂、道具牵引、纵向提沉。
- 连续两集禁止同家族；最近五集同家族最多两次。
- 九项视觉指纹中三项或以上相同，组合不得进入 Seedance 提示词。
- 水景不得默认绑定旋转、双袖圆弧和环形水特效。
- 最终提示词继续清除动作家族名称、字段名、内部编号、文件名和测试名。
- 《惊涛》和《黄河》不返工，只补齐台账指纹供后续比较。

---

### Task 1: 建立编舞多样性回归门禁

**Files:**
- Create: `zhixia-feihualing/tests/test_choreography_diversity_v2_rules.sh`
- Modify: `zhixia-feihualing/tests/test_high_impact_poetry_dance_rules.sh`
- Modify: `zhixia-feihualing/tests/test_classical_dance_library_rules.sh`
- Modify: `zhixia-feihualing/tests/test_seedance_evidence_tiered_prompt_rules.sh`
- Modify: `zhixia-feihualing/tests/test_zhixia_first_opening_rules.sh`

**Interfaces:**
- Consumes: 三份生效规范和 `operations/dance-design-history.csv`。
- Produces: 一个会在旧规则上失败、在 v2 规则上通过的 Zsh 回归测试；四个旧测试改为断言“主高潮动作”而非全局必选“完整旋转”。

- [x] **Step 1: 写入失败测试**

新测试逐份要求 `composer`、`style`、`workflow` 存在以下契约：

```zsh
for phrase in \
  "主高潮动作家族" \
  "行进旋转" "腾跃展开" "低位扫展" "倾身穿行" \
  "回身展臂" "道具牵引" "纵向提沉" \
  "连续两集禁止" "最多出现两次" \
  "九项视觉指纹" "三项或以上相同" \
  "不得进入 Seedance 提示词" \
  "水景不得默认选择"; do
  rg -qF "$phrase" "$composer" || exit 1
done
```

同时检查 `style` 和 `workflow` 包含“主高潮动作”“三项或以上相同”“开场进入与主高潮动作”，并拒绝以下旧强制句：

```zsh
obsolete=(
  "每支新诗境必须写明移动或脚步、至少两次重心或高低层次变化、完整旋转的进入与离开"
  "正文必须同时描述空间移动、至少两次重心或高低层次变化、完整旋转的进入与离开"
  "旋转是每支新诗境的固定观感要求"
)
```

台账表头必须严格等于：

```text
episode,poem,opening,movement,climax_family,rotation,body_level,opening_silhouette,arm_path,leg_silhouette,carrier,carrier_shape,effect,effect_shape,climax_window,camera_reaction,camera_climax,ending,status,notes
```

- [x] **Step 2: 更新旧规则测试的契约名称**

只修改全局规则断言：把 `完整旋转` 替换为 `主高潮动作`，把 `旋转与高潮` 替换为 `开场进入与主高潮动作`。保留《白雪歌》《惊涛》等既有单集提示词测试中的旋转断言，因为旧视频不返工。

- [x] **Step 3: 运行测试并确认按预期失败**

Run: `zsh zhixia-feihualing/tests/test_choreography_diversity_v2_rules.sh`

Expected: FAIL，首个缺失项为 `主高潮动作家族` 或新台账表头。

### Task 2: 改写生效编舞规则并迁移台账

**Files:**
- Modify: `zhixia-feihualing/docs/zhixia-poetry-dance-composer.md`
- Modify: `zhixia-feihualing/docs/realistic-visual-style.md`
- Modify: `zhixia-feihualing/docs/production-workflow.md`
- Modify: `zhixia-feihualing/operations/dance-design-history.csv`
- Test: `zhixia-feihualing/tests/test_choreography_diversity_v2_rules.sh`

**Interfaces:**
- Consumes: 设计稿中的七种家族、九项视觉指纹和三项重复门槛。
- Produces: 后续每首诗境必须执行的选择、比较、拒绝和提示词转换规则，以及可供最近五集比较的 CSV 数据。

- [x] **Step 1: 改写自动编舞组合器**

删除“完整旋转是固定观感要求”，新增七种家族的可观察定义；把组合顺序改为先选主高潮家族，再确定手臂、腿部、载体、特效和镜头。新增明确门禁：连续两集同家族拒绝；最近五集同家族已两次则拒绝；与上一集九项指纹相同三项及以上则重新编排。

新增水景解耦列表：直线破浪、落点迸溅、纵向水幕、侧向水雾带、非环形扩散水纹、远景浪涌。失败降级改为根据当前家族降低难度，不再一律“保留完整旋转”。

- [x] **Step 2: 同步视觉规范和生产流程**

将所有新诗境的动作必填项改为“空间移动、至少两次重心或高低层次变化、一个主高潮动作、上肢及腿部剪影、衣料或道具反馈、视觉高潮和诗意结束”。第一秒离点后进入“主体路线或主高潮动作准备”。摄影机的最多两次反应绑定“开场进入与主高潮动作”，不再固定绑定旋转。

生成前检查新增九项视觉指纹比较和三项拒绝门槛；复杂十秒结构的第二段描述改为“主体移动和主高潮动作”，不再写“移动和完整旋转”。

- [x] **Step 3: 迁移舞蹈台账**

使用新表头并将既有两行补齐：

```csv
jingtao,苏轼《念奴娇·赤壁怀古》,斜向踏步大幅展臂,湿黑礁石侧前方斜向移动,行进旋转,沉身蓄力后提转并继续跨步,两次换重与由低到高展开,三分之四正面斜向踏步并双臂展开,双臂展开后沿转体形成闭合袖弧,斜向跨步沉身后提转,衣袖与裙摆,环形袖裙弧线,水雾和白色浪沫,环形水雾与前景浪沫,7—10秒,低位斜向后退；旋转同向弧移；巨浪时抬升拉开,抬升拉开揭示赤壁大江,保持动作余势并揭示赤壁大江,designed,既有视频不返工；作为重复基线
huanghe,李白《将进酒》,横向疾行回身起袖,赭黄河滩沿岸横向连续推进,腾跃展开,跨步翻身进入行进旋转并沿原方向离开,两次换重与横向展开再提身,动态近景回身起袖并横向发力,双臂与长袖横向展开后形成高位弧线,横向跨步后短暂离地展开,衣袖与裙摆,高位袖弧与展开裙摆,逆光河雾与金色水滴,弧形水雾与金色水滴,4—7秒,贴水侧向平行跟拍；旋转沿向加速；高潮顺河抬升拉开,顺河抬升拉开揭示高山黄河,无定式并在最后一帧运动中切断,designed,既有视频不返工；与惊涛视觉相似项作为重复基线
```

- [x] **Step 4: 运行新旧规则测试**

Run:

```bash
zsh zhixia-feihualing/tests/test_choreography_diversity_v2_rules.sh
zsh zhixia-feihualing/tests/test_high_impact_poetry_dance_rules.sh
zsh zhixia-feihualing/tests/test_classical_dance_library_rules.sh
zsh zhixia-feihualing/tests/test_seedance_evidence_tiered_prompt_rules.sh
zsh zhixia-feihualing/tests/test_zhixia_first_opening_rules.sh
```

Expected: 五个测试全部 PASS。

### Task 3: 完成全局回归与提交

**Files:**
- Modify: `zhixia-feihualing/docs/superpowers/plans/2026-08-29-zhixia-choreography-diversity-v2.md`
- Test: `zhixia-feihualing/tests/*.sh`

**Interfaces:**
- Consumes: Task 2 完成的生效规则和台账。
- Produces: 已通过相关规则回归、且不修改既有成片和单集提示词的本地 Git 提交。

- [x] **Step 1: 运行全部相关规则测试与格式检查**

Run:

```bash
for test_file in zhixia-feihualing/tests/test_*dance*rules.sh zhixia-feihualing/tests/test_seedance_evidence_tiered_prompt_rules.sh zhixia-feihualing/tests/test_zhixia_first_opening_rules.sh; do
  zsh "$test_file"
done
git diff --check
```

Expected: 每个测试输出 PASS，`git diff --check` 无输出且退出码为 0。

- [x] **Step 2: 核对变更边界**

确认没有修改 `episodes/jingtao/prompts/seedance-v01.md`、`episodes/huanghe/prompts/seedance-v01.md`、任何既有视频、音频、字幕或封面资产；不暂存工作区内其他用户改动。

- [x] **Step 3: 提交实现**

```bash
git add zhixia-feihualing/docs/superpowers/plans/2026-08-29-zhixia-choreography-diversity-v2.md \
  zhixia-feihualing/docs/zhixia-poetry-dance-composer.md \
  zhixia-feihualing/docs/realistic-visual-style.md \
  zhixia-feihualing/docs/production-workflow.md \
  zhixia-feihualing/operations/dance-design-history.csv \
  zhixia-feihualing/tests/test_choreography_diversity_v2_rules.sh \
  zhixia-feihualing/tests/test_high_impact_poetry_dance_rules.sh \
  zhixia-feihualing/tests/test_classical_dance_library_rules.sh \
  zhixia-feihualing/tests/test_seedance_evidence_tiered_prompt_rules.sh \
  zhixia-feihualing/tests/test_zhixia_first_opening_rules.sh
git commit -m "优化诗境编舞多样性规则"
```

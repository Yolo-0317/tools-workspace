# 唐风三桅客船固定道具 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立可跨单集复用的“唐风三桅客船”固定道具母版，并同步修正《白帝城》四张场景卡与Seedance提示词中的船帆、船舱和三峡尺度。

**Architecture:** 项目级道具目录保存船舶不可变身份、母版提示词和验收规则；单集提示词只描述环境、人物动作、摄影和声音。通过文本一致性检查确保《白帝城》不再重新定义冲突船型，并让22至26米船体、通高长舱、缩小帆面和出框高峡贯穿全部提示词。

**Tech Stack:** Markdown生产文档、`rg`与Python内容一致性检查、Git定向提交。

## Global Constraints

- 用户可见内容和项目文档禁止emoji。
- 固定道具标识为`tang-three-mast-passenger-ship-v01`。
- 船长约22至26米、宽约5至6米；中央一层通高长舱长约7至9米、净高约2.2至2.5米、舱门高约1.8至2米。
- 主桅高出甲板约12至14米，主帆约7至9米高、4至5米宽；前帆面积约为主帆75%，后帆约为主帆65%。
- 三帆视觉面积缩小到第二轮返图的约60%至70%，帆底留空，不能遮挡人物、船舱、船体和峡壁。
- 最近峡壁坡度约70至85度并延伸到画面顶部之外；天空约占10%至15%，前景空水面不超过约20%至25%。
- 《白帝城》既定诗句、五句对白、9.6秒朗诗起点和全程Seedance声音规则不变。
- 只提交本任务路径，不包含工作区其他改动。

---

### Task 1: 建立固定道具母版目录

**Files:**
- Create: `zhixia-feihualing/assets/props/tang-three-mast-passenger-ship-v01/README.md`
- Create: `zhixia-feihualing/assets/props/tang-three-mast-passenger-ship-v01/master-prompt.md`
- Create: `zhixia-feihualing/assets/props/tang-three-mast-passenger-ship-v01/qa-checklist.md`
- Modify: `zhixia-feihualing/assets/README.md`

**Interfaces:**
- Consumes: `docs/superpowers/specs/2026-08-25-tang-three-mast-passenger-ship-prop-design.md`。
- Produces: 后续单集可引用的道具标识、固定尺寸、母版图生成提示词和验收门禁。

- [ ] **Step 1: 创建道具README**

写明道具名、标识、适用场景、船体尺寸、一层通高长舱、三桅三帆比例、人物允许区域、不可变字段和可变字段。图片状态写为“母版待生成”，不伪造已存在资产。

- [ ] **Step 2: 创建独立母版提示词**

提示词要求上传栀夏与阿砚角色卡，以栀夏作为舱门尺度参照；使用低机位三分之四视角；完整呈现22至26米船长、5至6米船宽、7至9米通高长舱和缩小三帆。背景使用低细节中性江面，不抢占船型结构。

- [ ] **Step 3: 创建母版验收清单**

按船体比例、舱门可进入、舱内暗部、桅杆数量与间距、三帆面积、帆底留空、人物尺度、船首尾和禁用结构逐项验收。明确任何一项失败都不能作为后续单集参考图。

- [ ] **Step 4: 在资产索引登记道具目录**

在`assets/README.md`增加固定道具区，链接到`tang-three-mast-passenger-ship-v01/README.md`，注明当前母版图片待生成。

- [ ] **Step 5: 验证母版文档**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
root=Path('zhixia-feihualing/assets/props/tang-three-mast-passenger-ship-v01')
texts={p.name:p.read_text() for p in (root/'README.md',root/'master-prompt.md',root/'qa-checklist.md')}
required=['tang-three-mast-passenger-ship-v01','22至26米','7至9米','2.2至2.5米','1.8至2米','三根桅杆']
assert all(all(x in text for x in required) for text in texts.values())
assert '母版待生成' in texts['README.md']
print('固定道具母版文档检查通过')
PY
```

Expected: 输出`固定道具母版文档检查通过`。

- [ ] **Step 6: 提交固定道具母版**

```bash
git add zhixia-feihualing/assets/README.md zhixia-feihualing/assets/props/tang-three-mast-passenger-ship-v01
git commit -m "文档：建立唐风三桅客船固定道具"
```

### Task 2: 更新《白帝城》四张场景卡

**Files:**
- Modify: `zhixia-feihualing/episodes/baidi/README.md`
- Modify: `zhixia-feihualing/episodes/baidi/prompts/scene-cards.md`

**Interfaces:**
- Consumes: Task 1的道具标识与母版结构。
- Produces: 引用固定道具、具有新比例和险峻三峡约束的四张独立场景卡。

- [ ] **Step 1: 在单集README引用固定道具**

把船型描述改为引用`tang-three-mast-passenger-ship-v01`，保留关键尺寸摘要和母版图待生成状态，避免单集出现与母版冲突的另一套比例。

- [ ] **Step 2: 优化第一张船型结构卡**

将机位降低到高于甲板约2至4米；船体占画面下半部主要面积；明确栀夏直立于舱门旁，舱门高约1.8至2米，门内可见真实暗部。三帆缩小到旧图约60%至70%，主帆、前帆、后帆比例为100:75:65，帆底保持空隙。

- [ ] **Step 3: 优化开场、中段与结尾卡的三峡尺度**

每张场景卡明确：最近峡壁坡度约70至85度、左右出框、合计占宽约60%至70%；天空约10%至15%；前景空水面不超过20%至25%；远处只留狭窄亮色峡口。禁止低缓青山、完整收进画框的近山和宽阔湖面。

- [ ] **Step 4: 增加返图失败门禁**

禁止巨帆小船、半人高木箱船舱、人物无法直立进门、帆面遮住峡谷、近山完整露顶、宽天空、宽湖面和低缓岸坡。

- [ ] **Step 5: 验证四张卡的比例约束**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
p=Path('zhixia-feihualing/episodes/baidi/prompts/scene-cards.md').read_text()
assert p.count('只输出一张独立的9:16竖屏高清图片')==4
for x in ['22至26米','7至9米','1.8至2米','60%至70%','70至85度','10%至15%','20%至25%']:
    assert x in p, x
assert 'tang-three-mast-passenger-ship-v01' in p
print('白帝城四张场景卡比例检查通过')
PY
```

Expected: 输出`白帝城四张场景卡比例检查通过`。

- [ ] **Step 6: 提交《白帝城》场景卡优化**

```bash
git add zhixia-feihualing/episodes/baidi/README.md zhixia-feihualing/episodes/baidi/prompts/scene-cards.md
git commit -m "文档：优化白帝城客船与高峡比例"
```

### Task 3: 同步Seedance连续性与最终验证

**Files:**
- Modify: `zhixia-feihualing/episodes/baidi/prompts/seedance-video.md`

**Interfaces:**
- Consumes: Task 1固定道具结构和Task 2通过的场景卡。
- Produces: 保持船舱尺度、帆面比例与高峡险峻程度的15秒视频提示词。

- [ ] **Step 1: 引用固定道具母版**

在参考图顺序与船体连续性中写明`tang-three-mast-passenger-ship-v01`优先级高于单集偶然细节。固定船长宽比、舱门高度、舱体长度、桅杆位置和三帆面积关系。

- [ ] **Step 2: 更新帆面与船舱动态门禁**

帆面只允许受风弧度和轻微摆动，不得放大、缩小、遮住人物或改变系挂点。人物靠近舱门时必须保持可直立通过，镜头变化不得让通高长舱变回半人高木箱。

- [ ] **Step 3: 更新峡壁动态尺度**

近峡壁全程出框并快速后移，不能横向拉伸、突然降低或变成缓坡；天空和前景水面占比在运镜中保持受控，前方峡口始终狭窄可通行。

- [ ] **Step 4: 运行最终一致性检查**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
paths=[
Path('zhixia-feihualing/assets/props/tang-three-mast-passenger-ship-v01/README.md'),
Path('zhixia-feihualing/assets/props/tang-three-mast-passenger-ship-v01/master-prompt.md'),
Path('zhixia-feihualing/episodes/baidi/README.md'),
Path('zhixia-feihualing/episodes/baidi/prompts/scene-cards.md'),
Path('zhixia-feihualing/episodes/baidi/prompts/seedance-video.md')]
texts=[p.read_text() for p in paths]
for x in ['tang-three-mast-passenger-ship-v01','22至26米','7至9米','三根桅杆']:
    assert all(x in text for text in texts), x
assert '从第一帧到最后一帧持续生成背景音乐与自然环境声' in texts[-1]
assert '它们什么时候，都跑到身后了？' in texts[-1]
print('固定道具与白帝城生产包一致性检查通过')
PY
git diff --check -- zhixia-feihualing/assets/README.md zhixia-feihualing/assets/props/tang-three-mast-passenger-ship-v01 zhixia-feihualing/episodes/baidi
```

Expected: 输出`固定道具与白帝城生产包一致性检查通过`，`git diff --check`退出码为0。

- [ ] **Step 5: 提交Seedance同步更新**

```bash
git add zhixia-feihualing/episodes/baidi/prompts/seedance-video.md zhixia-feihualing/docs/superpowers/plans/2026-08-25-tang-three-mast-passenger-ship-prop.md
git commit -m "文档：同步三桅客船视频连续性"
```

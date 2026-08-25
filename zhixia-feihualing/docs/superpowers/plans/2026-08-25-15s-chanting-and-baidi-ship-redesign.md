# 15秒唱诗与《白帝城》三桅船提示词 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将15秒唱诗登记为15秒诗句诗境的并行子方向，并把《白帝城》四张场景卡与Seedance提示词改造成一层舱、三桅三帆、明确驶入高峡纵深且朗诗前对白连续的版本。

**Architecture:** 产品线规则写入三条视频产品线设计，单集事实与时间轴写入《白帝城》README，四张卡和视频提示词分别承担静态连续性与动态连续性。所有修改以已确认设计稿为唯一输入，不改变诗句、角色固定身份和全程背景声音规则。

**Tech Stack:** Markdown生产文档、`rg`内容一致性检查、Git定向提交。

## Global Constraints

- 用户可见内容和项目文档禁止emoji。
- 15秒唱诗与15秒对白诗境并行，不替换《白帝城》当前形式。
- 《白帝城》使用同一条一层舱、三桅、三面米白或浅麻色布帆的中型唐风木船。
- 船头始终指向可通行的峡谷纵深，禁止船身横贯江面或船头指向山壁。
- 最近峡壁从水面陡直拔起并达到画面高度至少三分之二；天空不超过约四分之一，前景无主体水面不超过约三分之一。
- 0.0—9.6秒五句对白连续衔接，9.6—14.7秒朗诗，14.7—15.0秒仅保留自然环境声。
- Seedance从第一帧到最后一帧持续生成背景音乐与环境声，不生成人物对白、旁白、朗诵、歌声或其他可辨识人声。
- 不提交项目内其他未关联改动。

---

### Task 1: 登记15秒唱诗并更新《白帝城》单集事实

**Files:**
- Modify: `zhixia-feihualing/docs/superpowers/specs/2026-08-25-three-content-lines-design.md`
- Modify: `zhixia-feihualing/episodes/baidi/README.md`

**Interfaces:**
- Consumes: `docs/superpowers/specs/2026-08-25-15s-chanting-and-baidi-ship-redesign.md`中的A1a、A1b定义与五句对白时间轴。
- Produces: 项目级产品线分类和单集级船型、卡片职责、声音时间轴，供两份提示词引用。

- [ ] **Step 1: 在产品线设计中拆分A1a与A1b**

把原“A1：15秒诗句诗境”保留为上位分类，并增加：

```text
A1a：对白诗句诗境——以对白或事件开头，结尾朗诵取诗。
A1b：15秒唱诗——完整四句半吟半唱，约13.5至14.2秒唱完，结尾保留0.8至1.5秒音乐或环境声；先做声音测试再设计画面。
```

明确首测《静夜思》三版声音，不把《白帝城》切换为唱诗。

- [ ] **Step 2: 更新《白帝城》README时间轴和船型**

写入以下精确时间轴：

```text
0.0—1.5秒 阿砚：“栀夏，船在飞！”
1.5—3.4秒 栀夏：“坐稳，山要追不上了。”
3.4—5.6秒 阿砚：“一座、两座、三座——”
5.6—7.0秒 栀夏：“别数了，回头。”
7.0—9.6秒 阿砚：“它们什么时候，都跑到身后了？”
9.6—14.7秒 阿砚朗诵：“两岸猿声啼不住，轻舟已过万重山。”
14.7—15.0秒 自然环境声收尾
```

把小船结构替换为同一条一层低矮船舱、三桅三帆中型唐风木船，并更新四张卡职责。

- [ ] **Step 3: 运行产品线与单集一致性检查**

Run:

```bash
rg -n 'A1a|A1b|半吟半唱|静夜思|一层.*船舱|三根桅杆|三面.*帆|它们什么时候，都跑到身后了|9\.6—14\.7秒' zhixia-feihualing/docs/superpowers/specs/2026-08-25-three-content-lines-design.md zhixia-feihualing/episodes/baidi/README.md
```

Expected: 产品线文件命中A1a、A1b、半吟半唱和《静夜思》；README命中新船型、第五句对白和新朗诗区间。

- [ ] **Step 4: 提交产品线与单集记录**

```bash
git add zhixia-feihualing/docs/superpowers/specs/2026-08-25-three-content-lines-design.md zhixia-feihualing/episodes/baidi/README.md
git commit -m "文档：登记十五秒唱诗与白帝城新时间轴"
```

### Task 2: 将四张场景卡改为独立三桅船提示词

**Files:**
- Modify: `zhixia-feihualing/episodes/baidi/prompts/scene-cards.md`

**Interfaces:**
- Consumes: Task 1确定的船型、人物位置和四张卡职责。
- Produces: 四段分别可复制到GPT的独立9:16提示词；每段都自包含角色引用、船型、航向、三峡尺度、构图和禁止项。

- [ ] **Step 1: 把单段连续生成指令拆成四段**

每张卡使用独立代码块和独立标题：

```text
提示词一：船型结构卡
提示词二：开场卡
提示词三：中段卡
提示词四：结尾卡
```

每段都要求只输出一张9:16单图，使用上传的栀夏和阿砚角色卡，不生成四宫格、编号、文字或水印。

- [ ] **Step 2: 在每段锁定同一船型**

四段逐字包含核心锚点：

```text
同一条唐风中型木质帆船；一层低矮船舱；三根桅杆沿纵轴前中后排列；三面米白或浅麻色布帆；栀夏固定在后部船舱前方或后甲板；阿砚固定在前甲板。
```

结构卡完整展示船首尾、舱体、三桅三帆、甲板、吃水线和人物尺度。

- [ ] **Step 3: 分别写入航向与三峡构图**

- 开场：船尾左后或船身左后视角，船头朝画面中央偏上的峡谷入口，船身形成纵深对角线。
- 中段：同一左侧轴线的船头左前或船身左前视角，仍为三分之四构图，禁止正侧视。
- 结尾：船尾左后上方宽景，船继续向前，人物回望身后的四层高峡。
- 三张场景卡都明确最近峡壁高度至少占画面三分之二、天空不超过四分之一、空水面不超过三分之一。

- [ ] **Step 4: 增加三桅帆与失败图门禁**

禁止：桅杆增减、帆面消失、三帆风向相反、船舱变双层、多船、多角色、船夫、水手、船体横贯江面、船头指向岸壁、仙侠悬浮山、黄山式孤峰、巨大瀑布和重复山体贴片。

- [ ] **Step 5: 运行四卡结构检查**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
p = Path('zhixia-feihualing/episodes/baidi/prompts/scene-cards.md').read_text()
for title in ('提示词一：船型结构卡', '提示词二：开场卡', '提示词三：中段卡', '提示词四：结尾卡'):
    assert p.count(title) == 1
assert p.count('只输出一张独立的9:16竖屏高清图片') == 4
assert p.count('三根桅杆') >= 4
assert p.count('三面') >= 4
assert '最近峡壁' in p and '画面高度至少三分之二' in p
assert '船头指向画面中央偏上的峡谷入口' in p
print('四张独立场景卡检查通过')
PY
```

Expected: 输出`四张独立场景卡检查通过`。

- [ ] **Step 6: 提交四张卡提示词**

```bash
git add zhixia-feihualing/episodes/baidi/prompts/scene-cards.md
git commit -m "文档：重写白帝城三桅船场景卡"
```

### Task 3: 更新Seedance连续动作与声音提示词

**Files:**
- Modify: `zhixia-feihualing/episodes/baidi/prompts/seedance-video.md`

**Interfaces:**
- Consumes: Task 1的五句对白时间轴和Task 2的同船四卡连续性。
- Produces: 可直接生成15秒视频的Seedance提示词与生成后验收清单。

- [ ] **Step 1: 替换船体连续性与摄影约束**

把无帆小舟改为一层舱、三桅三帆中型木船。镜头始终保持左侧轴线，以左后、左前和左后上方三分之四视角为主；禁止长时间正侧视、船体横贯画面、船头指向山壁和摄影越轴。

- [ ] **Step 2: 更新15秒五句对白时间轴**

0.0—9.6秒逐段对应五句后期对白，不生成可辨识人声或连续说话口型；7.0—9.6秒在阿砚说“它们什么时候，都跑到身后了？”时同步完成两人回望和万重山揭示。9.6—14.7秒朗诗，14.7—15.0秒自然环境声收尾。

- [ ] **Step 3: 更新三峡尺度、帆面物理与声音分段**

全片维持陡直高峡、狭长航道和四层山体。三帆始终受到同一顺风，桅杆数量、帆形和船舱层数不变。背景音乐0—9.6秒为连续对白留中频空间，7—9.6秒配合回望形成唯一小高潮，9.6秒后主动降低中频为朗诗让位，最后0.3秒音乐轻收但环境声持续。

- [ ] **Step 4: 更新失败门禁和验收项**

增加桅杆数量、帆面数量、帆向一致、一层舱、纵深航向、峡壁高度、天空与空水面占比检查。出现船体镜像、三桅漂移、帆向冲突、正侧横船、山体尺度不足或人物原声时，不进入TTS后期。

- [ ] **Step 5: 运行全包一致性检查**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
paths = [
    Path('zhixia-feihualing/episodes/baidi/README.md'),
    Path('zhixia-feihualing/episodes/baidi/prompts/scene-cards.md'),
    Path('zhixia-feihualing/episodes/baidi/prompts/seedance-video.md'),
]
texts = [p.read_text() for p in paths]
poem = '两岸猿声啼不住，轻舟已过万重山'
dialogue = ['栀夏，船在飞！', '坐稳，山要追不上了。', '一座、两座、三座——', '别数了，回头。', '它们什么时候，都跑到身后了？']
assert all(poem in text for text in texts)
assert all(line in texts[0] and line in texts[2] for line in dialogue)
assert all('三根桅杆' in text and '一层' in text for text in texts)
assert '从第一帧到最后一帧持续生成背景音乐与自然环境声' in texts[2]
assert '不得生成任何人物对白、旁白、朗诵' in texts[2]
print('白帝城三桅船生产包一致性检查通过')
PY
git diff --check -- zhixia-feihualing/docs/superpowers/specs/2026-08-25-three-content-lines-design.md zhixia-feihualing/episodes/baidi
```

Expected: 输出`白帝城三桅船生产包一致性检查通过`，`git diff --check`退出码为0。

- [ ] **Step 6: 提交Seedance提示词**

```bash
git add zhixia-feihualing/episodes/baidi/prompts/seedance-video.md
git commit -m "文档：更新白帝城三桅船视频提示词"
```

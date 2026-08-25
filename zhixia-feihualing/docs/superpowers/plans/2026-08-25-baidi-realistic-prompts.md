# 《白帝城》写实场景卡与 Seedance 提示词 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将《秋思》验证过的写实质感沉淀为正式生产规范，并交付可直接用于生成《白帝城》四张独立场景卡和15秒Seedance视频的完整提示词。

**Architecture:** 项目级规则写入通用生产流程，单集卡片与视频提示词写入独立《白帝城》剧集目录，避免把单集动作细节塞进通用规范。卡片提示词锁定人物、船体、材质、光照和空间；Seedance提示词消费这些参考图，锁定连续摄影、船行物理、对白时间和全程声音。

**Tech Stack:** Markdown、GPT图像生成、Seedance、豆包TTS、FFmpeg

## Global Constraints

- 从《白帝城》开始，默认风格为“偏写实东方动画电影＋克制的诗意自然景观”。
- 人物、船体、水流、材质、光照和接触阴影真实可信，但不能变成真人照片或三维渲染。
- 使用李白《早发白帝城》后两句：“两岸猿声啼不住，轻舟已过万重山。”
- 栀夏始终坐在船后半部，阿砚始终位于船头附近；两人不站立、不换座、不触水、不跳船。
- 小船无船桨、竹篙、船帆、发动机、船夫和船篷，依靠江流自然顺流前进。
- Seedance从第一帧到最后一帧持续生成背景音乐与环境声，不生成人物对白、旁白、吟诵、歌声或可辨识人声。
- 人声后期使用固定角色TTS，自然语速，不为塞进15秒明显加速。
- 画面与汇报禁止emoji；不提交角色隐私素材、密钥或环境文件。

---

### Task 1: 将写实风格写入通用生产流程

**Files:**
- Modify: `docs/production-workflow.md`
- Reference: `docs/superpowers/specs/2026-08-25-qiusi-realistic-style-and-baidi-design.md`

**Interfaces:**
- Consumes: 已确认的《秋思》写实风格设计
- Produces: 后续所有场景卡和Seedance提示词共同引用的默认风格规范

- [ ] **Step 1: 在提示词三层结构后增加“默认视觉风格基线”**

写入以下明确内容：

- 默认名称为“偏写实东方动画电影＋克制的诗意自然景观”。
- 人物、道具、材质、单一主光源、接触阴影、近中远空间和电影摄影的必备要求。
- 远山、云雾和色彩可以诗意概括，但不能覆盖真实空间与物理关系。
- 删除式约束：不再用“赛璐璐、宣纸纹理、明亮清透”三个泛词替代材质、光源和摄影描述。
- 《秋思》作为正向风格参考，同时把方向反转、家书包裹化和落笔自动补完列为动作物理反例。

- [ ] **Step 2: 在视频生成检查中增加写实验收顺序**

顺序固定为：角色身份 → 空间与尺度 → 材质与光源 → 接触阴影 → 动作方向与物体守恒 → 摄影与景深 → 诗意色彩。

- [ ] **Step 3: 校验通用规范没有与既有声音、道具规则冲突**

Run: `git diff --check -- zhixia-feihualing/docs/production-workflow.md`

Expected: exit 0；默认风格不覆盖既有“颗粒型元素”“连接型道具”和“故事声音规范”。

- [ ] **Step 4: 提交通用规范**

```bash
git add zhixia-feihualing/docs/production-workflow.md
git commit -m "文档：统一栀夏写实动画电影风格"
```

### Task 2: 建立《白帝城》剧集提示词目录与单集说明

**Files:**
- Create: `episodes/baidi/README.md`
- Create: `episodes/baidi/prompts/scene-cards.md`
- Create: `episodes/baidi/prompts/seedance-video.md`

**Interfaces:**
- Consumes: 固定角色卡、项目风格基线、已确认对白时间轴
- Produces: 卡片生成与视频生成的单一事实源路径

- [ ] **Step 1: 创建单集说明**

`episodes/baidi/README.md`必须包含：取句、四句对白与朗诗、15秒时间轴、角色固定座位、四张卡职责、待生成资产路径和付费生成前确认门禁。

时间轴固定写为：

- 0.0—1.5秒：“栀夏，船在飞！”
- 1.6—3.5秒：“坐稳，山要追不上了。”
- 3.6—5.8秒：“一座、两座、三座——”
- 5.9—7.3秒：“别数了，回头。”
- 7.3—10.0秒：回望与万重山揭示。
- 10.0—约14.7秒：朗诗。
- 14.7—15.0秒：水声和远处猿声收尾。

- [ ] **Step 2: 创建两个提示词文档骨架**

`scene-cards.md`以“共同风格与身份锚点、小船结构卡、开场卡、中段卡、结尾卡、共同禁止项、验收清单”为固定章节。

`seedance-video.md`以“参考图顺序、连续性、15秒时间轴、摄影、水流与船体物理、角色动作、声音设计、禁止项、生成后验收”为固定章节。

- [ ] **Step 3: 校验文件结构与时间字段**

Run: `git diff --check -- zhixia-feihualing/episodes/baidi`

Expected: exit 0；三个文件均无占位符，且时间轴总长为15秒。

### Task 3: 重写四张独立场景卡提示词

**Files:**
- Modify: `episodes/baidi/prompts/scene-cards.md`
- Reference: `docs/superpowers/specs/2026-08-25-qiusi-realistic-style-and-baidi-design.md`

**Interfaces:**
- Consumes: 用户上传的栀夏与阿砚角色卡
- Produces: GPT可连续执行、分别输出四张独立9:16图片的完整提示词

- [ ] **Step 1: 写共同写实风格锚点**

必须明确：东方动画电影角色、自然人体比例、真实衣料重量、真实木船结构、真实水体反射、统一清晨侧逆光、接触阴影、近中远三层峡谷、低至中等饱和电影色彩、柔和但不遮挡动作的景深；排除照片、3D、扁平赛璐璐和全屏宣纸纹理。

- [ ] **Step 2: 写小船结构卡**

锁定一条深棕修长木船、两端微翘、三道横座板、船头较窄、船尾略宽、完整无遮挡轮廓；阿砚在船头，栀夏在后半部；无桨、篙、帆、篷、船夫和现代动力。

- [ ] **Step 3: 写开场卡**

侧前方中远景，清晨峡谷侧逆光，船头真实破水，近岸产生视差；阿砚压低身体兴奋看前方，栀夏坐稳看向阿砚；人物和船体拥有一致光源、投影与接触关系。

- [ ] **Step 4: 写中段卡**

同一侧轴线的侧面中景；阿砚不换座，只转头和上半身数岸边山峰；栀夏仍坐稳并看向阿砚；近景石壁移动快、中景山移动较慢、远山最慢。

- [ ] **Step 5: 写结尾卡**

船后上方宽景；人物自然回头，轻舟继续前进；身后近中远层叠青山与峡谷雾形成纵深；船尾只有短而破碎的真实水纹；左上保留竖排诗句安全区。

- [ ] **Step 6: 写共同禁止项和逐卡验收**

禁止角色复制、换座、站立、船体镜像、船体弯曲、整片背景拖影、速度线、摩托艇尾浪、可见猿猴、现代物品、文字水印和风格漂移。验收逐项核对船体结构、座位、光源、接触阴影、水体排水、山体层次和面部一致性。

- [ ] **Step 7: 文档自检**

Run: `rg -n '赛璐璐|宣纸纹理|TBD|TODO|四宫格' zhixia-feihualing/episodes/baidi/prompts/scene-cards.md`

Expected: 仅允许“不是扁平赛璐璐”和“不要全屏宣纸纹理”的否定语境；无占位符；明确输出四张独立图片而非四宫格。

### Task 4: 编写15秒Seedance完整提示词

**Files:**
- Modify: `episodes/baidi/prompts/seedance-video.md`
- Reference: `episodes/baidi/prompts/scene-cards.md`

**Interfaces:**
- Consumes: 栀夏角色卡、阿砚角色卡、小船结构卡、开场卡；可选中段卡与结尾卡
- Produces: 一条可直接提交Seedance的15秒视频提示词

- [ ] **Step 1: 写参考图优先级与单一轴线**

角色卡只锁身份，小船卡只锁结构，开场卡锁第一帧与摄影轴线，中段卡锁转头动作，结尾卡锁宽景方向；多图不能替代文字声明。摄影始终沿船左侧从侧前方移动至侧后方，不跨到另一侧。

- [ ] **Step 2: 写15秒画面与对白动作时间轴**

逐段写清0—1.5、1.6—3.5、3.6—5.8、5.9—7.3、7.3—10、10—14.7和14.7—15秒的人物动作、船行、水流、山体视差与镜头位置。人物只做压低身体、看向对方、转头数山和自然回望，不做可辨识口型。

- [ ] **Step 3: 写真实速度与船体物理**

使用船头低矮破水、船尾短水纹、近中远山体视差和统一迎面风表达速度；禁止船体腾空、拉长、弯曲、镜像、换向，禁止巨浪、瀑布、速度线和全景横向拖影。

- [ ] **Step 4: 写全程声音设计**

环境声从头到尾包含江流、破水、峡谷风和稀疏远猿声。音乐使用低音古琴、轻笛和少量弦乐：前7秒轻快流动，7—10秒回望时略展开，10秒后降低中频为朗诗让位，14.7秒后轻收但不提前消失。明确禁止全部人物声音、吟诵和歌声。

- [ ] **Step 5: 写生成后验收**

按角色、船体、座位、轴线、前进方向、破水方向、风向、山体视差、声音连续性和可辨识人声十项检查。任一身份漂移、船体镜像、角色换座或人物原声直接判为不可进入TTS后期。

- [ ] **Step 6: 文档自检**

Run: `git diff --check -- zhixia-feihualing/episodes/baidi/prompts/seedance-video.md`

Expected: exit 0；时间轴完整覆盖15秒；音乐和环境声均覆盖第一帧至最后一帧；结尾保留0.3秒环境声。

### Task 5: 全量复核与提交

**Files:**
- Verify: `docs/production-workflow.md`
- Verify: `episodes/baidi/README.md`
- Verify: `episodes/baidi/prompts/scene-cards.md`
- Verify: `episodes/baidi/prompts/seedance-video.md`

**Interfaces:**
- Consumes: Tasks 1—4全部文档
- Produces: 可复制使用且内部一致的《白帝城》生产包

- [ ] **Step 1: 检查占位符和内部矛盾**

Run: `rg -n 'TBD|TODO|待补|稍后|一边.*另一边|换座|站起|船桨|竹篙' zhixia-feihualing/docs/production-workflow.md zhixia-feihualing/episodes/baidi`

Expected: 无占位符；“换座、站起、船桨、竹篙”仅出现在禁止项；没有相互矛盾的船头方向和人物位置。

- [ ] **Step 2: 检查对白、诗句和出处**

人工核对所有文件中的四句对白完全一致，诗句为“两岸猿声啼不住，轻舟已过万重山”，出处为“唐·李白《早发白帝城》”。

- [ ] **Step 3: 检查格式**

Run: `git diff --check -- zhixia-feihualing/docs/production-workflow.md zhixia-feihualing/episodes/baidi`

Expected: exit 0。

- [ ] **Step 4: 提交单集生产包**

```bash
git add zhixia-feihualing/episodes/baidi
git commit -m "文档：完成白帝城写实生成提示词"
```

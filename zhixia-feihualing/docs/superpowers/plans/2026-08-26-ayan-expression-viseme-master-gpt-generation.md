# 阿砚表情口型综合卡 GPT 生成 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 使用 GPT 和阿砚新版身份主卡生成一张包含六种克制表情与六种普通话基础口型的 3×4 制作母板。

**Architecture:** 只上传阿砚身份主卡，通过固定格位描述生成十二个完整双耳的正面颈肩近景。生成后分别验收版式、身份、表情区、口型区中性锁定、非人类嘴部解剖和画面洁净度；通过后原样归档并登记为 performance-master。

**Tech Stack:** GPT 图像生成、PNG、Markdown 设计规格、CSV 资产清单、macOS `sips`、SHA-256、Git。

## Global Constraints

- 设计依据为 `docs/superpowers/specs/2026-08-26-ayan-expression-viseme-master-design.md`。
- 唯一参考图为 `assets/characters/阿砚角色卡电影半写实-v01.png`。
- 不上传全身比例卡、旧版角色卡、庐山场景卡、栀夏角色卡或其他动物图。
- 输出为单张 9:16、3 列×4 行、共 12 格的正面颈肩近景综合卡。
- 每格必须完整呈现两只耳朵、头部和颈肩上段，耳尖不得裁切。
- 上两行依次为平静专注、轻微得意、好奇疑惑、警觉坚定、轻微惊喜、克制担忧。
- 下两行依次为 M/B/P 闭口、自然轻启、A、I/E、O、U。
- 下两行六格的眉眼、视线、双耳角度和头部姿态必须完全中性一致，只有嘴唇与下颌变化。
- 十二格保持同一脸、琥珀眼、朱砂印、双耳、纸墨绒羽材质和颈肩浅金纹样。
- 不出现人类嘴唇、人牙、双排牙、巨大门牙、獠牙、鸟喙、尖长兽吻、尾巴、四足、铃铛、文字、标签、边框或水印。
- 候选文件为 `assets/characters/阿砚表情口型综合卡电影半写实-v01.png`，用户验收前不得登记为 approved。

---

### Task 1: 在 GPT 中生成十二格候选图

**Files:**
- Reference: `zhixia-feihualing/assets/characters/阿砚角色卡电影半写实-v01.png`
- Candidate: GPT 返回的原始 PNG

**Interfaces:**
- Consumes: 阿砚身份主卡、已确认设计规范和下方完整提示词。
- Produces: 单张无文字 9:16 十二格候选图。

- [ ] **Step 1: 只上传阿砚新版身份主卡**

不要附加全身比例卡、旧版角色卡、庐山场景卡、栀夏图片或其他动物参考。

- [ ] **Step 2: 粘贴完整生成提示词**

```text
请严格参考我上传的新版阿砚身份主卡，生成一张“阿砚表情与对白口型综合制作母板”。这是一张角色制作参考图，不是剧情场景，不得重新设计角色。

输出单张 9:16 竖屏图片，采用 3 列×4 行、共 12 个等大格位。从左到右、从上到下严格按照下方顺序排列。每格都是阿砚的正面近景，完整呈现两只笔锋长耳、头部、颈部和肩胸上段；两只耳尖必须完整入镜，不得裁切。十二格的镜头距离、头部大小、颈肩裁切、正面角度、背景、光线、白平衡和曝光完全一致。格位之间只保留窄而均匀的自然留白，不添加文字、标签、编号、边框或表格线。

十二格必须与参考图完全是同一个阿砚：保持相同的庐山版亲和脸型、暖琥珀大眼、小巧兽形口鼻、额心固定朱砂印、两只高耸水墨笔锋长耳、耳部固定墨色与飞白分布、柔软细腻的宣纸纤维与纸墨绒羽质感，以及颈肩上段平面的浅暖金回旋云纹。不得换脸、不得改变眼睛大小和瞳色、不得改变耳朵长度和形状、不得移动朱砂印、不得恢复铃铛。

第一行从左到右：

第一格，平静专注。作为中性身份基准，暖琥珀眼自然注视前方，眼睑放松，嘴巴自然闭合，两只耳朵自然竖立，表情安静聪慧。

第二格，轻微得意。眼神比中性略亮，一侧嘴角只有极轻微上扬，带一点试探性的顽皮；不露牙、不眯成笑眼、不卖萌，头部保持正直。

第三格，好奇疑惑。头部仍然正直，不歪头；眉眼出现轻微疑问感，两只耳朵只略微向前聚拢，嘴巴自然闭合；不能出现问号或夸张困惑。

第二行从左到右：

第四格，警觉坚定。眼神集中，两只耳朵竖直并略向前，嘴巴闭合；不皱成愤怒脸、不龇牙、不凶狠。

第五格，轻微惊喜。眼睛只比中性状态稍微睁大，嘴巴自然轻启，耳朵略微提起；不做动漫大眼、卡通惊叫或夸张张嘴。

第六格，克制担忧。视线略微降低，眼睑轻缓，两只耳朵轻微向外后收，嘴角自然放松；不哭、不流泪、不做悲情夸张表演。

第三、第四行是六种对白口型。六格必须使用完全相同的平静中性表情：眼睛大小、眼睑、瞳孔方向、眉眼、两只耳朵的角度、头部姿态、朱砂印、鼻子、颈肩和浅金纹样全部完全一致。只允许嘴唇、下颌和极少量面颊肌肉变化，禁止通过眼神或耳位表达情绪。

第三行从左到右：

第七格，M/B/P 闭口。上下唇完全自然闭合，下颌放松，不露牙。

第八格，自然过渡口型。嘴唇只轻微开启，开口幅度为六种口型中最小，不露牙。

第九格，A 类开口。口腔自然纵向打开，下颌适度下降；允许看到少量自然口腔，但不能成为纯黑洞，牙齿最多只露极少量细小前牙。

第四行从左到右：

第十格，I/E 类横展。嘴角向左右轻微展开，唇形明显比 A 更扁、更宽，开口高度较小；默认不露牙，不能做成人类微笑嘴。

第十一格，O 类圆口。形成中等大小的自然圆形开口，唇周轻微收拢；允许看到少量自然口腔，但不能变成黑洞或人类嘟嘴。

第十二格，U 类小圆口。形成比 O 明显更小、更收束的圆口，嘴部整体前收幅度克制；不露牙，不做人类化嘟嘴。

嘴部必须保持参考图现有的小巧兽形口鼻，不改成人类嘴唇、鸟喙、尖长兽吻或卡通嘴。唇缘细小自然，与暖象牙白纸墨绒羽材质可信连接。禁止口红、唇彩、浓重唇线、整排人类牙齿、双排牙、巨大门牙、獠牙、尖牙外露、舌头突出、口水和夸张下颌拉伸。A、I/E、O、U 四种口型必须形状清楚不同，尤其 I/E 不能与 A 相同，U 必须明显小于 O。

背景使用统一、低细节的浅暖灰。光线柔和均匀，保持电影级半写实纸墨材质，但十二格不得出现不同景深、不同阴影方向或不同曝光。画面不出现四足、尾巴、铃铛、项圈、其他角色、山林、青石、瀑布、水雾或道具。

严格禁止：少格、多格、重复格、额外头像；换脸、眼睛大小漂移、瞳色变化、朱砂印漂移；多耳、耳朵残影、耳尖裁切、耳朵长度或墨色变化；下两行口型格皱眉、眯眼、睁大眼、改变视线、压耳、前倾耳朵、歪头；六种口型相同；人类嘴唇、人牙、双排牙、巨大门牙、獠牙、鸟喙、尖长口鼻、卡通嘴；四足、尾巴、铃铛、文字、标签、编号、边框、表格线、Logo 和水印。

请直接输出一张干净的 9:16 十二格原图，不附加任何说明文字。
```

- [ ] **Step 3: 下载 GPT 原始 PNG**

不截图、不裁切、不调色、不添加标签、不二次压缩。

### Task 2: 验收候选综合卡

**Files:**
- Inspect: GPT 返回的原始 PNG
- Compare: `zhixia-feihualing/assets/characters/阿砚角色卡电影半写实-v01.png`
- Spec: `zhixia-feihualing/docs/superpowers/specs/2026-08-26-ayan-expression-viseme-master-design.md`

**Interfaces:**
- Consumes: Task 1 候选图。
- Produces: accepted 或 rejected 的明确结论；rejected 时输出只针对失败项的修改提示词。

- [ ] **Step 1: 检查版式和构图**

Expected: 准确包含 3 列×4 行共 12 格；格位等大；每格完整双耳、头部和颈肩上段；无裁切耳尖、缺格、重复格或额外头像。

- [ ] **Step 2: 检查身份一致性**

Expected: 十二格与身份主卡保持同一脸、琥珀眼、朱砂印、双耳、耳部墨色、纸墨绒羽材质和颈肩浅金纹样。

- [ ] **Step 3: 检查六种表情**

Expected: 第一、二行依次为平静专注、轻微得意、好奇疑惑、警觉坚定、轻微惊喜、克制担忧；表演清楚但不夸张。

- [ ] **Step 4: 检查六种口型**

Expected: 第三、四行依次为 M/B/P 闭口、自然轻启、A、I/E、O、U；六格眉眼、视线、耳位和头部姿态完全中性一致；I/E 横展，U 明显小于 O。

- [ ] **Step 5: 检查嘴部结构**

Expected: 小巧兽形口鼻稳定；唇缘、口腔和下颌自然；无纯黑口腔、人类嘴唇、人牙、双排牙、巨大门牙、獠牙、舌头突出或卡通嘴。

- [ ] **Step 6: 检查画面洁净度**

Expected: 统一浅暖灰背景；无四足、尾巴、铃铛、项圈、文字、标签、编号、边框、表格线、其他角色、Logo 或水印。

- [ ] **Step 7: 给出验收结论**

任一格数错误、换脸、耳尖裁切、耳朵数量错误、朱砂印漂移、口型格带情绪、口型无法区分或人类化嘴部均判定为 rejected。只有六类检查全部通过才判定为 accepted。

### Task 3: 验收后归档制作母板

**Files:**
- Create: `zhixia-feihualing/assets/characters/阿砚表情口型综合卡电影半写实-v01.png`
- Modify: `zhixia-feihualing/assets/inventory.csv`

**Interfaces:**
- Consumes: Task 2 判定为 accepted 的原始 PNG。
- Produces: approved 的阿砚 performance-master 资产记录。

- [ ] **Step 1: 原样保存已验收 PNG**

不得重采样、裁切、调色或添加标签。

- [ ] **Step 2: 验证格式、尺寸和指纹**

```bash
sips -g format -g pixelWidth -g pixelHeight zhixia-feihualing/assets/characters/阿砚表情口型综合卡电影半写实-v01.png
shasum -a 256 zhixia-feihualing/assets/characters/阿砚表情口型综合卡电影半写实-v01.png
```

Expected: `format: png`、有效 9:16 竖屏尺寸，并记录唯一 SHA-256。

- [ ] **Step 3: 新增唯一资产记录**

在 `assets/inventory.csv` 新增：

```csv
ayan-expression-viseme-cinematic-semi-real-v01,character,阿砚,performance-master,assets/characters/阿砚表情口型综合卡电影半写实-v01.png,approved,ChatGPT web image generation,original AI-assisted asset,3列×4行共12格；上两行六种克制表情；下两行六种普通话基础口型；完整双耳正面颈肩近景；仅用于制作与质检分镜卡
```

- [ ] **Step 4: 验证资产路径和唯一性**

```bash
awk -F, '$1=="ayan-expression-viseme-cinematic-semi-real-v01"{count++; if($4!="performance-master" || $6!="approved" || $5!="assets/characters/阿砚表情口型综合卡电影半写实-v01.png") exit 11} END{if(count!=1) exit 12}' zhixia-feihualing/assets/inventory.csv
test -f zhixia-feihualing/assets/characters/阿砚表情口型综合卡电影半写实-v01.png
```

Expected: 两条命令均以状态码 0 结束。

- [ ] **Step 5: 只提交综合卡和资产清单行**

```bash
git add zhixia-feihualing/assets/characters/阿砚表情口型综合卡电影半写实-v01.png
git add -p zhixia-feihualing/assets/inventory.csv
git commit -m "资产：定稿阿砚表情口型综合卡"
```

交互暂存资产清单时，只选择本轮新增的阿砚综合卡记录，不暂存其他任务的改动。
